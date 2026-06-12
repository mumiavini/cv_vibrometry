"""
Synthetic cantilever video generator for pipeline verification.

Renders a clamped ruler whose free tip follows the analytical free decay of
an underdamped 1-DOF system (eq:resposta_subamortecida):

    y(t) = A * exp(-zeta * wn * t) * sin(wd * t)

with a high-contrast marker at the tip and a static marker for the
reference ROI.  Because frequency, damping and amplitude are imposed, the
pipeline output can be checked against exact ground truth — the software
analogue of the Phase-1 validation strategy of the TCC.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class SyntheticGroundTruth:
    f_n: float                 # imposed natural frequency [Hz]
    zeta: float                # imposed damping ratio
    amplitude_px: float        # initial tip amplitude [px]
    fps: float
    marker_center: tuple[int, int]   # tip marker position at rest (x, y)
    marker_radius: int
    static_marker_center: tuple[int, int]
    tip_y: np.ndarray          # exact tip displacement per frame [px]

    @property
    def f_d(self) -> float:
        """Damped frequency f_d = f_n * sqrt(1 - zeta^2) [Hz]."""
        return self.f_n * np.sqrt(1.0 - self.zeta ** 2)


def generate_cantilever_video(
    path: str | Path,
    f_n: float = 2.5,
    zeta: float = 0.012,
    amplitude_px: float = 60.0,
    fps: float = 30.0,
    duration: float = 12.0,
    size: tuple[int, int] = (1280, 720),
    noise_std: float = 1.5,
    seed: int = 0,
) -> SyntheticGroundTruth:
    """Write a synthetic free-decay cantilever video and return ground truth.

    The scene: a horizontal ruler clamped at the left edge, black circular
    marker at the free tip moving vertically as a decaying sinusoid, and a
    static square marker near the bottom-left corner (reference ROI target).
    """
    width, height = size
    n_frames = int(round(duration * fps))
    t = np.arange(n_frames) / fps

    wn = 2.0 * np.pi * f_n
    wd = wn * np.sqrt(1.0 - zeta ** 2)
    tip_y = amplitude_px * np.exp(-zeta * wn * t) * np.sin(wd * t)

    clamp_w = 90
    ruler_y = height // 2
    ruler_half_h = 18
    tip_x = int(width * 0.82)
    marker_radius = 11
    static_center = (int(width * 0.08), int(height * 0.88))

    rng = np.random.default_rng(seed)
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for '{path}'.")

    x_axis = np.arange(clamp_w, tip_x + 1, dtype=float)
    # first cantilever mode shape (normalised tip deflection = 1)
    xi = (x_axis - clamp_w) / max(tip_x - clamp_w, 1)
    beta_l = 1.8751
    shape = (
        np.cosh(beta_l * xi) - np.cos(beta_l * xi)
        - ((np.cosh(beta_l) + np.cos(beta_l))
           / (np.sinh(beta_l) + np.sin(beta_l)))
        * (np.sinh(beta_l * xi) - np.sin(beta_l * xi))
    )
    shape /= shape[-1]

    for k in range(n_frames):
        img = np.full((height, width), 225, dtype=np.uint8)

        # clamp block
        cv2.rectangle(img, (0, ruler_y - 70), (clamp_w, ruler_y + 70),
                      60, thickness=-1)

        # deflected ruler (first mode shape scaled by the tip displacement)
        y_line = ruler_y + tip_y[k] * shape
        pts = np.stack([x_axis, y_line], axis=1).astype(np.int32)
        for offset in range(-ruler_half_h, ruler_half_h + 1):
            shifted = pts.copy()
            shifted[:, 1] += offset
            cv2.polylines(img, [shifted], False, 170, thickness=1)
        cv2.polylines(img, [pts + np.array([0, -ruler_half_h])], False, 90, 2)
        cv2.polylines(img, [pts + np.array([0, ruler_half_h])], False, 90, 2)

        # tip marker (high-contrast dot, TCC: marcador na ponta)
        cy = int(round(ruler_y + tip_y[k]))
        cv2.circle(img, (tip_x, cy), marker_radius, 20, thickness=-1)

        # static reference marker
        sx, sy = static_center
        cv2.rectangle(img, (sx - 12, sy - 12), (sx + 12, sy + 12),
                      30, thickness=-1)

        # sensor noise
        if noise_std > 0:
            noise = rng.normal(0.0, noise_std, img.shape)
            img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        writer.write(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    writer.release()

    return SyntheticGroundTruth(
        f_n=f_n,
        zeta=zeta,
        amplitude_px=amplitude_px,
        fps=fps,
        marker_center=(tip_x, ruler_y),
        marker_radius=marker_radius,
        static_marker_center=static_center,
        tip_y=tip_y,
    )
