"""Static stiffness fit of the bench springs (vibrometry.springs)."""

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from vibrometry.springs import fit_spring_stiffness

DATA = Path(__file__).resolve().parents[1] / "data" / "bancada" / "rigidez_molas.csv"


def test_exact_line_is_recovered():
    F = np.array([0.0, 2.0, 5.0, 10.0, 20.0])
    L = 0.120 + F / 900.0                       # k = 900 N/m
    fit = fit_spring_stiffness(F, L)
    assert fit.k == pytest.approx(900.0, rel=1e-9)
    assert fit.u_k == pytest.approx(0.0, abs=1e-6)
    assert fit.r2 == pytest.approx(1.0)
    assert fit.intercept_n == pytest.approx(0.0, abs=1e-9)
    assert fit.secant == pytest.approx(900.0)
    assert fit.incremental == pytest.approx([900.0] * 4)


def test_order_and_seating_offset_do_not_bias_the_slope():
    F = np.array([10.0, 0.0, 20.0, 5.0, 2.0])
    L = 0.130 + F / 3000.0
    L[F == 0.0] -= 0.0005                       # hook seats at the first load
    fit = fit_spring_stiffness(F, L)
    assert fit.k == pytest.approx(3000.0, rel=0.10)
    assert fit.u_k > 0 and fit.n == 5


def test_noisy_readings_stay_within_the_standard_error():
    rng = np.random.default_rng(1)
    F = np.repeat([0.0, 2.0, 5.0, 10.0, 20.0], 4)
    L = 0.12 + F / 850.0 + rng.normal(0.0, 0.2e-3, F.size)
    fit = fit_spring_stiffness(F, L)
    assert abs(fit.k - 850.0) < 3 * fit.u_k


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        fit_spring_stiffness([0.0, 1.0], [0.1, 0.2])
    with pytest.raises(ValueError):
        fit_spring_stiffness([0.0, 1.0, 2.0], [0.1, 0.1, 0.1])


def test_bench_measurements():
    """Lab readings (spring length in cm): k1 ~ 857 N/m and k2 ~ 3291 N/m,
    against 1500 and 2500 N/m in the catalog."""
    t = pl.read_csv(DATA)
    k = {}
    for name in ("k1", "k2"):
        r = t.filter(pl.col("mola") == name)
        k[name] = fit_spring_stiffness(r["forca_N"].to_numpy(), r["leitura"].to_numpy() * 1e-2)
    assert k["k1"].k == pytest.approx(857.0, abs=1.0)
    assert k["k1"].u_k == pytest.approx(62.0, abs=1.0)
    assert k["k2"].k == pytest.approx(3291.0, abs=1.0)
    assert k["k2"].u_k == pytest.approx(346.0, abs=1.0)
