"""Specimen configuration with support, springs and masses (finite-element model)."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vibrometry.session import Session, SpecimenCfg
from vibrometry.workflow import mode_shape_check

SESSION = Path(__file__).resolve().parents[1] / "sessions" / "k1_cm_acc.vibro.json"


def bench(spring_mass_g=0.0, hardware_g=0.0, k=1500.0) -> SpecimenCfg:
    """Al 6351-T6 bar pinned at a bearing, spring at 632 mm, 5 g accelerometer at 300 mm."""
    return SpecimenCfg(
        material="aluminum_6351_t6", E_gpa=69.0, rho=2710.0, L_mm=720.0, b_mm=25.4,
        t_mm=12.7, support="pinned",
        springs=[{"name": "k", "x_mm": 632.0, "k_n_m": k,
                  "mass_g": spring_mass_g, "hardware_g": hardware_g}],
        masses=[{"name": "acc", "x_mm": 300.0, "mass_g": 5.0}])


def test_default_specimen_keeps_the_closed_form():
    sp = SpecimenCfg(tip_mass_g=3.0)
    assert not sp.uses_fe
    assert sp.predicted_f1() == pytest.approx(
        sp.beam().mass_loaded_frequency(0.003), rel=1e-12)
    assert sp.model_label() == "Euler-Bernoulli, engastada"


def test_clamped_fe_agrees_with_the_closed_form():
    closed = SpecimenCfg(tip_mass_g=5.0)
    fe = SpecimenCfg(tip_mass_g=5.0, masses=[{"name": "x", "x_mm": 150.0, "mass_g": 0.0}])
    assert fe.uses_fe
    # the closed form is the single-DOF (0.2357 m) approximation: ~0.7 % apart here
    assert fe.predicted_f1() == pytest.approx(closed.predicted_f1(), rel=1.2e-2)


def test_bench_without_spring_mass_overestimates_f1():
    # no spring mass: ~11.7 Hz (the measured 7.6 Hz needs ~380 g effective mass)
    assert bench().predicted_f1() == pytest.approx(11.7, abs=0.2)


def test_spring_effective_mass_is_one_third_plus_hardware():
    a = bench(spring_mass_g=900.0, hardware_g=83.0).predicted_f1()     # 300 + 83 = 383 g
    b = bench(spring_mass_g=0.0, hardware_g=383.0).predicted_f1()
    assert a == pytest.approx(b, rel=1e-9)
    assert a == pytest.approx(7.6, abs=0.1)


def test_stiffer_spring_raises_f1_and_mass_lowers_it():
    assert bench(900, 83, k=2500).predicted_f1() > bench(900, 83, k=1500).predicted_f1()
    assert bench(1200, 83).predicted_f1() < bench(900, 83).predicted_f1()


def test_pinned_without_spring_has_a_rigid_body_mode_that_is_skipped():
    sp = SpecimenCfg(L_mm=720.0, b_mm=25.4, t_mm=12.7, support="pinned",
                     material="aluminum_6351_t6", E_gpa=69.0, rho=2710.0)
    fe = sp.fe_model()
    assert fe.n_rigid == 1 and fe.natural_frequency(1) < 0.5
    assert sp.predicted_f1() == pytest.approx(fe.natural_frequency(2))
    assert sp.predicted_f1() > 20.0


def test_position_outside_the_beam_is_rejected():
    sp = bench()
    sp.springs[0]["x_mm"] = 900.0
    with pytest.raises(ValueError):
        sp.predicted_f1()


def test_session_roundtrip_keeps_the_new_fields(tmp_path):
    s = Session(name="x")
    s.specimen = bench(900.0, 83.0)
    s.video.roi_positions_mm = {"a": 300.0, "b": 632.0}
    path = s.save(tmp_path / "x.vibro.json")
    r = Session.load(path)
    assert r.specimen.support == "pinned"
    assert r.specimen.springs == s.specimen.springs
    assert r.specimen.masses == s.specimen.masses
    assert r.video.roi_positions_mm == {"a": 300.0, "b": 632.0}
    assert r.specimen.predicted_f1() == pytest.approx(s.specimen.predicted_f1())


def test_old_session_without_the_new_fields_still_loads(tmp_path):
    d = {"name": "old", "specimen": {"material": "steel", "L_mm": 300.0, "b_mm": 25.0,
                                     "t_mm": 1.0, "tip_mass_g": 0.0}}
    p = tmp_path / "old.vibro.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    s = Session.load(p)
    assert s.specimen.support == "clamped" and s.specimen.springs == []
    assert not s.specimen.uses_fe and s.video.roi_positions_mm == {}


def test_repository_session_is_configured_for_the_bench():
    s = Session.load(SESSION)
    assert s.specimen.support == "pinned"
    assert s.specimen.springs[0]["k_n_m"] == 1500.0
    assert s.video.roi_positions_mm["Parafuso_de_fixação"] == 632.0


def _analysis(amplitudes: dict[str, float], f: float):
    modal = {n: SimpleNamespace(amplitude=a, f_n=f) for n, a in amplitudes.items()}
    return SimpleNamespace(modal=modal)


def test_mode_shape_check_recovers_the_model_ratios():
    s = Session()
    s.specimen = bench(900.0, 83.0)
    s.video.roi_positions_mm = {"Acelerometro": 300.0, "Parafuso": 632.0}
    fe = s.specimen.fe_model()
    shape = np.abs(fe.elastic_mode_shape(np.array([0.300, 0.632]), 1))
    chk = mode_shape_check(s, _analysis({"Acelerometro": 3.0 * shape[0],
                                         "Parafuso": 3.0 * shape[1]}, fe.elastic_frequency(1)))
    assert chk is not None and chk.mode == 1 and chk.reference == "Parafuso"
    assert all(abs(r.error_percent) < 1e-6 for r in chk.rows)
    assert chk.rows[0].predicted_ratio == pytest.approx(shape[0] / shape[1])


def test_mode_shape_check_needs_two_positioned_rois():
    s = Session()
    s.specimen = bench(900.0, 83.0)
    s.video.roi_positions_mm = {"A": 300.0}
    assert mode_shape_check(s, _analysis({"A": 1.0, "B": 2.0}, 7.6)) is None


def test_windows_style_relative_paths_resolve(tmp_path):
    (tmp_path / "videos").mkdir()
    (tmp_path / "videos" / "a.mov").write_bytes(b"x")
    (tmp_path / "sessions").mkdir()
    p = tmp_path / "sessions" / "w.vibro.json"
    p.write_text(json.dumps({"name": "w", "video": {"path": "..\\\\videos\\\\a.mov"}}),
                 encoding="utf-8")
    s = Session.load(p)
    assert Path(s.video.path) == (tmp_path / "videos" / "a.mov").resolve()
    saved = json.loads(Path(s.save(p)).read_text(encoding="utf-8"))
    assert saved["video"]["path"] == "../videos/a.mov"
