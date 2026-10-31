"""
Streaming video tracking: decode -> grayscale -> (resize) -> track every ROI,
frame by frame, without holding the frame stack in memory.

The same pass collects the clip pre-checks of the measurement plan
(planejamento, section 8.2): real frame timing and dropped frames, brightness
flicker, focus (variance of the Laplacian) and saturation.

All displacements returned here are in pixels of the *native* video
resolution, even when frames are downscaled for speed, so a spatial scale
measured on the original video applies directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from .gabor import GaborBank
from .roi import ROI
from .spectral import amplitude_spectrum
from .tracking import RoiTracker, TrackResult
from .video_io import VideoInfo, probe_video


@dataclass
class TrackingParams:
    start_frame: int = 0
    end_frame: int | None = None          # exclusive
    fps_override: float | None = None
    resize_width: int | None = None
    gabor_wavelengths: tuple[float, ...] = (8.0, 16.0)
    search_margin: int = 60               # native pixels
    min_score: float = 0.3
    subpixel: str = "phase"               # "phase" | "parabolic" | "none"
    local_frequency: bool = False         # phase stage: local vs centre frequency


@dataclass
class QualityReport:
    """Clip pre-checks (planejamento 8.2)."""

    frame_interval_ms: float              # mean interval between timestamps
    frame_jitter_ms: float                # std of that interval
    dropped_frames: int                   # intervals > 1.5 nominal periods
    brightness: np.ndarray                # mean frame brightness per frame
    flicker_hz: float | None              # dominant brightness oscillation
    flicker_percent: float                # its amplitude, % of mean level
    focus: dict[str, float] = field(default_factory=dict)       # Laplacian var
    saturation: dict[str, float] = field(default_factory=dict)  # % pixels 0/255
    lost_frames: dict[str, int] = field(default_factory=dict)   # NCC < min_score
    min_score: dict[str, float] = field(default_factory=dict)

    def warnings(self) -> list[str]:
        out = []
        if self.dropped_frames:
            out.append(f"{self.dropped_frames} quadro(s) perdido(s) "
                       f"(intervalo > 1,5 período)")
        if self.flicker_percent > 1.0 and self.flicker_hz:
            out.append(f"cintilação de {self.flicker_percent:.1f}% "
                       f"em {self.flicker_hz:.1f} Hz")
        for name, s in self.saturation.items():
            if s > 2.0:
                out.append(f"{name}: {s:.1f}% de pixels saturados")
        for name, n in self.lost_frames.items():
            if n:
                out.append(f"{name}: rastreamento perdido em {n} quadro(s)")
        return out


@dataclass
class VideoTrack:
    """Result of tracking all ROIs of one video."""

    info: VideoInfo
    params: TrackingParams
    fps: float
    fps_source: str
    resize_factor: float
    timestamps: np.ndarray                # container timestamps [s]
    tracks: dict[str, TrackResult]        # native-pixel displacements
    reference_frame: np.ndarray           # native-resolution grayscale
    quality: QualityReport

    @property
    def n_frames(self) -> int:
        return len(self.timestamps)

    @property
    def times(self) -> np.ndarray:
        """Uniform analysis time base t_k = k / F, from the first tracked
        frame [s]."""
        return np.arange(self.n_frames) / self.fps

    @property
    def t0(self) -> float:
        """Position of the first tracked frame in the original clip [s]."""
        return self.params.start_frame / self.fps

    @property
    def measurement_names(self) -> list[str]:
        return [n for n, t in self.tracks.items() if not t.roi.is_reference]

    @property
    def reference_name(self) -> str | None:
        refs = [n for n, t in self.tracks.items() if t.roi.is_reference]
        return refs[0] if refs else None

    def signals(
        self,
        axis: str = "auto",
        scale_mm_per_px: float | None = None,
        compensate: bool = True,
    ) -> tuple[dict[str, np.ndarray], dict[str, str]]:
        """Displacement of every measurement ROI, compensated by the reference
        ROI (eq:compensacao) and calibrated (eq:deslocamento_fisico).

        Displacements are relative to the first tracked frame (no mean
        removal), in mm if a scale is given, else in pixels.

        Returns (signals, axis_used) keyed by ROI name.
        """
        return compose_signals(
            {n: t.displacement for n, t in self.tracks.items()},
            self.reference_name, axis, scale_mm_per_px, compensate)


def compose_signals(
    displacements: dict[str, np.ndarray],
    reference: str | None,
    axis: str = "auto",
    scale_mm_per_px: float | None = None,
    compensate: bool = True,
) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Signals of the measurement ROIs from (n, 2) pixel displacements
    (all ROIs, same length); see ``VideoTrack.signals``. Also used on the
    partial results shown live while a video is being tracked."""
    n = len(next(iter(displacements.values())))
    ref_disp = (displacements[reference]
                if (compensate and reference in displacements)
                else np.zeros((n, 2)))
    signals, axes = {}, {}
    for name, d in displacements.items():
        if name == reference:
            continue
        disp = d - ref_disp
        ax = axis
        if ax == "auto":
            ax = "x" if disp[:, 0].std() >= disp[:, 1].std() else "y"
        sig = disp[:, 0] if ax == "x" else disp[:, 1]
        if scale_mm_per_px is not None:
            sig = sig * scale_mm_per_px
        signals[name] = sig
        axes[name] = ax
    return signals, axes


def _scaled_roi(roi: ROI, f: float) -> ROI:
    if f == 1.0:
        return roi
    return ROI(roi.name, round(roi.x * f), round(roi.y * f),
               max(4, round(roi.w * f)), max(4, round(roi.h * f)),
               roi.is_reference)


def _flicker(brightness: np.ndarray, fps: float) -> tuple[float | None, float]:
    if brightness.size < 16 or brightness.mean() <= 0:
        return None, 0.0
    freqs, amp = amplitude_spectrum(brightness, fps)
    valid = freqs >= 0.5
    if not valid.any():
        return None, 0.0
    i = int(np.argmax(amp[valid]))
    return (float(freqs[valid][i]),
            float(100.0 * amp[valid][i] / brightness.mean()))


def track_video(
    path: str | Path,
    rois: list[ROI],
    params: TrackingParams | None = None,
    progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    preview: Callable[[int, np.ndarray, dict[str, np.ndarray]], None] | None = None,
    preview_interval: float = 0.05,
) -> VideoTrack:
    """Track every ROI of ``rois`` (defined on the native-resolution frame
    ``params.start_frame``) through the clip.

    ``progress(done, total)`` is called periodically; if ``should_stop()``
    returns True the loop ends early and the frames processed so far are
    returned. ``preview(k, gray_frame, displacements)`` receives, at most
    every ``preview_interval`` seconds, the current native-resolution frame
    and the native-pixel displacements of every ROI up to frame k (for a
    live view).
    """
    params = params or TrackingParams()
    if not rois:
        raise ValueError("Defina ao menos uma ROI.")
    if all(r.is_reference for r in rois):
        raise ValueError("Defina ao menos uma ROI de medição.")
    path = str(path)
    info = probe_video(path, fps_override=params.fps_override)

    fps, fps_source = info.fps, info.fps_source

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {path}")
    start = max(0, params.start_frame)
    end = params.end_frame if params.end_frame is not None else info.n_frames
    end = min(end, info.n_frames) if info.n_frames > 0 else end
    total = max(1, end - start)
    if start > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)

    ok, frame = cap.read()
    if not ok:
        cap.release()
        raise ValueError(f"Não foi possível ler o quadro {start} de '{path}'.")
    ref_native = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h_nat, w_nat = ref_native.shape

    if params.resize_width and params.resize_width < w_nat:
        factor = params.resize_width / w_nat
        size = (params.resize_width, round(h_nat * factor))
    else:
        factor, size = 1.0, None

    def prepare(gray: np.ndarray) -> np.ndarray:
        if size is None:
            return gray
        return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)

    bank = GaborBank(wavelengths=tuple(params.gabor_wavelengths),
                     local_frequency=params.local_frequency)
    margin = max(4, round(params.search_margin * factor))
    ref = prepare(ref_native)
    trackers = {
        r.name: RoiTracker(ref, _scaled_roi(r, factor), bank=bank,
                           search_margin=margin, min_score=params.min_score,
                           subpixel=params.subpixel)
        for r in rois
    }

    def send_preview(k: int, gray: np.ndarray) -> None:
        preview(k, gray, {n: t.displacement_so_far() / factor
                          for n, t in trackers.items()})

    timestamps = [cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0]
    brightness = [float(ref_native.mean())]
    last_preview = time.perf_counter()
    if preview is not None:
        send_preview(0, ref_native)
    k = 1
    while k < total:
        if should_stop is not None and should_stop():
            break
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        timestamps.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
        brightness.append(float(gray.mean()))
        small = prepare(gray)
        for t in trackers.values():
            t.update(small)
        if preview is not None and time.perf_counter() - last_preview >= preview_interval:
            send_preview(k, gray)
            last_preview = time.perf_counter()
        k += 1
        if progress is not None and k % 10 == 0:
            progress(k, total)
    cap.release()
    if progress is not None:
        progress(k, total)

    # --- results back in native pixels ---------------------------------- #
    by_name = {r.name: r for r in rois}
    tracks: dict[str, TrackResult] = {}
    for name, t in trackers.items():
        res = t.result()
        tracks[name] = TrackResult(
            roi=by_name[name].clamp(h_nat, w_nat),
            displacement=res.displacement / factor,
            coarse=res.coarse / factor,
            residual=res.residual / factor,
            score=res.score,
            weight=res.weight,
        )

    # --- quality report --------------------------------------------------- #
    ts = np.asarray(timestamps)
    dts = np.diff(ts)
    dts = dts[dts > 0]
    nominal = 1.0 / fps
    bright = np.asarray(brightness)
    flicker_hz, flicker_pct = _flicker(bright, fps)
    quality = QualityReport(
        frame_interval_ms=float(dts.mean() * 1e3) if dts.size else nominal * 1e3,
        frame_jitter_ms=float(dts.std() * 1e3) if dts.size else 0.0,
        dropped_frames=int(np.sum(dts > 1.5 * nominal)) if dts.size else 0,
        brightness=bright,
        flicker_hz=flicker_hz,
        flicker_percent=flicker_pct,
    )
    for r in rois:
        rr = r.clamp(h_nat, w_nat)
        patch = ref_native[rr.slice()]
        quality.focus[r.name] = float(cv2.Laplacian(patch, cv2.CV_64F).var())
        quality.saturation[r.name] = float(
            100.0 * np.mean((patch <= 0) | (patch >= 255)))
        score = tracks[r.name].score
        quality.lost_frames[r.name] = int(np.sum(score < params.min_score))
        quality.min_score[r.name] = float(score.min())

    return VideoTrack(
        info=info,
        params=params,
        fps=fps,
        fps_source=fps_source,
        resize_factor=factor,
        timestamps=ts,
        tracks=tracks,
        reference_frame=ref_native,
        quality=quality,
    )
