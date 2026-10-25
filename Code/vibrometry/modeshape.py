"""
Multi-point measurement of the operating deflection shape along a beam
(TODO E5 / C7): ROIs placed at known positions along the beam in the same
video act as an array of virtual sensors. At the natural frequency, the
amplitude and phase of each ROI (common-frequency sine fit) form the
measured mode shape, compared with the model mode shape by the point-wise
amplitude ratio and by the Modal Assurance Criterion (MAC) [Ewins 2000]:

    MAC = |phi_m^T phi_a|^2 / ((phi_m^T phi_m) (phi_a^T phi_a)).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .analysis import fit_sine
from .roi import ROI


def point_on_beam(p_root: tuple[float, float], p_tip: tuple[float, float],
                  length_mm: float, x_mm: float) -> np.ndarray:
    """Image point [px] at distance ``x_mm`` from the root along the segment
    root -> tip of length ``length_mm`` (e.g. the calibration segment)."""
    p0, p1 = np.asarray(p_root, float), np.asarray(p_tip, float)
    return p0 + (p1 - p0) * (x_mm / length_mm)


def rois_along_beam(
    p_root: tuple[float, float],
    p_tip: tuple[float, float],
    length_mm: float,
    positions_mm: list[float],
    width_px: int = 30,
    height_px: int = 41,
    y_offset_px: float = 0.0,
    prefix: str = "x",
) -> list[ROI]:
    """Rectangular ROIs centred on the beam line at ``positions_mm`` (shifted
    by ``y_offset_px`` vertically, e.g. from the calibrated edge to the beam
    centre line). Names are ``<prefix><mm>``."""
    rois = []
    for x in positions_mm:
        c = point_on_beam(p_root, p_tip, length_mm, x)
        rois.append(ROI(f"{prefix}{x:g}", int(round(c[0] - width_px / 2)),
                        int(round(c[1] + y_offset_px - height_px / 2)),
                        int(width_px), int(height_px)))
    return rois


@dataclass
class MeasuredShape:
    names: list[str]
    positions_mm: np.ndarray
    amplitude: np.ndarray       # sine-fit amplitude at f (signal unit)
    phase_deg: np.ndarray       # relative to the reference point
    frequency: float            # common analysis frequency [Hz]
    r2: np.ndarray              # sine-fit quality of each point

    def signed(self) -> np.ndarray:
        """Real mode-shape vector: amplitude with the sign of cos(phase)
        (in phase = +, opposite = -)."""
        return self.amplitude * np.sign(np.cos(np.radians(self.phase_deg)))


def measured_shape(t: np.ndarray, signals: dict[str, np.ndarray],
                   positions_mm: dict[str, float], frequency: float,
                   reference: str | None = None) -> MeasuredShape:
    """Amplitude and phase of every positioned signal at a common frequency
    (sine fit with the frequency held). Phases are relative to ``reference``
    (default: the point of largest amplitude)."""
    names = sorted((n for n in signals if n in positions_mm), key=lambda n: positions_mm[n])
    fits = {n: fit_sine(t, np.asarray(signals[n]) - np.mean(signals[n]), frequency,
                        refine=False) for n in names}
    amp = np.array([fits[n].amplitude for n in names])
    ref = reference or names[int(np.argmax(amp))]
    ph = np.array([(fits[n].phase_deg - fits[ref].phase_deg + 180.0) % 360.0 - 180.0
                   for n in names])
    return MeasuredShape(names, np.array([positions_mm[n] for n in names]), amp, ph,
                         float(frequency), np.array([fits[n].r2 for n in names]))


def mac(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.dot(a, b) ** 2 / (np.dot(a, a) * np.dot(b, b)))


@dataclass
class ShapeComparison:
    measured: MeasuredShape
    predicted: np.ndarray          # model shape at the points, scaled to the measurement
    mode: int                      # elastic mode of the model
    f_model: float
    mac: float
    error_percent: np.ndarray      # point-wise (measured - predicted) / predicted
    scale: float                   # least-squares factor model -> measurement


def compare_shape(measured: MeasuredShape, fe) -> ShapeComparison:
    """Compare with the elastic mode of the finite-element model ``fe``
    (``BeamFE``) whose frequency is closest to the measured one. The model
    shape is scaled to the measurement by least squares, so the comparison
    is about the *shape*, not the absolute amplitude."""
    k = min(range(1, 5), key=lambda i: abs(fe.elastic_frequency(i) - measured.frequency))
    phi = fe.elastic_mode_shape(measured.positions_mm / 1e3, k)
    m = measured.signed()
    scale = float(np.dot(phi, m) / np.dot(phi, phi))
    pred = scale * phi
    with np.errstate(divide="ignore", invalid="ignore"):
        err = 100.0 * (m - pred) / pred
    return ShapeComparison(measured, pred, int(k), float(fe.elastic_frequency(k)),
                           mac(m, phi), err, scale)


# --------------------------------------------------------------------------- #
# tracking points on a straight beam edge
# --------------------------------------------------------------------------- #
@dataclass
class PointTracks:
    times: np.ndarray                 # [s]
    displacement: dict[str, np.ndarray]   # vertical, reference-compensated, scaled
    min_score: dict[str, float]       # lowest NCC score of the coarse match


def track_points(video_path: str, rois: list[ROI], reference: ROI | None,
                 fps: float, start_frame: int = 0, scale: float | None = None,
                 search_axes: dict[str, str] | None = None,
                 search_margin: int = 60, bank=None) -> PointTracks:
    """Track ROIs with a per-ROI coarse search direction (``search_axes``,
    default "xy"); ROIs on a uniform straight edge should use "y" (vertical
    motion only), because their position along the edge is undetermined.
    Returns the vertical displacement of every ROI minus that of
    ``reference``, times ``scale`` (mm/px) if given."""
    import cv2

    from .gabor import GaborBank
    from .tracking import RoiTracker

    bank = bank or GaborBank()
    axes = search_axes or {}
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(video_path)
    if start_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    ok, frame = cap.read()
    if not ok:
        raise ValueError("could not read the first frame")
    g0 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    trackers = {r.name: RoiTracker(g0, r, bank=bank, search_margin=search_margin,
                                   search_axes=axes.get(r.name, "xy"))
                for r in rois}
    ref_t = RoiTracker(g0, reference, bank=bank, search_margin=search_margin) if reference else None
    n = 1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for t in trackers.values():
            t.update(g)
        if ref_t is not None:
            ref_t.update(g)
        n += 1
    cap.release()
    ref_y = ref_t.result().displacement[:, 1] if ref_t else np.zeros(n)
    k = scale if scale else 1.0
    disp, score = {}, {}
    for name, t in trackers.items():
        res = t.result()
        disp[name] = (res.displacement[:, 1] - ref_y) * k
        score[name] = float(np.min(res.score))
    return PointTracks(np.arange(n) / fps, disp, score)


# --------------------------------------------------------------------------- #
# effective rotation centre
# --------------------------------------------------------------------------- #
def rotation_centre(positions_mm: np.ndarray, amplitudes: np.ndarray) -> tuple[float, float, float]:
    """Least-squares line A = c (x - x0) through the measured amplitudes of a
    (nearly) rigid rotation. Returns (x0 [mm], c, R^2): x0 is where the
    amplitude extrapolates to zero, i.e. the effective rotation centre."""
    x, a = np.asarray(positions_mm, float), np.asarray(amplitudes, float)
    c, b = np.polyfit(x, a, 1)
    pred = c * x + b
    r2 = 1.0 - np.sum((a - pred) ** 2) / np.sum((a - a.mean()) ** 2)
    return float(-b / c), float(c), float(r2)


def shifted_specimen(specimen, d_mm: float):
    """Copy of a specimen with the root moved ``d_mm`` *before* the original
    origin (positions measured from the old origin keep their meaning): the
    free length grows by d and every spring/mass position by d."""
    import copy

    s = copy.deepcopy(specimen)
    s.L_mm = specimen.L_mm + d_mm
    for item in list(s.springs) + list(s.masses):
        item["x_mm"] = float(item["x_mm"]) + d_mm
    return s
