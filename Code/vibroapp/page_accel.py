"""Step 3 — Acelerômetro: import, units, conversion to displacement and
modal summary of the reference sensor (planejamento R3, R6)."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QWidget,
)

from vibrometry.accelerometer import UNITS, guess_columns, guess_unit, read_table
from vibrometry.spectral import amplitude_spectrum
from vibrometry.workflow import accel_displacement_mm

from . import theme
from .state import AppState
from .widgets import (
    OptSpin,
    Panel,
    Table,
    curve,
    debounce,
    dspin,
    fmt,
    form,
    hbox,
    muted,
    plot,
    region,
    scroll,
    section,
    vbox,
    vline,
)

TABLE_FILTER = "Dados (*.csv *.txt *.tsv *.dat);;Todos (*.*)"


class AccelPage(QWidget):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.state = state
        self._loading = False

        # ---------------- controls ---------------- #
        self.open_btn = QPushButton("Abrir arquivo…")
        self.file_label = QLabel("Nenhum arquivo")
        self.file_label.setObjectName("Title")
        self.file_label.setWordWrap(True)
        self.file_info = muted()
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(96)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setStyleSheet(f"font-family: Consolas; font-size: 8.5pt; color: {theme.MUTED};")

        self.time_col = QComboBox()
        self.channel = QComboBox()
        self.fs = OptSpin("da coluna de tempo", 0, 1e7, 3, 100, "Hz")
        self.unit = QComboBox()
        self.unit.addItems(UNITS)
        self.sens = dspin(100, 0.001, 1e6, 3, 1, "mV/g")
        self.invert = QCheckBox("Inverter sinal (eixo oposto ao da imagem)")

        self.method = QComboBox()
        self.method.addItem("Frequência (recomendado)", "frequency")
        self.method.addItem("Tempo (passa-alta + trapézios)", "time")
        self.f_hp = dspin(1.0, 0.01, 1000, 2, 0.1, "Hz")
        self.f_lp = OptSpin("sem passa-baixa", 0, 1e5, 1, 5, "Hz")
        self.record_info = muted()

        controls = QWidget()
        cl = vbox(controls, spacing=8)
        p = Panel()
        p.lay.addWidget(self.open_btn)
        p.lay.addWidget(self.file_label)
        p.lay.addWidget(self.file_info)
        p.lay.addWidget(self.preview)
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Canal"))
        f = form()
        f.addRow("Tempo", self.time_col)
        f.addRow("Aceleração", self.channel)
        f.addRow("Taxa", self.fs)
        f.addRow("Unidade", self.unit)
        f.addRow("Sensibilidade", self.sens)
        p.lay.addLayout(f)
        p.lay.addWidget(self.invert)
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Conversão para deslocamento"))
        f = form()
        f.addRow("Método", self.method)
        f.addRow("Passa-alta", self.f_hp)
        f.addRow("Passa-baixa", self.f_lp)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Integração dupla com remoção de tendência e filtro "
                              "passa-alta; abaixo do corte, o deslocamento não é "
                              "recuperável pelo acelerômetro. Evite analisar o primeiro e "
                              "o último ~1/f_hp s do registro (2/f_hp s no método do "
                              "tempo): ali há efeito de borda."))
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Registro"))
        p.lay.addWidget(self.record_info)
        cl.addWidget(p)
        cl.addStretch(1)

        # ---------------- views ---------------- #
        self.acc_plot = plot("Tempo do acelerômetro [s]", "Aceleração [m/s²]")
        self.disp_plot = plot("Tempo do acelerômetro [s]", "Deslocamento [mm]")
        self.spec_plot = plot("Frequência [Hz]", "Amplitude", legend=True)
        self.region = region(theme.ACCEL)
        self.region.sigRegionChanged.connect(lambda: None if self._loading
                                             else self._window_timer.start())
        self.full_window = QPushButton("Janela inteira")
        self.full_window.setObjectName("Flat")
        self.full_window.clicked.connect(self._reset_window)
        self.window_label = muted("", wrap=False)
        self.modal_table = Table(["Sinal", "f [Hz]", "A", "ζ meia-pot.", "ζ decr. log.",
                                  "σ", "f prevista [Hz]", "Erro [%]"])
        self.spec_kind = QComboBox()
        self.spec_kind.addItems(["Deslocamento [mm]", "Aceleração [m/s²]"])
        self.spec_kind.currentIndexChanged.connect(self._draw)
        self.spec_log = QCheckBox("Escala log")
        self.spec_log.toggled.connect(lambda on: self.spec_plot.setLogMode(y=on))

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        sig_tab = QWidget()
        sl = vbox(sig_tab, spacing=6)
        sl.addWidget(self.acc_plot, 1)
        sl.addWidget(self.disp_plot, 1)
        sl.addLayout(hbox(self.window_label, None, self.full_window))
        sl.addWidget(self.modal_table)
        spec_tab = QWidget()
        pl = vbox(spec_tab, spacing=6)
        pl.addLayout(hbox(self.spec_kind, None, self.spec_log))
        pl.addWidget(self.spec_plot, 1)
        self.tabs.addTab(sig_tab, "Sinais")
        self.tabs.addTab(spec_tab, "Espectro")
        self.acc_plot.setXLink(self.disp_plot)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(scroll(controls, 340))
        lay.addWidget(self.tabs, 1)

        self._window_timer = debounce(self, 200, self._apply_window)

        # ---------------- wiring ---------------- #
        self.open_btn.clicked.connect(self.choose_file)
        for w in (self.time_col, self.channel, self.unit, self.method):
            w.currentIndexChanged.connect(self._changed)
        for w in (self.fs, self.sens, self.f_hp, self.f_lp):
            w.valueChanged.connect(self._changed)
        self.invert.toggled.connect(self._changed)
        state.sessionReplaced.connect(self.load_session)
        state.accelChanged.connect(self._draw)
        self.load_session()

    # ------------------------------------------------------------------ #
    def load_session(self) -> None:
        a = self.state.session.accel
        self._loading = True
        self.fs.put(a.fs)
        self.unit.setCurrentText(a.unit)
        self.sens.setValue(a.sensitivity_mv_per_g)
        self.invert.setChecked(a.invert)
        self.method.setCurrentIndex(max(0, self.method.findData(a.integration)))
        self.f_hp.setValue(a.f_hp)
        self.f_lp.put(a.f_lp)
        self._loading = False
        if a.path and os.path.exists(a.path):
            self._load_file(a.path, from_session=True)
        else:
            self._fill_columns([])
            self.file_label.setText("Arquivo não encontrado" if a.path else "Nenhum arquivo")
            self.file_info.setText(a.path or "")
            self.preview.setPlainText("")
            self.state.set_table(None)
        self._update_enabled()

    def choose_file(self) -> None:
        s = self.state.session
        start = os.path.dirname(s.accel.path or s.video.path or s.file or "")
        path, _ = QFileDialog.getOpenFileName(self, "Abrir dados do acelerômetro",
                                              start, TABLE_FILTER)
        if path:
            s.accel.path = path
            s.accel.window = None
            self.state.mark_dirty()
            self._load_file(path, from_session=False)

    def _load_file(self, path: str, from_session: bool) -> None:
        try:
            table = read_table(path)
        except Exception as exc:
            QMessageBox.warning(self, "Acelerômetro", f"Não foi possível ler o arquivo:\n{exc}")
            return
        a = self.state.session.accel
        self.file_label.setText(Path(path).name)
        delim = {"": "espaço", "\t": "tab"}.get(table.delimiter, f"'{table.delimiter}'")
        self.file_info.setText(f"{table.data.shape[0]} linhas · {table.data.shape[1]} colunas · "
                               f"separador {delim} · decimal '{table.decimal}' · "
                               f"{table.header_lines} linha(s) de cabeçalho")
        self.preview.setPlainText("\n".join(table.preview))
        self._fill_columns(table.columns)
        self._loading = True
        if not from_session:
            tcol, ch = guess_columns(table)
            a.time_column, a.channel = tcol, ch
            a.unit = guess_unit(table.columns[ch])
            self.unit.setCurrentText(a.unit)
        self.time_col.setCurrentIndex(0 if a.time_column is None else a.time_column + 1)
        self.channel.setCurrentIndex(min(a.channel, len(table.columns) - 1))
        self._loading = False
        self._update_enabled()
        self.state.set_table(table)

    def _fill_columns(self, names: list[str]) -> None:
        self._loading = True
        self.time_col.clear()
        self.time_col.addItem("— sem coluna (usar taxa) —")
        self.time_col.addItems(names)
        self.channel.clear()
        self.channel.addItems(names)
        self._loading = False

    def _update_enabled(self) -> None:
        self.sens.setEnabled(self.unit.currentText() in ("mV", "V"))

    def _changed(self) -> None:
        if self._loading:
            return
        a = self.state.session.accel
        a.time_column = None if self.time_col.currentIndex() <= 0 else self.time_col.currentIndex() - 1
        a.channel = max(0, self.channel.currentIndex())
        a.fs = self.fs.get()
        a.unit = self.unit.currentText()
        a.sensitivity_mv_per_g = self.sens.value()
        a.invert = self.invert.isChecked()
        a.integration = self.method.currentData()
        a.f_hp = self.f_hp.value()
        a.f_lp = self.f_lp.get()
        self._update_enabled()
        self.state.mark_dirty()
        if self.state.table is not None:
            self.state.rebuild_accel()

    def _apply_window(self) -> None:
        rec = self.state.accel
        if rec is None:
            return
        t0, t1 = self.region.getRegion()
        full = t0 <= rec.t[0] + 1e-9 and t1 >= rec.t[-1] - 1e-9
        self.state.session.accel.window = None if full else [float(t0), float(t1)]
        self.state.mark_dirty()
        self.state.rebuild_accel()

    def _reset_window(self) -> None:
        self.state.session.accel.window = None
        self.state.mark_dirty()
        self.state.rebuild_accel()

    # ------------------------------------------------------------------ #
    def _draw(self) -> None:
        for p in (self.acc_plot, self.disp_plot, self.spec_plot):
            p.clear()
        self.modal_table.set_rows([])
        rec = self.state.accel
        if rec is None:
            self.record_info.setText("")
            self.window_label.setText("")
            return
        s = self.state.session
        disp = accel_displacement_mm(s, rec)
        curve(self.acc_plot, rec.t, rec.a, theme.ACCEL, width=1)
        curve(self.disp_plot, rec.t, disp, theme.ACCEL)
        self.disp_plot.addItem(self.region, ignoreBounds=True)
        ms = self.state.accel_summary
        self._loading = True
        self.region.setBounds((rec.t[0], rec.t[-1]))
        if ms is not None:
            self.region.setRegion(ms.window)
        self._loading = False

        self.record_info.setText(
            f"{rec.label}\n{fmt(rec.fs, 2)} Hz · {rec.t.size} amostras · "
            f"{fmt(rec.duration, 2)} s\n"
            f"jitter da coluna de tempo {fmt(rec.jitter_percent, 3)} %"
            + (" (reamostrado em grade uniforme)" if rec.resampled else "")
            + f"\nRMS {fmt(float(np.std(rec.a)), 4)} m/s² · pico "
              f"{fmt(float(np.abs(rec.a).max()), 3)} m/s²")

        if ms is not None:
            self.window_label.setText(f"Janela {fmt(ms.window[0], 2)}–{fmt(ms.window[1], 2)} s"
                                      " (arraste a faixa laranja)")
            err = ms.error_predicted_percent
            crit = s.compare.crit_eb_pct
            self.modal_table.set_rows([[
                "deslocamento", fmt(ms.f_n, 3), fmt(ms.amplitude, 4),
                fmt(ms.zeta_half_power, 4), fmt(ms.zeta_log_decrement, 4),
                fmt(ms.std, 4), fmt(ms.f_predicted, 2),
                (fmt(err, 2), theme.OK if abs(err) <= crit else theme.BAD)
                if err is not None else "—"]])
            self.modal_table.fit_height(2)

        # spectrum inside the window
        w = s.accel.window
        m = (rec.t >= w[0]) & (rec.t <= w[1]) if w else np.ones(rec.t.size, bool)
        is_disp = self.spec_kind.currentIndex() == 0
        x = disp[m] if is_disp else rec.a[m]
        if x.size > 8:
            f, amp = amplitude_spectrum(x, rec.fs, zero_pad_factor=4)
            curve(self.spec_plot, f, amp, theme.ACCEL, "acelerômetro")
            self.spec_plot.setLabel("left", "Amplitude [mm]" if is_disp else "Amplitude [m/s²]")
            if ms is not None and ms.f_n:
                ln = vline(theme.ACCEL, Qt.DashLine, f"{fmt(ms.f_n, 2)} Hz")
                ln.setPos(ms.f_n)
                self.spec_plot.addItem(ln)
            f_hi = 5 * ms.f_n if (ms is not None and ms.f_n) else rec.fs / 2
            self.spec_plot.setXRange(0, min(rec.fs / 2, max(f_hi, 10)))
