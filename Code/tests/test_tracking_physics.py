"""Phase-based tracking, Euler-Bernoulli model and session files
(planejamento 10: "Vídeo sintético" and "Física")."""

import cv2
import numpy as np
import pytest

from vibrometry.beam import CantileverBeam
from vibrometry.gabor import GaborBank
from vibrometry.roi import ROI
from vibrometry.session import Session
from vibrometry.tracking import RoiTracker


def test_fft_responses_match_filter2d_in_interior():
    bank = GaborBank()
    rng = np.random.default_rng(0)
    patch = cv2.GaussianBlur(rng.uniform(0, 255, (100, 120)).astype(np.float32), (0, 0), 2)
    fast = bank.responses(patch)
    p = patch - patch.mean()
    m = bank.pad
    for f, r in zip(bank.filters, fast):
        ref = (cv2.filter2D(p, cv2.CV_32F, f.kernel.real)
               + 1j * cv2.filter2D(p, cv2.CV_32F, f.kernel.imag))
        scale = np.abs(ref[m:-m, m:-m]).max()
        assert np.abs(r[m:-m, m:-m] - ref[m:-m, m:-m]).max() < 1e-5 * scale


def test_tracker_recovers_subpixel_shift():
    rng = np.random.default_rng(1)
    base = cv2.GaussianBlur(rng.uniform(0, 255, (200, 200)).astype(np.float32), (0, 0), 3)
    roi = ROI("t", 70, 70, 60, 60)
    tracker = RoiTracker(base.astype(np.uint8), roi)
    shifts = [(0.3, -0.2), (2.6, 1.4), (-7.25, 3.5)]
    for dx, dy in shifts:
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        tracker.update(cv2.warpAffine(base, m, (200, 200), flags=cv2.INTER_CUBIC,
                                      borderMode=cv2.BORDER_REFLECT).astype(np.uint8))
    res = tracker.result()
    # 8-bit quantisation + cubic resampling of the test image limit the
    # agreement to a few hundredths of a pixel (0.01-0.05 px observed)
    assert np.allclose(res.displacement[1:], shifts, atol=0.08)


def test_export_speed():
    from vibrometry.render import export_speed
    assert export_speed(240, 1 / 8) == (30, 1)        # 1/8x slow motion
    assert export_speed(240, 1.0) == (60, 4)          # real time, every 4th frame
    fps, stride = export_speed(23.976, 1 / 16)
    assert stride == 1 and fps == 5                   # clamped to a playable rate


def test_compose_signals_matches_partial_data():
    from vibrometry.streaming import compose_signals
    d = {"ponta": np.array([[0, 0], [1, 2], [2, 4.0]]),
         "ref": np.array([[0, 0], [0.5, 0.5], [1, 1.0]])}
    sig, axes = compose_signals(d, "ref", "auto", scale_mm_per_px=0.5)
    assert axes == {"ponta": "y"}
    assert np.allclose(sig["ponta"], [0, 0.75, 1.5])


def test_euler_bernoulli_and_mass_loading():
    # TCC: polystyrene ruler L=300 mm, b=35 mm, h=3 mm -> f_n,1 = 9.40 Hz
    beam = CantileverBeam(0.30, 0.035, 0.003, 3.2e9, 1050.0)
    assert beam.natural_frequency(1) == pytest.approx(9.40, abs=0.01)
    assert beam.m_eq * 1e3 == pytest.approx(7.80, abs=0.01)
    f2_over_f1 = beam.natural_frequency(2) / beam.natural_frequency(1)
    assert f2_over_f1 == pytest.approx((4.6941 / 1.8751) ** 2, rel=1e-6)
    f_m = beam.mass_loaded_frequency(beam.m_eq)          # doubling the mass
    assert f_m == pytest.approx(beam.natural_frequency(1) / np.sqrt(2), rel=1e-9)


def test_session_roundtrip(tmp_path):
    video = tmp_path / "dados" / "v.mp4"
    video.parent.mkdir()
    video.write_bytes(b"")
    s = Session(name="20261010_aco_L300_t1_10Hz_A1_r2")
    s.video.path = str(video)
    s.video.rois = [{"name": "ponta", "x": 1, "y": 2, "w": 3, "h": 4, "is_reference": False}]
    s.compare.offset_s = 0.123
    (tmp_path / "sessoes").mkdir()
    path = s.save(tmp_path / "sessoes" / "x.vibro.json")
    loaded = Session.load(path)
    assert loaded.video.path == str(video.resolve())
    assert loaded.video.roi_objects()[0] == ROI("ponta", 1, 2, 3, 4)
    assert loaded.compare.offset_s == 0.123
    assert loaded.group == "20261010_aco_L300_t1_10Hz_A1"
    assert "../dados/v.mp4" in path.read_text().replace("\\\\", "/")
