"""Step 6 — Relatório: summary of the session and export of CSV, JSON,
LaTeX tables and figures (planejamento R8)."""

from __future__ import annotations

import html
import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QWidget,
)

from vibrometry.report import ExportOptions, criteria_checks, export_session

from . import theme
from .page_plan import MATERIAL_LABELS
from .state import AppState
from .widgets import Panel, debounce, fmt, hbox, muted, scroll, section, vbox


class ReportPage(QWidget):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.state = state

        self.summary = QTextBrowser()
        self.summary.setOpenExternalLinks(False)
        self.summary.setStyleSheet("QTextBrowser { border: none; padding: 8px; }")

        self.opt_csv = QCheckBox("Séries temporais (CSV)")
        self.opt_json = QCheckBox("Parâmetros e resultados (JSON)")
        self.opt_tex = QCheckBox("Tabelas LaTeX (booktabs)")
        self.opt_pdf = QCheckBox("Figuras vetoriais (PDF)")
        self.opt_png = QCheckBox("Figuras PNG (200 dpi)")
        for cb in (self.opt_csv, self.opt_json, self.opt_tex, self.opt_pdf, self.opt_png):
            cb.setChecked(True)
        self.folder = QLineEdit()
        self.browse = QPushButton("…")
        self.browse.setFixedWidth(36)
        self.export_btn = QPushButton("Exportar")
        self.export_btn.setObjectName("Primary")
        self.open_folder = QPushButton("Abrir pasta")
        self.open_folder.setEnabled(False)
        self.result = muted()

        side = QWidget()
        sl = vbox(side, spacing=8)
        p = Panel()
        p.lay.addWidget(section("Exportar"))
        for cb in (self.opt_csv, self.opt_json, self.opt_tex, self.opt_pdf, self.opt_png):
            p.lay.addWidget(cb)
        p.lay.addWidget(muted("Pasta de destino"))
        p.lay.addLayout(hbox(self.folder, self.browse))
        p.lay.addWidget(self.export_btn)
        p.lay.addWidget(self.open_folder)
        p.lay.addWidget(self.result)
        sl.addWidget(p)
        sl.addStretch(1)

        body = Panel(margins=4)
        body.lay.addWidget(self.summary)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(body, 1)
        lay.addWidget(scroll(side, 300))

        self._refresh_timer = debounce(self, 100, self.refresh)
        for sig in (state.sessionReplaced, state.analysisChanged, state.accelChanged,
                    state.comparisonChanged, state.nameChanged, state.specimenChanged):
            sig.connect(self._refresh_timer.start)
        state.sessionReplaced.connect(self._default_folder)
        self.browse.clicked.connect(self._browse)
        self.export_btn.clicked.connect(self.export)
        self.open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder.text())))
        self._default_folder()
        self.refresh()

    # ------------------------------------------------------------------ #
    def _default_folder(self) -> None:
        s = self.state.session
        base = (os.path.dirname(s.file) if s.file else
                os.path.dirname(s.video.path) if s.video.path else
                str(Path(__file__).resolve().parents[1] / "vibrometry" / "outputs"))
        self.folder.setText(str(Path(base) / f"{s.name or 'sessao'}_resultados"))

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta de destino", self.folder.text())
        if d:
            self.folder.setText(d)

    def export(self) -> None:
        st = self.state
        if st.analysis is None and st.accel is None:
            QMessageBox.information(self, "Exportar", "Nada para exportar ainda.")
            return
        opts = ExportOptions(csv=self.opt_csv.isChecked(), json=self.opt_json.isChecked(),
                             latex=self.opt_tex.isChecked(), pdf=self.opt_pdf.isChecked(),
                             png=self.opt_png.isChecked())
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            files = export_session(self.folder.text(), st.session, st.analysis, st.accel,
                                   st.accel_summary, st.comparison, opts)
        except Exception as exc:
            QMessageBox.warning(self, "Exportar", f"Falha na exportação:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.result.setText(f"{len(files)} arquivo(s) gravado(s):\n"
                            + "\n".join(f.name for f in files))
        self.open_folder.setEnabled(True)
        st.message.emit(f"Exportado para {self.folder.text()}")

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        st = self.state
        s = st.session
        h = [f"<h2 style='margin:0'>{html.escape(s.name or 'Sessão sem nome')}</h2>"]
        if s.meta.notes:
            h.append(f"<p style='color:{theme.MUTED}'>{html.escape(s.meta.notes)}</p>")

        sp = s.specimen
        material = MATERIAL_LABELS.get(sp.material, sp.material)
        rows = [("Corpo de prova", f"{material} · L = {fmt(sp.L_mm, 1)} mm · "
                                   f"b = {fmt(sp.b_mm, 2)} mm · t = {fmt(sp.t_mm, 3)} mm · "
                                   f"massa na ponta {fmt(sp.tip_mass_g, 2)} g"),
                ("Excitação", f"{fmt(s.meta.excitation_hz, 2)} Hz" if s.meta.excitation_hz
                 else "vibração livre")]
        try:
            rows.append(("f₁ prevista (E-B)", f"{fmt(sp.predicted_f1(), 3)} Hz"))
        except Exception:
            pass
        h.append(_section("Ensaio", rows))

        a = st.analysis
        if a is not None:
            tr = a.track
            q = tr.quality
            rows = [("Vídeo", html.escape(Path(tr.info.path).name)),
                    ("Amostragem", f"{fmt(tr.fps, 3)} fps ({tr.fps_source}) · {tr.n_frames} "
                                   f"quadros · {fmt(tr.n_frames / tr.fps, 2)} s"),
                    ("Escala", f"{fmt(s.video.scale_mm_per_px, 5)} mm/px"
                     if s.video.scale_mm_per_px else "não calibrada (px)"),
                    ("Qualidade", "; ".join(q.warnings()) or "sem alertas")]
            for name, ms in a.modal.items():
                rows.append((f"ROI {html.escape(name)} ({a.axes[name]})",
                             f"f = {fmt(ms.f_n, 3)} Hz · A = {fmt(ms.amplitude, 4)} {ms.unit}"
                             f" · ζ<sub>dl</sub> = {fmt(ms.zeta_log_decrement, 4)} · "
                             f"ζ<sub>mp</sub> = {fmt(ms.zeta_half_power, 4)} · "
                             f"σ = {fmt(ms.std, 4)} {ms.unit}"))
            h.append(_section("Método óptico", rows))
        else:
            h.append(_section("Método óptico", [("", "vídeo não processado")]))

        if st.accel is not None:
            r = st.accel
            ms = st.accel_summary
            rows = [("Canal", html.escape(r.label)),
                    ("Amostragem", f"{fmt(r.fs, 1)} Hz · {fmt(r.duration, 2)} s")]
            if ms is not None:
                rows.append(("Deslocamento integrado",
                             f"f = {fmt(ms.f_n, 3)} Hz · A = {fmt(ms.amplitude, 4)} mm · "
                             f"ζ<sub>dl</sub> = {fmt(ms.zeta_log_decrement, 4)}"))
            h.append(_section("Acelerômetro", rows))

        cmp = st.comparison
        if cmp is not None and cmp.metrics is not None:
            m = cmp.metrics
            rows = [("Sincronismo", f"atraso {fmt(cmp.offset_s, 5)} s · deriva "
                                    f"{fmt(cmp.drift_ppm, 1)} ppm"),
                    ("Janela", f"{fmt(cmp.window[0], 2)}–{fmt(cmp.window[1], 2)} s"),
                    ("Frequência", f"vídeo {fmt(m.f_test, 4)} Hz × acel. {fmt(m.f_ref, 4)} Hz"),
                    ("Amplitude", f"vídeo {fmt(m.amp_test, 4)} {cmp.unit_video} × acel. "
                                  f"{fmt(m.amp_ref, 4)} {cmp.unit_accel}"),
                    ("Fase", f"Δφ = {fmt(m.phase_diff_deg, 2)}°"),
                    ("Correlação", f"r = {fmt(m.pearson_r, 4)} · NRMSE "
                                   f"{fmt(m.nrmse_percent, 2)} %")]
            h.append(_section("Comparação", rows))

        checks = criteria_checks(s, a, cmp)
        if checks:
            items = "".join(
                f"<tr><td style='padding:3px 12px 3px 0'>{html.escape(c['criterio'])}</td>"
                f"<td align='right' style='padding:3px 12px'>{fmt(c['valor'], 3)}</td>"
                f"<td style='padding:3px 12px; color:{theme.MUTED}'>≤ {fmt(c['limite'], 2)}</td>"
                f"<td style='color:{theme.OK if c['ok'] else theme.BAD}; font-weight:600'>"
                f"{'✓' if c['ok'] else '✗'}</td></tr>" for c in checks)
            h.append(f"<h3 style='margin-bottom:4px'>Critérios de aceitação</h3>"
                     f"<table cellspacing='0'>{items}</table>")
        self.summary.setHtml(
            f"<div style='font-family:Segoe UI; font-size:10pt; color:{theme.TEXT}'>"
            + "".join(h) + "</div>")


def _section(title: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><td style='padding:3px 16px 3px 0; color:{theme.MUTED}; white-space:nowrap'>"
        f"{k}</td><td style='padding:3px 0'>{v}</td></tr>" for k, v in rows)
    return f"<h3 style='margin-bottom:4px'>{title}</h3><table cellspacing='0'>{body}</table>"
