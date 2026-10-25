"""Accelerometer import and conversion to displacement (planejamento 10:
"Acelerômetro sintético: senoide conhecida")."""

import numpy as np
import pytest

from vibrometry.accelerometer import (
    AccelSettings,
    G,
    acceleration_to_displacement,
    build_record,
    displacement_to_acceleration,
    guess_columns,
    guess_unit,
    read_table,
)


def test_read_brazilian_csv_with_metadata(tmp_path):
    p = tmp_path / "acc.csv"
    lines = ["Dewesoft export", "Sample rate;1000", "", "Tempo [s];AI 1 [g];AI 2 [g]"]
    lines += [f"{k / 1000:.3f};{np.sin(k / 10):.5f};0,1".replace(".", ",")
              for k in range(200)]
    p.write_text("\n".join(lines), encoding="latin-1")
    t = read_table(p)
    assert t.delimiter == ";" and t.decimal == ","
    assert t.columns == ["Tempo [s]", "AI 1 [g]", "AI 2 [g]"]
    assert t.data.shape == (200, 3)
    assert t.data[10, 0] == pytest.approx(0.010)
    assert guess_columns(t) == (0, 1)
    assert guess_unit(t.columns[1]) == "g"


def test_read_whitespace_without_header(tmp_path):
    p = tmp_path / "acc.txt"
    p.write_text("\n".join(f"{k * 0.002}  {k * 1.5}" for k in range(50)))
    t = read_table(p)
    assert t.delimiter == "" and t.data.shape == (50, 2)
    assert t.columns == ["Coluna 1", "Coluna 2"]


def test_units_and_inversion(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("t,a\n" + "\n".join(f"{k / 100},{(1 if k % 2 else -1) * 0.5}"
                                     for k in range(100)))
    t = read_table(p)
    rec = build_record(t, AccelSettings(time_column=0, channel=1, unit="g"))
    assert rec.fs == pytest.approx(100.0)
    assert np.abs(rec.a).max() == pytest.approx(0.5 * G)
    inv = build_record(t, AccelSettings(time_column=0, channel=1, unit="g", invert=True))
    assert np.allclose(inv.a, -rec.a)
    mv = build_record(t, AccelSettings(time_column=0, channel=1, unit="mV",
                                       sensitivity_mv_per_g=100.0))
    assert np.abs(mv.a).max() == pytest.approx(0.005 * G)


@pytest.mark.parametrize("method", ["frequency", "time"])
def test_double_integration_of_sine(method):
    fs, f, amp = 1000.0, 8.0, 2e-3          # 2 mm at 8 Hz
    t = np.arange(int(9.37 * fs)) / fs       # ends mid-cycle on purpose
    a = -(2 * np.pi * f) ** 2 * amp * np.sin(2 * np.pi * f * t)
    d = acceleration_to_displacement(a, fs, f_hp=1.0, method=method)
    err = np.abs(d - amp * np.sin(2 * np.pi * f * t)) / amp
    margin = 2.0 if method == "frequency" else 3.0       # s, with f_hp = 1 Hz
    inner = (t > margin) & (t < t[-1] - margin)
    assert err[inner].max() < 0.005          # < 0.5 % away from the edges
    # edge effects: the frequency method stays within a few percent up to
    # 1 s from the end; the time method (filtfilt transients) does not
    tail = (t > t[-1] - 1.0) & (t < t[-1] - 0.5)
    if method == "frequency":
        assert err[tail].max() < 0.03
    else:
        assert err[tail].max() > 0.1


def test_differentiation_is_inverse():
    fs, f = 240.0, 5.0
    t = np.arange(int(6 * fs)) / fs
    x = np.sin(2 * np.pi * f * t)
    a = displacement_to_acceleration(x, fs, f_lp=40.0)
    m = (t > 0.5) & (t < t[-1] - 0.5)
    assert np.allclose(a[m], -(2 * np.pi * f) ** 2 * x[m], rtol=0, atol=0.02 * (2 * np.pi * f) ** 2)
