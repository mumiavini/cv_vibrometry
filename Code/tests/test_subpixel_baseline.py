"""Sub-pixel stage alternatives (phase, parabolic NCC, integer NCC) on a
translated textured pattern with known sub-pixel shifts."""

import numpy as np
import pytest

from vibrometry.baseline import noise_floor, signal_metrics
from vibrometry.gabor import GaborBank
from vibrometry.roi import ROI
from vibrometry.tracking import track_roi


def _frames(shifts, size=160, seed=1):
    """Smooth random texture translated by ``shifts`` (sub-pixel, y only) via
    Fourier shift."""
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(size, size))
    k = np.fft.fftfreq(size)
    g = np.exp(-(k[:, None] ** 2 + k[None, :] ** 2) / (2 * 0.06 ** 2))
    tex = np.real(np.fft.ifft2(np.fft.fft2(base) * g))
    tex = (tex - tex.min()) / (tex.max() - tex.min())
    F = np.fft.fft2(tex)
    out = []
    for dy in shifts:
        ph = np.exp(-2j * np.pi * k[:, None] * dy)
        out.append(np.clip(np.real(np.fft.ifft2(F * ph)) * 220 + 15, 0, 255).astype(np.uint8))
    return np.stack(out)


SHIFTS = np.array([0.0, 0.3, 1.7, -2.45, 3.6, 0.5, -0.8])


@pytest.mark.parametrize("method, tol", [("phase", 0.1), ("parabolic", 0.2), ("none", 0.5)])
def test_subpixel_methods_recover_known_shifts(method, tol):
    frames = _frames(SHIFTS)
    res = track_roi(frames, ROI("r", 50, 50, 50, 50), search_margin=10, subpixel=method)
    err = np.abs(res.y - SHIFTS)
    assert err.max() <= tol + 1e-9
    if method == "none":
        assert np.allclose(res.y, np.round(res.y))      # integer positions only


def _rms(method, bank=None, seed=1):
    r = track_roi(_frames(SHIFTS, seed=seed), ROI("r", 50, 50, 50, 50), bank=bank,
                  search_margin=10, subpixel=method)
    return float(np.sqrt(np.mean((r.y - SHIFTS) ** 2)))


def test_sub_pixel_stages_beat_integer_ncc():
    # On this smooth synthetic texture the parabolic NCC is the most precise;
    # the point here is only that both sub-pixel stages beat integer NCC.
    none = _rms("none")
    assert _rms("phase") < none / 5
    assert _rms("parabolic") < none / 5


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_local_frequency_reduces_the_phase_gain_bias(seed):
    centre = _rms("phase", GaborBank(), seed)
    local = _rms("phase", GaborBank(local_frequency=True), seed)
    assert local < 0.6 * centre


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError):
        track_roi(_frames([0, 1]), ROI("r", 50, 50, 50, 50), subpixel="xyz")


def test_signal_metrics_on_known_decay():
    fs, f, sigma = 240.0, 7.6, 0.35
    t = np.arange(0, 8, 1 / fs)
    rng = np.random.default_rng(0)
    x = 5 * np.exp(-sigma * t) * np.cos(2 * np.pi * f * t) + rng.normal(0, 0.01, t.size)
    m = signal_metrics(t, x, fs)
    assert m.f_n == pytest.approx(f, abs=0.01)
    assert m.sigma == pytest.approx(sigma, rel=0.08)
    assert m.snr_db > 40
    nf = noise_floor(x, fs, f)
    assert nf is not None and nf < 0.01
