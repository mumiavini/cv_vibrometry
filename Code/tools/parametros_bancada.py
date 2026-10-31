"""
Parâmetros medidos da bancada (roteiro de laboratório, seções 1 e 2) e a
previsão do modelo com eles.

Lê ``data/bancada/{massas,rigidez_molas,geometria}.csv``, ajusta k de cada mola
(F × alongamento, mínimos quadrados), monta o modelo de elementos finitos da
barra articulada (mola com ⅓ da massa + ferragens, acelerômetro) e grava em
``data/bancada/resultados/``:

* ``parametros.json`` / ``parametros.md`` — k ajustado, massas, f₁ e f₂
  previstos (elementos finitos e 1 GDL rígido), forma modal, efeito do
  acelerômetro, orçamento de incerteza do f₁ previsto e o k / a massa que
  reproduziriam as frequências medidas;
* ``fig_rigidez_molas.{png,pdf}`` — ensaio estático das duas molas.

Uso (a partir de Code/):  python -m tools.parametros_bancada
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from scipy.optimize import brentq  # noqa: E402

from vibrometry.session import SPRING_EFFECTIVE_MASS_FACTOR, SpecimenCfg  # noqa: E402
from vibrometry.springs import fit_spring_stiffness  # noqa: E402
from vibrometry.uncertainty import model_uncertainty  # noqa: E402

DATA = Path("data/bancada")
OUT = DATA / "resultados"

# As leituras de comprimento da mola foram anotadas como "mm", mas são cm:
# 12,75 mm seria curto demais para uma mola de 161 g, e em mm k₁ ≈ 8,6 kN/m
# daria f₁ ≈ 24 Hz, contra 7,6 Hz medidos (ver README da pasta).
READING_TO_M = 1e-2

CATALOG_K = {"k1": 1500.0, "k2": 2500.0}
# frequências já medidas com a mola k1 (sessão k1_cm_acc, 15/10/2026)
MEASURED_F = {"k1": {"PULSE (cursor)": 7.600, "vídeo (k1_cm_acc)": 7.763}}

# incertezas-padrão das entradas (além de k, que sai do ajuste)
INPUT_U = {
    "E_gpa": 2.0,                 # 69 ± 2 GPa (liga, sem ensaio)
    "rho": 0.005 * 2662.0,        # massa por comprimento: balança ±1 g, trena ±2 mm
    "L_mm": 2.0,                  # trena
    "b_mm": 0.1,                  # seção nominal (polegadas), sem paquímetro
    "t_mm": 0.1,
    "springs[0].x_mm": 2.0,
    "springs[0].mass_g": 1.0,     # resolução da balança não anotada
    "springs[0].hardware_g": 1.0,
    "masses[0].x_mm": 2.0,
    "masses[0].mass_g": 0.5,      # acelerômetro (nominal, não pesado)
}

COLORS = {"k1": "#2a78d6", "k2": "#eb6834"}       # categóricos 1 e 2 (validados)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def read_inputs() -> tuple[dict, pl.DataFrame, dict]:
    masses = {r["peca"]: float(r["massa_g"])
              for r in pl.read_csv(DATA / "massas.csv").iter_rows(named=True)}
    springs = pl.read_csv(DATA / "rigidez_molas.csv")
    geo = {r["grandeza"]: float(r["valor_mm"])
           for r in pl.read_csv(DATA / "geometria.csv").iter_rows(named=True)}
    return masses, springs, geo


def specimen(masses: dict, geo: dict, spring: str, k: float) -> SpecimenCfg:
    b, t, total = geo["barra_largura"], geo["barra_espessura"], geo["barra_comprimento"]
    # densidade efetiva pela massa medida (furos e tolerâncias incluídos)
    rho = masses["barra"] / 1e3 / (total * b * t * 1e-9)
    return SpecimenCfg(
        material="aluminum_6351_t6", E_gpa=69.0, rho=round(rho, 1),
        L_mm=geo["mancal_ponta"], b_mm=b, t_mm=t, support="pinned",
        springs=[{"name": f"mola {spring} (k medido)", "x_mm": geo["mancal_parafuso_mola"],
                  "k_n_m": round(k, 0), "mass_g": masses[f"mola_{spring}"],
                  "hardware_g": masses["parafuso"] + masses["porcas"]}],
        masses=[{"name": "acelerometro B&K 4507", "x_mm": geo["mancal_acelerometro"],
                 "mass_g": masses["acelerometro"]}])


def rigid_frequency(sp: SpecimenCfg) -> float:
    """1 GDL, barra rígida (eq. fn_rigida): f = a/2π · sqrt(k / J_O)."""
    s = sp.springs[0]
    a, k = s["x_mm"] / 1e3, s["k_n_m"]
    m_ef = (s["mass_g"] * SPRING_EFFECTIVE_MASS_FACTOR + s["hardware_g"]) / 1e3
    L = sp.L_mm / 1e3
    m_b = sp.rho * sp.b_mm * sp.t_mm * 1e-6 * L
    J = m_b * L ** 2 / 3 + sum(m["mass_g"] / 1e3 * (m["x_mm"] / 1e3) ** 2
                               for m in sp.masses) + m_ef * a ** 2
    return a / (2 * np.pi) * np.sqrt(k / J)


def solve_for(sp: SpecimenCfg, key: str, f_target: float, lo: float, hi: float) -> float:
    """Valor de springs[0][key] que leva f₁ a ``f_target``."""
    def g(v):
        s = copy.deepcopy(sp)
        s.springs[0][key] = v
        return s.predicted_f1() - f_target
    return float(brentq(g, lo, hi, xtol=1e-3))


def analyse() -> dict:
    masses, table, geo = read_inputs()
    out: dict = {"leitura_para_m": READING_TO_M, "massas_g": masses, "geometria_mm": geo,
                 "molas": {}}
    fits = {}
    for name in ("k1", "k2"):
        rows = table.filter(pl.col("mola") == name).sort("forca_N")
        F = rows["forca_N"].to_numpy()
        x = rows["leitura"].to_numpy() * READING_TO_M
        fit = fit_spring_stiffness(F, x)
        fits[name] = (F, (x - x[0]) * 1e3, fit)
        sp = specimen(masses, geo, name, fit.k)
        fe = sp.fe_model()
        f1, f2 = fe.elastic_frequency(1), fe.elastic_frequency(2)
        shape = np.abs(fe.elastic_mode_shape(np.array([geo["mancal_acelerometro"],
                                                       geo["mancal_parafuso_mola"]]) / 1e3, 1))
        no_acc = copy.deepcopy(sp)
        no_acc.masses = []
        no_spring_mass = copy.deepcopy(sp)
        no_spring_mass.springs[0].update(mass_g=0.0, hardware_g=0.0)
        catalog = copy.deepcopy(no_spring_mass)
        catalog.springs[0]["k_n_m"] = CATALOG_K[name]
        unc = dict(INPUT_U, **{"springs[0].k_n_m": fit.u_k})
        mu = model_uncertainty(sp, unc, n_mc=400, seed=0)
        mm = copy.deepcopy(sp)                     # leitura em mm (descartada): k × 10
        mm.springs[0]["k_n_m"] = fit.k * 10
        d = {
            "ajuste": fit.to_dict(),
            "k_catalogo_n_m": CATALOG_K[name],
            "diferenca_catalogo_pct": 100 * (fit.k - CATALOG_K[name]) / CATALOG_K[name],
            "m_ef_g": sp.springs[0]["mass_g"] * SPRING_EFFECTIVE_MASS_FACTOR
                      + sp.springs[0]["hardware_g"],
            "especime": {"L_mm": sp.L_mm, "rho": sp.rho, "springs": sp.springs,
                         "masses": sp.masses},
            "f1_hz": f1, "f2_hz": f2,
            "f1_rigida_1gdl_hz": rigid_frequency(sp),
            "f1_sem_acelerometro_hz": no_acc.predicted_f1(),
            "efeito_acelerometro_pct": 100 * (f1 - no_acc.predicted_f1()) / no_acc.predicted_f1(),
            "f1_sem_massa_da_mola_hz": no_spring_mass.predicted_f1(),
            "f1_catalogo_sem_massa_da_mola_hz": catalog.predicted_f1(),
            "f1_se_leitura_em_mm_hz": mm.predicted_f1(),
            "razao_forma_modal_xa_sobre_a": float(shape[0] / shape[1]),
            "razao_forma_modal_a_sobre_xa": float(shape[1] / shape[0]),
            "incerteza": mu.to_dict(),
            "medido": {},
        }
        for label, f_meas in MEASURED_F.get(name, {}).items():
            d["medido"][label] = {
                "f_hz": f_meas,
                "erro_modelo_pct": 100 * (f_meas - f1) / f1,
                "erro_em_u_modelo": (f_meas - f1) / mu.u,
                "k_que_reproduz_n_m": solve_for(sp, "k_n_m", f_meas, 300, 5000),
                "ferragens_que_reproduzem_g": solve_for(sp, "hardware_g", f_meas, -200, 2000),
            }
        out["molas"][name] = d
    out["_fits"] = fits
    return out


def figure(fits: dict) -> plt.Figure:
    # dimensionada para a largura da coluna do TCC (≈ 8,5 cm): texto em tamanho real
    plt.rcParams.update({"font.size": 8})
    fig, ax = plt.subplots(figsize=(3.5, 2.6), constrained_layout=True)
    xmax = max(e.max() for _, e, _ in fits.values())
    for name, (F, ext, fit) in fits.items():
        c = COLORS[name]
        xs = np.linspace(0, xmax * 1.05, 50)
        ax.plot(xs, fit.intercept_n + fit.k * xs / 1e3, color=c, lw=1.5, zorder=2)
        ax.plot(ext, F, "o", ms=5, color=c, mec="white", mew=1.0, zorder=3,
                label=f"mola {name[0]}$_{name[1]}$")
        label = f"$k_{name[1]}$ = {fit.k:.0f} ± {fit.u_k:.0f} N/m"
        # rótulo direto: abaixo da reta de k1 (mais longa), à direita do topo da de k2
        if fit.k < 2000:
            x_lab = 0.45 * xmax
            y_lab = fit.intercept_n + fit.k * x_lab / 1e3 - 3.2
            ha = "left"
        else:
            x_lab = ext[-1] + 0.8
            y_lab = F[-1]
            ha = "left"
        ax.text(x_lab, y_lab, label, color=INK, fontsize=7.5, ha=ha, va="center")
    ax.set_xlabel("Alongamento da mola (mm)", color=INK)
    ax.set_ylabel("Força aplicada (N)", color=INK)
    ax.set_xlim(0, xmax * 1.12)
    ax.set_ylim(-1, 22)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, loc="lower right", fontsize=7.5)
    return fig


def markdown(res: dict) -> str:
    def f(x, nd=3):
        return f"{x:.{nd}f}"
    lines = ["# Parâmetros medidos da bancada e previsão do modelo", "",
             "Gerado por `python -m tools.parametros_bancada` a partir de `data/bancada/*.csv`.",
             "Leituras de comprimento da mola interpretadas em **cm** (ver README).", "",
             "| Grandeza | k₁ | k₂ |", "|---|---|---|"]
    m1, m2 = res["molas"]["k1"], res["molas"]["k2"]

    def row(label, key, nd=3, fn=None):
        a = fn(m1) if fn else m1[key]
        b = fn(m2) if fn else m2[key]
        lines.append(f"| {label} | {f(a, nd)} | {f(b, nd)} |")
    lines.append(f"| k de catálogo (N/m) | {m1['k_catalogo_n_m']:.0f} | {m2['k_catalogo_n_m']:.0f} |")
    lines.append(f"| k medido (N/m) | {m1['ajuste']['k']:.0f} ± {m1['ajuste']['u_k']:.0f} "
                 f"({100 * m1['ajuste']['rel_u']:.1f} %) | {m2['ajuste']['k']:.0f} ± "
                 f"{m2['ajuste']['u_k']:.0f} ({100 * m2['ajuste']['rel_u']:.1f} %) |")
    row("diferença ao catálogo (%)", "diferenca_catalogo_pct", 1)
    row("R² do ajuste", None, 4, lambda m: m["ajuste"]["r2"])
    lines.append("| k incremental entre leituras (N/m) | "
                 + ", ".join(f"{v:.0f}" for v in m1["ajuste"]["incremental"]) + " | "
                 + ", ".join(f"{v:.0f}" for v in m2["ajuste"]["incremental"]) + " |")
    row("massa efetiva m_s/3 + m_f (g)", "m_ef_g", 1)
    row("f₁ elementos finitos (Hz)", "f1_hz", 3)
    row("u(f₁) modelo (Hz)", None, 3, lambda m: m["incerteza"]["u_hz"])
    row("f₁ 1 GDL rígido (Hz)", "f1_rigida_1gdl_hz", 3)
    row("f₂ (Hz)", "f2_hz", 1)
    row("φ(x_a)/φ(a)", "razao_forma_modal_xa_sobre_a", 4)
    row("φ(a)/φ(x_a)", "razao_forma_modal_a_sobre_xa", 4)
    row("efeito do acelerômetro em f₁ (%)", "efeito_acelerometro_pct", 3)
    row("f₁ sem massa da mola e ferragens (Hz)", "f1_sem_massa_da_mola_hz", 3)
    row("f₁ com k de catálogo, sem massa da mola (Hz)", "f1_catalogo_sem_massa_da_mola_hz", 3)
    row("f₁ se a leitura fosse em mm (Hz)", "f1_se_leitura_em_mm_hz", 2)
    lines += ["", "## Frequências já medidas × modelo", "",
              "| Mola | Medida | f (Hz) | erro × modelo (%) | em u(modelo) | k que reproduz (N/m) "
              "| ferragens que reproduzem (g) |", "|---|---|---|---|---|---|---|"]
    for name, m in res["molas"].items():
        for label, d in m["medido"].items():
            lines.append(f"| {name} | {label} | {d['f_hz']:.3f} | {d['erro_modelo_pct']:+.2f} | "
                         f"{d['erro_em_u_modelo']:+.2f} | {d['k_que_reproduz_n_m']:.0f} | "
                         f"{d['ferragens_que_reproduzem_g']:.1f} |")
    for name, m in res["molas"].items():
        lines += ["", f"## Orçamento de incerteza do f₁ previsto ({name})", "",
                  f"f₁ = {m['incerteza']['f_hz']:.3f} ± {m['incerteza']['u_hz']:.3f} Hz "
                  f"({m['incerteza']['u_rel_pct']:.1f} %); Monte Carlo: "
                  f"{m['incerteza']['monte_carlo']['media_hz']:.3f} ± "
                  f"{m['incerteza']['monte_carlo']['desvio_hz']:.3f} Hz", "",
                  "| Parâmetro | valor | u | u_f (Hz) | parcela (%) |", "|---|---|---|---|---|"]
        contrib = sorted(m["incerteza"]["contribuicoes"].items(),
                         key=lambda kv: -kv[1]["u_f_hz"])
        for p, c in contrib:
            lines.append(f"| {p} | {c['valor']:g} | {c['u']:g} | {c['u_f_hz']:.4f} | "
                         f"{c['parcela_pct']:.1f} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    res = analyse()
    fits = res.pop("_fits")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "parametros.json").write_text(json.dumps(res, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    md = markdown(res)
    (OUT / "parametros.md").write_text(md, encoding="utf-8")
    fig = figure(fits)
    fig.savefig(OUT / "fig_rigidez_molas.pdf")
    fig.savefig(OUT / "fig_rigidez_molas.png", dpi=200)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
