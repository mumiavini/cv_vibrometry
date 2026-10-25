"""
Export of a processed session (planejamento, section 8 item 11): CSV time
series, JSON with every parameter and result (plus code version), LaTeX
tables (booktabs) and vector figures (PDF) / PNG for the thesis text.

Figures use matplotlib's object API (no pyplot), so this module is safe to
call from the GUI thread.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from .accelerometer import AccelRecord
from .analysis import coefficient_of_variation, coherence_and_frf
from .session import Session
from .spectral import amplitude_spectrum, stft_spectrogram
from .workflow import (
    ComparisonData,
    ModalSummary,
    VideoAnalysis,
    accel_displacement_mm,
)

RC = {
    "font.family": "serif",
    "mathtext.fontset": "dejavuserif",
    "font.size": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
}
C_VIDEO = "tab:blue"
C_ACC = "tab:orange"


@dataclass
class ExportOptions:
    csv: bool = True
    json: bool = True
    latex: bool = True
    pdf: bool = True
    png: bool = True


def code_version() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def spectrum_xmax(fs: float, f_n: float | None, f_pred: float | None = None) -> float:
    """Upper frequency limit for spectrum plots: a few times the dominant /
    predicted frequency, so the peak is not squashed against 0 Hz at high
    frame rates (240 fps -> Nyquist 120 Hz for a ~10 Hz mode)."""
    hi = max(10.0, 4.0 * (f_n or 0.0), 1.5 * (f_pred or 0.0))
    return min(fs / 2 * 1.02, hi)


def fmt_tex(x: float | None, nd: int = 2) -> str:
    """Number with Brazilian decimal comma for LaTeX ("—" if missing)."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "--"
    return f"{x:.{nd}f}".replace(".", "{,}")


# --------------------------------------------------------------------------- #
# criteria
# --------------------------------------------------------------------------- #
def criteria_checks(session: Session, analysis: VideoAnalysis | None,
                    comparison: ComparisonData | None) -> list[dict]:
    """Acceptance criteria of planejamento section 11 that can be evaluated
    for this session: [{criterio, valor, limite, ok}]."""
    c = session.compare
    out = []
    if comparison is not None and comparison.metrics is not None:
        m = comparison.metrics
        if m.freq_error_percent is not None:
            out.append({"criterio": "Frequência, vídeo × acelerômetro [%]",
                        "valor": abs(m.freq_error_percent),
                        "limite": c.crit_freq_pct,
                        "ok": abs(m.freq_error_percent) <= c.crit_freq_pct})
        if m.amp_error_percent is not None and comparison.units_match:
            out.append({"criterio": "Amplitude, vídeo × acelerômetro [%]",
                        "valor": abs(m.amp_error_percent),
                        "limite": c.crit_amp_pct,
                        "ok": abs(m.amp_error_percent) <= c.crit_amp_pct})
        if m.phase_diff_deg is not None:
            out.append({"criterio": "Fase, vídeo × acelerômetro [°]",
                        "valor": abs(m.phase_diff_deg),
                        "limite": c.crit_phase_deg,
                        "ok": abs(m.phase_diff_deg) <= c.crit_phase_deg})
    if analysis is not None:
        for name, ms in analysis.modal.items():
            if ms.error_predicted_percent is not None:
                out.append({"criterio": f"f₁ {name} × Euler-Bernoulli [%]",
                            "valor": abs(ms.error_predicted_percent),
                            "limite": c.crit_eb_pct,
                            "ok": abs(ms.error_predicted_percent) <= c.crit_eb_pct})
    return out


# --------------------------------------------------------------------------- #
# figures
# --------------------------------------------------------------------------- #
def _fig(w=8.0, h=3.8, nrows=1, ncols=1, **kw):
    import matplotlib as mpl
    with mpl.rc_context(RC):
        fig = Figure(figsize=(w, h), layout="constrained")
        axes = fig.subplots(nrows, ncols, **kw)
    return fig, axes


def fig_rois(analysis: VideoAnalysis) -> Figure:
    tr = analysis.track
    h, w = tr.reference_frame.shape
    fig, ax = _fig(8, 8 * h / w * 0.95 + 0.4)
    ax.imshow(tr.reference_frame, cmap="gray")
    for name, res in tr.tracks.items():
        r = res.roi
        color = "tab:orange" if r.is_reference else C_VIDEO
        ax.add_patch(Rectangle((r.x, r.y), r.w, r.h, fill=False,
                               edgecolor=color, linewidth=1.8))
        ax.text(r.x, r.y - 4, name, color=color, fontsize=9, va="bottom")
    ax.set_axis_off()
    ax.set_title("Quadro de referência e ROIs")
    return fig


def fig_displacement(analysis: VideoAnalysis) -> Figure:
    fig, ax = _fig()
    t = analysis.times
    for name, x in analysis.signals.items():
        ax.plot(t, x, linewidth=0.8, label=f"{name} ({analysis.axes[name]})")
        ms = analysis.modal[name]
        if ms.decay is not None:
            d = ms.decay
            a0, lam = d.envelope
            # decay fit is on the mean-removed window; peak_times are
            # relative to the window start
            mean_w = float(np.mean(x[(t >= ms.window[0]) & (t <= ms.window[1])]))
            tp = d.peak_times + ms.window[0]
            te = np.linspace(tp[0], ms.window[1], 300)
            env = a0 * np.exp(-lam * (te - tp[0]))
            ax.plot(tp, d.peak_amplitudes + mean_w, "o", color="tab:red",
                    markersize=3)
            ax.plot(te, mean_w + env, "k--", linewidth=0.9,
                    label=rf"envoltória ($\zeta$ = {d.zeta:.4f})")
            ax.plot(te, mean_w - env, "k--", linewidth=0.9)
    first = next(iter(analysis.modal.values()), None)
    if first is not None and (first.window[0] > t[0] or first.window[1] < t[-1]):
        ax.axvspan(*first.window, color="0.85", alpha=0.5, lw=0,
                   label="janela de análise")
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel(f"Deslocamento [{analysis.unit}]")
    ax.set_title("Deslocamento compensado (método de fase)")
    ax.legend(loc="upper right")
    return fig


def fig_spectrum(analysis: VideoAnalysis) -> Figure:
    fig, ax = _fig()
    fs = analysis.fps
    for name, ms in analysis.modal.items():
        if ms.freqs is None:
            continue
        line, = ax.plot(ms.freqs, ms.spectrum, linewidth=1.0, label=name)
        if ms.f_n:
            i = int(np.argmin(abs(ms.freqs - ms.f_n)))
            ax.plot(ms.freqs[i], ms.spectrum[i], "v", color="tab:red", markersize=6)
            ax.annotate(f"{ms.f_n:.2f} Hz", (ms.freqs[i], ms.spectrum[i]),
                        xytext=(6, 2), textcoords="offset points", fontsize=9)
    f_pred = next((m.f_predicted for m in analysis.modal.values()
                   if m.f_predicted), None)
    if f_pred:
        ax.axvline(f_pred, color="tab:green", linestyle="--", linewidth=1.0,
                   label=f"$f_{{n,1}}^{{anl}}$ = {f_pred:.2f} Hz")
    first = next(iter(analysis.modal.values()), None)
    xmax = spectrum_xmax(fs, first.f_n if first else None, f_pred)
    if xmax >= fs / 2:
        ax.axvline(fs / 2, color="gray", linestyle=":", linewidth=1.0,
                   label=f"Nyquist = {fs / 2:.1f} Hz")
    ax.set_xlim(0, xmax)
    ax.set_xlabel("Frequência [Hz]")
    ax.set_ylabel(f"Amplitude [{analysis.unit}]")
    ax.set_title("Espectro de amplitude (janela de Hann)")
    ax.legend(loc="upper right")
    return fig


def fig_spectrogram(analysis: VideoAnalysis, name: str) -> Figure:
    fig, ax = _fig(8, 3.6)
    st, sf, sm = stft_spectrogram(analysis.signals[name], analysis.fps)
    floor = max(sm.max() * 1e-4, 1e-12)
    mesh = ax.pcolormesh(st, sf, 20 * np.log10(np.maximum(sm, floor)),
                         shading="auto", cmap="magma")
    fig.colorbar(mesh, ax=ax, label=f"Amplitude [dB re 1 {analysis.unit}]")
    ax.grid(False)
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel("Frequência [Hz]")
    ax.set_title(f"Espectrograma (STFT) — {name}")
    return fig


def fig_accelerometer(session: Session, rec: AccelRecord) -> Figure:
    fig, (a1, a2) = _fig(8, 5.2, nrows=2, sharex=True)
    a1.plot(rec.t, rec.a, color=C_ACC, linewidth=0.6)
    a1.set_ylabel("Aceleração [m/s²]")
    a1.set_title(f"Acelerômetro — {rec.label}")
    a2.plot(rec.t, accel_displacement_mm(session, rec), color=C_ACC, linewidth=0.8)
    a2.set_ylabel("Deslocamento [mm]")
    a2.set_xlabel("Tempo do acelerômetro [s]")
    return fig


def fig_comparison_time(cmp: ComparisonData) -> Figure:
    fig, (a1, a2) = _fig(8, 5.6, nrows=2)
    lab_v = f"Vídeo [{cmp.unit_video}]"
    lab_a = f"Acelerômetro [{cmp.unit_accel}]"
    for ax in (a1, a2):
        ax.plot(cmp.t, cmp.video, color=C_VIDEO, linewidth=0.8, label=lab_v)
        ax.plot(cmp.t, cmp.accel, color=C_ACC, linewidth=0.8, label=lab_a,
                alpha=0.9)
        ax.set_ylabel("Deslocamento" if cmp.domain == "displacement"
                      else "Aceleração")
    a1.axvspan(*cmp.window, color="0.85", alpha=0.5, lw=0)
    a1.set_title("Vídeo × acelerômetro (sincronizados)")
    a1.legend(loc="upper right")
    # detail: ~6 periods in the middle of the window
    m = cmp.metrics
    w0, w1 = cmp.window
    if m is not None and m.f_common:
        mid = 0.5 * (w0 + w1)
        half = min(3.0 / m.f_common, 0.5 * (w1 - w0))
        w0, w1 = mid - half, mid + half
    a2.set_xlim(w0, w1)
    sel = (cmp.t >= w0) & (cmp.t <= w1)
    vals = np.concatenate([cmp.video[sel], cmp.accel[sel]])
    vals = vals[np.isfinite(vals)]
    if vals.size:
        pad = 0.1 * (vals.max() - vals.min() + 1e-12)
        a2.set_ylim(vals.min() - pad, vals.max() + pad)
    a2.set_xlabel("Tempo [s]")
    a2.set_title("Detalhe")
    return fig


def fig_comparison_spectrum(cmp: ComparisonData) -> Figure:
    fig, ax = _fig()
    m = cmp.window_mask()
    for x, c, lab in ((cmp.video, C_VIDEO, f"Vídeo [{cmp.unit_video}]"),
                      (cmp.accel, C_ACC, f"Acelerômetro [{cmp.unit_accel}]")):
        f, a = amplitude_spectrum(x[m], cmp.fs)
        ax.plot(f, a, color=c, linewidth=1.0, label=lab)
    if cmp.metrics is not None and cmp.metrics.f_common:
        ax.set_xlim(0, min(cmp.fs / 2, 4 * cmp.metrics.f_common))
    ax.set_xlabel("Frequência [Hz]")
    ax.set_ylabel("Amplitude")
    ax.set_title("Espectros na janela de análise")
    ax.legend(loc="upper right")
    return fig


def fig_scatter(cmp: ComparisonData) -> Figure:
    fig, ax = _fig(5, 4.6)
    m = cmp.window_mask()
    a, v = cmp.accel[m], cmp.video[m]
    ax.plot(a, v, ".", markersize=2, color=C_VIDEO, alpha=0.6)
    lim = np.nanmax(np.abs(np.concatenate([a, v]))) * 1.05 if a.size else 1
    ax.plot([-lim, lim], [-lim, lim], "k--", linewidth=0.8, label="1:1")
    if cmp.metrics is not None:
        g = cmp.metrics.gain
        ax.plot([-lim, lim], [-g * lim, g * lim], color="tab:red", linewidth=0.9,
                label=f"ajuste: inclinação {g:.3f}, r = {cmp.metrics.pearson_r:.4f}")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel(f"Acelerômetro [{cmp.unit_accel}]")
    ax.set_ylabel(f"Vídeo [{cmp.unit_video}]")
    ax.set_title("Dispersão vídeo × acelerômetro")
    ax.legend(loc="upper left")
    return fig


def fig_coherence(cmp: ComparisonData) -> Figure:
    fig, (a1, a2) = _fig(8, 5.2, nrows=2, sharex=True)
    m = cmp.window_mask()
    f, coh, h1 = coherence_and_frf(cmp.accel[m], cmp.video[m], cmp.fs)
    a1.plot(f, coh, color=C_VIDEO, linewidth=1.0)
    a1.set_ylim(0, 1.05)
    a1.set_ylabel("Coerência $\\gamma^2$")
    a1.set_title("Coerência e FRF (vídeo / acelerômetro)")
    a2.semilogy(f, h1, color=C_VIDEO, linewidth=1.0)
    a2.set_ylabel("$|H_1|$")
    a2.set_xlabel("Frequência [Hz]")
    if cmp.metrics is not None and cmp.metrics.f_common:
        a2.set_xlim(0, min(cmp.fs / 2, 4 * cmp.metrics.f_common))
    return fig


# --------------------------------------------------------------------------- #
# tables
# --------------------------------------------------------------------------- #
def latex_modal_table(analysis: VideoAnalysis, accel: ModalSummary | None,
                      session: Session) -> str:
    u = analysis.unit
    rows = []
    for ms in analysis.modal.values():
        rows.append((ms.name, ms.f_n, ms.amplitude, ms.zeta_half_power,
                     ms.zeta_log_decrement, ms.f_predicted,
                     ms.error_predicted_percent))
    if accel is not None:
        rows.append(("Acelerômetro", accel.f_n, accel.amplitude,
                     accel.zeta_half_power, accel.zeta_log_decrement,
                     accel.f_predicted, accel.error_predicted_percent))
    body = "\n".join(
        f"    {n.replace('_', chr(92) + '_')} & {fmt_tex(f, 3)} & {fmt_tex(a, 3)} & "
        f"{fmt_tex(zh, 4)} & {fmt_tex(zl, 4)} & {fmt_tex(fp, 2)} & {fmt_tex(e, 2)} \\\\"
        for n, f, a, zh, zl, fp, e in rows)
    name = session.name.replace("_", "\\_")
    return (
        "\\begin{table}[htbp]\n  \\centering\n"
        f"  \\caption{{Parâmetros modais identificados — {name}.}}\n"
        f"  \\label{{tab:modal_{session.name}}}\n"
        "  \\begin{tabular}{lrrrrrr}\n    \\toprule\n"
        f"    Sinal & $f_n$ [Hz] & $A$ [{u}] & $\\zeta_{{mp}}$ & $\\zeta_{{dl}}$ & "
        "$f_{n,1}^{anl}$ [Hz] & $\\varepsilon$ [\\%] \\\\\n    \\midrule\n"
        f"{body}\n    \\bottomrule\n  \\end{{tabular}}\n\\end{{table}}\n"
    )


def latex_comparison_table(cmp: ComparisonData, session: Session) -> str:
    m = cmp.metrics
    if m is None:
        return ""
    u_v, u_a = cmp.unit_video, cmp.unit_accel
    lines = [
        ("Frequência [Hz]", fmt_tex(m.f_test, 3), fmt_tex(m.f_ref, 3),
         fmt_tex(m.freq_error_percent, 2) + " \\%"),
        (f"Amplitude [{u_v} / {u_a}]", fmt_tex(m.amp_test, 4),
         fmt_tex(m.amp_ref, 4), fmt_tex(m.amp_error_percent, 2) + " \\%"),
        ("Fase [°]", fmt_tex(m.phase_test_deg, 1), fmt_tex(m.phase_ref_deg, 1),
         fmt_tex(m.phase_diff_deg, 1) + "°"),
        ("RMS", fmt_tex(m.rms_test, 4), fmt_tex(m.rms_ref, 4),
         fmt_tex(m.rms_error_percent, 2) + " \\%"),
        ("Correlação $r$", "", "", fmt_tex(m.pearson_r, 4)),
        ("NRMSE", "", "", fmt_tex(m.nrmse_percent, 2) + " \\%"),
    ]
    body = "\n".join(f"    {a} & {b} & {c} & {d} \\\\" for a, b, c, d in lines)
    name = session.name.replace("_", "\\_")
    return (
        "\\begin{table}[htbp]\n  \\centering\n"
        f"  \\caption{{Comparação entre o método óptico e o acelerômetro — {name}.}}\n"
        f"  \\label{{tab:comp_{session.name}}}\n"
        "  \\begin{tabular}{lrrr}\n    \\toprule\n"
        "    Grandeza & Vídeo & Acelerômetro & Diferença \\\\\n    \\midrule\n"
        f"{body}\n    \\bottomrule\n  \\end{{tabular}}\n\\end{{table}}\n"
    )


BATCH_COLUMNS = [
    ("sessao", "Sessão", None), ("f_video_hz", "$f$ vídeo [Hz]", 3),
    ("f_acc_hz", "$f$ acel. [Hz]", 3), ("erro_f_pct", "$\\varepsilon_f$ [\\%]", 2),
    ("A_opt", "$A$ vídeo", 4), ("A_ref", "$A$ acel.", 4),
    ("erro_A_pct", "$\\varepsilon_A$ [\\%]", 2),
    ("dfase_graus", "$\\Delta\\varphi$ [°]", 1),
    ("zeta_video", "$\\zeta$ vídeo", 4), ("erro_prevista_pct", "$\\varepsilon_{EB}$ [\\%]", 2),
]


def latex_batch_table(rows: list[dict]) -> str:
    cols = [c for c in BATCH_COLUMNS if any(r.get(c[0]) not in (None, "") for r in rows)]
    head = " & ".join(c[1] for c in cols)
    body = []
    for r in rows:
        cells = []
        for key, _, nd in cols:
            v = r.get(key)
            cells.append(str(v).replace("_", "\\_") if nd is None else fmt_tex(v, nd))
        body.append("    " + " & ".join(cells) + " \\\\")
    return (
        "\\begin{table}[htbp]\n  \\centering\n  \\small\n"
        "  \\caption{Resultados do processamento em lote.}\n"
        "  \\label{tab:lote}\n"
        f"  \\begin{{tabular}}{{l{'r' * (len(cols) - 1)}}}\n    \\toprule\n"
        f"    {head} \\\\\n    \\midrule\n" + "\n".join(body) +
        "\n    \\bottomrule\n  \\end{tabular}\n\\end{table}\n"
    )


def group_statistics(rows: list[dict], keys: tuple[str, ...] = (
        "f_video_hz", "f_acc_hz", "A_opt", "A_ref", "erro_f_pct", "erro_A_pct",
        "dfase_graus", "zeta_video")) -> list[dict]:
    """Mean, sample std and CV [%] per group (repetitions pooled)."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        if not r.get("erro"):
            groups.setdefault(r.get("grupo") or r["sessao"], []).append(r)
    out = []
    for g, rs in groups.items():
        d = {"grupo": g, "n": len(rs)}
        for k in keys:
            vals = [r.get(k) for r in rs if r.get(k) is not None]
            if vals:
                arr = np.asarray(vals, dtype=float)
                d[f"{k}_media"] = float(arr.mean())
                d[f"{k}_dp"] = float(arr.std(ddof=1)) if arr.size > 1 else None
                d[f"{k}_cv_pct"] = coefficient_of_variation(arr)
        out.append(d)
    return out


# --------------------------------------------------------------------------- #
# json
# --------------------------------------------------------------------------- #
def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def results_dict(session: Session, analysis: VideoAnalysis | None,
                 accel: AccelRecord | None, accel_summary: ModalSummary | None,
                 comparison: ComparisonData | None) -> dict:
    d: dict = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "versao_codigo": code_version(),
        "sessao": session.to_dict(),
    }
    if analysis is not None:
        tr = analysis.track
        q = tr.quality
        d["video"] = {
            "arquivo": tr.info.path, "resolucao": [tr.info.width, tr.info.height],
            "codec": tr.info.codec, "fps": tr.fps, "fps_fonte": tr.fps_source,
            "fps_declarado": tr.info.declared_fps, "fps_medido": tr.info.measured_fps,
            "quadros_processados": tr.n_frames, "fator_reducao": tr.resize_factor,
            "inicio_s": tr.t0, "unidade": analysis.unit,
            "eixos": analysis.axes,
            "qualidade": {
                "intervalo_quadros_ms": q.frame_interval_ms,
                "jitter_ms": q.frame_jitter_ms, "quadros_perdidos": q.dropped_frames,
                "cintilacao_hz": q.flicker_hz, "cintilacao_pct": q.flicker_percent,
                "foco_laplaciano": q.focus, "saturacao_pct": q.saturation,
                "quadros_perdidos_rastreamento": q.lost_frames,
                "ncc_minimo": q.min_score, "avisos": q.warnings(),
            },
            "modal": {n: m.to_dict() for n, m in analysis.modal.items()},
        }
    if accel is not None:
        d["acelerometro"] = {
            "canal": accel.label, "fs_hz": accel.fs, "duracao_s": accel.duration,
            "reamostrado": accel.resampled, "jitter_pct": accel.jitter_percent,
            "modal": accel_summary.to_dict() if accel_summary else None,
        }
    if comparison is not None:
        d["comparacao"] = {
            "roi": comparison.roi, "dominio": comparison.domain,
            "unidade_video": comparison.unit_video,
            "unidade_acelerometro": comparison.unit_accel,
            "offset_s": comparison.offset_s, "deriva_ppm": comparison.drift_ppm,
            "janela_s": list(comparison.window),
            "metricas": comparison.metrics.to_dict() if comparison.metrics else None,
        }
    d["criterios"] = criteria_checks(session, analysis, comparison)
    return _clean(d)


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #
def export_session(
    out_dir: str | Path,
    session: Session,
    analysis: VideoAnalysis | None = None,
    accel: AccelRecord | None = None,
    accel_summary: ModalSummary | None = None,
    comparison: ComparisonData | None = None,
    options: ExportOptions | None = None,
) -> list[Path]:
    opts = options or ExportOptions()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save_fig(fig: Figure, stem: str) -> None:
        if opts.pdf:
            fig.savefig(out / f"{stem}.pdf")
            written.append(out / f"{stem}.pdf")
        if opts.png:
            fig.savefig(out / f"{stem}.png", dpi=200)
            written.append(out / f"{stem}.png")

    def save_text(name: str, text: str) -> None:
        (out / name).write_text(text, encoding="utf-8")
        written.append(out / name)

    if opts.json:
        save_text("resultados.json", json.dumps(
            results_dict(session, analysis, accel, accel_summary, comparison),
            indent=2, ensure_ascii=False))

    if analysis is not None:
        u = analysis.unit
        if opts.csv:
            cols = {"tempo_s": analysis.times}
            for n, x in analysis.signals.items():
                cols[f"{n}_{u}"] = x
            for n, tr in analysis.track.tracks.items():
                cols[f"{n}_dx_px"] = tr.displacement[:, 0]
                cols[f"{n}_dy_px"] = tr.displacement[:, 1]
                cols[f"{n}_ncc"] = tr.score
            pl.DataFrame(cols).write_csv(out / "deslocamento_video.csv")
            written.append(out / "deslocamento_video.csv")
        if opts.latex:
            save_text("tabela_modal.tex",
                      latex_modal_table(analysis, accel_summary, session))
        if opts.pdf or opts.png:
            save_fig(fig_rois(analysis), "fig_rois")
            save_fig(fig_displacement(analysis), "fig_deslocamento")
            save_fig(fig_spectrum(analysis), "fig_espectro")
            for n in analysis.signals:
                save_fig(fig_spectrogram(analysis, n), f"fig_espectrograma_{n}")

    if accel is not None:
        if opts.csv:
            pl.DataFrame({
                "tempo_acc_s": accel.t, "aceleracao_m_s2": accel.a,
                "deslocamento_mm": accel_displacement_mm(session, accel),
            }).write_csv(out / "acelerometro.csv")
            written.append(out / "acelerometro.csv")
        if opts.pdf or opts.png:
            save_fig(fig_accelerometer(session, accel), "fig_acelerometro")

    if comparison is not None:
        if opts.csv:
            pl.DataFrame({
                "tempo_s": comparison.t,
                f"video_{comparison.unit_video}": comparison.video,
                f"acelerometro_{comparison.unit_accel}": comparison.accel,
            }).write_csv(out / "comparacao.csv")
            written.append(out / "comparacao.csv")
        if comparison.metrics is not None:
            if opts.latex:
                save_text("tabela_comparacao.tex",
                          latex_comparison_table(comparison, session))
            if opts.pdf or opts.png:
                save_fig(fig_comparison_time(comparison), "fig_comparacao_tempo")
                save_fig(fig_comparison_spectrum(comparison), "fig_comparacao_espectro")
                save_fig(fig_scatter(comparison), "fig_dispersao")
                save_fig(fig_coherence(comparison), "fig_coerencia")
    return written
