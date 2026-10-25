"""Step 1 — Planejar: Euler-Bernoulli predictions and sampling-rule check
before recording (planejamento R1), session naming and checklist (R2)."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from scipy.optimize import brentq

from vibrometry.beam import MATERIALS, CantileverBeam
from vibrometry.session import CHECKLIST

from . import theme
from .state import AppState
from .widgets import (
    Chip,
    OptSpin,
    Panel,
    curve,
    dspin,
    fmt,
    form,
    ispin,
    muted,
    plot,
    scroll,
    section,
    vbox,
    vline,
)

MATERIAL_LABELS = {
    "steel": "Aço inox",
    "polypropylene": "Polipropileno",
    "polystyrene": "Poliestireno",
    "aluminum_6351_t6": "Alumínio 6351-T6",
    "custom": "Personalizado",
}


class Metric(QWidget):
    """Label over a big number."""

    def __init__(self, label: str) -> None:
        super().__init__()
        lay = vbox(self, spacing=0)
        self.value = QLabel("—")
        self.value.setObjectName("Big")
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(muted(label, wrap=False))
        lay.addWidget(self.value)

    def set(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class PlanPage(QWidget):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.state = state
        self._loading = False

        # ---------------- inputs ---------------- #
        self.material = QComboBox()
        for key, label in MATERIAL_LABELS.items():
            self.material.addItem(label, key)
        self.E = dspin(193, 0.001, 1000, 3, 1, "GPa")
        self.rho = dspin(7850, 1, 30000, 0, 10, "kg/m³")
        self.L = dspin(300, 1, 5000, 1, 1, "mm")
        self.b = dspin(25, 0.1, 1000, 2, 0.5, "mm")
        self.t = dspin(1, 0.01, 100, 3, 0.1, "mm")
        self.mass = dspin(0, 0, 10000, 2, 0.5, "g")
        self.fps = dspin(240, 1, 100000, 2, 30, "fps")
        self.oversampling = dspin(10, 2, 100, 1, 1, "×")

        self.date = QLineEdit()
        self.exc = OptSpin("livre (sem excitação)", 0, 10000, 2, 1, "Hz")
        self.level = QLineEdit()
        self.rep = ispin(1, 1, 999)
        self.camera = QComboBox()
        self.camera.setEditable(True)
        self.camera.addItems(["osmo", "iphone", "sintetico"])
        self.suggested = QLabel()
        self.suggested.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.suggested.setStyleSheet(f"font-family: Consolas; color: {theme.TEXT};")
        self.suggested.setWordWrap(True)
        self.use_name = QPushButton("Usar como nome")
        self.copy_names = QPushButton("Copiar nomes")
        self.files = muted()
        self.files.setStyleSheet(f"font-family: Consolas; font-size: 8.5pt; color: {theme.MUTED};")
        # long names have no spaces to wrap at: don't let them widen the panel
        for lab in (self.suggested, self.files):
            lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Observações do ensaio…")
        self.notes.setFixedHeight(70)

        left = QWidget()
        ll = vbox(left, margins=0, spacing=6)
        p = Panel()
        p.lay.addWidget(section("Corpo de prova"))
        f = form()
        f.addRow("Material", self.material)
        f.addRow("Módulo E", self.E)
        f.addRow("Densidade ρ", self.rho)
        f.addRow("Comprimento livre L", self.L)
        f.addRow("Largura b", self.b)
        f.addRow("Espessura t", self.t)
        f.addRow("Massa na ponta", self.mass)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Meça L da linha de aperto até a ponta (L efetivo). "
                              "A massa na ponta inclui o acelerômetro, se montado."))
        p.lay.addWidget(section("Gravação"))
        f = form()
        f.addRow("Taxa de quadros", self.fps)
        f.addRow("Sobreamostragem", self.oversampling)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Regra do TCC1: f_max ≤ fps / sobreamostragem."))
        ll.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Sessão"))
        f = form()
        f.addRow("Data", self.date)
        f.addRow("Excitação", self.exc)
        f.addRow("Nível", self.level)
        f.addRow("Repetição", self.rep)
        f.addRow("Câmera", self.camera)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Nome sugerido"))
        p.lay.addWidget(self.suggested)
        p.lay.addLayout(_row(self.use_name, self.copy_names))
        p.lay.addWidget(self.files)
        p.lay.addWidget(self.notes)
        ll.addWidget(p)
        ll.addStretch(1)

        # ---------------- outputs ---------------- #
        self.m_f1 = Metric("f₁ (com massa)")
        self.m_f1_free = Metric("f₁ sem massa")
        self.m_f2 = Metric("f₂")
        self.m_f3 = Metric("f₃")
        self.m_limit = Metric("Limite fps / sobreamostragem")
        self.m_nyq = Metric("Nyquist")
        self.m_mb = Metric("Massa da régua m_b")
        self.m_meq = Metric("Massa equivalente m_eq")
        self.m_keq = Metric("Rigidez k_eq")
        self.m_fps_min = Metric("fps mínimo")
        self.m_tmax = Metric("t máx. p/ este fps")
        self.m_lmin = Metric("L mín. p/ este fps")
        self.verdict = Chip()
        self.verdict.setWordWrap(True)
        self.verdict.setStyleSheet("font-weight: 600;")

        cards = Panel()
        cards.lay.addWidget(section("Previsão (Euler-Bernoulli)"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(14)
        metrics = [self.m_f1, self.m_f1_free, self.m_f2, self.m_f3,
                   self.m_limit, self.m_nyq, self.m_fps_min, self.m_tmax,
                   self.m_mb, self.m_meq, self.m_keq, self.m_lmin]
        for i, m in enumerate(metrics):
            grid.addWidget(m, i // 4, i % 4)
        cards.lay.addLayout(grid)
        cards.lay.addWidget(self.verdict)

        self.mass_plot = plot("Massa na ponta [g]", "f₁ [Hz]")
        self.mass_plot.setMinimumHeight(220)
        mp = Panel()
        mp.lay.addWidget(section("Efeito de massa na ponta"))
        mp.lay.addWidget(self.mass_plot)

        self.checks: list[QCheckBox] = []
        cp = Panel()
        cp.lay.addWidget(section("Checklist antes da gravação"))
        for item in CHECKLIST:
            cb = QCheckBox(item)
            cb.toggled.connect(self._checklist_changed)
            self.checks.append(cb)
            cp.lay.addWidget(cb)

        right = QWidget()
        rl = vbox(right, spacing=12)
        rl.addWidget(cards)
        rl.addWidget(mp, 1)
        rl.addWidget(cp)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(scroll(left, 340))
        lay.addWidget(scroll(right), 1)

        # ---------------- wiring ---------------- #
        self.material.currentIndexChanged.connect(self._material_changed)
        for w in (self.E, self.rho, self.L, self.b, self.t, self.mass,
                  self.fps, self.oversampling, self.exc):
            w.valueChanged.connect(self._changed)
        self.rep.valueChanged.connect(self._changed)
        self.date.textEdited.connect(self._changed)
        self.level.textEdited.connect(self._changed)
        self.camera.currentTextChanged.connect(self._changed)
        self.notes.textChanged.connect(self._notes_changed)
        self.use_name.clicked.connect(self._use_name)
        self.copy_names.clicked.connect(self._copy_names)
        state.sessionReplaced.connect(self.load_session)
        self.load_session()

    # ------------------------------------------------------------------ #
    def load_session(self) -> None:
        self._loading = True
        s = self.state.session
        sp, m = s.specimen, s.meta
        i = self.material.findData(sp.material)
        self.material.setCurrentIndex(i if i >= 0 else self.material.count() - 1)
        self.E.setValue(sp.E_gpa)
        self.rho.setValue(sp.rho)
        self.L.setValue(sp.L_mm)
        self.b.setValue(sp.b_mm)
        self.t.setValue(sp.t_mm)
        self.mass.setValue(sp.tip_mass_g)
        self.fps.setValue(sp.fps)
        self.oversampling.setValue(sp.oversampling)
        self.date.setText(m.date)
        self.exc.put(m.excitation_hz)
        self.level.setText(m.level)
        self.rep.setValue(m.repetition)
        self.camera.setCurrentText(m.camera)
        self.notes.setPlainText(m.notes)
        for cb, v in zip(self.checks, m.checklist):
            cb.setChecked(bool(v))
        self._loading = False
        self._update()

    def _material_changed(self) -> None:
        key = self.material.currentData()
        if key in MATERIALS and not self._loading:
            self._loading = True
            self.E.setValue(MATERIALS[key]["E"] / 1e9)
            self.rho.setValue(MATERIALS[key]["rho"])
            self._loading = False
        self._changed()

    def _changed(self) -> None:
        if self._loading:
            return
        s = self.state.session
        sp, m = s.specimen, s.meta
        sp.material = self.material.currentData()
        sp.E_gpa, sp.rho = self.E.value(), self.rho.value()
        sp.L_mm, sp.b_mm, sp.t_mm = self.L.value(), self.b.value(), self.t.value()
        sp.tip_mass_g = self.mass.value()
        sp.fps, sp.oversampling = self.fps.value(), self.oversampling.value()
        m.date = self.date.text().strip()
        m.excitation_hz = self.exc.get()
        m.level = self.level.text().strip()
        m.repetition = self.rep.value()
        m.camera = self.camera.currentText().strip()
        self.state.mark_dirty()
        self.state.specimenChanged.emit()
        self._update()

    def _notes_changed(self) -> None:
        if not self._loading:
            self.state.session.meta.notes = self.notes.toPlainText()
            self.state.mark_dirty()

    def _checklist_changed(self) -> None:
        if not self._loading:
            self.state.session.meta.checklist = [cb.isChecked() for cb in self.checks]
            self.state.mark_dirty()

    def _use_name(self) -> None:
        self.state.session.name = self.state.session.suggested_name()
        self.state.mark_dirty()
        self.state.nameChanged.emit()
        self._update()

    def _copy_names(self) -> None:
        QGuiApplication.clipboard().setText(
            "\n".join(self.state.session.file_names().values()))
        self.state.message.emit("Nomes de arquivo copiados.")

    # ------------------------------------------------------------------ #
    def _update(self) -> None:
        s = self.state.session
        sp = s.specimen
        self.suggested.setText(s.suggested_name())
        self.files.setText("\n".join(s.file_names().values()))
        try:
            beam = sp.beam()
            f = [beam.natural_frequency(i) for i in (1, 2, 3)]
        except (ValueError, ZeroDivisionError):
            return
        m = sp.tip_mass_g / 1e3
        f1m = beam.mass_loaded_frequency(m)
        limit = sp.fps / sp.oversampling
        nyq = sp.fps / 2
        m_b = sp.rho * beam.area * beam.length

        ok = f1m <= limit
        self.m_f1.set(fmt(f1m, 2, "Hz"), theme.OK if ok else theme.BAD)
        self.m_f1_free.set(fmt(f[0], 2, "Hz"))
        self.m_f2.set(fmt(f[1], 1, "Hz"), theme.WARN if f[1] > nyq else None)
        self.m_f3.set(fmt(f[2], 1, "Hz"), theme.WARN if f[2] > nyq else None)
        self.m_limit.set(fmt(limit, 1, "Hz"))
        self.m_nyq.set(fmt(nyq, 1, "Hz"))
        self.m_mb.set(fmt(m_b * 1e3, 2, "g"))
        self.m_meq.set(fmt(beam.m_eq * 1e3, 2, "g"))
        self.m_keq.set(fmt(beam.k_eq, 2, "N/m"))
        self.m_fps_min.set(fmt(sp.oversampling * f1m, 0, "fps"))

        def f_of(L=None, t=None) -> float:
            bb = CantileverBeam((L or sp.L_mm) / 1e3, sp.b_mm / 1e3,
                                (t or sp.t_mm) / 1e3, sp.E_gpa * 1e9, sp.rho)
            return bb.mass_loaded_frequency(m) - limit

        self.m_tmax.set(_solve_text(lambda t: f_of(t=t), 1e-3, 100.0, "mm", 2))
        self.m_lmin.set(_solve_text(lambda L: -f_of(L=L), 1.0, 1e5, "mm", 0))

        parts = []
        if ok:
            parts.append(f"✓ f₁ = {fmt(f1m, 2)} Hz atende à regra (≤ {fmt(limit, 1)} Hz).")
        else:
            parts.append(f"✗ f₁ = {fmt(f1m, 2)} Hz excede fps/{fmt(sp.oversampling, 0)} = "
                         f"{fmt(limit, 1)} Hz: aumente o fps ou altere L/t.")
        if f1m > nyq:
            parts.append("f₁ acima de Nyquist: haverá aliasing.")
        exc_ok = not s.meta.excitation_hz or s.meta.excitation_hz <= limit
        if not exc_ok:
            parts.append(f"A excitação de {fmt(s.meta.excitation_hz, 1)} Hz excede o limite.")
        self.verdict.set("  ".join(parts), ok and exc_ok)
        self._plot_mass(beam, m, limit)

    def _plot_mass(self, beam: CantileverBeam, m: float, limit: float) -> None:
        pw = self.mass_plot
        pw.clear()
        m_max = max(0.02, 3 * beam.m_eq, 1.5 * m)
        masses = np.linspace(0, m_max, 200)
        freqs = [beam.mass_loaded_frequency(x) for x in masses]
        curve(pw, masses * 1e3, freqs, theme.ACCENT, width=2)
        lim = pg.InfiniteLine(pos=limit, angle=0, pen=pg.mkPen(
            theme.BAD, width=1, style=Qt.DashLine))
        lim.label = pg.InfLineLabel(lim, text=f"fps/{self.oversampling.value():g}",
                                    position=0.95, color=theme.BAD,
                                    anchors=[(1, 1), (1, 1)])
        pw.addItem(lim)
        sel = pg.ScatterPlotItem([m * 1e3], [beam.mass_loaded_frequency(m)], size=9,
                                 brush=pg.mkBrush(theme.ACCENT), pen=pg.mkPen(theme.SURFACE))
        pw.addItem(sel)
        mark = vline(theme.FAINT, Qt.DotLine)
        mark.setPos(m * 1e3)
        pw.addItem(mark)


def _row(*widgets) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(6)
    for w in widgets:
        lay.addWidget(w)
    lay.addStretch(1)
    return lay


def _solve_text(fn, lo: float, hi: float, unit: str, nd: int) -> str:
    try:
        a, b = fn(lo), fn(hi)
        if np.sign(a) == np.sign(b):
            return "—"
        return fmt(brentq(fn, lo, hi, xtol=1e-6), nd, unit)
    except (ValueError, ZeroDivisionError):
        return "—"
