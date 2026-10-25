"""
Signal analysis for the validation campaigns (planejamento, sections 8.9 and
8.10): dominant frequency, least-squares sine fit (amplitude, phase,
offset), and the comparison metrics between the optical measurement and the
accelerometer reference.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy import optimize
from scipy import signal as ss

from .spectral import amplitude_spectrum


def wrap_deg(angle: float) -> float:
    """Wrap an angle to (-180, 180] degrees."""
    return float(-((-angle + 180.0) % 360.0 - 180.0))


def dominant_frequency(
    x: np.ndarray,
    fs: float,
    f_min: float = 0.3,
    f_max: float | None = None,
) -> float | None:
    """Frequency of the largest peak of the Hann-windowed, zero-padded
    amplitude spectrum, refined by parabolic interpolation."""
    x = np.asarray(x, dtype=float)
    if x.size < 8 or not np.isfinite(x).all() or x.std() == 0:
        return None
    freqs, amp = amplitude_spectrum(x, fs)
    valid = freqs >= f_min
    if f_max is not None:
        valid &= freqs <= f_max
    idx = np.flatnonzero(valid)
    if idx.size < 3:
        return None
    i = idx[np.argmax(amp[idx])]
    if 0 < i < freqs.size - 1:
        a, b, c = amp[i - 1], amp[i], amp[i + 1]
        den = a - 2 * b + c
        delta = 0.5 * (a - c) / den if den != 0 else 0.0
        return float(freqs[i] + delta * (freqs[1] - freqs[0]))
    return float(freqs[i])


@dataclass
class SineFit:
    """x(t) ≈ amplitude * cos(2 pi f t + phase) + offset."""

    frequency: float
    amplitude: float
    phase_deg: float
    offset: float
    r2: float
    rms_residual: float


def _linear_fit(t: np.ndarray, x: np.ndarray, f: float):
    w = 2.0 * np.pi * f
    m = np.column_stack([np.cos(w * t), np.sin(w * t), np.ones_like(t)])
    coef, *_ = np.linalg.lstsq(m, x, rcond=None)
    resid = x - m @ coef
    return coef, resid


def fit_sine(
    t: np.ndarray,
    x: np.ndarray,
    f0: float,
    refine: bool = True,
    rel_span: float = 0.03,
) -> SineFit:
    """Least-squares sine fit. With ``refine`` the frequency is optimised in
    f0 * (1 ± rel_span); otherwise it is held at ``f0`` (e.g. the known
    excitation frequency, or a common frequency for a phase comparison)."""
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    f = f0
    if refine and f0 > 0:
        res = optimize.minimize_scalar(
            lambda ff: float(np.sum(_linear_fit(t, x, ff)[1] ** 2)),
            bounds=(f0 * (1 - rel_span), f0 * (1 + rel_span)),
            method="bounded",
            options={"xatol": 1e-7 * f0},
        )
        f = float(res.x)
    (a, b, c), resid = _linear_fit(t, x, f)
    ss_tot = float(np.sum((x - x.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid ** 2)) / ss_tot if ss_tot > 0 else 0.0
    return SineFit(
        frequency=float(f),
        amplitude=float(np.hypot(a, b)),
        phase_deg=float(np.degrees(np.arctan2(-b, a))),
        offset=float(c),
        r2=r2,
        rms_residual=float(np.sqrt(np.mean(resid ** 2))),
    )


@dataclass
class SignalSummary:
    rms: float
    peak_to_peak: float
    std: float
    f_dominant: float | None
    fit: SineFit | None


def summarize(t: np.ndarray, x: np.ndarray, fs: float,
              f_min: float = 0.3) -> SignalSummary:
    f = dominant_frequency(x, fs, f_min=f_min)
    fit = fit_sine(t, x, f) if f else None
    xc = x - x.mean()
    return SignalSummary(
        rms=float(np.sqrt(np.mean(xc ** 2))),
        peak_to_peak=float(x.max() - x.min()),
        std=float(x.std()),
        f_dominant=fit.frequency if fit else f,
        fit=fit,
    )


@dataclass
class Comparison:
    """Optical (test) vs accelerometer (reference) on a common time base."""

    f_ref: float | None
    f_test: float | None
    freq_error_percent: float | None
    f_common: float | None            # frequency both fits are held at
    amp_ref: float | None
    amp_test: float | None
    amp_error_percent: float | None
    phase_ref_deg: float | None
    phase_test_deg: float | None
    phase_diff_deg: float | None      # test - ref, wrapped
    r2_ref: float | None
    r2_test: float | None
    rms_ref: float
    rms_test: float
    rms_error_percent: float | None
    pearson_r: float
    rmse: float
    nrmse_percent: float              # RMSE / RMS(ref)
    gain: float                       # slope of test vs ref regression
    coherence: float | None           # magnitude-squared coherence at f_common

    def to_dict(self) -> dict:
        return asdict(self)


def compare_signals(
    t: np.ndarray,
    ref: np.ndarray,
    test: np.ndarray,
    fs: float,
    f_common: float | None = None,
    f_min: float = 0.3,
) -> Comparison:
    """Comparison metrics of the planejamento (section 8.10).

    Frequencies come from independent sine fits of each signal. Amplitude and
    phase come from fits held at the common frequency ``f_common`` (the
    excitation frequency if known, else the reference's), so the phase
    difference is meaningful.
    """
    t = np.asarray(t, dtype=float)
    ref = np.asarray(ref, dtype=float)
    test = np.asarray(test, dtype=float)

    f_ref = dominant_frequency(ref, fs, f_min=f_min)
    f_test = dominant_frequency(test, fs, f_min=f_min)
    if f_ref:
        f_ref = fit_sine(t, ref, f_ref).frequency
    if f_test:
        f_test = fit_sine(t, test, f_test).frequency
    freq_err = (100.0 * (f_test - f_ref) / f_ref
                if (f_ref and f_test) else None)

    fc = f_common or f_ref
    fit_r = fit_sine(t, ref, fc, refine=False) if fc else None
    fit_t = fit_sine(t, test, fc, refine=False) if fc else None

    rc, tc = ref - ref.mean(), test - test.mean()
    rms_r = float(np.sqrt(np.mean(rc ** 2)))
    rms_t = float(np.sqrt(np.mean(tc ** 2)))
    rmse = float(np.sqrt(np.mean((tc - rc) ** 2)))
    r = float(np.corrcoef(rc, tc)[0, 1]) if rms_r > 0 and rms_t > 0 else 0.0
    gain = float(np.dot(rc, tc) / np.dot(rc, rc)) if rms_r > 0 else 0.0

    coh = None
    if fc and ref.size >= 64:
        nper = min(ref.size, max(64, int(4 * fs / fc)))
        nper = min(nper, ref.size // 2) if ref.size >= 256 else ref.size
        fq, cxy = ss.coherence(rc, tc, fs=fs, nperseg=nper)
        coh = float(np.interp(fc, fq, cxy))

    return Comparison(
        f_ref=f_ref, f_test=f_test, freq_error_percent=freq_err,
        f_common=fc,
        amp_ref=fit_r.amplitude if fit_r else None,
        amp_test=fit_t.amplitude if fit_t else None,
        amp_error_percent=(100.0 * (fit_t.amplitude - fit_r.amplitude)
                           / fit_r.amplitude
                           if (fit_r and fit_t and fit_r.amplitude > 0) else None),
        phase_ref_deg=fit_r.phase_deg if fit_r else None,
        phase_test_deg=fit_t.phase_deg if fit_t else None,
        phase_diff_deg=(wrap_deg(fit_t.phase_deg - fit_r.phase_deg)
                        if (fit_r and fit_t) else None),
        r2_ref=fit_r.r2 if fit_r else None,
        r2_test=fit_t.r2 if fit_t else None,
        rms_ref=rms_r, rms_test=rms_t,
        rms_error_percent=100.0 * (rms_t - rms_r) / rms_r if rms_r > 0 else None,
        pearson_r=r, rmse=rmse,
        nrmse_percent=100.0 * rmse / rms_r if rms_r > 0 else float("nan"),
        gain=gain, coherence=coh,
    )


def coherence_and_frf(
    ref: np.ndarray,
    test: np.ndarray,
    fs: float,
    seg_seconds: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Welch estimates: (freqs, coherence, |H1|) with H1 = P_rt / P_rr."""
    nper = int(min(ref.size, max(64, seg_seconds * fs)))
    if ref.size >= 4 * 64:
        nper = min(nper, ref.size // 2)
    f, coh = ss.coherence(ref, test, fs=fs, nperseg=nper)
    _, p_rt = ss.csd(ref, test, fs=fs, nperseg=nper)
    _, p_rr = ss.welch(ref, fs=fs, nperseg=nper)
    h1 = np.abs(p_rt) / np.maximum(p_rr, 1e-30)
    return f, coh, h1


def coefficient_of_variation(values) -> float | None:
    """CV [%] of repeated measurements (sample std / mean)."""
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)],
                   dtype=float)
    if v.size < 2 or v.mean() == 0:
        return None
    return float(100.0 * v.std(ddof=1) / abs(v.mean()))
