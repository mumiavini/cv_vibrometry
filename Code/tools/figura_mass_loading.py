"""
Figura do efeito de mass loading (Fundamentação Teórica, Eq. 6), extraída de
``legacy/opa main.ipynb`` com a notação do texto: massa do sensor m_sens e massa
modal efetiva no ponto de montagem m_mod (m_s e m_ef ficam para a mola, Seção 3.2.2).

Gera Book/Images/fig_mass_loading.png. Executar a partir de Code/:
    python -m tools.figura_mass_loading
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "Book" / "Images" / "fig_mass_loading.png"

plt.rcParams.update({
    "font.family": "serif", "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "legend.fontsize": 10, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 120,
    "savefig.dpi": 300, "savefig.bbox": "tight",
})


def plot_mass_loading():
    """
    Ilustra a Equação 6 do texto:
        w'_n = w_n * sqrt( m_mod / (m_mod + m_sens) )
    Painel esquerdo: deslocamento percentual da frequência natural medida
    em função da razão m_sens/m_mod, para diferentes massas modais efetivas
    (estruturas leves vs pesadas).
    Painel direito: comparação de FRFs antes e depois da fixação do
    acelerômetro em uma estrutura leve, mostrando o pico se deslocando
    para baixo (medição "contaminada" pelo próprio sensor).
    """
    # ---------------- Painel 1: shift percentual ----------------
    razao = np.linspace(0, 1.0, 400)             # m_sens / m_mod
    shift_pct = (1 - np.sqrt(1 / (1 + razao))) * 100   # %

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))

    ax1.plot(razao, shift_pct, color="#1f77b4", lw=2.2)
    ax1.fill_between(razao, 0, shift_pct, color="#1f77b4", alpha=0.10)

    # Pontos representativos de cenários práticos
    cenarios = [
        (0.02, "Estrutura robusta\n($m_{sens} \\ll m_{mod}$)",       "#2ca02c"),
        (0.20, "Componente leve\n($m_{sens} = 0{,}2\\,m_{mod}$)",     "#ff7f0e"),
        (0.50, "Pá de rotor / painel fino\n($m_{sens} = 0{,}5\\,m_{mod}$)", "#d62728"),
    ]
    for r, rotulo, cor in cenarios:
        s = (1 - np.sqrt(1 / (1 + r))) * 100
        ax1.scatter(r, s, color=cor, s=70, zorder=5, edgecolor="k")
        ax1.annotate(rotulo, xy=(r, s), xytext=(r + 0.04, s + 1.5),
                     fontsize=8.5, color=cor,
                     arrowprops=dict(arrowstyle="-", color=cor, lw=0.8, alpha=0.6))

    ax1.set_xlabel("Razão de massas $m_{sens} \\, / \\, m_{mod}$")
    ax1.set_ylabel("Erro relativo em $f_n$  $(1 - f_n'/f_n) \\cdot 100\\%$")
    ax1.set_title("Efeito de $mass\\ loading$ na frequência natural medida")
    ax1.set_xlim(0, 1.0)
    ax1.set_ylim(0, 22)

    # ---------------- Painel 2: FRFs antes/depois ----------------
    # Estrutura leve hipotética
    m_mod = 0.05                 # kg (componente leve, ex.: pá fina)
    k    = 4000.0                # N/m
    zeta = 0.06                  # amortecimento estrutural típico

    # Acelerômetros de diferentes tamanhos (incluindo cabeamento)
    sensores = [
        ("Sem sensor",                          0.000, "#1f77b4", "-"),
        ("Acel. miniatura",              0.001, "#2ca02c", "--"),
        ("Acel. industrial",            0.010, "#ff7f0e", "-."),
        ("Acel. pesado + cabo",         0.025, "#d62728", ":"),
    ]

    f = np.linspace(20, 60, 2000)
    w = 2 * np.pi * f

    for rotulo, ms, cor, est in sensores:
        m_total = m_mod + ms
        wn = np.sqrt(k / m_total)
        fn = wn / (2 * np.pi)
        r = w / wn
        H = 1.0 / np.sqrt((1 - r**2)**2 + (2 * zeta * r)**2) / k
        ax2.plot(f, H * 1e3, color=cor, ls=est, lw=1.8,
                 label=f"{rotulo}  $\\to f_n' = {fn:.2f}$ Hz")
        ax2.axvline(fn, color=cor, lw=0.6, alpha=0.35)

    ax2.set_xlabel("Frequência [Hz]")
    ax2.set_ylabel("Receptância $|X/F|$ [mm/N]")
    ax2.set_title("FRF contaminada pela massa do acelerômetro\n"
                  "(estrutura leve, $m_{mod} = 50$ g)")
    ax2.legend(loc="upper left", fontsize=7)
    ax2.set_xlim(20, 60)
    ax2.set_ylim(0, 2.6)

    fig.suptitle("Efeito de $mass\\ loading$: como o próprio sensor altera a grandeza medida",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT)
    plt.close(fig)


if __name__ == "__main__":
    plot_mass_loading()
    print(OUT)
