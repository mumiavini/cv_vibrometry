"""Multi-point mode shape and uncertainty propagation."""

import numpy as np
import pytest

from vibrometry.modeshape import compare_shape, mac, measured_shape, rois_along_beam
from vibrometry.session import SpecimenCfg
from vibrometry.uncertainty import (
    frequency_uncertainty,
    model_uncertainty,
    relative_error,
    repeatability,
    scale_uncertainty,
)


def bench(meff=383.0) -> SpecimenCfg:
    return SpecimenCfg(
        material="aluminum_6351_t6", E_gpa=69.0, rho=2710.0, L_mm=720.0, b_mm=25.4,
        t_mm=12.7, support="pinned",
        springs=[{"name": "k", "x_mm": 632.0, "k_n_m": 1500.0, "mass_g": 0.0,
                  "hardware_g": meff}],
        masses=[{"name": "acc", "x_mm": 300.0, "mass_g": 5.0}])


def test_rois_along_beam_follow_the_calibration_segment():
    rois = rois_along_beam((0, 100), (720, 64), 720.0, [0, 360, 720], 20, 10)
    assert [r.name for r in rois] == ["x0", "x360", "x720"]
    centres = [(r.x + r.w / 2, r.y + r.h / 2) for r in rois]
    assert centres[1] == pytest.approx((360, 82), abs=0.6)
    assert centres[2] == pytest.approx((720, 64), abs=0.6)


def test_measured_shape_and_mac_recover_the_model_shape():
    fe = bench().fe_model()
    f = fe.elastic_frequency(1)
    pos = {f"x{x}": float(x) for x in (100, 200, 300, 400, 500, 600, 700)}
    phi = fe.elastic_mode_shape(np.array(list(pos.values())) / 1e3, 1)
    t = np.arange(0, 6, 1 / 240)
    sig = {n: 4.0 * p * np.exp(-0.3 * t) * np.cos(2 * np.pi * f * t) for n, p in zip(pos, phi)}
    ms = measured_shape(t, sig, pos, f)
    assert np.all(np.abs(ms.phase_deg) < 1.0)               # all in phase in mode 1
    cmp = compare_shape(ms, fe)
    assert cmp.mode == 1 and cmp.mac == pytest.approx(1.0, abs=1e-6)
    assert np.nanmax(np.abs(cmp.error_percent)) < 1.0
    assert mac(phi, -phi) == pytest.approx(1.0) and mac([1, 0], [0, 1]) == 0.0


def test_frequency_uncertainty_contains_the_truth():
    fs, f = 240.0, 7.6
    t = np.arange(0, 8, 1 / fs)
    rng = np.random.default_rng(3)
    x = 3 * np.exp(-0.3 * t) * np.cos(2 * np.pi * f * t + 0.4) + rng.normal(0, 0.05, t.size)
    fu = frequency_uncertainty(t, x, fs)
    assert len(fu.segments) == 4
    assert fu.resolution == pytest.approx(1 / t[-1])
    assert abs(fu.f - f) < 3 * fu.u + 1e-3
    assert fu.u < fu.resolution                              # fit resolves well below 1/T


def test_repeatability_statistics():
    r = repeatability([7.60, 7.62, 7.58])
    assert r.mean == pytest.approx(7.60) and r.std == pytest.approx(0.02)
    assert r.cv_percent == pytest.approx(0.2632, rel=1e-3)
    lo, hi = r.ci95
    assert lo < 7.60 < hi and (hi - lo) / 2 == pytest.approx(4.303 * 0.02 / np.sqrt(3), rel=1e-3)
    with pytest.raises(ValueError):
        repeatability([1.0])


def test_model_uncertainty_linear_matches_monte_carlo():
    unc = {"springs[0].k_n_m": 45.0, "springs[0].hardware_g": 10.0,
           "masses[0].x_mm": 3.0, "L_mm": 2.0, "E_gpa": 2.0}
    res = model_uncertainty(bench(), unc, n_mc=200, seed=1, n_elements=60)
    assert res.f == pytest.approx(7.6, abs=0.05)
    assert res.u > 0 and res.mc_std == pytest.approx(res.u, rel=0.25)
    assert sum(c["parcela_pct"] for c in res.contributions.values()) == pytest.approx(100.0)
    # the spring stiffness and the effective mass dominate
    top = max(res.contributions, key=lambda k: res.contributions[k]["parcela_pct"])
    assert top in ("springs[0].k_n_m", "springs[0].hardware_g")
    # specimen not modified by the propagation
    assert bench().springs[0]["k_n_m"] == 1500.0


def test_scale_and_relative_error():
    s, u = scale_uncertainty(720.0, 1.0, 1403.5, 2.0)
    assert s == pytest.approx(0.51300, rel=1e-4)
    assert u == pytest.approx(s * np.hypot(1 / 720, 2 / 1403.5))
    eps, ue = relative_error(7.763, 0.01, 7.600, 0.025)
    assert eps == pytest.approx(2.1447, rel=1e-3) and ue > 0
