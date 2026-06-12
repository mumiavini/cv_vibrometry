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
    if bank is None:
        bank = GaborBank()

    n_frames, height, width = frames.shape
    roi = roi.clamp(height, width)
    pad = bank.pad

    template = frames[0][roi.slice()].astype(np.float32)
    ref_patch = extract_patch(frames[0], roi.x, roi.y, roi.w, roi.h, pad)
    ref_responses = bank.responses(ref_patch)

    displacement = np.zeros((n_frames, 2))
    coarse = np.zeros((n_frames, 2), dtype=int)
    residual = np.zeros((n_frames, 2))
    score = np.ones(n_frames)
    weight = np.zeros(n_frames)

    last_xy = np.array([roi.x, roi.y], dtype=int)
    for k in range(1, n_frames):
        frame = frames[k]

        # --- stage 1: integer-pixel template matching in a local window ---
        wx0 = int(np.clip(last_xy[0] - search_margin, 0, width - roi.w))
        wy0 = int(np.clip(last_xy[1] - search_margin, 0, height - roi.h))
        wx1 = int(np.clip(last_xy[0] + roi.w + search_margin, roi.w, width))
        wy1 = int(np.clip(last_xy[1] + roi.h + search_margin, roi.h, height))
        window = frames[k, wy0:wy1, wx0:wx1].astype(np.float32)

        ncc = cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(ncc)
        score[k] = max_val
        if max_val >= min_score:
            last_xy = np.array([wx0 + max_loc[0], wy0 + max_loc[1]])
        coarse[k] = last_xy - np.array([roi.x, roi.y])

        # --- stage 2: phase-based sub-pixel residual (Gabor bank) ---
        cur_patch = extract_patch(frame, last_xy[0], last_xy[1],
                                  roi.w, roi.h, pad)
        cur_responses = bank.responses(cur_patch)
        residual[k], weight[k] = bank.phase_displacement(
            ref_responses, cur_responses
        )

        displacement[k] = coarse[k] + residual[k]

    return TrackResult(
        roi=roi,
        displacement=displacement,
        coarse=coarse,
        residual=residual,
        score=score,
        weight=weight,
    )
