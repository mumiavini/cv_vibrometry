"""Synchronisation with a known fractional delay and the comparison metrics
(planejamento 10: "Sincronismo sintético: atraso fracionário conhecido")."""

import numpy as np
import pytest

from vibrometry.analysis import compare_signals, fit_sine, wrap_deg
from vibrometry.sync import bandpass, estimate_drift, estimate_offset


def _event_signal(t):
    """Tap at 1 s followed by a ramped 8 Hz sine from 2 s."""
    tap = 3 * np.exp(-0.5 * ((t - 1.0) / 0.012) ** 2)
    ramp = np.clip((t - 2.0) / 0.5, 0, 1)
    return tap + ramp * 2 * np.sin(2 * np.pi * 8 * (t - 2.0))


@pytest.mark.parametrize("mode", ["impact", "waveform"])
def test_offset_recovers_fractional_delay(mode):
    fs_v, fs_a, offset = 240.0, 1000.0, 0.83741   # 0.83741 s = 200.98 video frames
    t_v = np.arange(int(8 * fs_v)) / fs_v
    t_a = np.arange(int(10 * fs_a)) / fs_a
    v = _event_signal(t_v)
    a = _event_signal(t_a - offset)
    if mode == "waveform":   # only unambiguous around the right lag
        r = estimate_offset(v, t_a, a, fs_v, mode=mode, max_lag=0.05, around=0.83)
    else:
        r = estimate_offset(v, t_a, a, fs_v, mode=mode, f_dominant=8.0)
    assert r.offset == pytest.approx(offset, abs=0.1 / fs_v)   # < 0.1 frame
    assert not r.inverted and r.correlation > 0.99


def test_offset_detects_inverted_polarity():
    fs_v, fs_a = 240.0, 1000.0
    t_v = np.arange(int(8 * fs_v)) / fs_v
    t_a = np.arange(int(10 * fs_a)) / fs_a
    r = estimate_offset(_event_signal(t_v), t_a, -_event_signal(t_a - 0.5), fs_v,
                        mode="impact", f_dominant=8.0)
    assert r.inverted
    assert r.offset == pytest.approx(0.5, abs=0.1 / fs_v)


def test_drift_estimate():
    fs_v, fs_a, offset, drift_ppm = 240.0, 1000.0, 0.4, 800.0
    t_v = np.arange(int(20 * fs_v)) / fs_v
    t_a = np.arange(int(22 * fs_a)) / fs_a
    sig = lambda t: np.sin(2 * np.pi * 6.3 * t) + 0.5 * np.sin(2 * np.pi * 2.1 * t)
    v = sig(t_v)
    a = sig((t_a - offset) / (1 + drift_ppm * 1e-6))
    r = estimate_drift(v, t_a, a, fs_v, offset, f_dominant=6.3)
    assert r.drift_ppm == pytest.approx(drift_ppm, abs=50)
    assert r.offset == pytest.approx(offset, abs=1e-3)


def test_fit_sine_and_compare():
    fs = 240.0
    t = np.arange(int(5 * fs)) / fs
    ref = 2.0 * np.cos(2 * np.pi * 10.003 * t + 0.3)
    test = 1.9 * np.cos(2 * np.pi * 10.003 * t + 0.3 + np.radians(12.0))
    fit = fit_sine(t, ref, 10.0)
    assert fit.frequency == pytest.approx(10.003, rel=1e-5)
    assert fit.amplitude == pytest.approx(2.0, rel=1e-4)
    assert fit.phase_deg == pytest.approx(np.degrees(0.3), abs=0.05)
    c = compare_signals(t, ref, test, fs)
    assert c.amp_error_percent == pytest.approx(-5.0, abs=0.05)
    assert c.phase_diff_deg == pytest.approx(12.0, abs=0.05)
    assert abs(c.freq_error_percent) < 1e-3


def test_wrap_and_bandpass():
    assert wrap_deg(190) == pytest.approx(-170)
    assert wrap_deg(-190) == pytest.approx(170)
    fs = 240.0
    t = np.arange(int(6 * fs)) / fs
    x = 5 + 0.5 * t + np.sin(2 * np.pi * 8 * t)          # offset + drift + 8 Hz
    y = bandpass(x, fs, f_hp=1.0)
    m = (t > 1) & (t < 5)
    assert np.allclose(y[m], np.sin(2 * np.pi * 8 * t[m]), atol=0.03)
