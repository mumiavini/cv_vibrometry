"""
Figuras do TCC para o ensaio preliminar com a régua engastada
(Seção "Resultados Preliminares").

Lê os resultados exportados por

    python -m vibrometry.run_analysis "videos/video low res.LRF" \
        --resize-width 360 --rois vibrometry/rois_lrf.json \
        --out vibrometry/outputs/regua_lrf --material polystyrene \
        --length 0.30 --width 0.035 --thickness 0.003

e gera as versões em português em Book/Images/fig_regua_*.png.
Executar a partir de Code/:  python figuras_tcc_regua.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.patches import Rectangle

from vibrometry.roi import load_rois
from vibrometry.spectral import (
    amplitude_spectrum,
    log_decrement_damping,
    stft_spectrogram,
)

VIDEO = Path("videos/video low res.LRF")
RESULTS = Path("vibrometry/outputs/regua_lrf")
ROIS = Path("vibrometry/rois_lrf.json")
OUT = Path("../Book/Images")
RESIZE_WIDTH = 360          # mesmo --resize-width da análise
CROP_ROWS = 330             # recorte vertical dos quadros (cartão + referência)
T_BLUR = 11.0               # instante [s] do quadro com borramento

plt.rcParams.update({
    "font.family": "serif",
    "mathtext.fontset": "dejavuserif",
    "font.size": 12,
    "axes.titlesize": 13,
    "legend.fontsize": 10,
})


def read_frame(t: float) -> np.ndarray:
    cap = cv2.VideoCapture(str(VIDEO))
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * cap.get(cv2.CAP_PROP_FPS)))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Could not read frame at t = {t} s")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    size = (RESIZE_WIDTH, round(h * RESIZE_WIDTH / w))
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)


def fig_rois(rois) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.9))
    panels = [(0.0, "(a) Quadro de referência"),
              (T_BLUR, f"(b) Quadro em t = {T_BLUR:.1f} s")]
    for ax, (t, title) in zip(axes, panels):
        ax.imshow(read_frame(t)[:CROP_ROWS], cmap="gray")
        ax.set_title(title)
        ax.axis("off")
    for r in rois:
        color = "tab:orange" if r.is_reference else "tab:blue"
        label = "ROI de referência" if r.is_reference else "ROI de medição"
        axes[0].add_patch(Rectangle((r.x, r.y), r.w, r.h, fill=False,
                                    edgecolor=color, linewidth=2, label=label))
    axes[0].legend(loc="upper left", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    return fig


def fig_deslocamento(t, x, fps, f_n) -> plt.Figure:
    decay = log_decrement_damping(x, fps, f_n)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(t, x, linewidth=0.8, label="Deslocamento medido")
    if decay is not None:
        a0, lam = decay.envelope
        t0 = decay.peak_times[0]
        t_env = np.linspace(t0, t[-1], 300)
        env = a0 * np.exp(-lam * (t_env - t0))
        ax.plot(decay.peak_times, decay.peak_amplitudes, "o", color="tab:red",
                markersize=3.5, label="Picos ajustados")
        ax.plot(t_env, env, "k--", linewidth=1.0,
                label=rf"Envoltória ($\zeta$ = {decay.zeta:.4f})")
        ax.plot(t_env, -env, "k--", linewidth=1.0)
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel("Deslocamento [px]")
    ax.set_title("Deslocamento vertical do marcador na ponta da régua")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig, decay


def fig_espectro(x, fps, f_n, f_anl) -> plt.Figure:
    freqs, amp = amplitude_spectrum(x, fps)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(freqs, amp, linewidth=1.1)
    ax.axvline(f_anl, color="tab:green", linestyle="--", linewidth=1.1,
               label=f"$f_{{n,1}}^{{anl}}$ = {f_anl:.2f} Hz (poliestireno)")
    ax.axvline(fps / 2, color="gray", linestyle=":", linewidth=1.2,
               label=f"Nyquist = {fps / 2:.2f} Hz")
    i = np.argmin(abs(freqs - f_n))
    ax.plot(freqs[i], amp[i], "v", color="tab:red", markersize=7)
    ax.annotate(f"$f_{{n,1}}^{{opt}}$ = {f_n:.2f} Hz", (freqs[i], amp[i]),
                xytext=(-12, 0), textcoords="offset points",
                ha="right", va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"))
    ax.set_xlim(0, fps / 2 + 0.3)
    ax.set_ylim(0, 1.35 * amp.max())
    ax.set_xlabel("Frequência [Hz]")
    ax.set_ylabel("Amplitude [px]")
    ax.set_title("Espectro de amplitude do deslocamento (janela de Hann)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(0.12, 1.0))
    fig.tight_layout()
    return fig


def fig_espectrograma(x, fps) -> plt.Figure:
    st, sf, sm = stft_spectrogram(x, fps)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    floor = max(sm.max() * 1e-4, 1e-12)
    mesh = ax.pcolormesh(st, sf, 20 * np.log10(np.maximum(sm, floor)),
                         shading="auto", cmap="magma")
    fig.colorbar(mesh, ax=ax, label="Amplitude [dB re 1 px]")
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel("Frequência [Hz]")
    ax.set_title("Espectrograma (STFT) do deslocamento")
    fig.tight_layout()
    return fig


def main() -> None:
    modal = json.loads((RESULTS / "modal_results.json").read_text())
    fps = modal["fps"]
    roi = modal["rois"][0]
    f_n = roi["f_n_hz"]
    f_anl = modal["analytical_model"]["f_n1_hz"]

    df = pl.read_csv(RESULTS / "displacement_signals.csv")
    t = df["time_s"].to_numpy()
    x = df[f"{roi['name']}_px"].to_numpy()

    OUT.mkdir(parents=True, exist_ok=True)
    rois = load_rois(ROIS)
    fig_rois(rois).savefig(OUT / "fig_regua_rois.png", dpi=200)
    fig, decay = fig_deslocamento(t, x, fps, f_n)
    fig.savefig(OUT / "fig_regua_deslocamento.png", dpi=200)
    fig_espectro(x, fps, f_n, f_anl).savefig(OUT / "fig_regua_espectro.png",
                                             dpi=200)
    fig_espectrograma(x, fps).savefig(OUT / "fig_regua_espectrograma.png",
                                      dpi=200)

    print(f"f_n,1 opt = {f_n:.3f} Hz | anl = {f_anl:.3f} Hz | "
          f"Nyquist = {fps / 2:.3f} Hz | alias candidate = {fps - f_n:.3f} Hz")
    if decay is not None:
        print(f"log decrement: zeta = {decay.zeta:.4f}, f_d = {decay.f_d:.3f} Hz, "
              f"{decay.peak_times.size} peaks from t = {decay.peak_times[0]:.2f} "
              f"to {decay.peak_times[-1]:.2f} s")
    print(f"pre-excitation std (t < 10 s): {x[t < 10].std():.2f} px | "
          f"max |x| = {abs(x).max():.1f} px")


if __name__ == "__main__":
    main()
