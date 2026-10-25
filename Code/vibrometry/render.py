"""
Side-by-side video export: the recorded clip (with the tracked ROIs drawn on
it) next to the displacement plot being drawn in sync — for presentations.

The plot is rendered with matplotlib's Agg backend using blitting: axes,
labels and legend are drawn once, and only the growing curves, the cursor
and the time label are redrawn per frame.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import cv2
import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .streaming import VideoTrack

RC = {
    "font.family": "serif",
    "mathtext.fontset": "dejavuserif",
    "font.size": 13,
    "legend.fontsize": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
}


def _even(x: float) -> int:
    return int(round(x / 2.0)) * 2


def _hex_to_bgr(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    r, g, b = (int(c[i: i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


def _open_writer(path: Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    # H.264 through Windows Media Foundation (plays everywhere, PowerPoint
    # included); the pip OpenCV's FFmpeg has no H.264 encoder, so elsewhere
    # fall back to MPEG-4 Part 2 (plays in VLC / browsers)
    attempts = [(cv2.CAP_MSMF, "H264")] if sys.platform == "win32" else []
    attempts.append((cv2.CAP_FFMPEG, "mp4v"))
    for api, code in attempts:
        w = cv2.VideoWriter(str(path), api, cv2.VideoWriter_fourcc(*code), fps, size)
        if w.isOpened():
            return w
        w.release()
    raise RuntimeError(f"Não foi possível criar o vídeo '{path}'.")


def render_side_by_side(
    out_path: str | Path,
    track: VideoTrack,
    series: list[tuple[str, np.ndarray, str]],
    ylabel: str = "Deslocamento",
    out_fps: float = 30.0,
    stride: int = 1,
    height: int = 720,
    progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Path:
    """Write ``out_path`` (MP4) with the video on the left and the plot of
    ``series`` = [(label, values over track.times, colour hex)] on the right.

    Every ``stride``-th tracked frame becomes one output frame at ``out_fps``,
    so the playback speed is out_fps * stride / track.fps (e.g. a 240 fps
    clip at 30 fps, stride 1 -> 1/8x slow motion).
    """
    out_path = Path(out_path)
    t = track.times
    n = track.n_frames
    start = track.params.start_frame
    h0, w0 = track.reference_frame.shape
    vid_w = _even(w0 * height / h0)
    plot_w = _even(max(1.35 * height, 640))
    height = _even(height)

    with mpl.rc_context(RC):
        fig = Figure(figsize=(plot_w / 100, height / 100), dpi=100)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot()
        lines, dots = [], []
        values = []
        for label, y, color in series:
            ln, = ax.plot([], [], color=color, linewidth=1.4, label=label, animated=True)
            dot, = ax.plot([], [], "o", color=color, markersize=5, animated=True)
            lines.append(ln)
            dots.append(dot)
            values.append(np.asarray(y, dtype=float))
        allv = np.concatenate(values) if values else np.zeros(1)
        allv = allv[np.isfinite(allv)]
        lo, hi = (float(allv.min()), float(allv.max())) if allv.size else (-1.0, 1.0)
        pad = 0.08 * (hi - lo or 1.0)
        ax.set_xlim(float(t[0]), float(t[-1]))
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xlabel("Tempo [s]")
        ax.set_ylabel(ylabel)
        ax.legend(loc="upper right")
        cursor = ax.axvline(float(t[0]), color="0.6", linewidth=1.0, animated=True)
        clock = ax.text(0.02, 0.96, "", transform=ax.transAxes, va="top",
                        animated=True, fontsize=12)
        fig.tight_layout()
        canvas.draw()
        background = canvas.copy_from_bbox(fig.bbox)

    rects = [(_hex_to_bgr("#A1A1AA" if res.roi.is_reference else "#2563EB"), res)
             for res in track.tracks.values()]
    writer = _open_writer(out_path, out_fps, (vid_w + plot_w, height))
    cap = cv2.VideoCapture(track.info.path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    pos = 0
    frames = list(range(0, n, max(1, stride)))
    try:
        for i, k in enumerate(frames):
            if should_stop is not None and should_stop():
                break
            while pos < k:                       # skip without decoding fully
                cap.grab()
                pos += 1
            ok, frame = cap.read()
            pos += 1
            if not ok:
                break
            for bgr, res in rects:
                r = res.roi
                dx, dy = res.displacement[k]
                p0 = (int(round(r.x + dx)), int(round(r.y + dy)))
                cv2.rectangle(frame, p0, (p0[0] + r.w, p0[1] + r.h), bgr,
                              max(2, w0 // 400), cv2.LINE_AA)
            left = cv2.resize(frame, (vid_w, height), interpolation=cv2.INTER_AREA)

            canvas.restore_region(background)
            for ln, dot, y in zip(lines, dots, values):
                ln.set_data(t[: k + 1], y[: k + 1])
                dot.set_data([t[k]], [y[k]])
                ax.draw_artist(ln)
                ax.draw_artist(dot)
            cursor.set_xdata([t[k], t[k]])
            clock.set_text(f"t = {t[k]:.3f} s".replace(".", ","))
            ax.draw_artist(cursor)
            ax.draw_artist(clock)
            right = cv2.cvtColor(np.asarray(canvas.buffer_rgba()), cv2.COLOR_RGBA2BGR)

            writer.write(np.hstack([left, right]))
            if progress is not None and i % 10 == 0:
                progress(i, len(frames))
    finally:
        writer.release()
        cap.release()
    if progress is not None:
        progress(len(frames), len(frames))
    return out_path


def export_speed(fps: float, speed: float, max_fps: float = 60.0,
                 min_fps: float = 5.0) -> tuple[float, int]:
    """(out_fps, stride) that play a clip recorded at ``fps`` at ``speed``x
    (e.g. 1/8) within the frame rates video players handle well."""
    raw = fps * speed
    stride = max(1, int(np.ceil(raw / max_fps)))
    return max(min_fps, raw / stride), stride
