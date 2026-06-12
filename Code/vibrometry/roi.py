"""
Module 2 — Region-of-interest definition (TCC: "Definição das regiões de interesse").

Two ROI sets are defined over the reference frame:
  * measurement ROIs — rectangles (x0, y0, w, h) over the points of interest
    (typically the free tip of the beam and intermediate points);
  * one reference ROI — fixed to a static point of the background, used to
    estimate and compensate rigid-body motion of the camera / support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np


@dataclass
class ROI:
    name: str
    x: int
    y: int
    w: int
    h: int
    is_reference: bool = False

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    def slice(self) -> tuple[slice, slice]:
        return (slice(self.y, self.y + self.h), slice(self.x, self.x + self.w))

    def clamp(self, height: int, width: int) -> "ROI":
        """Clip the rectangle to the frame bounds."""
        x = int(np.clip(self.x, 0, width - 2))
        y = int(np.clip(self.y, 0, height - 2))
        w = int(np.clip(self.w, 1, width - x))
        h = int(np.clip(self.h, 1, height - y))
        return ROI(self.name, x, y, w, h, self.is_reference)


def save_rois(rois: list[ROI], path: str | Path) -> None:
    Path(path).write_text(json.dumps([asdict(r) for r in rois], indent=2))


def load_rois(path: str | Path) -> list[ROI]:
    return [ROI(**d) for d in json.loads(Path(path).read_text())]


def select_rois_interactive(frame: np.ndarray) -> list[ROI]:
    """Interactively draw ROIs over the reference frame.

    First select any number of measurement ROIs (ENTER/SPACE after each box,
    ESC to finish), then optionally one reference ROI on a static region of
    the background (ESC to skip).
    """
    rois: list[ROI] = []

    boxes = cv2.selectROIs("Measurement ROIs  (ESC to finish)", frame,
                           showCrosshair=True)
    cv2.destroyAllWindows()
    for i, (x, y, w, h) in enumerate(np.atleast_2d(np.asarray(boxes))):
        if w > 0 and h > 0:
            rois.append(ROI(f"roi_{i}", int(x), int(y), int(w), int(h)))

    box = cv2.selectROI("Reference ROI on static background  (ESC to skip)",
                        frame, showCrosshair=True)
    cv2.destroyAllWindows()
    x, y, w, h = box
    if w > 0 and h > 0:
        rois.append(ROI("reference", int(x), int(y), int(w), int(h),
                        is_reference=True))

    return rois
