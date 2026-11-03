"""
Figura explicativa da estimativa de movimento por fase com filtros de Gabor
(Fundamentação Teórica, Seção 2.4.2).

(a) parte real e imaginária do filtro de Gabor 2D usado no banco (θ = 0, λ = 16 px);
(b) perfil de intensidade de um marcador em dois quadros, deslocado de δ;
(c) amplitude A e fase φ da resposta ao filtro nos dois quadros;
(d) δ estimado por Δφ/ω em cada pixel, com ω a frequência espacial local da
    resposta (gradiente da fase, ≈ ω0), e média ponderada por A.

Gera Book/Images/fig_gabor_fase.png. Executar a partir de Code/:
    python -m tools.figura_gabor
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from vibrometry.gabor import gabor_kernel  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "Book" / "Images" / "fig_gabor_fase.png"
LAMBDA = 16.0           # comprimento de onda do filtro [px]
DELTA = 1.5             # deslocamento imposto [px]


def marker(x: np.ndarray, x0: float) -> np.ndarray:
    """Marcador escuro de borda suave (largura ~12 px) sobre fundo claro."""
    edge = lambda u: 0.5 * (1 + np.tanh(u / 1.5))  # noqa: E731
    return 0.9 - 0.7 * (edge(x - (x0 - 6)) - edge(x - (x0 + 6)))


def main() -> int:
    k2d = gabor_kernel(LAMBDA, 0.0)
    omega0 = 2 * np.pi / LAMBDA
    sigma = 0.56 * LAMBDA                            # mesmo envelope do banco
    u = np.arange(-int(np.ceil(3 * sigma)), int(np.ceil(3 * sigma)) + 1, dtype=float)
    g1d = np.exp(-u ** 2 / (2 * sigma ** 2)) * np.exp(1j * omega0 * u)
    g1d -= g1d.mean()                                # sem resposta a fundo uniforme
    x = np.arange(0, 120, 1.0)
    i0 = marker(x, 60.0)
    i1 = marker(x, 60.0 + DELTA)
    c0 = np.convolve(i0 - i0.mean(), g1d, mode="same")
    c1 = np.convolve(i1 - i1.mean(), g1d, mode="same")
    a0, p0, p1 = np.abs(c0), np.angle(c0), np.angle(c1)
    dphi = np.angle(c1 * np.conj(c0))                # Δφ sem salto de 2π
    w = a0 ** 2
    valid = a0 > 0.2 * a0.max()
    grad = np.angle(c0[2:] * np.conj(c0[:-2])) / 2   # dφ/dx (diferença central)
    omega = abs(np.sum(w[1:-1] * grad * valid[1:-1]) / np.sum(w[1:-1] * valid[1:-1]))
    d_est = np.abs(dphi) / omega                     # deslocamento positivo imposto
    d_mean = float(np.sum(w[valid] * d_est[valid]) / np.sum(w[valid]))

    fig = plt.figure(figsize=(7.0, 5.6))
    gs = fig.add_gridspec(2, 2, hspace=0.45, wspace=0.32)

    ax = fig.add_subplot(gs[0, 0])
    h = k2d.shape[0] // 2
    ext = (-h, h, -h, h)
    ax.imshow(k2d.real, cmap="RdBu_r", extent=ext, origin="lower")
    ax.set_title("(a) Filtro de Gabor, parte real\n" rf"($\theta = 0$, $\lambda$ = {LAMBDA:.0f} px)",
                 fontsize=9)
    ax.set_xlabel("x' (px)")
    ax.set_ylabel("y' (px)")

    ax = fig.add_subplot(gs[0, 1])
    ax.plot(x, i0, color="C0", label="quadro $t_0$")
    ax.plot(x, i1, color="C3", ls="--", label=rf"quadro $t$ ($\delta$ = {DELTA} px)")
    ax.set_xlim(30, 90)
    ax.set_title("(b) Intensidade ao longo de x", fontsize=9)
    ax.set_xlabel("x (px)")
    ax.set_ylabel("I (normalizada)")
    ax.legend(fontsize=7, loc="lower left")

    ax = fig.add_subplot(gs[1, 0])
    ax.fill_between(x, 0, a0 / a0.max() * np.pi, color="0.85", label="amplitude A (escala)")
    ax.plot(x, p0, color="C0", label=r"fase $\varphi$, $t_0$")
    ax.plot(x, p1, color="C3", ls="--", label=r"fase $\varphi$, $t$")
    ax.set_xlim(30, 90)
    ax.set_ylim(-np.pi, np.pi)
    ax.set_yticks([-np.pi, 0, np.pi], [r"$-\pi$", "0", r"$\pi$"])
    ax.set_title("(c) Amplitude e fase da resposta", fontsize=9)
    ax.set_xlabel("x (px)")
    ax.legend(fontsize=6.5, loc="lower left")

    ax = fig.add_subplot(gs[1, 1])
    ax.plot(x[valid], d_est[valid], "o", ms=3, color="C2", label=r"$\Delta\varphi/\omega$ por pixel")
    ax.axhline(DELTA, color="k", lw=0.8, ls=":", label=rf"imposto: {DELTA} px")
    ax.axhline(d_mean, color="C2", lw=1.0, label=f"média ponderada por A: {d_mean:.3f} px")
    ax.set_xlim(30, 90)
    ax.set_ylim(0, 3)
    ax.set_title(r"(d) Deslocamento $\delta = \Delta\varphi/\omega$", fontsize=9)
    ax.set_xlabel("x (px)")
    ax.set_ylabel(r"$\delta$ (px)")
    ax.legend(fontsize=6.5, loc="upper left")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"{OUT}  (δ estimado {d_mean:.4f} px; imposto {DELTA}; ω/ω0 = {omega / omega0:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
