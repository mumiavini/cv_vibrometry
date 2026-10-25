"""
ROI displacement tracking: coarse template matching + phase-based refinement.

Phase-based motion estimation resolves displacements smaller than half the
filter wavelength (|delta| < lambda/2).  A freely vibrating cantilever tip
travels tens of pixels between frames, far beyond that range, so each ROI is
tracked in two stages:

  1. coarse  — normalized cross-correlation (cv2.matchTemplate) of the
     reference-frame template inside a search window, giving the
     integer-pixel position of the ROI in the current frame;
  2. fine    — Gabor phase difference between the reference template and the
     patch extracted at the matched position (TCC eq:fase_deslocamento),
     giving the sub-pixel residual.

The total displacement is the sum of the two terms.  For small-amplitude
vibrations the coarse term stays at zero and the measurement reduces to the
pure phase-based estimate described in the TCC.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .gabor import GaborBank
from .roi import ROI


def extract_patch(frame: np.ndarray, x: int, y: int, w: int, h: int,
                  pad: int) -> np.ndarray:
    """Extract frame[y:y+h, x:x+w] with ``pad`` pixels of context around it,
    replicating edges where the padded window leaves the frame."""
    height, width = frame.shape
    x0, x1 = x - pad, x + w + pad
    y0, y1 = y - pad, y + h + pad
    cx0, cx1 = max(x0, 0), min(x1, width)
    cy0, cy1 = max(y0, 0), min(y1, height)
    patch = frame[cy0:cy1, cx0:cx1]
    return np.pad(
        patch,
        ((cy0 - y0, y1 - cy1), (cx0 - x0, x1 - cx1)),
        mode="edge",
    )


@dataclass
class TrackResult:
    roi: ROI
    displacement: np.ndarray   # (n_frames, 2) total (dx, dy) [pixels]
    coarse: np.ndarray         # (n_frames, 2) integer template-match part
    residual: np.ndarray       # (n_frames, 2) phase-based sub-pixel part
    score: np.ndarray          # (n_frames,) NCC score of the coarse match
    weight: np.ndarray         # (n_frames,) Gabor amplitude weight

    @property
    def x(self) -> np.ndarray:
        return self.displacement[:, 0]

    @property
    def y(self) -> np.ndarray:
        return self.displacement[:, 1]


class RoiTracker:
    """Frame-by-frame (streaming) version of the coarse + fine tracker.

    Holds only the reference template and the per-frame results, so a video
    can be processed while it is decoded instead of being stacked in memory
    first (see issues.md, "Full-video batch processing is too slow").

    Usage: ``t = RoiTracker(reference_frame, roi)``, then ``t.update(frame)``
    for every following frame and ``t.result()`` at the end.
    """

    def __init__(
        self,
        reference_frame: np.ndarray,
        roi: ROI,
        bank: GaborBank | None = None,
        search_margin: int = 60,
        min_score: float = 0.3,
    ) -> None:
        self.bank = bank if bank is not None else GaborBank()
        self.search_margin = search_margin
        self.min_score = min_score
        self.height, self.width = reference_frame.shape
        self.roi = roi.clamp(self.height, self.width)
        r = self.roi

        self.template = reference_frame[r.slice()].astype(np.float32)
        ref_patch = extract_patch(reference_frame, r.x, r.y, r.w, r.h,
                                  self.bank.pad)
        self.ref_responses = self.bank.responses(ref_patch)
        self.last_xy = np.array([r.x, r.y], dtype=int)

        # frame 0 is the reference: zero displacement, perfect score
        self._coarse: list[np.ndarray] = [np.zeros(2, dtype=int)]
        self._residual: list[np.ndarray] = [np.zeros(2)]
        self._score: list[float] = [1.0]
        self._weight: list[float] = [0.0]

    def update(self, frame: np.ndarray) -> None:
        r, m = self.roi, self.search_margin
        last_xy = self.last_xy

        # --- stage 1: integer-pixel template matching in a local window ---
        wx0 = int(np.clip(last_xy[0] - m, 0, self.width - r.w))
        wy0 = int(np.clip(last_xy[1] - m, 0, self.height - r.h))
        wx1 = int(np.clip(last_xy[0] + r.w + m, r.w, self.width))
        wy1 = int(np.clip(last_xy[1] + r.h + m, r.h, self.height))
        window = frame[wy0:wy1, wx0:wx1].astype(np.float32)

        ncc = cv2.matchTemplate(window, self.template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(ncc)
        if max_val >= self.min_score:
            self.last_xy = np.array([wx0 + max_loc[0], wy0 + max_loc[1]])
        self._score.append(float(max_val))
        self._coarse.append(self.last_xy - np.array([r.x, r.y]))

        # --- stage 2: phase-based sub-pixel residual (Gabor bank) ---
        cur_patch = extract_patch(frame, self.last_xy[0], self.last_xy[1],
                                  r.w, r.h, self.bank.pad)
        cur_responses = self.bank.responses(cur_patch)
        residual, weight = self.bank.phase_displacement(
            self.ref_responses, cur_responses
        )
        self._residual.append(residual)
        self._weight.append(weight)

    def displacement_so_far(self) -> np.ndarray:
        """(k, 2) displacement of the frames processed so far [pixels]."""
        return (np.asarray(self._coarse, dtype=float)
                + np.asarray(self._residual, dtype=float))

    def result(self) -> TrackResult:
        coarse = np.asarray(self._coarse, dtype=int)
        residual = np.asarray(self._residual, dtype=float)
        return TrackResult(
            roi=self.roi,
            displacement=coarse + residual,
            coarse=coarse,
            residual=residual,
            score=np.asarray(self._score),
            weight=np.asarray(self._weight),
        )


def track_roi(
    frames: np.ndarray,
    roi: ROI,
    bank: GaborBank | None = None,
    search_margin: int = 60,
    min_score: float = 0.3,
) -> TrackResult:
    """Track one ROI through the frame stack.

    Parameters
    ----------
    frames : (n, h, w) uint8 grayscale stack; frames[0] is the reference.
    roi : region to track, defined on the reference frame.
    bank : Gabor filter bank for the sub-pixel stage (default bank if None).
    search_margin : half-size of the search window around the last known
        position [pixels]; must exceed the largest frame-to-frame motion.
    min_score : NCC score below which the coarse match is considered lost
        (the previous position is kept and a warning is attached).
    """
    tracker = RoiTracker(frames[0], roi, bank=bank,
                         search_margin=search_margin, min_score=min_score)
    for k in range(1, frames.shape[0]):
        tracker.update(frames[k])
    return tracker.result()
