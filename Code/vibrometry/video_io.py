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


@dataclass
class VideoData:
    """Grayscale frame stack plus sampling information."""

    frames: np.ndarray          # (n_frames, height, width) uint8
    fps: float                  # sampling rate F [frames/s]
    path: str = ""

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


def load_video(
    path: str | Path,
    start_frame: int = 0,
    end_frame: int | None = None,
    fps_override: float | None = None,
) -> VideoData:
    """Read a video file into a grayscale frame stack.

    Parameters
    ----------
    path : video file readable by OpenCV.
    start_frame, end_frame : optional frame range [start, end).
    fps_override : use this sampling rate instead of the container metadata
        (useful for high-frame-rate footage saved with a playback fps that
        differs from the capture fps, e.g. 240 fps recorded / 30 fps tagged).
    """
    path = str(path)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {path}")

    fps = fps_override if fps_override is not None else cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        raise ValueError(
            f"Invalid fps ({fps}) in '{path}' metadata; pass fps_override."
        )

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames: list[np.ndarray] = []
    index = start_frame
    while True:
        if end_frame is not None and index >= end_frame:
            break
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        index += 1
    cap.release()

    if not frames:
        raise ValueError(f"No frames read from '{path}' in range "
                         f"[{start_frame}, {end_frame}).")

    return VideoData(frames=np.stack(frames), fps=float(fps), path=path)
