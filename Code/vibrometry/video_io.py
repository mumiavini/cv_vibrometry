"""
Module 1 — Frame import (TCC: "Importação dos quadros").

The video is read frame by frame, converted to grayscale and stored as a
stack I(x, y, t_k) with t_k = k / F.  The first frame I(x, y, t_0) is the
reference frame against which all displacements are computed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

FPS_MISMATCH_TOLERANCE = 0.02  # relative difference above which we warn/switch


@dataclass
class VideoData:
    """Grayscale frame stack plus sampling information."""

    frames: np.ndarray          # (n_frames, height, width) uint8
    fps: float                  # sampling rate F [frames/s]
    path: str = ""
    fps_source: str = "container"   # "override" | "container" | "measured"
    resize_factor: float = 1.0      # applied_width / native_width (<=1.0)

    @property
    def n_frames(self) -> int:
        return self.frames.shape[0]

    @property
    def shape(self) -> tuple[int, int]:
        """(height, width) of each frame."""
        return self.frames.shape[1:]

    @property
    def dt(self) -> float:
        """Sampling interval Δt = 1/F [s]."""
        return 1.0 / self.fps

    @property
    def duration(self) -> float:
        return self.n_frames / self.fps

    @property
    def nyquist(self) -> float:
        """Highest frequency identifiable without aliasing, F/2 [Hz]."""
        return self.fps / 2.0

    @property
    def times(self) -> np.ndarray:
        """Capture instants t_k = k/F [s]."""
        return np.arange(self.n_frames) / self.fps

    @property
    def reference_frame(self) -> np.ndarray:
        return self.frames[0]


def _measure_fps(cap: cv2.VideoCapture, n_frames: int, start_frame: int) -> float | None:
    """Effective fps computed from the real timestamps of the first and last
    frame, independent of the container's (possibly wrong) average-fps tag.

    This catches a mislabeled/rounded fps tag on an otherwise correctly
    timestamped file. It does NOT recover the true capture rate of footage
    that was intentionally re-timestamped for slow motion (e.g. 240 fps
    captured but authored to play back at 30 fps) — for that case the real
    rate isn't recoverable from standard container timing at all, and
    ``fps_override`` is still required.
    """
    if n_frames < 2:
        return None
    pos_before = cap.get(cv2.CAP_PROP_POS_FRAMES)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    ok0, _ = cap.read()
    t_first = cap.get(cv2.CAP_PROP_POS_MSEC)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame + n_frames - 1)
    ok1, _ = cap.read()
    t_last = cap.get(cv2.CAP_PROP_POS_MSEC)

    cap.set(cv2.CAP_PROP_POS_FRAMES, pos_before)
    if not (ok0 and ok1) or t_last <= t_first:
        return None
    return (n_frames - 1) / ((t_last - t_first) / 1000.0)


def load_video(
    path: str | Path,
    start_frame: int = 0,
    end_frame: int | None = None,
    fps_override: float | None = None,
    resize_width: int | None = None,
) -> VideoData:
    """Read a video file into a grayscale frame stack.

    Parameters
    ----------
    path : video file readable by OpenCV.
    start_frame, end_frame : optional frame range [start, end).
    fps_override : use this sampling rate instead of any auto-detected value
        (needed for footage re-timestamped for slow motion, where the true
        capture rate cannot be recovered from container timing at all).
    resize_width : if given and smaller than the native frame width, frames
        are downscaled to this width (aspect ratio preserved, INTER_AREA)
        before being stacked. Never upscales. Trades spatial resolution for
        lower memory/runtime; see issues.md for the accuracy tradeoff.
    """
    path = str(path)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {path}")

    n_frames_meta = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    declared_fps = cap.get(cv2.CAP_PROP_FPS)

    if fps_override is not None:
        fps, fps_source = fps_override, "override"
    else:
        measured_fps = _measure_fps(cap, n_frames_meta, start_frame) \
            if n_frames_meta > start_frame else None
        if (measured_fps and declared_fps
                and abs(measured_fps - declared_fps) / declared_fps > FPS_MISMATCH_TOLERANCE):
            print(f"[video_io] fps mismatch in '{path}': container tag says "
                  f"{declared_fps:.3f} fps, measured from frame timestamps "
                  f"{measured_fps:.3f} fps -> using the measured value. "
                  f"Pass fps_override explicitly if this is wrong (e.g. "
                  f"footage re-timestamped for slow motion).")
            fps, fps_source = measured_fps, "measured"
        else:
            fps, fps_source = declared_fps, "container"

    if not fps or fps <= 0:
        raise ValueError(
            f"Invalid fps ({fps}) in '{path}' metadata; pass fps_override."
        )

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    native_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    native_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if resize_width is not None and resize_width < native_width:
        resize_factor = resize_width / native_width
        target_size = (resize_width, round(native_height * resize_factor))
    else:
        resize_factor = 1.0
        target_size = None

    frames: list[np.ndarray] = []
    index = start_frame
    while True:
        if end_frame is not None and index >= end_frame:
            break
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if target_size is not None:
            gray = cv2.resize(gray, target_size, interpolation=cv2.INTER_AREA)
        frames.append(gray)
        index += 1
    cap.release()

    if not frames:
        raise ValueError(f"No frames read from '{path}' in range "
                         f"[{start_frame}, {end_frame}).")

    return VideoData(frames=np.stack(frames), fps=float(fps), path=path,
                     fps_source=fps_source, resize_factor=resize_factor)
