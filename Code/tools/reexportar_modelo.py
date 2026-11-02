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

Uso (a partir de Code/):  python -m tools.reexportar_modelo sessions/<sessão>.vibro.json [...]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from vibrometry.report import (  # noqa: E402
    _clean, code_version, criteria_checks, fig_spectrum, latex_modal_table,
    latex_mode_shape_table)
from vibrometry.session import SESSION_SUFFIX, Session  # noqa: E402
from vibrometry.uncertainty import model_uncertainty  # noqa: E402
from vibrometry.workflow import (  # noqa: E402
    accel_modal, load_accel, mode_shape_check, modal_summary, predicted_frequency)


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


def reexport(session_path: Path) -> dict:
    s = Session.load(session_path)
    out = session_path.parent / f"{session_path.name.removesuffix(SESSION_SUFFIX)}_resultados"
    res_path = out / "resultados.json"
    crlf = _is_crlf(res_path)
    res = json.loads(res_path.read_text(encoding="utf-8"))

    analysis = rebuild_analysis(s, res, out)
    accel_summary = None
    if s.accel.path and Path(s.accel.path).exists():
        _, rec = load_accel(s)
        accel_summary = accel_modal(s, rec)

    # --- resultados.json: model-dependent fields only --------------------- #
    sess = s.to_dict(session_path.parent)
    for key in ("video", "accel"):                    # keep the exported paths
        sess[key]["path"] = res["sessao"][key]["path"]
    res["sessao"] = sess
    # the signals are the exported ones, so only the model fields change
    model_keys = ("f_predicted_hz", "error_predicted_percent")
    for n, m in analysis.modal.items():
        new = m.to_dict()
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
    # criteria: keep the comparison ones, recompute the model ones
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
    fig = fig_spectrum(analysis)
    for ext, kw in (("pdf", {}), ("png", {"dpi": 200})):
        if (out / f"fig_espectro.{ext}").exists():
            fig.savefig(out / f"fig_espectro.{ext}", **kw)
    return res


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    for a in argv:
        res = reexport(Path(a))
        f_pred = next(iter(res["video"]["modal"].values()))["f_predicted_hz"]
        print(f"{Path(a).name}: modelo {f_pred:.3f} Hz; forma modal "
              f"{'ok' if res.get('forma_modal') else '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
