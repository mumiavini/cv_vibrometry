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

_SHIFT = 4                # fractional bits for cv2 drawing (1/16 px)
_SUB = 1 << _SHIFT


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
    n_frames = int(round(duration * fps))
    t = np.arange(n_frames) / fps

    wn = 2.0 * np.pi * f_n
    wd = wn * np.sqrt(1.0 - zeta ** 2)
    tip_y = amplitude_px * np.exp(-zeta * wn * t) * np.sin(wd * t)

    geometry = render_cantilever_video(path, tip_y, fps, size=size,
                                       noise_std=noise_std, seed=seed)
    return SyntheticGroundTruth(
        f_n=f_n,
        zeta=zeta,
        amplitude_px=amplitude_px,
        fps=fps,
        tip_y=tip_y,
        **geometry,
    )


def render_cantilever_video(
    path: str | Path,
    tip_y: np.ndarray,
    fps: float,
    size: tuple[int, int] = (1280, 720),
    noise_std: float = 1.5,
    seed: int = 0,
) -> dict:
    """Write a video of the clamped ruler whose tip follows ``tip_y`` [px]
    (one value per frame, +y down). Returns the marker geometry."""
    width, height = size
    n_frames = len(tip_y)
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

        # deflected ruler (first mode shape scaled by the tip displacement);
        # drawn with fractional coordinates (1/16 px) and anti-aliasing so
        # that sub-pixel motion is actually present in the image
        y_line = ruler_y + tip_y[k] * shape
        pts = np.round(np.stack([x_axis, y_line], axis=1) * _SUB).astype(np.int32)
        for offset in range(-ruler_half_h, ruler_half_h + 1):
            shifted = pts.copy()
            shifted[:, 1] += offset * _SUB
            cv2.polylines(img, [shifted], False, 170, 1, cv2.LINE_AA, _SHIFT)
        for edge in (-ruler_half_h, ruler_half_h):
            cv2.polylines(img, [pts + np.array([0, edge * _SUB])], False, 90, 2,
                          cv2.LINE_AA, _SHIFT)

        # tip marker (high-contrast dot, TCC: marcador na ponta)
        cy = int(round((ruler_y + tip_y[k]) * _SUB))
        cv2.circle(img, (tip_x * _SUB, cy), marker_radius * _SUB, 20, -1,
                   cv2.LINE_AA, _SHIFT)

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

    return {
        "marker_center": (tip_x, ruler_y),
        "marker_radius": marker_radius,
        "static_marker_center": static_center,
    }


# --------------------------------------------------------------------------- #
# video + accelerometer validation dataset
# --------------------------------------------------------------------------- #
def _forced_motion(t, f, amp, t_tap, t_start, ramp=0.5, tap_amp=None, tap_sigma=0.012):
    """Sync tap (Gaussian pulse) followed by a ramped-up sine.
    Returns displacement and its exact second derivative (same unit / s^2)."""
    tap_amp = 1.5 * amp if tap_amp is None else tap_amp
    u = (t - t_tap) / tap_sigma
    g = tap_amp * np.exp(-u ** 2 / 2)
    g2 = tap_amp / tap_sigma ** 2 * (u ** 2 - 1) * np.exp(-u ** 2 / 2)

    w = 2 * np.pi * f
    tau = np.clip((t - t_start) / ramp, 0.0, 1.0)
    inside = (t > t_start) & (t < t_start + ramp)
    r = 3 * tau ** 2 - 2 * tau ** 3
    r1 = np.where(inside, (6 * tau - 6 * tau ** 2) / ramp, 0.0)
    r2 = np.where(inside, (6 - 12 * tau) / ramp ** 2, 0.0)
    s = amp * np.sin(w * (t - t_start))
    s1 = amp * w * np.cos(w * (t - t_start))
    s2 = -w ** 2 * s
    return g + r * s, g2 + r2 * s + 2 * r1 * s1 + r * s2


def _free_motion(t, f, zeta, amp, t_release, t_push=0.2, push=0.5):
    """Pluck test (campaign A): the tip is pushed smoothly to ``amp``
    (smoothstep from ``t_push`` over ``push`` s), held, and released at
    ``t_release`` with zero velocity:

        x = A e^{-a tau} (cos w_d tau + (a / w_d) sin w_d tau),  a = zeta w_n

    Position and velocity are continuous (the acceleration only jumps), so
    the accelerometer signal is physically consistent with the video.
    Returns displacement and its exact second derivative.
    """
    wd = 2 * np.pi * f                       # f is the damped frequency
    wn = wd / np.sqrt(1 - zeta ** 2)
    a = zeta * wn

    tau_p = np.clip((t - t_push) / push, 0.0, 1.0)
    pushing = (t > t_push) & (t < t_push + push)
    x_hold = amp * (3 * tau_p ** 2 - 2 * tau_p ** 3)
    a_hold = np.where(pushing, amp * (6 - 12 * tau_p) / push ** 2, 0.0)

    tau = np.maximum(t - t_release, 0.0)
    e = np.exp(-a * tau)
    x_free = amp * e * (np.cos(wd * tau) + a / wd * np.sin(wd * tau))
    v_free = -amp * wn ** 2 / wd * e * np.sin(wd * tau)
    a_free = -wn ** 2 * x_free - 2 * a * v_free      # equation of motion

    on = t >= t_release
    return np.where(on, x_free, x_hold), np.where(on, a_free, a_hold)


def generate_validation_dataset(
    folder: str | Path,
    kind: str = "forced",
    f: float = 8.0,
    amplitude_mm: float = 2.0,
    zeta: float = 0.01,
    scale_mm_per_px: float = 0.25,
    fps: float = 240.0,
    duration: float = 8.0,
    size: tuple[int, int] = (640, 360),
    video_noise: float = 1.5,
    acc_fs: float = 1000.0,
    acc_offset_s: float = 0.8374,
    acc_noise_g: float = 0.002,
    seed: int = 0,
) -> dict:
    """Synthetic video + accelerometer CSV of the *same* motion with known
    ground truth, plus a ready-to-use session file.

    The accelerometer starts ``acc_offset_s`` before the video, so the clock
    model t_a = offset + t_v must recover ``acc_offset_s``. The CSV mimics a
    Brazilian-locale export (``;`` separator, ``,`` decimal) to exercise the
    importer.

    kind : "forced" (sync tap + steady sine at ``f``) or "free" (tip pushed
        to ``amplitude_mm`` and released at t = 1 s: free decay at damped
        frequency ``f``).
    """
    from .roi import ROI
    from .session import Session

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"sintetico_{kind}_{f:g}Hz".replace(".", "p")
    video_path = folder / f"{stem}_video.mp4"
    acc_path = folder / f"{stem}_acc.csv"

    def motion(t):
        if kind == "free":
            return _free_motion(t, f, zeta, amplitude_mm, t_release=1.0)
        return _forced_motion(t, f, amplitude_mm, t_tap=0.6, t_start=1.5)

    # --- video ------------------------------------------------------------ #
    n_frames = int(round(duration * fps))
    t_v = np.arange(n_frames) / fps
    x_mm, _ = motion(t_v)
    geo = render_cantilever_video(video_path, x_mm / scale_mm_per_px, fps,
                                  size=size, noise_std=video_noise, seed=seed)

    # --- accelerometer (its clock: t_a = offset + t_v); like in a real test
    # it keeps recording a few seconds after the camera stops ------------- #
    rng = np.random.default_rng(seed + 1)
    t_a = np.arange(int((acc_offset_s + duration + 3.0) * acc_fs)) / acc_fs
    _, a_mm = motion(t_a - acc_offset_s)
    a_g = a_mm * 1e-3 / 9.80665 + rng.normal(0.0, acc_noise_g, t_a.size)
    with open(acc_path, "w", encoding="utf-8", newline="") as fh:
        fh.write("Tempo [s];AI 1 [g]\n")
        for ti, ai in zip(t_a, a_g):
            fh.write(f"{ti:.6f};{ai:.7f}\n".replace(".", ","))

    # --- session ---------------------------------------------------------- #
    # ROI on the marker only: the ruler edges next to it move less than the
    # tip (mode shape), which would bias the measured amplitude low
    tx, ty = geo["marker_center"]
    r = geo["marker_radius"] + 4
    sx, sy = geo["static_marker_center"]
    rois = [ROI("ponta", tx - r, ty - r, 2 * r, 2 * r),
            ROI("referencia", sx - 26, sy - 26, 52, 52, is_reference=True)]

    s = Session(name=stem)
    s.meta.excitation_hz = f if kind == "forced" else None
    s.meta.camera = "sintetico"
    # 1 mm steel ruler whose Euler-Bernoulli f_n,1 equals the imposed f, so
    # the analytical-validation path can be exercised too
    sp = s.specimen
    c = 1.8751 ** 2 / (2 * np.pi) * (sp.t_mm / 1e3) * np.sqrt(
        sp.E_gpa * 1e9 / (12 * sp.rho))
    sp.L_mm = round(1e3 * np.sqrt(c / f), 2)
    sp.fps = fps
    truth = {
        "kind": kind, "f_hz": f, "amplitude_mm": amplitude_mm,
        "zeta": zeta if kind == "free" else None,
        "scale_mm_per_px": scale_mm_per_px, "fps": fps,
        "acc_offset_s": acc_offset_s, "acc_fs": acc_fs,
    }
    s.meta.notes = "Verdade de referência (sintético): " + ", ".join(
        f"{k}={v}" for k, v in truth.items() if v is not None)
    s.video.path = str(video_path)
    s.video.rois = [r.__dict__.copy() for r in rois]
    s.video.scale_mm_per_px = scale_mm_per_px
    s.video.axis = "y"
    s.accel.path = str(acc_path)
    s.accel.time_column, s.accel.channel, s.accel.unit = 0, 1, "g"
    s.compare.roi = "ponta"
    s.compare.sync_mode = "impact"
    if kind == "forced":
        s.compare.window = [2.5, duration - 0.2]
        s.compare.f_analysis = f
    else:
        s.video.window = [1.0, duration]
        s.compare.window = [1.0, duration - 0.2]
    session_path = s.save(folder / f"{stem}.vibro.json")
    return {"video": video_path, "accel": acc_path, "session": session_path,
            "truth": truth}
