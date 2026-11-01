"""
Session-level processing shared by the desktop app and the batch mode:
video tracking (with on-disk cache), modal analysis, accelerometer import,
synchronisation and the optical-vs-accelerometer comparison.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .accelerometer import (
    AccelRecord,
    AccelSettings,
    TableData,
    acceleration_to_displacement,
    build_record,
    displacement_to_acceleration,
    read_table,
)
from .analysis import Comparison, compare_signals, dominant_frequency, fit_sine
from .session import SESSION_SUFFIX, Session, roi_position
from .spectral import (
    LogDecrementResult,
    SpectralPeak,
    amplitude_spectrum,
    find_spectral_peaks,
    half_power_damping,
    log_decrement_damping,
)
from .streaming import TrackingParams, VideoTrack, track_video
from .uncertainty import FrequencyUncertainty, frequency_uncertainty
from .sync import (
    DriftResult,
    SyncResult,
    accel_time,
    bandpass,
    estimate_drift,
    estimate_offset,
    resample_at,
    video_time,
)
from .video_io import probe_video

Progress = Callable[[int, int], None]


# --------------------------------------------------------------------------- #
# modal analysis of one signal
# --------------------------------------------------------------------------- #
@dataclass
class ModalSummary:
    name: str
    unit: str
    window: tuple[float, float]
    f_n: float | None
    amplitude: float | None           # sine-fit amplitude at f_n
    zeta_half_power: float | None
    zeta_log_decrement: float | None
    std: float                        # noise / stability (D1 control)
    peak_to_peak: float
    peaks: list[SpectralPeak] = field(default_factory=list)
    decay: LogDecrementResult | None = None
    freqs: np.ndarray | None = None
    spectrum: np.ndarray | None = None
    f_predicted: float | None = None
    error_predicted_percent: float | None = None
    f_uncertainty: FrequencyUncertainty | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name, "unit": self.unit,
            "window_s": list(self.window),
            "f_n_hz": self.f_n, "amplitude": self.amplitude,
            "zeta_half_power": self.zeta_half_power,
            "zeta_log_decrement": self.zeta_log_decrement,
            "std": self.std, "peak_to_peak": self.peak_to_peak,
            "spectral_peaks": [asdict(p) for p in self.peaks],
            "f_predicted_hz": self.f_predicted,
            "error_predicted_percent": self.error_predicted_percent,
            "f_uncertainty": (self.f_uncertainty.to_dict()
                              if self.f_uncertainty else None),
        }


def modal_summary(
    name: str,
    t: np.ndarray,
    x: np.ndarray,
    fs: float,
    unit: str,
    window: tuple[float, float] | None = None,
    f_predicted: float | None = None,
    f_min: float = 0.3,
) -> ModalSummary:
    if window is not None:
        m = (t >= window[0]) & (t <= window[1])
        if m.sum() >= 8:
            t, x = t[m], x[m]
    win = (float(t[0]), float(t[-1]))
    freqs, amp = amplitude_spectrum(x, fs)
    peaks = find_spectral_peaks(freqs, amp, f_min=f_min)
    f_n = dominant_frequency(x, fs, f_min=f_min)
    fit = fit_sine(t, x, f_n) if f_n else None
    if fit is not None:
        f_n = fit.frequency
    zeta_hp = half_power_damping(freqs, amp, f_n) if f_n else None
    decay = log_decrement_damping(x, fs, f_n) if f_n else None
    err = (100.0 * (f_n - f_predicted) / f_predicted
           if (f_n and f_predicted) else None)
    fu = frequency_uncertainty(t, x, fs, f0=f_n) if f_n else None
    return ModalSummary(
        name=name, unit=unit, window=win, f_n=f_n,
        amplitude=fit.amplitude if fit else None,
        zeta_half_power=zeta_hp,
        zeta_log_decrement=decay.zeta if decay else None,
        std=float(np.std(x)), peak_to_peak=float(np.ptp(x)),
        peaks=peaks, decay=decay, freqs=freqs, spectrum=amp,
        f_predicted=f_predicted, error_predicted_percent=err,
        f_uncertainty=fu,
    )


def predicted_frequency(session: Session) -> float | None:
    """Euler-Bernoulli f_n,1 with tip mass, only for free-vibration runs
    (in a forced run the response frequency is the excitation's)."""
    if session.meta.excitation_hz:
        return None
    try:
        return float(session.specimen.predicted_f1())
    except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
        return None


# --------------------------------------------------------------------------- #
# video
# --------------------------------------------------------------------------- #
def tracking_params(session: Session, fps: float) -> TrackingParams:
    v = session.video
    start = max(0, int(round(v.start_s * fps)))
    end = int(round(v.end_s * fps)) if v.end_s else None
    return TrackingParams(
        start_frame=start, end_frame=end,
        fps_override=v.fps_override, resize_width=v.resize_width,
        gabor_wavelengths=tuple(v.wavelengths), search_margin=v.search_margin,
    )


def _cache_key(session: Session, params: TrackingParams) -> str:
    v = session.video
    st = os.stat(v.path)
    payload = {
        "path": os.path.abspath(v.path), "size": st.st_size,
        "mtime": int(st.st_mtime), "rois": v.rois,
        "params": asdict(params),
    }
    return hashlib.sha1(json.dumps(payload, sort_keys=True,
                                   default=str).encode()).hexdigest()


def cache_path(session: Session) -> Path | None:
    if not session.file:
        return None
    p = Path(session.file)
    stem = p.name[: -len(SESSION_SUFFIX)] if p.name.endswith(SESSION_SUFFIX) else p.stem
    return p.with_name(stem + ".track.pkl")


def save_track_cache(session: Session, track: VideoTrack) -> None:
    path = cache_path(session)
    if path is None or not session.video.path:
        return
    key = _cache_key(session, track.params)
    with open(path, "wb") as fh:
        pickle.dump({"key": key, "track": track}, fh)


def load_track_cache(session: Session) -> VideoTrack | None:
    """Tracking result saved next to the session, if it still matches the
    video file, the ROIs and the tracking parameters."""
    path = cache_path(session)
    if path is None or not path.exists() or not session.video.path:
        return None
    try:
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        track: VideoTrack = payload["track"]
        if payload["key"] != _cache_key(session, tracking_params(session, track.fps)):
            return None
        return track
    except Exception:
        return None


def run_video(
    session: Session,
    progress: Progress | None = None,
    should_stop: Callable[[], bool] | None = None,
    preview: Callable | None = None,
    preview_interval: float = 0.05,
) -> VideoTrack:
    v = session.video
    if not v.path:
        raise ValueError("Nenhum vídeo selecionado.")
    info = probe_video(v.path, fps_override=v.fps_override)
    params = tracking_params(session, info.fps)
    return track_video(v.path, v.roi_objects(), params, progress=progress,
                       should_stop=should_stop, preview=preview,
                       preview_interval=preview_interval)


@dataclass
class VideoAnalysis:
    track: VideoTrack
    unit: str
    signals: dict[str, np.ndarray]
    axes: dict[str, str]
    modal: dict[str, ModalSummary]

    @property
    def times(self) -> np.ndarray:
        return self.track.times

    @property
    def fps(self) -> float:
        return self.track.fps


def analyze_video(session: Session, track: VideoTrack) -> VideoAnalysis:
    v = session.video
    signals, axes = track.signals(v.axis, v.scale_mm_per_px, v.compensate)
    unit = "mm" if v.scale_mm_per_px else "px"
    t = track.times
    f_pred = predicted_frequency(session)
    window = tuple(v.window) if v.window else None
    modal = {
        name: modal_summary(name, t, x, track.fps, unit, window, f_pred)
        for name, x in signals.items()
    }
    return VideoAnalysis(track, unit, signals, axes, modal)


@dataclass
class ModeShapeRow:
    name: str
    x_mm: float                 # distance from the root
    amplitude: float            # sine-fit amplitude of the ROI
    measured_ratio: float       # amplitude / amplitude of the reference ROI
    predicted_ratio: float      # |shape(x)| / |shape(x_ref)| of the model
    error_percent: float        # (measured - predicted) / predicted


@dataclass
class ModeShapeCheck:
    """Amplitude ratio between measurement ROIs against the mode shape of the
    analytical model (multi-point check, independent of the accelerometer
    and of the spatial scale)."""
    reference: str              # ROI the ratios are relative to
    mode: int                   # elastic mode of the model that matches f
    f_model: float              # frequency of that mode [Hz]
    f_measured: float
    rows: list[ModeShapeRow]


def mode_shape_check(session: Session, analysis: VideoAnalysis) -> ModeShapeCheck | None:
    """Compare the ROI amplitude ratios with the model mode shape. Needs at
    least two measurement ROIs with a position along the beam
    (``session.video.roi_positions_mm``)."""
    raw = session.video.roi_positions_mm or {}
    pos = {n: roi_position(raw, n) for n in analysis.modal}
    pos = {n: x for n, x in pos.items() if x is not None}
    names = [n for n, m in analysis.modal.items()
             if n in pos and m.amplitude and m.f_n]
    if len(names) < 2:
        return None
    ref = max(names, key=lambda n: analysis.modal[n].amplitude)
    f_meas = analysis.modal[ref].f_n
    try:
        fe = session.specimen.fe_model()
        modes = range(1, 5)
        k = min(modes, key=lambda i: abs(fe.elastic_frequency(i) - f_meas))
        x = np.array([pos[n] / 1e3 for n in names])
        shape = np.abs(fe.elastic_mode_shape(x, k))
    except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
        return None
    i_ref = names.index(ref)
    if shape[i_ref] <= 0:
        return None
    rows = []
    for n, xm, sh in zip(names, x, shape):
        meas = analysis.modal[n].amplitude / analysis.modal[ref].amplitude
        pred = sh / shape[i_ref]
        rows.append(ModeShapeRow(
            name=n, x_mm=float(xm * 1e3), amplitude=float(analysis.modal[n].amplitude),
            measured_ratio=float(meas), predicted_ratio=float(pred),
            error_percent=float(100.0 * (meas - pred) / pred) if pred > 0 else float("nan")))
    return ModeShapeCheck(reference=ref, mode=int(k),
                          f_model=float(fe.elastic_frequency(k)),
                          f_measured=float(f_meas), rows=rows)


# --------------------------------------------------------------------------- #
# accelerometer
# --------------------------------------------------------------------------- #
def accel_settings(session: Session) -> AccelSettings:
    a = session.accel
    return AccelSettings(time_column=a.time_column, channel=a.channel, fs=a.fs,
                         unit=a.unit, sensitivity_mv_per_g=a.sensitivity_mv_per_g,
                         invert=a.invert)


def load_accel(session: Session) -> tuple[TableData, AccelRecord]:
    if not session.accel.path:
        raise ValueError("Nenhum arquivo de acelerômetro selecionado.")
    table = read_table(session.accel.path)
    return table, build_record(table, accel_settings(session))


def accel_displacement_mm(session: Session, rec: AccelRecord) -> np.ndarray:
    a = session.accel
    return 1e3 * acceleration_to_displacement(
        rec.a, rec.fs, f_hp=a.f_hp, f_lp=a.f_lp, method=a.integration)


def accel_modal(session: Session, rec: AccelRecord,
                displacement: bool = True) -> ModalSummary:
    """Modal summary of the accelerometer (as displacement [mm], or raw
    acceleration [m/s²]) inside its own window."""
    x = accel_displacement_mm(session, rec) if displacement else rec.a
    window = tuple(session.accel.window) if session.accel.window else None
    return modal_summary("acelerômetro", rec.t, x, rec.fs,
                         "mm" if displacement else "m/s²", window,
                         predicted_frequency(session))


# --------------------------------------------------------------------------- #
# comparison
# --------------------------------------------------------------------------- #
@dataclass
class ComparisonData:
    roi: str
    domain: str
    unit_video: str
    unit_accel: str
    t: np.ndarray                 # video time base [s]
    video: np.ndarray             # band-passed, NaN outside the common span
    accel: np.ndarray             # aligned and resampled to t, band-passed
    window: tuple[float, float]
    metrics: Comparison | None
    offset_s: float
    drift_ppm: float
    fs: float

    @property
    def units_match(self) -> bool:
        return self.unit_video == self.unit_accel

    def window_mask(self) -> np.ndarray:
        return ((self.t >= self.window[0]) & (self.t <= self.window[1])
                & np.isfinite(self.video) & np.isfinite(self.accel))


def _quantities(session: Session, analysis: VideoAnalysis, rec: AccelRecord,
                roi: str) -> tuple[np.ndarray, str, np.ndarray, str]:
    """(video quantity, unit, accelerometer quantity at its own rate, unit)
    in the comparison domain."""
    c = session.compare
    fs = analysis.fps
    x = analysis.signals[roi]
    if c.domain == "acceleration":
        f_lp = c.f_lp or 0.4 * fs
        vq = displacement_to_acceleration(x, fs, f_lp=f_lp)
        if analysis.unit == "mm":
            vq, vu = vq * 1e-3, "m/s²"
        else:
            vu = "px/s²"
        return vq, vu, rec.a, "m/s²"
    return x, analysis.unit, accel_displacement_mm(session, rec), "mm"


def comparison_roi(session: Session, analysis: VideoAnalysis) -> str:
    names = list(analysis.signals)
    if not names:
        raise ValueError("Nenhuma ROI de medição processada.")
    return session.compare.roi if session.compare.roi in names else names[0]


def auto_sync(
    session: Session,
    analysis: VideoAnalysis,
    rec: AccelRecord,
    with_drift: bool = False,
) -> tuple[SyncResult, DriftResult | None]:
    """Estimate the offset (and optionally the drift) and store them in the
    session."""
    c = session.compare
    roi = comparison_roi(session, analysis)
    fs = analysis.fps
    vq, _, aq, _ = _quantities(session, analysis, rec, roi)
    v = bandpass(vq, fs, c.f_hp, c.f_lp)
    a = bandpass(aq, rec.fs, c.f_hp, c.f_lp)
    f_dom = c.f_analysis or dominant_frequency(v, fs)
    mode = "waveform" if c.sync_mode == "waveform" else "impact"
    sync = estimate_offset(v, rec.t, a, fs, mode=mode, f_dominant=f_dom)
    drift = None
    c.offset_s, c.drift_ppm = sync.offset, 0.0
    if with_drift:
        drift = estimate_drift(v, rec.t, a, fs, sync.offset, f_dominant=f_dom)
        c.offset_s, c.drift_ppm = drift.offset, drift.drift_ppm
    return sync, drift


def build_comparison(
    session: Session,
    analysis: VideoAnalysis,
    rec: AccelRecord,
) -> ComparisonData:
    c = session.compare
    roi = comparison_roi(session, analysis)
    fs = analysis.fps
    t = analysis.times
    vq, vu, aq, au = _quantities(session, analysis, rec, roi)

    a_on_t = resample_at(rec.t, aq, accel_time(t, c.offset_s, c.drift_ppm), fs)
    valid = np.isfinite(a_on_t)
    video = np.full_like(t, np.nan)
    accel = np.full_like(t, np.nan)
    if valid.sum() >= 16:
        idx = np.flatnonzero(valid)
        sl = slice(idx[0], idx[-1] + 1)
        video[sl] = bandpass(vq[sl], fs, c.f_hp, c.f_lp)
        accel[sl] = bandpass(a_on_t[sl], fs, c.f_hp, c.f_lp)

    if c.window:
        window = (float(c.window[0]), float(c.window[1]))
    elif valid.any():
        window = (float(t[valid][0]), float(t[valid][-1]))
    else:
        window = (float(t[0]), float(t[-1]))

    data = ComparisonData(roi, c.domain, vu, au, t, video, accel, window, None,
                          c.offset_s, c.drift_ppm, fs)
    m = data.window_mask()
    if m.sum() >= 16:
        data.metrics = compare_signals(t[m], accel[m], video[m], fs,
                                       f_common=c.f_analysis)
    return data


def accel_edge_warning(session: Session, comparison: ComparisonData,
                       rec: AccelRecord) -> str | None:
    """Warn when the analysis window gets within the integration edge zone of
    the accelerometer record (~1/f_hp s for the frequency method, ~2/f_hp s
    for the time method; see tests/test_accelerometer.py)."""
    if comparison.domain != "displacement":
        return None
    a = session.accel
    margin = (1.0 if a.integration == "frequency" else 2.0) / max(a.f_hp, 1e-3)
    tv0, tv1 = video_time(np.array([rec.t[0], rec.t[-1]]),
                          comparison.offset_s, comparison.drift_ppm)
    w0, w1 = comparison.window
    if w0 < tv0 + margin or w1 > tv1 - margin:
        return (f"A janela está a menos de {margin:.1f} s da borda do registro do ".replace(".", ",")
                + "acelerômetro: o deslocamento integrado ali tem efeito de borda.")
    return None


# --------------------------------------------------------------------------- #
# batch
# --------------------------------------------------------------------------- #
@dataclass
class SessionResult:
    session: Session
    analysis: VideoAnalysis | None = None
    accel: AccelRecord | None = None
    accel_summary: ModalSummary | None = None
    comparison: ComparisonData | None = None
    sync: SyncResult | None = None
    error: str | None = None
    from_cache: bool = False

    def row(self) -> dict:
        """Flat summary used by the batch table and its CSV/LaTeX export."""
        s = self.session
        r: dict = {"sessao": s.name or Path(s.file).name, "grupo": s.group,
                   "erro": self.error or ""}
        if self.analysis is not None:
            roi = comparison_roi(s, self.analysis)
            m = self.analysis.modal[roi]
            r.update({
                "roi": roi, "unidade": m.unit,
                "f_video_hz": m.f_n, "A_video": m.amplitude,
                "zeta_video": m.zeta_log_decrement,
                "zeta_video_hp": m.zeta_half_power,
                "std_video": m.std,
                "f_prevista_hz": m.f_predicted,
                "erro_prevista_pct": m.error_predicted_percent,
            })
        if self.accel_summary is not None:
            r.update({"f_acc_hz": self.accel_summary.f_n,
                      "zeta_acc": self.accel_summary.zeta_log_decrement})
        if self.comparison is not None and self.comparison.metrics is not None:
            cm = self.comparison.metrics
            r.update({
                "f_ref_hz": cm.f_ref, "f_opt_hz": cm.f_test,
                "erro_f_pct": cm.freq_error_percent,
                "A_ref": cm.amp_ref, "A_opt": cm.amp_test,
                "erro_A_pct": cm.amp_error_percent,
                "dfase_graus": cm.phase_diff_deg,
                "r": cm.pearson_r, "nrmse_pct": cm.nrmse_percent,
                "offset_s": self.comparison.offset_s,
                "deriva_ppm": self.comparison.drift_ppm,
            })
        return r


def process_session(
    session: Session,
    progress: Progress | None = None,
    should_stop: Callable[[], bool] | None = None,
    use_cache: bool = True,
) -> SessionResult:
    res = SessionResult(session)
    try:
        track = load_track_cache(session) if use_cache else None
        res.from_cache = track is not None
        if track is None:
            track = run_video(session, progress, should_stop)
            if use_cache:
                try:
                    save_track_cache(session, track)
                except OSError:
                    pass
        res.analysis = analyze_video(session, track)
        if session.accel.path:
            _, rec = load_accel(session)
            res.accel = rec
            res.accel_summary = accel_modal(session, rec)
            if session.compare.sync_mode != "manual":
                res.sync, _ = auto_sync(session, res.analysis, rec)
            res.comparison = build_comparison(session, res.analysis, rec)
    except Exception as exc:  # reported per session in the batch table
        res.error = f"{type(exc).__name__}: {exc}"
    return res
