"""
B2 / E2 — incerteza da frequência medida, do modelo e do erro entre eles.

1. Frequência de cada ROI: tipo A pelos segmentos do registro (e resolução 1/T);
2. Modelo: propagação linear (e Monte Carlo) das incertezas dos parâmetros do
   corpo de prova; usa ``specimen.uncertainties`` da sessão ou, se vazio, um
   conjunto de HIPÓTESE (tolerâncias típicas) até as medições do laboratório;
3. Escala: incerteza do fator mm/px pela calibração;
4. Erro vídeo × modelo com incerteza.

Grava JSON e tabela em ``<sessão>_resultados/incerteza/``.
Uso (a partir de Code/):  python -m tools.incerteza sessions/k1_cm_acc.vibro.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vibrometry.session import SESSION_SUFFIX, Session
from vibrometry.uncertainty import model_uncertainty, relative_error, scale_uncertainty
from vibrometry.workflow import process_session

# HIPÓTESE (substituir pelos valores medidos): incertezas-padrão por parâmetro
HYPOTHESIS = {
    "E_gpa": 2.0,                 # 69 ± 2 GPa (liga, sem ensaio)
    "rho": 27.0,                  # ± 1 %
    "L_mm": 2.0,
    "b_mm": 0.05,
    "t_mm": 0.05,
    "springs[0].k_n_m": 150.0,    # ± 10 % (tolerância típica de catálogo)
    "springs[0].x_mm": 2.0,
    "masses[0].x_mm": 2.0,        # acelerômetro
    "masses[0].mass_g": 0.5,
    "masses[1].mass_g": 5.0,      # ferragem / massa efetiva no ponto da mola
    "masses[1].x_mm": 2.0,
}


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    path = Path(argv[0])
    s = Session.load(path)
    res = process_session(s)
    if res.error:
        raise SystemExit(res.error)

    unc = dict(s.specimen.uncertainties) or {
        k: v for k, v in HYPOTHESIS.items()
        if k.split("[")[0] in ("E_gpa", "rho", "L_mm", "b_mm", "t_mm")
        or _exists(s.specimen, k)}
    source = "sessão" if s.specimen.uncertainties else "hipótese (tolerâncias típicas)"
    mu = model_uncertainty(s.specimen, unc, n_mc=300, seed=0)

    cal = s.video.calibration or {}
    scale = None
    if cal.get("length_px"):
        # ±1 mm no comprimento de referência; ±1 px em cada extremidade clicada
        sv, su = scale_uncertainty(cal["length_mm"], 1.0, cal["length_px"], 2 ** 0.5)
        scale = {"s_mm_px": sv, "u_mm_px": su, "u_rel_pct": 100 * su / sv,
                 "hipotese": "±1 mm no comprimento, ±1 px por extremidade"}

    rois = {}
    for name, m in res.analysis.modal.items():
        fu = m.f_uncertainty
        if fu is None:
            continue
        eps, u_eps = relative_error(fu.f, fu.u, mu.f, mu.u)
        rois[name] = {**fu.to_dict(), "erro_vs_modelo_pct": eps, "u_erro_pct": u_eps}

    out = path.parent / f"{path.name.removesuffix(SESSION_SUFFIX)}_resultados" / "incerteza"
    out.mkdir(parents=True, exist_ok=True)
    (out / "incerteza.json").write_text(json.dumps({
        "sessao": s.name, "fonte_incertezas_modelo": source, "incertezas_entrada": unc,
        "modelo": mu.to_dict(), "escala": scale, "frequencia_por_roi": rois},
        indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [f"Modelo ({s.specimen.model_label()}): f = {mu.f:.3f} ± {mu.u:.3f} Hz "
             f"({100 * mu.u / mu.f:.1f} %, k = 1); Monte Carlo: {mu.mc_mean:.3f} ± {mu.mc_std:.3f} Hz",
             f"Incertezas de entrada: {source}", "",
             "| Parâmetro | valor | u | ∂f/∂p (Hz/un.) | u_f (Hz) | parcela (%) |", "|---|---|---|---|---|---|"]
    for k, c in sorted(mu.contributions.items(), key=lambda kv: -kv[1]["parcela_pct"]):
        lines.append(f"| {k} | {c['valor']:g} | {c['u']:g} | {c['sensibilidade_hz_por_unidade']:.4g} | "
                     f"{c['u_f_hz']:.4f} | {c['parcela_pct']:.1f} |")
    lines += ["", "| ROI | f (Hz) | u_f tipo A (Hz) | 1/T (Hz) | segmentos (Hz) | erro × modelo (%) |",
              "|---|---|---|---|---|---|"]
    for n, r in rois.items():
        segs = ", ".join(f"{x:.3f}" for x in r["segmentos_hz"])
        lines.append(f"| {n} | {r['f_hz']:.4f} | {r['u_hz']:.4f} | {r['resolucao_hz']:.3f} | {segs} | "
                     f"{r['erro_vs_modelo_pct']:+.2f} ± {r['u_erro_pct']:.2f} |")
    if scale:
        lines += ["", f"Escala: {scale['s_mm_px']:.4f} ± {scale['u_mm_px']:.4f} mm/px "
                      f"({scale['u_rel_pct']:.2f} %; {scale['hipotese']})"]
    (out / "incerteza.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"resultados em {out}")
    return 0


def _exists(spec, path: str) -> bool:
    import re
    m = re.match(r"^(\w+)\[(\d+)\]\.(\w+)$", path)
    if not m:
        return hasattr(spec, path)
    attr, idx, key = m.groups()
    lst = getattr(spec, attr, [])
    return int(idx) < len(lst) and key in lst[int(idx)]


if __name__ == "__main__":
    raise SystemExit(main())
