"""
Comparison of the optical measurement with the accelerometer reference
(TCC: "Ensaio comparativo com acelerômetro piezoelétrico").

The accelerometer reference currently available is the *digitized* PULSE
screen of the bench test (``Code/data/acelerometro/``): the time-signal
envelope and the amplitude spectrum, plus the frequency read directly from
the PULSE cursor.  Both the video and the accelerometer see the same
free decay of the first mode,

    x(t) = X exp(-sigma t) sin(w t + phi),   a(t) = -w^2 x(t),

so the optical displacement is converted to an acceleration-equivalent
``w^2 x`` and compared on three quantities:

  * natural frequency (video FFT peak vs accelerometer),
  * decay rate sigma / damping ratio (exponential fit of each envelope),
  * envelope amplitude (checks the mm/pixel calibration and the tracking).

The accelerometer is sampled at only ~25.6 Hz (about 3.4 samples per 7.6 Hz
cycle), so the comparison is made on envelopes and spectra, not on
sample-by-sample waveforms.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .spectral import amplitude_spectrum, find_spectral_peaks


# ---------------------------------------------------------------------- #
# loading                                                                #
# ---------------------------------------------------------------------- #
def _read_columns(path: str | Path) -> dict[str, np.ndarray]:
    data = np.genfromtxt(path, delimiter=",", names=True, dtype=None,
                         encoding="utf-8")
    return {name: data[name] for name in data.dtype.names}


def load_accelerometer_envelope(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Time [s] and half-peak-to-peak envelope [m/s^2] of the accelerometer."""
    cols = _read_columns(path)
    t, env = cols["t_s"].astype(float), cols["half_p2p_ms2"].astype(float)
    ok = np.isfinite(t) & np.isfinite(env)
    return t[ok], env[ok]


def load_accelerometer_spectrum(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Frequency [Hz] and amplitude [m/s^2] of the accelerometer spectrum."""
    cols = _read_columns(path)
    return cols["f_hz"].astype(float), cols["amplitude_ms2"].astype(float)


def load_video_displacement(path: str | Path, column: str
                            ) -> tuple[np.ndarray, np.ndarray]:
    """Time [s] and displacement of one ROI from ``displacement_signals.csv``
    (the file exported by :meth:`VibrometryPipeline.export`)."""
    cols = _read_columns(path)
    if column not in cols:
        raise KeyError(f"column '{column}' not in {path}; "
                       f"available: {sorted(cols)}")
    return cols["time_s"].astype(float), cols[column].astype(float)


# ---------------------------------------------------------------------- #
# envelope and decay fit                                                 #
# ---------------------------------------------------------------------- #
def sliding_envelope(t: np.ndarray, x: np.ndarray, window_s: float = 0.4
                     ) -> np.ndarray:
    """Half peak-to-peak of ``x`` over a centred window of ``window_s``
    (same definition as the digitized accelerometer envelope)."""
    n = max(3, int(round(window_s / np.median(np.diff(t)))) | 1)
    pad = n // 2
    xp = np.pad(x, pad, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(xp, n)
    return 0.5 * (win.max(axis=1) - win.min(axis=1))


@dataclass
class DecayFit:
    sigma: float        # decay rate [1/s]
    amplitude0: float   # fitted amplitude at the envelope peak time
    r2: float
    n_points: int
    t_peak: float       # time of the envelope maximum [s]

    def zeta(self, f_hz: float) -> float:
        """Damping ratio for a free decay at frequency ``f_hz`` (small zeta)."""
        return self.sigma / (2.0 * np.pi * f_hz)


def fit_exponential_decay(
    t: np.ndarray,
    env: np.ndarray,
    window: tuple[float, float] = (0.5, 8.0),
    min_rel: float = 0.02,
    min_abs: float = 0.0,
) -> DecayFit:
    """Fit ``A exp(-sigma (t - t_peak))`` to an envelope.

    The fit runs over ``[t_peak + window[0], t_peak + window[1]]`` and uses
    only points above ``min_rel * peak`` and ``min_abs`` (noise floor).
    """
    i_peak = int(np.nanargmax(env))
    t_peak, a_peak = float(t[i_peak]), float(env[i_peak])
    sel = ((t >= t_peak + window[0]) & (t <= t_peak + window[1])
           & (env > min_rel * a_peak) & (env > min_abs))
    if sel.sum() < 5:
        raise ValueError("too few envelope points in the fit window")
    y = np.log(env[sel])
    slope, intercept = np.polyfit(t[sel] - t_peak, y, 1)
    resid = y - (slope * (t[sel] - t_peak) + intercept)
    r2 = 1.0 - resid.var() / y.var() if y.var() > 0 else 1.0
    return DecayFit(float(-slope), float(np.exp(intercept)), float(r2),
                    int(sel.sum()), t_peak)


# ---------------------------------------------------------------------- #
# comparison                                                             #
# ---------------------------------------------------------------------- #
@dataclass
class ComparisonResult:
    f_video: float              # [Hz] FFT peak of the video displacement
    f_accelerometer: float      # [Hz] PULSE cursor reading
    f_error_percent: float      # |f_video - f_acc| / f_acc * 100
    f_resolution_video: float   # 1 / T of the video record [Hz]
    sigma_video: float          # [1/s]
    sigma_accelerometer: float  # [1/s]
    zeta_video: float
    zeta_accelerometer: float
    amplitude_ratio: float      # video-equivalent / accelerometer, at t_peak + 1 s
    shift_s: float              # time shift applied to the video [s]
    r2_video: float
    r2_accelerometer: float

    def to_dict(self) -> dict:
        return {k: float(v) for k, v in asdict(self).items()}


def compare(
    t_video: np.ndarray,
    x_video: np.ndarray,
    t_acc: np.ndarray,
    env_acc: np.ndarray,
    f_acc: float,
    unit_scale: float = 1e-3,
    window: tuple[float, float] = (0.5, 8.0),
    acc_noise_floor: float = 0.3,
    shift: float | None = None,
) -> tuple[ComparisonResult, dict]:
    """Compare the optical response of the ROI on the accelerometer with
    the accelerometer reference.

    Parameters
    ----------
    x_video : ROI displacement; ``unit_scale`` converts it to metres
        (1e-3 for the mm columns of the pipeline export).
    f_acc : accelerometer natural frequency [Hz] (PULSE cursor reading).
    shift : time shift added to the video so the envelope peaks coincide
        with the accelerometer's; ``None`` aligns the two maxima.

    Returns the :class:`ComparisonResult` and a dict with the aligned
    series for plotting.
    """
    t_video = np.asarray(t_video, float)
    x = np.asarray(x_video, float) * unit_scale
    freqs, amp = amplitude_spectrum(x, 1.0 / np.median(np.diff(t_video)))
    peaks = find_spectral_peaks(freqs, amp)
    if not peaks:
        raise ValueError("no spectral peak in the video displacement")
    f_video = peaks[0].frequency

    a_eq = (2.0 * np.pi * f_video) ** 2 * (x - x.mean())   # [m/s^2]
    env_video = sliding_envelope(t_video, a_eq)

    fit_v = fit_exponential_decay(t_video, env_video, window, min_rel=0.02)
    fit_a = fit_exponential_decay(t_acc, env_acc, window,
                                  min_rel=0.0, min_abs=acc_noise_floor)
    if shift is None:
        shift = fit_a.t_peak - fit_v.t_peak

    def amp_at(fit: DecayFit) -> float:
        return fit.amplitude0 * np.exp(-fit.sigma * 1.0)

    result = ComparisonResult(
        f_video=f_video,
        f_accelerometer=f_acc,
        f_error_percent=abs(f_video - f_acc) / f_acc * 100.0,
        f_resolution_video=1.0 / (t_video[-1] - t_video[0]),
        sigma_video=fit_v.sigma,
        sigma_accelerometer=fit_a.sigma,
        zeta_video=fit_v.zeta(f_video),
        zeta_accelerometer=fit_a.zeta(f_acc),
        amplitude_ratio=amp_at(fit_v) / amp_at(fit_a),
        shift_s=float(shift),
        r2_video=fit_v.r2,
        r2_accelerometer=fit_a.r2,
    )
    series = {
        "t_video": t_video + shift, "env_video": env_video, "a_eq": a_eq,
        "freqs": freqs, "amp": amp, "fit_video": fit_v, "fit_acc": fit_a,
        "t_acc": np.asarray(t_acc, float), "env_acc": np.asarray(env_acc, float),
    }
    return result, series


def plot_overlay(result: ComparisonResult, series: dict,
                 acc_spectrum: tuple[np.ndarray, np.ndarray] | None = None):
    """Envelope overlay (linear and semilog) and normalised spectra."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, log in zip(axes[:2], (False, True)):
        ax.plot(series["t_acc"], series["env_acc"], color="tab:red", lw=1.4,
                label="acelerômetro (digitalizado)")
        ax.plot(series["t_video"], series["env_video"], color="tab:blue",
                lw=1.0, label=r"vídeo ($\omega^2 x$)")
        ax.set_xlabel("tempo [s]")
        ax.set_ylabel("envoltória [m/s²]")
        if log:
            ax.set_yscale("log")
            ax.set_ylim(0.1, None)
            ax.set_title("escala semilog")
        else:
            ax.set_title("sobreposição das envoltórias")
        ax.grid(alpha=0.3)
        ax.legend()

    ax = axes[2]
    f, a = series["freqs"], series["amp"]
    lo, hi = result.f_accelerometer - 1.5, result.f_accelerometer + 1.5
    m = (f >= lo) & (f <= hi)
    ax.plot(f[m], a[m] / a[m].max(), color="tab:blue", label="vídeo")
    if acc_spectrum is not None:
        fa, aa = acc_spectrum
        ma = (fa >= lo) & (fa <= hi)
        ax.plot(fa[ma], aa[ma] / aa[ma].max(), color="tab:red", marker="o",
                ms=3, label="acelerômetro (digitalizado)")
    ax.axvline(result.f_accelerometer, color="k", ls="--", lw=0.8,
               label=f"cursor PULSE {result.f_accelerometer:.3f} Hz")
    ax.set_xlabel("frequência [Hz]")
    ax.set_ylabel("amplitude normalizada")
    ax.set_title(f"vídeo {result.f_video:.3f} Hz "
                 f"(erro {result.f_error_percent:.2f} %)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------- #
# command line                                                           #
# ---------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="vibrometry.reference",
        description="Compare a video-derived ROI signal with the "
                    "accelerometer reference.")
    p.add_argument("video_csv", help="displacement_signals.csv from the pipeline")
    p.add_argument("--column", required=True,
                   help="column of the ROI on the accelerometer, e.g. roi_acc_mm")
    p.add_argument("--acc-envelope", required=True)
    p.add_argument("--acc-spectrum")
    p.add_argument("--f-acc", type=float, default=7.600,
                   help="accelerometer frequency [Hz] (PULSE cursor)")
    p.add_argument("--shift", type=float,
                   help="time shift [s] added to the video (default: align peaks)")
    p.add_argument("--out", default="vibrometry/outputs/reference")
    args = p.parse_args(argv)

    if not args.column.endswith("_mm"):
        raise SystemExit("the ROI column must be calibrated (…_mm): "
                         "run the pipeline with --scale")
    t_v, x_v = load_video_displacement(args.video_csv, args.column)
    t_a, env_a = load_accelerometer_envelope(args.acc_envelope)
    result, series = compare(t_v, x_v, t_a, env_a, args.f_acc, shift=args.shift)
    spectrum = (load_accelerometer_spectrum(args.acc_spectrum)
                if args.acc_spectrum else None)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    import json
    (out / "comparison.json").write_text(json.dumps(result.to_dict(), indent=2))
    fig = plot_overlay(result, series, spectrum)
    fig.savefig(out / "overlay.png", dpi=150)
    r = result
    print(f"f_video = {r.f_video:.3f} Hz  vs  accelerometer {r.f_accelerometer:.3f} Hz "
          f"-> error {r.f_error_percent:.2f} % (video resolution {r.f_resolution_video:.3f} Hz)")
    print(f"zeta: video {r.zeta_video:.4f}  accelerometer {r.zeta_accelerometer:.4f}")
    print(f"amplitude ratio (video / accelerometer) = {r.amplitude_ratio:.3f}")
    print(f"results in {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
