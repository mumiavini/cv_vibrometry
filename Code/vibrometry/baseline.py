"""
Baseline comparison of the sub-pixel stage (TODO E1): the phase-based
estimate (the method of the TCC) against intensity-based tracking with the
same coarse search — integer normalized cross-correlation (NCC) and NCC with
parabolic peak interpolation, the usual sub-pixel step of template matching
and DIC.

The same video, ROIs, reference compensation and calibration are used for
every method, so the differences come only from the sub-pixel estimator.
Metrics per measurement ROI: natural frequency and amplitude (sine fit),
decay rate / damping (exponential envelope fit), and a noise floor (median
spectral amplitude in a band without modal content). The reference ROI
(static background) gives a second noise measure: its detrended standard
deviation.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .analysis import dominant_frequency, fit_sine
from .reference import fit_exponential_decay, sliding_envelope
from .session import Session
from .spectral import amplitude_spectrum
from .streaming import VideoTrack, track_video
from .video_io import probe_video

METHOD_LABELS = {
    "phase": "Fase (Gabor, ω₀)",
    "phase_local": "Fase (Gabor, ω local)",
    "parabolic": "NCC + parábola",
    "none": "NCC inteiro",
}
METHODS = tuple(METHOD_LABELS)

# method -> (subpixel stage, local frequency in the phase stage)
_METHOD_PARAMS = {
    "phase": ("phase", False),
    "phase_local": ("phase", True),
    "parabolic": ("parabolic", False),
    "none": ("none", False),
}


@dataclass
class SignalMetrics:
    f_n: float | None             # [Hz] sine-fit frequency
    amplitude: float | None       # sine-fit amplitude (signal unit)
    sigma: float | None           # envelope decay rate [1/s]
    zeta: float | None            # sigma / (2 pi f_n)
    noise_floor: float | None     # median spectral amplitude in the noise band
    snr_db: float | None          # 20 log10(amplitude / noise_floor)


@dataclass
class MethodResult:
    method: str
    unit: str
    metrics: dict[str, SignalMetrics]          # per measurement ROI
    reference_noise_px: float | None           # detrended std of the reference ROI
    signals: dict[str, np.ndarray] = field(repr=False, default_factory=dict)
    times: np.ndarray | None = field(repr=False, default=None)


def noise_floor(x: np.ndarray, fs: float, f_n: float | None,
                band: tuple[float, float] = (30.0, 110.0),
                guard_hz: float = 1.5) -> float | None:
    """Median amplitude of the spectrum in ``band``, excluding ±guard_hz
    around every harmonic of f_n (a robust estimate of the broadband noise
    level of the displacement signal)."""
    freqs, amp = amplitude_spectrum(x, fs)
    sel = (freqs >= band[0]) & (freqs <= min(band[1], fs / 2))
    if f_n:
        for k in range(1, int(band[1] / f_n) + 2):
            sel &= np.abs(freqs - k * f_n) > guard_hz
    return float(np.median(amp[sel])) if sel.any() else None


def signal_metrics(t: np.ndarray, x: np.ndarray, fs: float,
                   decay_window: tuple[float, float] = (0.3, 6.0)) -> SignalMetrics:
    x = np.asarray(x, float) - np.mean(x)
    f0 = dominant_frequency(x, fs)
    if not f0:
        return SignalMetrics(None, None, None, None, None, None)
    fit = fit_sine(t, x, f0)
    sigma = zeta = None
    try:
        env = sliding_envelope(t, x)
        dec = fit_exponential_decay(t, env, window=decay_window, min_rel=0.02)
        sigma, zeta = dec.sigma, dec.zeta(fit.frequency)
    except ValueError:
        pass
    nf = noise_floor(x, fs, fit.frequency)
    snr = (20.0 * np.log10(fit.amplitude / nf)) if (nf and nf > 0) else None
    return SignalMetrics(float(fit.frequency), float(fit.amplitude), sigma, zeta,
                         nf, None if snr is None else float(snr))


def _reference_noise(track: VideoTrack) -> float | None:
    name = track.reference_name
    if name is None:
        return None
    d = track.tracks[name].displacement
    out = []
    for k in range(2):
        y = d[:, k]
        tt = np.arange(y.size)
        out.append(np.std(y - np.polyval(np.polyfit(tt, y, 1), tt)))
    return float(np.hypot(*out))


def method_result(session: Session, track: VideoTrack, method: str) -> MethodResult:
    v = session.video
    sig, _ = track.signals(v.axis, v.scale_mm_per_px, v.compensate)
    t = track.times
    metrics = {n: signal_metrics(t, x, track.fps) for n, x in sig.items()}
    return MethodResult(method, "mm" if v.scale_mm_per_px else "px", metrics,
                        _reference_noise(track), sig, t)


def compare_subpixel_methods(
    session: Session,
    methods: tuple[str, ...] = METHODS,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, MethodResult]:
    """Track the session video once per sub-pixel method and compute the
    metrics of every measurement ROI."""
    from .workflow import tracking_params
    v = session.video
    info = probe_video(v.path, fps_override=v.fps_override)
    base = tracking_params(session, info.fps)
    out: dict[str, MethodResult] = {}
    for m in methods:
        sub, local = _METHOD_PARAMS[m]
        params = dataclasses.replace(base, subpixel=sub, local_frequency=local)
        cb = (lambda i, n, m=m: progress(m, i, n)) if progress else None
        track = track_video(v.path, v.roi_objects(), params, progress=cb)
        out[m] = method_result(session, track, m)
    return out


def static_pair_noise(
    session: Session,
    roi_a,
    roi_b,
    methods: tuple[str, ...] = METHODS,
) -> dict[str, dict[str, float]]:
    """Noise of each method from two *static* ROIs (e.g. two wall regions):
    the difference of their displacements cancels the common camera motion,
    and its detrended standard deviation / sqrt(2) estimates the noise of one
    ROI [px]. This is the noise floor relevant for small vibrations (the
    D1 control), where the coarse stage stays at zero."""
    from .workflow import tracking_params
    v = session.video
    info = probe_video(v.path, fps_override=v.fps_override)
    base = tracking_params(session, info.fps)
    out: dict[str, dict[str, float]] = {}
    for m in methods:
        sub, local = _METHOD_PARAMS[m]
        params = dataclasses.replace(base, subpixel=sub, local_frequency=local)
        tr = track_video(v.path, [roi_a, roi_b], params)
        d = tr.tracks[roi_a.name].displacement - tr.tracks[roi_b.name].displacement
        tt = np.arange(d.shape[0])
        res = {}
        for k, ax in enumerate("xy"):
            y = d[:, k] - np.polyval(np.polyfit(tt, d[:, k], 1), tt)
            res[f"std_{ax}_px"] = float(np.std(y) / np.sqrt(2.0))
        out[m] = res
    return out


def consistency(results: dict[str, MethodResult], ref: str = "phase") -> dict[str, dict[str, float]]:
    """RMS difference between each method's signal and the ``ref`` method's,
    per ROI (same unit as the signals)."""
    base = results[ref]
    out: dict[str, dict[str, float]] = {}
    for m, r in results.items():
        if m == ref:
            continue
        out[m] = {n: float(np.sqrt(np.mean((x - base.signals[n]) ** 2)))
                  for n, x in r.signals.items() if n in base.signals}
    return out
