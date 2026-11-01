"""
E5 / C7 — forma modal com várias ROIs ao longo da barra (mesmo vídeo).

Cria ROIs na linha média da barra em posições conhecidas (segmento de
calibração p1 = raiz, p2 = ponta), rastreia com busca grosseira só na vertical
(a borda da barra é uniforme na horizontal: problema de abertura), ajusta
amplitude e fase de cada ponto na frequência natural e compara com a forma
modal do modelo de elementos finitos da sessão (razão ponto a ponto e MAC).
Pontos com rastreamento duvidoso (NCC mínimo < 0,8 ou R² do ajuste < 0,9) são
mostrados mas ficam fora do MAC. A reta pelos pontos confiáveis dá o centro de
rotação efetivo, e o modelo é recalculado com a raiz nesse ponto.

Grava tabela, JSON e figura em ``<sessão>_resultados/forma_modal/``.
Uso (a partir de Code/):  python -m tools.forma_modal_multiponto sessions/k1_cm_acc.vibro.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from vibrometry.analysis import dominant_frequency, fit_sine  # noqa: E402
from vibrometry.modeshape import (  # noqa: E402
    compare_shape, measured_shape, rois_along_beam, rotation_centre,
    shifted_specimen, track_points)
from vibrometry.session import SESSION_SUFFIX, Session, roi_position  # noqa: E402
from vibrometry.video_io import probe_video  # noqa: E402

# posições ao longo da barra a partir da raiz do modelo (eixo do mancal) [mm];
# o ponto p1 da calibração fica em ``calibration["x0_mm"]`` (0 se ausente)
POSITIONS = [65, 115, 215, 265, 365, 415, 465, 515, 565, 615, 655, 695, 725]
BAR_HALF_THICKNESS_PX = 12.5      # calibration segment runs on the lower edge
MIN_NCC, MIN_R2 = 0.8, 0.9


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    path = Path(argv[0])
    s = Session.load(path)
    v = s.video
    cal = v.calibration
    cal_x0 = float(cal.get("x0_mm", 0.0))      # p1 medido a partir da raiz
    bar = rois_along_beam(cal["p1"], cal["p2"], cal["length_mm"],
                          [x - cal_x0 for x in POSITIONS],
                          width_px=30, height_px=41,
                          y_offset_px=-BAR_HALF_THICKNESS_PX, prefix="barra_")
    for r, x in zip(bar, POSITIONS):              # nome pela posição a partir da raiz
        r.name = f"barra_{x:g}"
    meas = [r for r in v.roi_objects() if not r.is_reference]
    ref = next((r for r in v.roi_objects() if r.is_reference), None)
    info = probe_video(v.path, fps_override=v.fps_override)
    pts = track_points(v.path, meas + bar, ref, info.fps,
                       start_frame=int(round(v.start_s * info.fps)),
                       scale=v.scale_mm_per_px,
                       search_axes={r.name: "y" for r in bar})
    t, unit = pts.times, ("mm" if v.scale_mm_per_px else "px")

    pos = {r.name: float(r.name.split("_")[1]) for r in bar}
    known = {n: roi_position(v.roi_positions_mm, n) for n in pts.displacement}
    known = {n: x for n, x in known.items() if x is not None and not n.startswith("barra_")}
    pos.update(known)
    ref_name = max(known, key=known.get)
    xr = pts.displacement[ref_name]
    f = fit_sine(t, xr - xr.mean(), dominant_frequency(xr, info.fps)).frequency
    ms_all = measured_shape(t, pts.displacement, pos, f, reference=ref_name)
    ok = np.array([pts.min_score[n] >= MIN_NCC and r2 >= MIN_R2
                   for n, r2 in zip(ms_all.names, ms_all.r2)])
    keep = [n for n, k in zip(ms_all.names, ok) if k]
    ms = measured_shape(t, {n: pts.displacement[n] for n in keep}, pos, f, reference=ref_name)

    fe = s.specimen.fe_model()
    cmp_nom = compare_shape(ms, fe)
    x0, slope, r2_line = rotation_centre(ms.positions_mm, ms.signed())
    # a mesma reta ajustada à forma do próprio modelo nos mesmos pontos: a
    # flexão da barra também desloca o intercepto, então compare x0 com este
    x0_model, _, _ = rotation_centre(
        ms.positions_mm, fe.elastic_mode_shape(ms.positions_mm / 1e3, cmp_nom.mode))
    d = max(0.0, -x0)
    fe_shift = shifted_specimen(s.specimen, d).fe_model()
    ms_shift = measured_shape(t, {n: pts.displacement[n] for n in keep},
                              {n: pos[n] + d for n in keep}, f, reference=ref_name)
    cmp_shift = compare_shape(ms_shift, fe_shift)

    out = path.parent / f"{path.name.removesuffix(SESSION_SUFFIX)}_resultados" / "forma_modal"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n, x, a, p, r2 in zip(ms_all.names, ms_all.positions_mm, ms_all.amplitude,
                              ms_all.phase_deg, ms_all.r2):
        row = {"roi": n, "x_mm": float(x), "amplitude": float(a), "fase_graus": float(p),
               "r2": float(r2), "ncc_min": pts.min_score[n], "confiavel": n in keep}
        if n in keep:
            i = ms.names.index(n)
            row.update({"prevista_raiz_nominal": float(cmp_nom.predicted[i]),
                        "erro_raiz_nominal_pct": float(cmp_nom.error_percent[i]),
                        "prevista_raiz_ajustada": float(cmp_shift.predicted[i]),
                        "erro_raiz_ajustada_pct": float(cmp_shift.error_percent[i])})
        rows.append(row)
    summary = {
        "sessao": s.name, "unidade": unit, "frequencia_hz": f, "referencia": ref_name,
        "modelo": s.specimen.model_label(), "criterio_confiavel": {"ncc_min": MIN_NCC, "r2_min": MIN_R2},
        "raiz_nominal": {"modo": cmp_nom.mode, "f_modelo_hz": cmp_nom.f_model, "mac": cmp_nom.mac},
        "origem_calibracao_x0_mm": cal_x0,
        "centro_rotacao": {"x0_mm": x0, "r2_reta": r2_line, "x0_modelo_mm": x0_model,
                           "raiz_deslocada_mm": d, "modo": cmp_shift.mode,
                           "f_modelo_hz": cmp_shift.f_model, "mac": cmp_shift.mac},
        "pontos": rows}
    (out / "forma_modal.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                          encoding="utf-8")

    lines = [f"Frequência medida {f:.4f} Hz (referência {ref_name}); {len(keep)} de {len(rows)} pontos confiáveis",
             f"Raiz nominal (x = 0): modo {cmp_nom.mode}, {cmp_nom.f_model:.3f} Hz, MAC = {cmp_nom.mac:.4f}",
             f"Centro de rotação pela reta dos pontos: x0 = {x0:.1f} mm (R² = {r2_line:.4f}); "
             f"a mesma reta na forma do modelo: x0 = {x0_model:.1f} mm; "
             f"modelo com a raiz em x0: {cmp_shift.f_model:.3f} Hz, MAC = {cmp_shift.mac:.4f}",
             f"Posições a partir do eixo do mancal; p1 da calibração em x = {cal_x0:g} mm",
             "", f"| ROI | x (mm) | A ({unit}) | fase (°) | R² | NCC mín. | ok | erro raiz nominal (%) | erro raiz em x0 (%) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        e1 = f"{r['erro_raiz_nominal_pct']:.1f}" if r["confiavel"] else "—"
        e2 = f"{r['erro_raiz_ajustada_pct']:.1f}" if r["confiavel"] else "—"
        lines.append(f"| {r['roi']} | {r['x_mm']:.0f} | {r['amplitude']:.3f} | {r['fase_graus']:.1f} | "
                     f"{r['r2']:.3f} | {r['ncc_min']:.2f} | {'sim' if r['confiavel'] else 'não'} | {e1} | {e2} |")
    (out / "forma_modal.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    xs = np.linspace(0, s.specimen.L_mm, 200)
    fig, ax = plt.subplots(figsize=(7.8, 4.0))
    ax.plot(xs, cmp_nom.scale * fe.elastic_mode_shape(xs / 1e3, cmp_nom.mode), color="tab:blue",
            label=f"modelo, raiz em x = 0 (MAC {cmp_nom.mac:.3f})")
    xs2 = np.linspace(-d, s.specimen.L_mm, 200)
    ax.plot(xs2, cmp_shift.scale * fe_shift.elastic_mode_shape((xs2 + d) / 1e3, cmp_shift.mode),
            "--", color="tab:green", label=f"modelo, raiz em x = {x0:.0f} mm (MAC {cmp_shift.mac:.3f})")
    sig = ms_all.signed()
    ax.plot(ms_all.positions_mm[ok], sig[ok], "o", color="tab:red", label="vídeo (pontos confiáveis)")
    if (~ok).any():
        ax.plot(ms_all.positions_mm[~ok], sig[~ok], "o", mfc="none", color="tab:red",
                label="vídeo (rastreamento duvidoso)")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("posição a partir do eixo do mancal [mm]")
    ax.set_ylabel(f"amplitude em {f:.2f} Hz [{unit}]")
    ax.set_title("Forma modal: vídeo × modelo de elementos finitos")
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_forma_modal.png", dpi=170)
    print(f"resultados em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
