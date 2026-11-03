"""
Reexporta as saídas que dependem do modelo analítico, sem o vídeo.

Quando um parâmetro do corpo de prova muda depois da exportação (k medido,
massas, posições das ROIs), não é preciso rastrear o vídeo de novo: os sinais
exportados (``deslocamento_video.csv``, já na grade uniforme) e o CSV do
acelerômetro bastam. Esta ferramenta recalcula, com o modelo atual da sessão:

* resumo modal de cada ROI e do acelerômetro (f prevista e erro);
* forma modal (razões entre ROIs × modelo);
* incerteza do modelo e critérios × Euler-Bernoulli;

e regrava ``tabela_modal.tex``, ``tabela_forma_modal.tex``,
``fig_espectro.{pdf,png}`` e os campos correspondentes de ``resultados.json``.
Sincronismo, comparação com o acelerômetro e demais figuras ficam como estavam.

Com ``--escala-rois A B`` a escala espacial é refeita pela distância entre os
centros das ROIs ``A`` e ``B`` (posições ao longo da barra na sessão ÷
distância em pixels no quadro): os deslocamentos exportados são multiplicados
pelo fator novo/antigo e a comparação com o acelerômetro é refeita com o mesmo
sincronismo da sessão (``deslocamento_video.csv``, ``comparacao.csv``,
``tabela_comparacao.tex`` e as figuras de deslocamento e comparação também são
regravados).

Com ``--figuras`` as figuras da comparação com o acelerômetro
(``fig_comparacao_tempo`` e ``fig_comparacao_espectro``) são refeitas com o
sincronismo da sessão, sem alterar ``resultados.json`` (útil quando só o
desenho das figuras mudou).

Uso (a partir de Code/):
    python -m tools.reexportar_modelo sessions/<sessão>.vibro.json [...]
    python -m tools.reexportar_modelo --escala-rois Acelerometro Parafuso sessions/<sessão>.vibro.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from vibrometry.report import (  # noqa: E402
    _clean, code_version, criteria_checks, fig_coherence, fig_comparison_spectrum,
    fig_comparison_time, fig_displacement, fig_scatter, fig_spectrum,
    latex_comparison_table, latex_modal_table, latex_mode_shape_table)
from vibrometry.session import SESSION_SUFFIX, Session, roi_key, roi_position  # noqa: E402
from vibrometry.uncertainty import model_uncertainty  # noqa: E402
from vibrometry.workflow import (  # noqa: E402
    accel_modal, build_comparison, load_accel, mode_shape_check, modal_summary,
    predicted_frequency)


def _write(path: Path, text: str, crlf: bool) -> None:
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def _is_crlf(path: Path) -> bool:
    return path.exists() and b"\r\n" in path.read_bytes()


def rebuild_analysis(session: Session, res: dict, out: Path) -> SimpleNamespace:
    """Video modal summaries from the exported signals, with the session's
    current model."""
    v = res["video"]
    unit, fps = v["unidade"], float(v["fps"])
    df = pl.read_csv(out / "deslocamento_video.csv")
    t = df["tempo_s"].to_numpy()
    window = tuple(session.video.window) if session.video.window else None
    f_pred = predicted_frequency(session)
    signals, modal = {}, {}
    for name in v["modal"]:
        x = df[f"{name}_{unit}"].to_numpy()
        signals[name] = x
        modal[name] = modal_summary(name, t, x, fps, unit, window, f_pred)
    return SimpleNamespace(modal=modal, signals=signals, times=t, fps=fps,
                           unit=unit, axes=v.get("eixos", {}))


def _roi_centre(session: Session, name: str) -> tuple[float, float]:
    r = next(r for r in session.video.rois if roi_key(r["name"]) == roi_key(name))
    return r["x"] + r["w"] / 2.0, r["y"] + r["h"] / 2.0


def rescale(session_path: Path, s: Session, out: Path, roi_a: str, roi_b: str) -> float:
    """Scale from two positioned ROIs; rescales the exported displacement
    signals and stores the new calibration in the session file. Returns the
    factor new / old."""
    pa, pb = _roi_centre(s, roi_a), _roi_centre(s, roi_b)
    xa = roi_position(s.video.roi_positions_mm, roi_a)
    xb = roi_position(s.video.roi_positions_mm, roi_b)
    d_px = float(np.hypot(pb[0] - pa[0], pb[1] - pa[1]))
    new = abs(xb - xa) / d_px
    old = float(s.video.scale_mm_per_px)
    factor = new / old
    csv = out / "deslocamento_video.csv"
    crlf = _is_crlf(csv)
    df = pl.read_csv(csv)
    df = df.with_columns([pl.col(c) * factor for c in df.columns if c.endswith("_mm")])
    text = df.write_csv()
    _write(csv, text, crlf)
    # session file: new scale and calibration (same JSON layout and line endings)
    raw = session_path.read_bytes().decode("utf-8")
    d = json.loads(raw)
    d["video"]["scale_mm_per_px"] = new
    d["video"]["calibration"] = {
        "p1": list(pa), "p2": list(pb), "length_mm": abs(xb - xa), "length_px": d_px,
        "origem": f"centros das ROIs {roi_a} e {roi_b} (posições da sessão); "
                  f"escala anterior {old:.5f} mm/px"}
    txt = json.dumps(d, indent=2, ensure_ascii=False)
    _write(session_path, txt, "\r\n" in raw)
    s.video.scale_mm_per_px = new
    return factor


def redraw_comparison(session_path: Path) -> list[Path]:
    """Redraw the accelerometer-comparison figures from the exported signals
    and the session's sync; resultados.json is left untouched."""
    s = Session.load(session_path)
    out = session_path.parent / f"{session_path.name.removesuffix(SESSION_SUFFIX)}_resultados"
    res = json.loads((out / "resultados.json").read_text(encoding="utf-8"))
    if not (s.accel.path and Path(s.accel.path).exists() and res.get("comparacao")):
        return []
    analysis = rebuild_analysis(s, res, out)
    _, rec = load_accel(s)
    comparison = build_comparison(s, analysis, rec)
    written = []
    for stem, fig in (("fig_comparacao_tempo", fig_comparison_time(comparison)),
                      ("fig_comparacao_espectro", fig_comparison_spectrum(comparison))):
        for ext, kw in (("pdf", {}), ("png", {"dpi": 200})):
            if (out / f"{stem}.{ext}").exists():
                fig.savefig(out / f"{stem}.{ext}", **kw)
                written.append(out / f"{stem}.{ext}")
    return written


def reexport(session_path: Path, scale_rois: tuple[str, str] | None = None) -> dict:
    s = Session.load(session_path)
    out = session_path.parent / f"{session_path.name.removesuffix(SESSION_SUFFIX)}_resultados"
    res_path = out / "resultados.json"
    crlf = _is_crlf(res_path)
    res = json.loads(res_path.read_text(encoding="utf-8"))
    factor = rescale(session_path, Session.load(session_path), out, *scale_rois) if scale_rois else None
    if factor is not None:
        s = Session.load(session_path)

    analysis = rebuild_analysis(s, res, out)
    accel_summary = rec = None
    if s.accel.path and Path(s.accel.path).exists():
        _, rec = load_accel(s)
        accel_summary = accel_modal(s, rec)

    # --- resultados.json: model-dependent fields only --------------------- #
    sess = s.to_dict(session_path.parent)
    for key in ("video", "accel"):                    # keep the exported paths
        sess[key]["path"] = res["sessao"][key]["path"]
    res["sessao"] = sess
    # the signals are the exported ones, so only the model fields change
    # (with a new scale the amplitudes change too: replace the summaries)
    model_keys = ("f_predicted_hz", "error_predicted_percent")
    for n, m in analysis.modal.items():
        new = m.to_dict()
        if factor is not None:
            res["video"]["modal"][n] = new
        else:
            res["video"]["modal"][n].update({k: new[k] for k in model_keys})
    if accel_summary is not None and (res.get("acelerometro") or {}).get("modal"):
        new = accel_summary.to_dict()
        res["acelerometro"]["modal"].update({k: new[k] for k in model_keys})
    chk = mode_shape_check(s, analysis)
    if chk is not None:
        res["forma_modal"] = {
            "referencia": chk.reference, "modo_modelo": chk.mode,
            "f_modelo_hz": chk.f_model, "f_medida_hz": chk.f_measured,
            "rois": [{"nome": r.name, "x_mm": r.x_mm, "amplitude": r.amplitude,
                      "razao_medida": r.measured_ratio, "razao_prevista": r.predicted_ratio,
                      "erro_pct": r.error_percent} for r in chk.rows]}
    else:
        res.pop("forma_modal", None)
    if s.specimen.uncertainties:
        res["incerteza_modelo"] = model_uncertainty(s.specimen, s.specimen.uncertainties).to_dict()
    comparison = None
    if factor is not None and rec is not None and res.get("comparacao"):
        comparison = build_comparison(s, analysis, rec)      # same sync as exported
        res["comparacao"]["metricas"] = (comparison.metrics.to_dict()
                                         if comparison.metrics else None)
        res["video"]["escala_mm_px"] = s.video.scale_mm_per_px
    # criteria: keep the comparison ones, recompute the model ones
    if comparison is not None:
        res["criterios"] = criteria_checks(s, analysis, comparison)
    else:
        kept = [c for c in res.get("criterios", []) if "Euler-Bernoulli" not in c["criterio"]]
        res["criterios"] = kept + [c for c in criteria_checks(s, analysis, None)]
    res["modelo_atualizado"] = {
        "em": datetime.now().isoformat(timespec="seconds"), "versao_codigo": code_version(),
        "nota": "previsão do modelo, forma modal, incerteza e critérios × modelo recalculados "
                "com a sessão atual (tools/reexportar_modelo.py); sinais, sincronismo e "
                "comparação são os da exportação original (gerado_em)"}
    _write(res_path, json.dumps(_clean(res), indent=2, ensure_ascii=False), crlf)

    # --- tables and spectrum figure --------------------------------------- #
    p = out / "tabela_modal.tex"
    _write(p, latex_modal_table(analysis, accel_summary, s), _is_crlf(p))
    p = out / "tabela_forma_modal.tex"
    if chk is not None:
        _write(p, latex_mode_shape_table(chk, s), _is_crlf(p))
    figs = {"fig_espectro": fig_spectrum(analysis)}
    if factor is not None:
        figs["fig_deslocamento"] = fig_displacement(analysis)
        if comparison is not None and comparison.metrics is not None:
            p = out / "tabela_comparacao.tex"
            _write(p, latex_comparison_table(comparison, s), _is_crlf(p))
            p = out / "comparacao.csv"
            df = pl.DataFrame({"tempo_s": comparison.t,
                               f"video_{comparison.unit_video}": comparison.video,
                               f"acelerometro_{comparison.unit_accel}": comparison.accel})
            _write(p, df.write_csv(), _is_crlf(p))
            figs.update({"fig_comparacao_tempo": fig_comparison_time(comparison),
                         "fig_comparacao_espectro": fig_comparison_spectrum(comparison),
                         "fig_dispersao": fig_scatter(comparison),
                         "fig_coerencia": fig_coherence(comparison)})
    for stem, fig in figs.items():
        for ext, kw in (("pdf", {}), ("png", {"dpi": 200})):
            if (out / f"{stem}.{ext}").exists():
                fig.savefig(out / f"{stem}.{ext}", **kw)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("sessoes", nargs="+")
    ap.add_argument("--escala-rois", nargs=2, metavar=("ROI_A", "ROI_B"),
                    help="refaz a escala pela distância entre estas duas ROIs posicionadas")
    ap.add_argument("--figuras", action="store_true",
                    help="só refaz as figuras da comparação com o acelerômetro")
    args = ap.parse_args(argv)
    if args.figuras:
        for a in args.sessoes:
            print(f"{Path(a).name}: {len(redraw_comparison(Path(a)))} figuras")
        return 0
    for a in args.sessoes:
        res = reexport(Path(a), tuple(args.escala_rois) if args.escala_rois else None)
        f_pred = next(iter(res["video"]["modal"].values()))["f_predicted_hz"]
        msg = f"{Path(a).name}: modelo {f_pred:.3f} Hz; forma modal {'ok' if res.get('forma_modal') else '—'}"
        if args.escala_rois:
            m = (res.get("comparacao") or {}).get("metricas") or {}
            msg += (f"; escala {res['video'].get('escala_mm_px', float('nan')):.4f} mm/px; "
                    f"A vídeo {m.get('amp_test', float('nan')):.3f} × acel. {m.get('amp_ref', float('nan')):.3f} mm "
                    f"({m.get('amp_error_percent', float('nan')):+.1f} %)")
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
