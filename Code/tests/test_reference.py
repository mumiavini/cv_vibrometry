"""Video-vs-accelerometer comparison on synthetic signals with known truth."""

import numpy as np
import pytest

from vibrometry import reference

F_N, SIGMA, A0, T_ON = 7.6, 0.345, 20.0, 1.3


def _video(fs=240.0, duration=20.0, a0=A0):
    t = np.arange(0.0, duration, 1.0 / fs)
    x = np.where(t >= T_ON, np.exp(-SIGMA * (t - T_ON)), 0.0) \
        * np.sin(2 * np.pi * F_N * t)
    x_mm = x * a0 / (2 * np.pi * F_N) ** 2 * 1e3        # displacement giving a0 m/s²
    return t, x_mm


def _accelerometer(a0=A0):
    t = np.arange(T_ON, 14.0, 0.0125)
    return t, a0 * np.exp(-SIGMA * (t - T_ON))


def test_compare_recovers_known_frequency_decay_and_amplitude():
    t_v, x_v = _video()
    t_a, env_a = _accelerometer()
    res, _ = reference.compare(t_v, x_v, t_a, env_a, f_acc=F_N)
    assert res.f_video == pytest.approx(F_N, abs=0.05)
    assert res.f_error_percent < 0.7
    assert res.sigma_video == pytest.approx(SIGMA, rel=0.05)
    assert res.sigma_accelerometer == pytest.approx(SIGMA, rel=0.02)
    assert res.zeta_video == pytest.approx(SIGMA / (2 * np.pi * F_N), rel=0.06)
    assert res.amplitude_ratio == pytest.approx(1.0, rel=0.1)
    assert abs(res.shift_s) < 0.3


def test_amplitude_ratio_detects_wrong_scale():
    t_v, x_v = _video(a0=1.25 * A0)       # video scale 25 % too high
    t_a, env_a = _accelerometer()
    res, _ = reference.compare(t_v, x_v, t_a, env_a, f_acc=F_N)
    assert res.amplitude_ratio == pytest.approx(1.25, rel=0.1)


def test_fit_exponential_decay_on_clean_envelope():
    t, env = _accelerometer()
    fit = reference.fit_exponential_decay(t, env)
    assert fit.sigma == pytest.approx(SIGMA, rel=1e-3)
    assert fit.r2 > 0.999


def test_command_line_end_to_end(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    t_v, x_v = _video()
    t_a, env_a = _accelerometer()
    video_csv = tmp_path / "displacement_signals.csv"
    np.savetxt(video_csv, np.c_[t_v, x_v], delimiter=",",
               header="time_s,roi_acc_mm", comments="")
    acc_csv = tmp_path / "env.csv"
    np.savetxt(acc_csv, np.c_[t_a, env_a, env_a, env_a], delimiter=",",
               header="t_s,upper_ms2,lower_ms2,half_p2p_ms2", comments="")
    out = tmp_path / "out"
    rc = reference.main([str(video_csv), "--column", "roi_acc_mm",
                         "--acc-envelope", str(acc_csv), "--f-acc", "7.6",
                         "--out", str(out)])
    assert rc == 0
    assert (out / "comparison.json").exists() and (out / "overlay.png").exists()
