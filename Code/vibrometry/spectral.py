"""
Module 4 — Spectral analysis and modal parameter extraction
(TCC: "Extração de Parâmetros Modais e Mitigação de Ruído").

Implements, with numpy only:
  * amplitude spectrum via FFT with Hann window (eq:fft);
  * spectral peak identification (natural frequencies);
  * damping ratio by the half-power bandwidth method (eq:zeta_halfpower);
  * damping ratio by the logarithmic decrement of the free-decay envelope
    (eq:resposta_subamortecida discussion);
  * STFT spectrogram for time-varying excitation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def amplitude_spectrum(
    signal: np.ndarray,
    fs: float,
    zero_pad_factor: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    """One-sided amplitude spectrum with Hann window (eq:fft).

    The DC offset is removed before windowing and the amplitude is corrected
    for the window gain so that a pure sinusoid of amplitude A produces a
    peak of height ~A.  Zero padding interpolates the spectrum, improving
    the localisation of peaks and half-power points (it does not add
    physical resolution, which remains 1/duration).

    Returns
    -------
    freqs : frequency axis [Hz].
    amp : amplitude spectrum (same unit as the input signal).
    """
    x = np.asarray(signal, dtype=float)
    x = x - x.mean()
    n = x.size
    window = np.hanning(n)
    n_fft = int(2 ** np.ceil(np.log2(n * zero_pad_factor)))
    spectrum = np.fft.rfft(x * window, n=n_fft)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs)
    amp = 2.0 * np.abs(spectrum) / window.sum()
    return freqs, amp


@dataclass
class SpectralPeak:
    frequency: float   # [Hz]
    amplitude: float   # same unit as the signal


def find_spectral_peaks(
    freqs: np.ndarray,
    amp: np.ndarray,
    f_min: float = 0.3,
    min_rel_height: float = 0.05,
    max_peaks: int = 5,
) -> list[SpectralPeak]:
    """Local maxima of the amplitude spectrum, strongest first.

    Peaks below ``f_min`` (DC leakage region) or below ``min_rel_height``
    times the global maximum are discarded.
    """
    valid = freqs >= f_min
    f, a = freqs[valid], amp[valid]
    if a.size < 3:
        return []

    is_peak = (a[1:-1] > a[:-2]) & (a[1:-1] >= a[2:])
    idx = np.flatnonzero(is_peak) + 1
    idx = idx[a[idx] >= min_rel_height * a.max()]
    idx = idx[np.argsort(a[idx])[::-1]][:max_peaks]
    return [SpectralPeak(float(f[i]), float(a[i])) for i in idx]


def half_power_damping(
    freqs: np.ndarray,
    amp: np.ndarray,
    f_peak: float,
) -> float | None:
    """Damping ratio by the half-power bandwidth method (eq:zeta_halfpower):

        zeta ≈ (f2 - f1) / (2 * fn)

    with f1, f2 the frequencies at which |X| = |X|_peak / sqrt(2), found by
    linear interpolation on each side of the peak.  Returns None when the
    half-power points cannot be bracketed (peak too narrow for the spectral
    resolution, or overlapping modes).
    """
    i_peak = int(np.argmin(np.abs(freqs - f_peak)))
    target = amp[i_peak] / np.sqrt(2.0)

    def cross(indices: np.ndarray) -> float | None:
        """First crossing of `target` walking away from the peak."""
        for j0, j1 in zip(indices[:-1], indices[1:]):
            a0, a1 = amp[j0], amp[j1]
            if (a0 - target) * (a1 - target) <= 0 and a0 != a1:
                t = (target - a0) / (a1 - a0)
                return float(freqs[j0] + t * (freqs[j1] - freqs[j0]))
        return None

    f1 = cross(np.arange(i_peak, -1, -1))
    f2 = cross(np.arange(i_peak, freqs.size))
    if f1 is None or f2 is None or f_peak <= 0:
        return None
    return (f2 - f1) / (2.0 * f_peak)


def _signal_peaks(x: np.ndarray, min_distance: int) -> np.ndarray:
    """Indices of local maxima separated by at least ``min_distance``."""
    is_max = (x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:])
    idx = np.flatnonzero(is_max) + 1
    if idx.size == 0:
        return idx
    keep = [idx[0]]
    for i in idx[1:]:
        if i - keep[-1] >= min_distance:
            keep.append(i)
        elif x[i] > x[keep[-1]]:
            keep[-1] = i
    return np.asarray(keep)


@dataclass
class LogDecrementResult:
    zeta: float                 # damping ratio
    delta: float                # logarithmic decrement per cycle
    f_d: float                  # damped frequency from peak spacing [Hz]
    peak_times: np.ndarray      # instants of the fitted peaks [s]
    peak_amplitudes: np.ndarray  # amplitudes of the fitted peaks
    envelope: tuple[float, float]  # (A0, lambda): A(t) = A0 * exp(-lambda t)


def log_decrement_damping(
    signal: np.ndarray,
    fs: float,
    f_estimate: float,
    min_peaks: int = 3,
) -> LogDecrementResult | None:
    """Damping ratio from the free-decay envelope (logarithmic decrement).

    Successive positive peaks x_i of the decaying response
    x(t) = A exp(-zeta wn t) sin(wd t + phi) satisfy
    ln(x_i) = ln(A) - delta * i, with delta = 2 pi zeta / sqrt(1 - zeta^2).
    A linear fit of ln(x_i) against the cycle index i yields delta and

        zeta = delta / sqrt(4 pi^2 + delta^2).

    Parameters
    ----------
    f_estimate : dominant frequency [Hz] (e.g. from the FFT peak), used to
        set the minimum peak separation.
    """
    x = np.asarray(signal, dtype=float)
    x = x - x.mean()
    if f_estimate <= 0:
        return None

    min_distance = max(1, int(0.6 * fs / f_estimate))
    idx = _signal_peaks(x, min_distance)
    idx = idx[x[idx] > 0]
    if idx.size < min_peaks:
        return None

    # use the decay portion: from the largest peak onwards
    start = int(np.argmax(x[idx]))
    idx = idx[start:]
    # stop at the first non-positive or strongly non-monotonic sample
    amps = x[idx]
    keep = amps > 0.05 * amps[0]
    idx, amps = idx[keep], amps[keep]
    if idx.size < min_peaks:
        return None

    cycles = np.arange(idx.size, dtype=float)
    slope, intercept = np.polyfit(cycles, np.log(amps), 1)
    delta = -slope
    if delta <= 0:
        return None
    zeta = delta / np.sqrt(4.0 * np.pi ** 2 + delta ** 2)

    times = idx / fs
    f_d = float((idx.size - 1) / (times[-1] - times[0])) if idx.size > 1 else f_estimate
    lam = delta * f_d  # zeta * wn ≈ delta * f_d for small zeta
    return LogDecrementResult(
        zeta=float(zeta),
        delta=float(delta),
        f_d=f_d,
        peak_times=times,
        peak_amplitudes=amps,
        envelope=(float(np.exp(intercept)), float(lam)),
    )


def stft_spectrogram(
    signal: np.ndarray,
    fs: float,
    nperseg: int = 128,
    hop: int = 16,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Short-Time Fourier Transform magnitude (Hann window).

    Suitable for runs with time-varying excitation (sweeps, run-ups).

    Returns
    -------
    times : centre instant of each segment [s].
    freqs : frequency axis [Hz].
    magnitude : (n_freqs, n_segments) amplitude.
    """
    x = np.asarray(signal, dtype=float)
    x = x - x.mean()
    nperseg = min(nperseg, x.size)
    window = np.hanning(nperseg)
    starts = np.arange(0, x.size - nperseg + 1, hop)
    if starts.size == 0:
        starts = np.array([0])

    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    mag = np.empty((freqs.size, starts.size))
    for j, s in enumerate(starts):
        seg = x[s: s + nperseg] * window
        mag[:, j] = 2.0 * np.abs(np.fft.rfft(seg)) / window.sum()
    times = (starts + nperseg / 2.0) / fs
    return times, freqs, mag
