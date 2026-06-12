"""Figure generation for the vibrometry pipeline reports."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from .spectral import LogDecrementResult, SpectralPeak
from .tracking import TrackResult


def plot_tracking_overview(
    frame: np.ndarray,
    results: dict[str, TrackResult],
) -> plt.Figure:
    """Reference frame with ROI boxes and tip trajectories overlaid."""
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.imshow(frame, cmap="gray")
    colors = plt.cm.tab10.colors
    for i, (name, res) in enumerate(results.items()):
        c = colors[i % len(colors)]
        r = res.roi
        ax.add_patch(plt.Rectangle((r.x, r.y), r.w, r.h, fill=False,
                                   edgecolor=c, linewidth=1.5))
        cx, cy = r.center
        ax.plot(cx + res.x, cy + res.y, color=c, linewidth=0.7,
                label=name + (" (ref)" if r.is_reference else ""))
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("ROIs and tracked trajectories on the reference frame")
    ax.set_axis_off()
    fig.tight_layout()
    return fig


def plot_time_series(
    times: np.ndarray,
    signals: dict[str, np.ndarray],
    unit: str = "px",
    title: str = "Compensated displacement",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 4))
    for name, sig in signals.items():
        ax.plot(times, sig, linewidth=0.9, label=name)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(f"Displacement [{unit}]")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_spectrum(
    freqs: np.ndarray,
    amp: np.ndarray,
    peaks: list[SpectralPeak],
    f_analytical: float | None = None,
    unit: str = "px",
    title: str = "Amplitude spectrum (Hann window)",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(freqs, amp, linewidth=1.0)
    for i, p in enumerate(peaks):
        ax.plot(p.frequency, p.amplitude, "rv", markersize=6)
        ax.annotate(f"{p.frequency:.2f} Hz", (p.frequency, p.amplitude),
                    textcoords="offset points", xytext=(6, 4), fontsize=8)
    if f_analytical is not None:
        ax.axvline(f_analytical, color="g", linestyle="--", linewidth=1.0,
                   label=f"analytical $f_{{n,1}}$ = {f_analytical:.2f} Hz")
        ax.legend(fontsize=8)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel(f"Amplitude [{unit}]")
    ax.set_title(title)
    ax.set_xlim(left=0)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def plot_decay_fit(
    times: np.ndarray,
    signal: np.ndarray,
    result: LogDecrementResult,
    unit: str = "px",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(times, signal, linewidth=0.9, label="signal")
    ax.plot(result.peak_times, result.peak_amplitudes, "ro", markersize=4,
            label="fitted peaks")
    a0, lam = result.envelope
    t0 = result.peak_times[0]
    t_env = np.linspace(t0, times[-1], 200)
    env = a0 * np.exp(-lam * (t_env - t0))
    ax.plot(t_env, env, "k--", linewidth=1.0,
            label=rf"envelope $\zeta$ = {result.zeta:.4f}")
    ax.plot(t_env, -env, "k--", linewidth=1.0)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(f"Displacement [{unit}]")
    ax.set_title("Free decay and logarithmic-decrement fit")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_spectrogram(
    times: np.ndarray,
    freqs: np.ndarray,
    magnitude: np.ndarray,
    unit: str = "px",
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(9, 4))
    floor = max(magnitude.max() * 1e-4, 1e-12)
    mesh = ax.pcolormesh(
        times, freqs, 20 * np.log10(np.maximum(magnitude, floor)),
        shading="auto", cmap="magma",
    )
    fig.colorbar(mesh, ax=ax, label=f"Amplitude [dB re 1 {unit}]")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Frequency [Hz]")
    ax.set_title("STFT spectrogram")
    fig.tight_layout()
    return fig
