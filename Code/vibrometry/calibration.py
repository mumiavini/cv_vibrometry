"""
Spatial calibration (TCC: "Calibração Espacial").

The scale factor s [mm/pixel] converts displacements measured in pixels to
physical units (eq:escala, eq:deslocamento_fisico):

    s = d_ref / d_px        delta(t) = s * delta_px(t)

The reference object must lie in the same focal plane as the structure;
re-calibrate after any change of camera position or configuration.
"""

from __future__ import annotations

import numpy as np


def scale_from_pixels(d_ref_mm: float, d_px: float) -> float:
    """Scale factor from a known physical length and its extent in pixels."""
    if d_px <= 0:
        raise ValueError("d_px must be positive.")
    return d_ref_mm / d_px


def scale_from_points(
    d_ref_mm: float,
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    """Scale factor from two image points spanning a known physical length."""
    d_px = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
    return scale_from_pixels(d_ref_mm, d_px)
