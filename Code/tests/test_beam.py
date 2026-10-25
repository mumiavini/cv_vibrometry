"""Analytical-model checks: closed form vs finite elements vs plain cantilever."""

import numpy as np
import pytest

from vibrometry.beam import BeamFE, CantileverBeam, SpringSupportedBeam

# aluminium bar of the bench test, 700 mm free length
BAR = CantileverBeam(0.70, 0.0254, 0.0127, 69e9, 2710.0)


def test_plain_cantilever_matches_tcc_table():
    assert BAR.natural_frequency(1) == pytest.approx(21.1, abs=0.05)
    assert BAR.natural_frequency(2) == pytest.approx(132.4, abs=0.1)


@pytest.mark.parametrize("mode", [1, 2, 3])
def test_fe_without_attachments_matches_cantilever(mode):
    fe = BeamFE(BAR)
    assert fe.natural_frequency(mode) == pytest.approx(
        BAR.natural_frequency(mode), rel=2e-3)


@pytest.mark.parametrize("k, mass", [(500, 0.0), (2000, 0.0), (2000, 0.05)])
def test_closed_form_tip_spring_matches_fe(k, mass):
    exact = SpringSupportedBeam(BAR, k, mass)
    fe = BeamFE(BAR, springs=((BAR.length, k),), masses=((BAR.length, mass),))
    for mode in (1, 2, 3):
        assert fe.natural_frequency(mode) == pytest.approx(
            exact.natural_frequency(mode), rel=2e-3)


def test_spring_stiffens_the_bar():
    f = [BeamFE(BAR, springs=((0.62, k),)).natural_frequency(1)
         for k in (0.0, 1500.0, 2500.0)]
    assert f[0] < f[1] < f[2]


def test_added_mass_lowers_frequency():
    f0 = BeamFE(BAR).natural_frequency(1)
    f1 = BeamFE(BAR, masses=((0.30, 0.005),)).natural_frequency(1)
    assert f1 < f0


def test_mode_shape_normalised_and_consistent():
    x = np.array([0.0, 0.2, 0.4, 0.7])
    exact = SpringSupportedBeam(BAR, 2000.0).mode_shape(x, 1)
    fe = BeamFE(BAR, springs=((BAR.length, 2000.0),)).mode_shape(x, 1)
    assert exact[0] == pytest.approx(0.0, abs=1e-9)
    assert exact[-1] == pytest.approx(1.0)
    assert fe == pytest.approx(exact, abs=1e-2)


def test_pinned_root_has_rigid_body_mode_without_spring():
    fe = BeamFE(BAR, root="pinned")
    assert fe.natural_frequency(1) < 0.5
    assert BeamFE(BAR, springs=((0.62, 1500.0),),
                  root="pinned").natural_frequency(1) > 1.0
