"""
Resumo das tomadas de uma campanha a partir dos ``resultados.json`` exportados.

Por tomada: f do vídeo (ROI comparada com o acelerômetro), f do acelerômetro,
diferença, f do modelo e erro, ζ (decremento logarítmico) do vídeo e do
acelerômetro, quadros perdidos e razão de amplitude acelerômetro/parafuso ×
modelo. Por grupo (sufixo ``_r<n>`` removido): média, desvio e CV.

Grava ``<saida>.md`` e ``<saida>.csv``.
Uso (a partir de Code/):
    python -m tools.resumo_tomadas sessions/resumo_dia2 sessions/20261030_al_L735_k?_r?.vibro.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import polars as pl

from vibrometry.session import SESSION_SUFFIX, roi_key


def take_row(session_path: Path) -> dict:
    stem = session_path.name.removesuffix(SESSION_SUFFIX)
    res = json.loads((session_path.parent / f"{stem}_resultados" / "resultados.json")
                     .read_text(encoding="utf-8"))
    v, cmp = res["video"], res.get("comparacao") or {}
    roi = cmp.get("roi") or next(iter(v["modal"]))
    mv = v["modal"][roi]
    ma = (res.get("acelerometro") or {}).get("modal") or {}
    met = cmp.get("metricas") or {}
    ratio = ratio_pred = None
    for r in (res.get("forma_modal") or {}).get("rois", []):
        if roi_key(r["nome"]) == "acelerometro":
            ratio, ratio_pred = r["razao_medida"], r["razao_prevista"]
    return {
        "tomada": stem, "grupo": re.sub(r"_r\d+$", "", stem),
        "f_video_hz": mv["f_n_hz"], "f_acel_hz": ma.get("f_n_hz"),
        "dif_video_acel_pct": met.get("freq_error_percent"),
        "f_modelo_hz": mv["f_predicted_hz"], "erro_modelo_pct": mv["error_predicted_percent"],
        "zeta_video": mv["zeta_log_decrement"], "zeta_acel": ma.get("zeta_log_decrement"),
        "fase_graus": met.get("phase_diff_deg"), "r": met.get("pearson_r"),
        "A_video_mm": met.get("amp_test"), "A_acel_mm": met.get("amp_ref"),
        "dif_A_pct": met.get("amp_error_percent"), "escala_mm_px": v.get("escala_mm_px"),
        "razao_acel_parafuso": ratio, "razao_modelo": ratio_pred,
        "erro_forma_pct": None if ratio is None else 100 * (ratio - ratio_pred) / ratio_pred,
        "quadros_perdidos": v.get("quadros_perdidos"),
    }


def fmt(x, nd=3):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    out, paths = Path(argv[0]), [Path(a) for a in argv[1:]]
    rows = [take_row(p) for p in sorted(paths)]
    df = pl.DataFrame(rows)
    df.write_csv(out.with_suffix(".csv"))
    lines = ["# Resumo das tomadas", "",
             f"Gerado por `python -m tools.resumo_tomadas` a partir de {len(rows)} `resultados.json`.", "",
             "| Tomada | f vídeo (Hz) | f acel. (Hz) | vídeo × acel. (%) | f modelo (Hz) | vídeo × modelo (%) "
             "| ζ vídeo | ζ acel. | fase (°) | razão acel./parafuso | modelo | erro forma (%) | quadros perdidos |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['tomada']} | {fmt(r['f_video_hz'])} | {fmt(r['f_acel_hz'])} | "
            f"{fmt(r['dif_video_acel_pct'], 2)} | {fmt(r['f_modelo_hz'], 2)} | "
            f"{fmt(r['erro_modelo_pct'], 1)} | {fmt(r['zeta_video'], 4)} | {fmt(r['zeta_acel'], 4)} | "
            f"{fmt(r['fase_graus'], 1)} | {fmt(r['razao_acel_parafuso'])} | {fmt(r['razao_modelo'])} | "
            f"{fmt(r['erro_forma_pct'], 1)} | {r['quadros_perdidos']} |")
    lines += ["", "## Amplitude na janela de comparação (ROI do acelerômetro)", "",
              "| Tomada | escala (mm/px) | A vídeo (mm) | A acel. (mm) | diferença (%) | r |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['tomada']} | {fmt(r['escala_mm_px'], 4)} | {fmt(r['A_video_mm'])} | "
                     f"{fmt(r['A_acel_mm'])} | {fmt(r['dif_A_pct'], 1)} | {fmt(r['r'], 3)} |")
    lines += ["", "## Por grupo (média ± desvio, CV)", "",
              "| Grupo | n | f vídeo (Hz) | CV (%) | f acel. (Hz) | vídeo × acel. (%) | vídeo × modelo (%) "
              "| ζ vídeo | ζ acel. | razão acel./parafuso |", "|---|---|---|---|---|---|---|---|---|---|"]
    for g in dict.fromkeys(r["grupo"] for r in rows):
        sub = [r for r in rows if r["grupo"] == g]

        def ms(key, nd=3, sub=sub):
            x = np.array([r[key] for r in sub if r[key] is not None], dtype=float)
            if not x.size:
                return "—", None
            sd = x.std(ddof=1) if x.size > 1 else 0.0
            return f"{x.mean():.{nd}f} ± {sd:.{nd}f}", (100 * sd / x.mean() if x.mean() else None)
        fv, cv = ms("f_video_hz")
        fa, _ = ms("f_acel_hz")
        f_v = np.mean([r["f_video_hz"] for r in sub])
        f_a = np.mean([r["f_acel_hz"] for r in sub if r["f_acel_hz"]])
        f_m = sub[0]["f_modelo_hz"]
        lines.append(f"| {g} | {len(sub)} | {fv} | {fmt(cv, 2)} | {fa} | {100 * (f_v / f_a - 1):+.2f} | "
                     f"{100 * (f_v / f_m - 1):+.1f} | {ms('zeta_video', 4)[0]} | {ms('zeta_acel', 4)[0]} | "
                     f"{ms('razao_acel_parafuso')[0]} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
