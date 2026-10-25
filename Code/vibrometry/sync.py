"""
Synchronisation between the video and the accelerometer (planejamento,
sections 2.2 and 8.7).

Clock model: an instant ``t_v`` on the video time base corresponds to

    t_a = offset + (1 + drift) * t_v

on the accelerometer clock. ``offset`` is found by cross-correlation with
sub-sample (parabolic) interpolation of the correlation peak; ``drift``
from the offsets of the start and end of the record.

Periodic steady-state signals make a waveform correlation ambiguous by whole
periods, so the "impact" mode first aligns the *envelopes* (the sync tap /
onset of vibration, which happens once) and only then refines on the
waveform within half a period.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal as ss


def bandpass(
    x: np.ndarray,
    fs: float,
    f_hp: float | None = None,
    f_lp: float | None = None,
) -> np.ndarray:
    """Zero-phase band-pass (either edge optional) with raised-cosine edges
    (0 below f_hp/2, 1 above f_hp; 1 below f_lp, 0 above 1.25 f_lp), applied
    in the frequency domain to the mirrored record.

    The same filter is applied to the video and the accelerometer signals.
    A Butterworth filtfilt was used first, but its edge transients last
    ~2/f_hp seconds (visible distortion near the ends of the record with a
    1 Hz high-pass); the mirrored FFT filter has none.
    """
    from .accelerometer import _mirror_filter, _taper

    x = np.asarray(x, dtype=float)
    if f_lp is not None and f_lp >= 0.8 * fs / 2.0:
        f_lp = None
    if f_hp is not None and f_hp <= 0:
        f_hp = None
    if f_hp is None and f_lp is None:
        return x - x.mean()
    return _mirror_filter(x - x.mean(), fs, lambda f: _taper(f, f_hp, f_lp))


def resample_at(
    t_src: np.ndarray,
    x_src: np.ndarray,
    t_query: np.ndarray,
    fs_target: float,
) -> np.ndarray:
    """Sample ``x_src(t_src)`` at ``t_query``, low-passing first (anti-alias,
    0.45 fs_target) when the source is faster than the target. NaN outside
    the source span."""
    fs_src = 1.0 / np.median(np.diff(t_src))
    x = np.asarray(x_src, dtype=float)
    if fs_src > 1.05 * fs_target:
        sos = ss.butter(6, 0.45 * fs_target, btype="lowpass", fs=fs_src,
                        output="sos")
        x = ss.sosfiltfilt(sos, x)
    return np.interp(t_query, t_src, x, left=np.nan, right=np.nan)


def accel_time(t_v: np.ndarray, offset: float, drift_ppm: float) -> np.ndarray:
    """Accelerometer-clock instants of the video instants ``t_v``."""
    return offset + (1.0 + drift_ppm * 1e-6) * np.asarray(t_v)


def video_time(t_a: np.ndarray, offset: float, drift_ppm: float) -> np.ndarray:
    """Inverse of ``accel_time``."""
    return (np.asarray(t_a) - offset) / (1.0 + drift_ppm * 1e-6)


# --------------------------------------------------------------------------- #
# cross-correlation
# --------------------------------------------------------------------------- #
def normalized_xcorr(
    a: np.ndarray,
    b: np.ndarray,
    min_overlap: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Correlation coefficient between ``a[n + k]`` and ``b[n]`` over their
    overlap, for every lag ``k`` with at least ``min_overlap`` samples.

    Returns (lags, rho).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    c = ss.correlate(a, b, mode="full", method="fft")
    lags = ss.correlation_lags(a.size, b.size, mode="full")

    ca = np.concatenate([[0.0], np.cumsum(a * a)])
    cb = np.concatenate([[0.0], np.cumsum(b * b)])
    n0 = np.maximum(0, -lags)                       # first index in b
    n1 = np.minimum(b.size, a.size - lags)          # one past last, in b
    overlap = n1 - n0
    ok = overlap >= max(2, min_overlap)
    lags, c, n0, n1, overlap = lags[ok], c[ok], n0[ok], n1[ok], overlap[ok]
    eb = cb[n1] - cb[n0]
    ea = ca[n1 + lags] - ca[n0 + lags]
    rho = c / np.sqrt(np.maximum(ea * eb, 1e-300))
    return lags, rho


def _parabolic(y: np.ndarray, i: int) -> float:
    if 0 < i < y.size - 1:
        a, b, c = y[i - 1], y[i], y[i + 1]
        den = a - 2 * b + c
        if den != 0:
            return float(np.clip(0.5 * (a - c) / den, -0.5, 0.5))
    return 0.0


def envelope(x: np.ndarray, fs: float, smooth_s: float = 0.05) -> np.ndarray:
    """Smoothed RMS envelope."""
    n = max(1, int(round(smooth_s * fs)))
    kernel = np.ones(n) / n
    return np.sqrt(np.convolve(np.asarray(x) ** 2, kernel, mode="same"))


@dataclass
class SyncResult:
    offset: float          # accelerometer time at video t = 0 [s]
    correlation: float     # correlation coefficient at the chosen lag
    inverted: bool         # best match had opposite polarity
    method: str


def estimate_offset(
    v: np.ndarray,
    t_a: np.ndarray,
    q_a: np.ndarray,
    fs: float,
    mode: str = "impact",
    f_dominant: float | None = None,
    max_lag: float | None = None,
    allow_inversion: bool = True,
    around: float | None = None,
) -> SyncResult:
    """Offset between the video signal ``v`` (sampled at ``fs`` from video
    t = 0) and the accelerometer quantity ``q_a(t_a)`` *in the same domain*
    (both already band-passed alike).

    mode : "impact" (envelope, then waveform refinement) or "waveform".
    max_lag : restrict |offset - around| (or |offset|) to this value [s].
    around : centre of the allowed offset range (default: none).
    """
    t0 = t_a[0]
    grid = t0 + np.arange(int((t_a[-1] - t0) * fs) + 1) / fs
    a = resample_at(t_a, q_a, grid, fs)
    a = np.nan_to_num(a - np.nanmean(a))
    v = np.asarray(v, dtype=float) - np.mean(v)
    min_overlap = int(0.2 * min(a.size, v.size))

    def offsets_of(lags):
        return t0 + lags / fs

    def restrict(lags, centre, half):
        off = offsets_of(lags)
        return np.abs(off - centre) <= half

    if mode == "impact":
        ea = envelope(a, fs)
        ev = envelope(v, fs)
        lags, rho = normalized_xcorr(ea - ea.mean(), ev - ev.mean(), min_overlap)
        if max_lag is not None:
            m = restrict(lags, around or 0.0, max_lag)
            lags, rho = lags[m], rho[m]
        if lags.size == 0:
            raise ValueError("Sem sobreposição suficiente entre os sinais.")
        coarse = offsets_of(lags[np.argmax(rho)])
        half = 0.5 / f_dominant if f_dominant else 0.1
        centre, max_lag = coarse, max(half, 1.5 / fs)
    else:
        centre = around or 0.0

    lags, rho = normalized_xcorr(a, v, min_overlap)
    if max_lag is not None:
        m = restrict(lags, centre, max_lag)
        lags, rho = lags[m], rho[m]
    if lags.size == 0:
        raise ValueError("Sem sobreposição suficiente entre os sinais.")
    score = np.abs(rho) if allow_inversion else rho
    i = int(np.argmax(score))
    inverted = bool(rho[i] < 0)
    y = -rho if inverted else rho
    frac = _parabolic(y, i) if (0 < i < y.size - 1
                                and lags[i + 1] - lags[i - 1] == 2) else 0.0
    offset = float(t0 + (lags[i] + frac) / fs)
    return SyncResult(offset=offset, correlation=float(rho[i]),
                      inverted=inverted, method=mode)


@dataclass
class DriftResult:
    offset: float          # offset at video t = 0 [s]
    drift_ppm: float
    offset_start: float
    offset_end: float
    t_start: float         # centres of the two windows (video time) [s]
    t_end: float
    corr_start: float
    corr_end: float


def estimate_drift(
    v: np.ndarray,
    t_a: np.ndarray,
    q_a: np.ndarray,
    fs: float,
    offset: float,
    f_dominant: float | None = None,
    fraction: float = 0.3,
) -> DriftResult:
    """Local offsets at the start and end of the record (first/last
    ``fraction`` of the video), each searched within half a period of
    ``offset``; their slope is the clock drift."""
    n = v.size
    m = max(16, int(fraction * n))
    half = 0.5 / f_dominant if f_dominant else 0.1
    t_v = np.arange(n) / fs
    out = []
    for sl in (slice(0, m), slice(n - m, n)):
        seg_t = t_v[sl]
        # accelerometer span covering this segment (plus search margin)
        lo = offset + seg_t[0] - 2 * half - 1.0
        hi = offset + seg_t[-1] + 2 * half + 1.0
        keep = (t_a >= lo) & (t_a <= hi)
        if keep.sum() < 16:
            raise ValueError("Acelerômetro não cobre o início/fim do vídeo.")
        r = estimate_offset(v[sl], t_a[keep], q_a[keep], fs, mode="waveform",
                            max_lag=max(half, 1.5 / fs),
                            around=offset + seg_t[0], allow_inversion=True)
        # r.offset aligns the segment start (its local t = 0) -> subtract
        out.append((r.offset - seg_t[0], float(seg_t.mean()), r.correlation))
    (o1, t1, c1), (o2, t2, c2) = out
    drift = (o2 - o1) / (t2 - t1) if t2 > t1 else 0.0
    return DriftResult(
        offset=float(o1 - drift * t1),
        drift_ppm=float(drift * 1e6),
        offset_start=float(o1), offset_end=float(o2),
        t_start=t1, t_end=t2, corr_start=c1, corr_end=c2,
    )
