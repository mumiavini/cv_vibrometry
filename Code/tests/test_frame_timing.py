"""Dropped frames: the analysis uses the real time of every frame."""

from types import SimpleNamespace

import numpy as np
import pytest

from vibrometry.analysis import fit_sine
from vibrometry.roi import ROI
from vibrometry.streaming import VideoTrack, resample
from vibrometry.tracking import TrackResult

FPS = 240.0


def _track(timestamps, y_px):
    n = len(timestamps)
    zeros = np.zeros((n, 2))
    disp = np.column_stack([np.zeros(n), y_px])
    res = TrackResult(roi=ROI("A", 0, 0, 10, 10), displacement=disp, coarse=zeros,
                      residual=zeros, score=np.ones(n), weight=np.ones(n))
    return VideoTrack(info=None, params=SimpleNamespace(start_frame=0), fps=FPS,
                      fps_source="override", resize_factor=1.0,
                      timestamps=np.asarray(timestamps), tracks={"A": res},
                      reference_frame=np.zeros((4, 4)), quality=None)


def _dropped_clock(n_frames, every=6, container_dt=1 / FPS, seed=0):
    """Frame instants of a 240 fps capture that skips one frame now and then
    (≈ 17 % of intervals doubled, as in the iPhone originals)."""
    rng = np.random.default_rng(seed)
    steps = np.where(rng.random(n_frames - 1) < 1 / every, 2, 1)
    k = np.concatenate([[0], np.cumsum(steps)])
    return k * container_dt


def test_uniform_clip_is_unchanged():
    ts = np.arange(500) / 30.0                  # slow-motion container at 30 fps
    tr = _track(ts, np.sin(np.arange(500)))
    assert not tr.irregular and tr.dropped_frames == 0
    np.testing.assert_allclose(tr.frame_times, np.arange(500) / FPS)
    assert len(tr.times) == 500
    sig, _ = tr.signals(axis="y")
    np.testing.assert_allclose(sig["A"], np.sin(np.arange(500)))


@pytest.mark.parametrize("container_dt", [1 / FPS, 8 / FPS])   # original or 30 fps container
def test_dropped_frames_keep_the_true_frequency(container_dt):
    f_true = 14.67
    ts = _dropped_clock(2400, container_dt=container_dt)
    t_real = ts / container_dt / FPS
    y = 10.0 * np.sin(2 * np.pi * f_true * t_real)
    tr = _track(ts, y)
    assert tr.irregular and tr.dropped_frames > 300
    np.testing.assert_allclose(tr.frame_times, t_real, atol=1e-9)
    sig, _ = tr.signals(axis="y")
    t = tr.times
    assert len(sig["A"]) == len(t) > tr.n_frames
    f = fit_sine(t, sig["A"], 14.5).frequency
    assert f == pytest.approx(f_true, rel=1e-4)
    # the old assumption (k / F) inflates the frequency by the dropped share
    f_naive = fit_sine(np.arange(tr.n_frames) / FPS, y, 16.0, rel_span=0.3).frequency
    assert f_naive > 1.1 * f_true


def test_frame_index_maps_frames_onto_the_grid():
    ts = np.array([0, 1, 3, 4, 6]) / FPS
    tr = _track(ts, np.zeros(5))
    assert [tr.frame_index(k) for k in range(5)] == [0, 1, 3, 4, 6]
    assert len(tr.times) == 7


def test_resample_handles_missing_values():
    t = np.arange(10.0)
    x = t.copy(); x[4] = np.nan
    np.testing.assert_allclose(resample(t, x, np.array([3.5, 4.0, 4.5])), [3.5, 4.0, 4.5])
