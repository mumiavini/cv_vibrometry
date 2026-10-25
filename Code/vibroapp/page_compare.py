"""Step 4 — Comparar: synchronisation, optical vs accelerometer metrics and
acceptance criteria (planejamento R6, R7, sections 8.7–8.10 and 11)."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QWidget,
)

from vibrometry.analysis import coherence_and_frf
from vibrometry.spectral import amplitude_spectrum
from vibrometry.workflow import accel_edge_warning, auto_sync

from . import theme
from .state import AppState
from .widgets import (
    OptSpin,
    Panel,
    Table,
    curve,
    debounce,
    dspin,
    empty_state,
    fmt,
    form,
    hbox,
    muted,
    plot,
    region,
    scroll,
    section,
    status_cell,
    vbox,
    vline,
)


def _alpha(color: str, a: int) -> QColor:
    q = QColor(color)
    q.setAlpha(a)
    return q


class ComparePage(QWidget):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.state = state
        self._loading = False

        # ---------------- controls ---------------- #
        self.roi = QComboBox()
        self.domain = QComboBox()
        self.domain.addItem("Deslocamento", "displacement")
        self.domain.addItem("Aceleração", "acceleration")
        self.f_hp = OptSpin("sem passa-alta", 0, 1000, 2, 0.1, "Hz")
        self.f_lp = OptSpin("sem passa-baixa", 0, 1e5, 1, 5, "Hz")

        self.sync_mode = QComboBox()
        self.sync_mode.addItem("Impacto / início da vibração", "impact")
        self.sync_mode.addItem("Correlação da forma de onda", "waveform")
        self.sync_mode.addItem("Manual", "manual")
        self.sync_btn = QPushButton("Sincronizar")
        self.sync_btn.setObjectName("Primary")
        self.drift_btn = QPushButton("Estimar deriva")
        self.offset = dspin(0, -1e5, 1e5, 5, 0.001, "s")
        self.drift = dspin(0, -1e5, 1e5, 2, 1, "ppm")
        self.sync_info = QLabel()
        self.sync_info.setWordWrap(True)
        self.sync_info.setObjectName("Muted")

        self.f_analysis = OptSpin("automática", 0, 1e5, 4, 0.1, "Hz")
        self.w0 = dspin(0, -1e6, 1e6, 3, 0.1, "s")
        self.w1 = dspin(0, -1e6, 1e6, 3, 0.1, "s")
        self.full_window = QPushButton("Janela inteira")
        self.full_window.setObjectName("Flat")

        self.c_freq = dspin(1, 0, 100, 2, 0.1, "%")
        self.c_amp = dspin(10, 0, 100, 2, 0.5, "%")
        self.c_phase = dspin(10, 0, 180, 1, 1, "°")
        self.c_eb = dspin(5, 0, 100, 2, 0.5, "%")

        controls = QWidget()
        cl = vbox(controls, spacing=8)
        p = Panel()
        p.lay.addWidget(section("Sinais"))
        f = form()
        f.addRow("ROI do vídeo", self.roi)
        f.addRow("Comparar em", self.domain)
        f.addRow("Passa-alta", self.f_hp)
        f.addRow("Passa-baixa", self.f_lp)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("O mesmo filtro é aplicado aos dois sinais."))
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Sincronismo"))
        f = form()
        f.addRow("Método", self.sync_mode)
        p.lay.addLayout(f)
        p.lay.addLayout(hbox(self.sync_btn, self.drift_btn))
        f = form()
        f.addRow("Atraso do acel.", self.offset)
        f.addRow("Deriva", self.drift)
        p.lay.addLayout(f)
        p.lay.addWidget(self.sync_info)
        p.lay.addWidget(muted("t_acel = atraso + (1 + deriva) · t_vídeo. Um quadro a "
                              "240 fps em 20 Hz equivale a ~30° de fase."))
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Análise"))
        f = form()
        f.addRow("Frequência", self.f_analysis)
        f.addRow("Janela de", self.w0)
        f.addRow("até", self.w1)
        p.lay.addLayout(f)
        p.lay.addWidget(self.full_window)
        p.lay.addWidget(muted("Use a frequência de excitação nos ensaios forçados; "
                              "amplitude e fase são ajustadas nela."))
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Critérios de aceitação"))
        f = form()
        f.addRow("Frequência ≤", self.c_freq)
        f.addRow("Amplitude ≤", self.c_amp)
        f.addRow("Fase ≤", self.c_phase)
        f.addRow("Euler-Bernoulli ≤", self.c_eb)
        p.lay.addLayout(f)
        cl.addWidget(p)
        cl.addStretch(1)

        # ---------------- views ---------------- #
        self.overview = plot("Tempo do vídeo [s]", "", legend=True)
        self.detail = plot("Tempo do vídeo [s]", "")
        self.region = region()
        self.region.sigRegionChanged.connect(self._region_moved)
        self.spec = plot("Frequência [Hz]", "Amplitude", legend=True)
        self.scatter = plot("Acelerômetro", "Vídeo", legend=True)
        self.scatter.getPlotItem().setAspectLocked(True)
        self.coh = plot("Frequência [Hz]", "Coerência γ²")
        self.frf = plot("Frequência [Hz]", "|H₁| vídeo/acel.")
        self.frf.setLogMode(y=True)
        self.frf.setXLink(self.coh)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        t_tab = QWidget()
        tl = vbox(t_tab, spacing=6)
        tl.addWidget(self.overview, 3)
        tl.addWidget(self.detail, 2)
        c_tab = QWidget()
        clay = vbox(c_tab, spacing=6)
        clay.addWidget(self.coh)
        clay.addWidget(self.frf)
        self.tabs.addTab(t_tab, "Tempo")
        self.tabs.addTab(self.spec, "Espectro")
        self.tabs.addTab(self.scatter, "Dispersão")
        self.tabs.addTab(c_tab, "Coerência / FRF")

        self.metrics = Table(["Grandeza", "Vídeo", "Acelerômetro", "Diferença", "Critério"])
        self.verdict = QLabel()
        self.verdict.setStyleSheet("font-weight: 600;")
        results = QWidget()
        rl = vbox(results, spacing=6)
        rl.addWidget(self.tabs, 1)
        rl.addWidget(self.verdict)
        rl.addWidget(self.metrics)

        self.stack = QStackedWidget()
        self.empty = empty_state("Processe o vídeo (passo 2) e carregue o acelerômetro "
                                 "(passo 3) para comparar.")
        self.stack.addWidget(self.empty)
        self.stack.addWidget(results)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(scroll(controls, 340))
        lay.addWidget(self.stack, 1)

        self._recompute = debounce(self, 150, self.state.recompare)
        self._region_timer = debounce(self, 200, self._apply_region)

        # ---------------- wiring ---------------- #
        self.roi.currentIndexChanged.connect(self._changed)
        self.domain.currentIndexChanged.connect(self._changed)
        self.sync_mode.currentIndexChanged.connect(self._changed)
        for w in (self.f_hp, self.f_lp, self.offset, self.drift, self.f_analysis,
                  self.c_freq, self.c_amp, self.c_phase, self.c_eb):
            w.valueChanged.connect(self._changed)
        self.w0.valueChanged.connect(self._window_edited)
        self.w1.valueChanged.connect(self._window_edited)
        self.full_window.clicked.connect(self._reset_window)
        self.sync_btn.clicked.connect(lambda: self._sync(False))
        self.drift_btn.clicked.connect(lambda: self._sync(True))
        state.sessionReplaced.connect(self.load_session)
        state.analysisChanged.connect(self._fill_rois)
        state.comparisonChanged.connect(self._draw)
        self.load_session()

    # ------------------------------------------------------------------ #
    def load_session(self) -> None:
        c = self.state.session.compare
        self._loading = True
        self.domain.setCurrentIndex(max(0, self.domain.findData(c.domain)))
        self.f_hp.put(c.f_hp)
        self.f_lp.put(c.f_lp)
        self.sync_mode.setCurrentIndex(max(0, self.sync_mode.findData(c.sync_mode)))
        self.offset.setValue(c.offset_s)
        self.drift.setValue(c.drift_ppm)
        self.f_analysis.put(c.f_analysis)
        self.c_freq.setValue(c.crit_freq_pct)
        self.c_amp.setValue(c.crit_amp_pct)
        self.c_phase.setValue(c.crit_phase_deg)
        self.c_eb.setValue(c.crit_eb_pct)
        self._loading = False
        self.sync_info.setText("")
        self._fill_rois()

    def _fill_rois(self) -> None:
        a = self.state.analysis
        names = list(a.signals) if a is not None else []
        self._loading = True
        self.roi.clear()
        self.roi.addItems(names)
        want = self.state.session.compare.roi
        if want in names:
            self.roi.setCurrentText(want)
        self._loading = False

    def _changed(self) -> None:
        if self._loading:
            return
        c = self.state.session.compare
        c.roi = self.roi.currentText() or None
        c.domain = self.domain.currentData()
        c.f_hp = self.f_hp.get()
        c.f_lp = self.f_lp.get()
        c.sync_mode = self.sync_mode.currentData()
        c.offset_s = self.offset.value()
        c.drift_ppm = self.drift.value()
        c.f_analysis = self.f_analysis.get()
        c.crit_freq_pct, c.crit_amp_pct = self.c_freq.value(), self.c_amp.value()
        c.crit_phase_deg, c.crit_eb_pct = self.c_phase.value(), self.c_eb.value()
        manual = c.sync_mode == "manual"
        self.sync_btn.setEnabled(not manual)
        self.drift_btn.setEnabled(not manual)
        self.state.mark_dirty()
        self._recompute.start()

    def _window_edited(self) -> None:
        if self._loading:
            return
        t0, t1 = sorted((self.w0.value(), self.w1.value()))
        self.state.session.compare.window = [t0, t1]
        self.state.mark_dirty()
        self._recompute.start()

    def _region_moved(self) -> None:
        if not self._loading:
            self._region_timer.start()

    def _apply_region(self) -> None:
        t0, t1 = self.region.getRegion()
        self.state.session.compare.window = [float(t0), float(t1)]
        self.state.mark_dirty()
        self.state.recompare()

    def _reset_window(self) -> None:
        self.state.session.compare.window = None
        self.state.mark_dirty()
        self.state.recompare()

    def _sync(self, with_drift: bool) -> None:
        s = self.state
        if s.analysis is None or s.accel is None:
            return
        try:
            sync, drift = auto_sync(s.session, s.analysis, s.accel, with_drift=with_drift)
        except Exception as exc:
            QMessageBox.warning(self, "Sincronismo", str(exc))
            return
        self._loading = True
        self.offset.setValue(s.session.compare.offset_s)
        self.drift.setValue(s.session.compare.drift_ppm)
        self._loading = False
        lines = [f"Correlação no pico: r = {fmt(sync.correlation, 4)}"]
        color = theme.OK if abs(sync.correlation) > 0.8 else theme.WARN
        if sync.inverted:
            lines.append("⚠ Melhor ajuste com polaridade invertida: verifique o eixo do "
                         "acelerômetro (opção 'Inverter sinal' no passo 3).")
            color = theme.WARN
        if drift is not None:
            lines.append(f"Atraso no início {fmt(drift.offset_start, 5)} s (r = "
                         f"{fmt(drift.corr_start, 3)}); no fim {fmt(drift.offset_end, 5)} s "
                         f"(r = {fmt(drift.corr_end, 3)}) → deriva {fmt(drift.drift_ppm, 1)} ppm")
        self.sync_info.setText("\n".join(lines))
        self.sync_info.setStyleSheet(f"color: {color};")
        s.mark_dirty()
        s.recompare()

    # ------------------------------------------------------------------ #
    def _draw(self) -> None:
        cmp = self.state.comparison
        for p in (self.overview, self.detail, self.spec, self.scatter, self.coh, self.frf):
            p.clear()
        if cmp is None:
            self.stack.setCurrentIndex(0)
            return
        self.stack.setCurrentIndex(1)
        dom = "Deslocamento" if cmp.domain == "displacement" else "Aceleração"
        lab_v = f"vídeo [{cmp.unit_video}]"
        lab_a = f"acelerômetro [{cmp.unit_accel}]"
        self.overview.setLabel("left", dom)
        self.detail.setLabel("left", dom)
        curve(self.overview, cmp.t, cmp.video, theme.VIDEO, lab_v)
        curve(self.overview, cmp.t, cmp.accel, theme.ACCEL, lab_a)
        self.overview.addItem(self.region, ignoreBounds=True)
        self._loading = True
        valid = np.isfinite(cmp.video) & np.isfinite(cmp.accel)
        if valid.any():
            self.region.setBounds((cmp.t[valid][0], cmp.t[valid][-1]))
        self.region.setRegion(cmp.window)
        self.w0.setValue(cmp.window[0])
        self.w1.setValue(cmp.window[1])
        self._loading = False

        m = cmp.window_mask()
        mt = cmp.metrics
        curve(self.detail, cmp.t[m], cmp.video[m], theme.VIDEO, width=1.6)
        curve(self.detail, cmp.t[m], cmp.accel[m], theme.ACCEL, width=1.6)
        if mt is not None and mt.f_common:
            mid = 0.5 * (cmp.window[0] + cmp.window[1])
            half = min(4.0 / mt.f_common, 0.5 * (cmp.window[1] - cmp.window[0]))
            self.detail.setXRange(mid - half, mid + half, padding=0)

        # spectra in the window
        if m.sum() > 16:
            for x, c, lab in ((cmp.video, theme.VIDEO, lab_v), (cmp.accel, theme.ACCEL, lab_a)):
                f, a = amplitude_spectrum(x[m], cmp.fs)
                curve(self.spec, f, a, c, lab)
            if mt is not None and mt.f_common:
                ln = vline(theme.FAINT, Qt.DashLine, f"{fmt(mt.f_common, 3)} Hz")
                ln.setPos(mt.f_common)
                self.spec.addItem(ln)
                self.spec.setXRange(0, min(cmp.fs / 2, 5 * mt.f_common))

            # scatter
            av, vv = cmp.accel[m], cmp.video[m]
            self.scatter.plot(av, vv, pen=None, symbol="o", symbolSize=3,
                              symbolBrush=pg.mkBrush(_alpha(theme.VIDEO, 110)),
                              symbolPen=None)
            lim = float(np.nanmax(np.abs(np.concatenate([av, vv])))) * 1.05
            curve(self.scatter, [-lim, lim], [-lim, lim], theme.FAINT, "1:1",
                  style=Qt.DashLine)
            if mt is not None:
                curve(self.scatter, [-lim, lim], [-mt.gain * lim, mt.gain * lim], theme.BAD,
                      f"ajuste: {fmt(mt.gain, 3)}")
            self.scatter.setLabel("bottom", lab_a)
            self.scatter.setLabel("left", lab_v)

            # coherence / FRF
            fq, coh, h1 = coherence_and_frf(cmp.accel[m], cmp.video[m], cmp.fs)
            curve(self.coh, fq, coh, theme.VIDEO)
            curve(self.frf, fq[1:], np.maximum(h1[1:], 1e-12), theme.VIDEO)
            self.coh.setYRange(0, 1.05)
            if mt is not None and mt.f_common:
                self.coh.setXRange(0, min(cmp.fs / 2, 5 * mt.f_common))

        self._fill_metrics(cmp)

    def _fill_metrics(self, cmp) -> None:
        mt = cmp.metrics
        c = self.state.session.compare
        if mt is None:
            self.metrics.set_rows([["Janela muito curta ou sem sobreposição", "", "", "", ""]])
            self.verdict.setText("")
            return
        uv, ua = cmp.unit_video, cmp.unit_accel

        def check(val, lim):
            return status_cell(None) if val is None else status_cell(abs(val) <= lim)

        amp_ok = cmp.units_match
        rows = [
            ["Frequência [Hz]", fmt(mt.f_test, 4), fmt(mt.f_ref, 4),
             fmt(mt.freq_error_percent, 3, "%"), check(mt.freq_error_percent, c.crit_freq_pct)],
            [f"Amplitude @ {fmt(mt.f_common, 3)} Hz", fmt(mt.amp_test, 4, uv),
             fmt(mt.amp_ref, 4, ua),
             fmt(mt.amp_error_percent, 2, "%") if amp_ok else "unidades diferentes",
             check(mt.amp_error_percent, c.crit_amp_pct) if amp_ok
             else status_cell(None, "defina a escala")],
            ["Fase [°]", fmt(mt.phase_test_deg, 2), fmt(mt.phase_ref_deg, 2),
             fmt(mt.phase_diff_deg, 2, "°"), check(mt.phase_diff_deg, c.crit_phase_deg)],
            ["RMS", fmt(mt.rms_test, 4, uv), fmt(mt.rms_ref, 4, ua),
             fmt(mt.rms_error_percent, 2, "%") if amp_ok else "—", status_cell(None, "")],
            ["R² do ajuste senoidal", fmt(mt.r2_test, 4), fmt(mt.r2_ref, 4), "",
             status_cell(None, "")],
            ["Correlação r / NRMSE", "", "", f"{fmt(mt.pearson_r, 4)} / "
             f"{fmt(mt.nrmse_percent, 2)} %" if amp_ok else fmt(mt.pearson_r, 4),
             status_cell(None, "")],
            ["Ganho (inclinação) / coerência", "", "",
             f"{fmt(mt.gain, 4)} / {fmt(mt.coherence, 4)}", status_cell(None, "")],
        ]
        a = self.state.analysis
        if a is not None and cmp.roi in a.modal:
            ms = a.modal[cmp.roi]
            acc = self.state.accel_summary
            if ms.f_predicted:
                rows.append(["f₁ × Euler-Bernoulli [Hz]", fmt(ms.f_n, 3),
                             fmt(acc.f_n if acc else None, 3),
                             f"prev. {fmt(ms.f_predicted, 3)} → "
                             f"{fmt(ms.error_predicted_percent, 2)} %",
                             check(ms.error_predicted_percent, c.crit_eb_pct)])
        self.metrics.set_rows(rows)
        self.metrics.fit_height(len(rows))
        checks = [r[4] for r in rows if isinstance(r[4], tuple) and r[4][1] in (theme.OK, theme.BAD)]
        n_ok = sum(1 for _, col in checks if col == theme.OK)
        edge = (accel_edge_warning(self.state.session, cmp, self.state.accel)
                if self.state.accel is not None else None)
        if checks:
            all_ok = n_ok == len(checks)
            text = (f"{n_ok} de {len(checks)} critérios atendidos · janela "
                    f"{fmt(cmp.window[0], 2)}–{fmt(cmp.window[1], 2)} s · "
                    f"atraso {fmt(cmp.offset_s, 5)} s")
            if edge:
                text += f"\n⚠ {edge}"
            self.verdict.setText(text)
            self.verdict.setStyleSheet(f"font-weight: 600; color: "
                                       f"{theme.OK if all_ok and not edge else theme.BAD if not all_ok else theme.WARN};")
