"""Step 1 — Planejar: Euler-Bernoulli predictions and sampling-rule check
before recording (planejamento R1), session naming and checklist (R2)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
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
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from scipy.optimize import brentq

from vibrometry.beam import MATERIALS, CantileverBeam
from vibrometry.session import CHECKLIST, SUPPORTS

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


class ItemTable(QTableWidget):
    """Small editable table (springs, lumped masses). Columns flagged numeric
    are parsed as floats (comma accepted); anything unreadable becomes 0."""

    edited = Signal()

    def __init__(self, headers: list[str], numeric: list[bool]) -> None:
        super().__init__(0, len(headers))
        self.numeric = numeric
        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(26)
        self.horizontalHeader().setStretchLastSection(True)
        self.setMinimumHeight(80)
        self.setMaximumHeight(150)
        self.itemChanged.connect(lambda _=None: self.edited.emit())

    def set_rows(self, rows: list[list]) -> None:
        self.blockSignals(True)
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                self.setItem(i, j, QTableWidgetItem(_cell_text(v, self.numeric[j])))
        self.blockSignals(False)

    def add_row(self, values: list) -> None:
        i = self.rowCount()
        self.blockSignals(True)
        self.insertRow(i)
        for j, v in enumerate(values):
            self.setItem(i, j, QTableWidgetItem(_cell_text(v, self.numeric[j])))
        self.blockSignals(False)
        self.edited.emit()

    def remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.selectedIndexes()}, reverse=True)
        if not rows and self.rowCount():
            rows = [self.rowCount() - 1]
        for r in rows:
            self.removeRow(r)
        if rows:
            self.edited.emit()

    def rows(self) -> list[list]:
        out = []
        for i in range(self.rowCount()):
            row = []
            for j in range(self.columnCount()):
                it = self.item(i, j)
                txt = it.text().strip() if it else ""
                row.append(_to_float(txt) if self.numeric[j] else txt)
            out.append(row)
        return out


def _cell_text(v, numeric: bool) -> str:
    if not numeric:
        return str(v)
    return f"{float(v):g}"


def _to_float(txt: str) -> float:
    try:
        return float(txt.replace(",", "."))
    except ValueError:
        return 0.0


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
        self.support = QComboBox()
        for key, label in SUPPORTS.items():
            self.support.addItem(label, key)
        self.root_k = OptSpin("não definida", 0, 1e9, 2, 10, "N·m/rad")
        self.springs = ItemTable(["Nome", "x [mm]", "k [N/m]", "m mola [g]", "ferragens [g]"],
                                 [False, True, True, True, True])
        self.add_spring = QPushButton("+ Mola")
        self.del_spring = QPushButton("Remover")
        self.del_spring.setObjectName("Flat")
        self.masses = ItemTable(["Nome", "x [mm]", "massa [g]"], [False, True, True])
        self.add_mass = QPushButton("+ Massa")
        self.del_mass = QPushButton("Remover")
        self.del_mass.setObjectName("Flat")
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
        p.lay.addWidget(section("Apoio e elementos"))
        f = form()
        f.addRow("Apoio na raiz", self.support)
        f.addRow("Rigidez torcional", self.root_k)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Molas e massas pontuais (ex.: acelerômetro), com a posição x "
                              "medida a partir da raiz. Massa efetiva da mola ≈ ⅓ da massa "
                              "da mola, somada às ferragens (parafuso, porcas, gancho) em x. "
                              "Sem nenhuma mola ou massa e apoio engastado vale o modelo "
                              "fechado de viga engastada."))
        p.lay.addWidget(self.springs)
        p.lay.addLayout(_row(self.add_spring, self.del_spring))
        p.lay.addWidget(self.masses)
        p.lay.addLayout(_row(self.add_mass, self.del_mass))
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
        self.cards_title = section("Previsão (Euler-Bernoulli)")
        cards.lay.addWidget(self.cards_title)
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
        self.support.currentIndexChanged.connect(self._changed)
        self.root_k.valueChanged.connect(self._changed)
        self.springs.edited.connect(self._changed)
        self.masses.edited.connect(self._changed)
        self.add_spring.clicked.connect(
            lambda: self.springs.add_row(["mola", self.L.value(), 1000, 0, 0]))
        self.del_spring.clicked.connect(self.springs.remove_selected)
        self.add_mass.clicked.connect(
            lambda: self.masses.add_row(["massa", self.L.value(), 0]))
        self.del_mass.clicked.connect(self.masses.remove_selected)
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
        j = self.support.findData(sp.support)
        self.support.setCurrentIndex(j if j >= 0 else 0)
        self.root_k.put(sp.root_stiffness)
        self.root_k.setEnabled(sp.support == "rotational")
        self.springs.set_rows([[d.get("name", ""), d.get("x_mm", 0), d.get("k_n_m", 0),
                                d.get("mass_g", 0), d.get("hardware_g", 0)]
                               for d in sp.springs])
        self.masses.set_rows([[d.get("name", ""), d.get("x_mm", 0), d.get("mass_g", 0)]
                              for d in sp.masses])
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
        sp.support = self.support.currentData()
        self.root_k.setEnabled(sp.support == "rotational")
        sp.root_stiffness = self.root_k.get() if sp.support == "rotational" else None
        sp.springs = [{"name": r[0], "x_mm": r[1], "k_n_m": r[2],
                       "mass_g": r[3], "hardware_g": r[4]} for r in self.springs.rows()]
        sp.masses = [{"name": r[0], "x_mm": r[1], "mass_g": r[2]}
                     for r in self.masses.rows()]
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
        self.cards_title.setText(f"Previsão ({sp.model_label()})")
        try:
            beam = sp.beam()
            f = sp.predicted_frequencies(3)
            if sp.uses_fe:
                fe = sp.fe_model()
                f_free = sp.fe_model(masses=False).elastic_frequency(1)
                m_eq, k_eq = fe.m_eq, fe.k_eq
            else:
                f_free = beam.natural_frequency(1)
                m_eq, k_eq = beam.m_eq, beam.k_eq
        except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
            for w in (self.m_f1, self.m_f1_free, self.m_f2, self.m_f3, self.m_meq,
                      self.m_keq, self.m_fps_min, self.m_tmax, self.m_lmin):
                w.set("—")
            self.verdict.set("Parâmetros inválidos para o modelo (posição fora da barra ou rigidez torcional não definida).", False)
            return
        m = sp.tip_mass_g / 1e3
        f1m = f[0]
        limit = sp.fps / sp.oversampling
        nyq = sp.fps / 2
        m_b = sp.rho * beam.area * beam.length

        ok = f1m <= limit
        self.m_f1.set(fmt(f1m, 2, "Hz"), theme.OK if ok else theme.BAD)
        self.m_f1_free.set(fmt(f_free, 2, "Hz"))
        self.m_f2.set(fmt(f[1], 1, "Hz"), theme.WARN if f[1] > nyq else None)
        self.m_f3.set(fmt(f[2], 1, "Hz"), theme.WARN if f[2] > nyq else None)
        self.m_limit.set(fmt(limit, 1, "Hz"))
        self.m_nyq.set(fmt(nyq, 1, "Hz"))
        self.m_mb.set(fmt(m_b * 1e3, 2, "g"))
        self.m_meq.set(fmt(m_eq * 1e3, 2, "g"))
        self.m_keq.set(fmt(k_eq, 2, "N/m"))
        self.m_fps_min.set(fmt(sp.oversampling * f1m, 0, "fps"))

        if sp.uses_fe:
            # each evaluation is a finite-element solve: no root finding while typing
            self.m_tmax.set("—")
            self.m_lmin.set("—")
        else:
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
        no_mass = [d.get("name") or "mola" for d in sp.springs
                   if not d.get("mass_g") and not d.get("hardware_g")]
        warn = bool(no_mass)
        if no_mass:
            parts.append("Massa não informada para " + ", ".join(no_mass)
                         + ": a massa efetiva da mola e das ferragens baixa f₁ e não está "
                           "no cálculo.")
        if sp.support == "pinned" and not sp.springs:
            parts.append("Apoio articulado sem mola: o modo 1 é a rotação de corpo rígido (~0 Hz).")
        self.verdict.set("  ".join(parts), ok and exc_ok and not warn)
        self._plot_mass(sp, limit)

    def _plot_mass(self, sp, limit: float) -> None:
        pw = self.mass_plot
        pw.clear()
        if sp.uses_fe:
            self._plot_mass_fe(sp, limit)
            return
        beam = sp.beam()
        m = sp.tip_mass_g / 1e3
        pw.setLabel("bottom", "Massa na ponta [g]")
        m_max = max(0.02, 3 * beam.m_eq, 1.5 * m)
        masses = np.linspace(0, m_max, 200)
        freqs = [beam.mass_loaded_frequency(x) for x in masses]
        curve(pw, masses * 1e3, freqs, theme.ACCENT, width=2)
        self._mass_decorations(pw, m * 1e3, beam.mass_loaded_frequency(m), limit)

    def _plot_mass_fe(self, sp, limit: float) -> None:
        """f₁ against a lumped mass at the position of the first listed mass
        (or at the free end)."""
        pw = self.mass_plot
        L = sp.L_mm
        if sp.masses:
            x_mm, m_now = float(sp.masses[0]["x_mm"]), float(sp.masses[0]["mass_g"])
            rest = dataclasses.replace(sp, masses=sp.masses[1:])
        else:
            x_mm, m_now = L, sp.tip_mass_g
            rest = dataclasses.replace(sp, tip_mass_g=0.0)
        pw.setLabel("bottom", f"Massa em x = {x_mm:g} mm [g]")
        m_max = max(20.0, 3.0 * m_now)
        grid = np.linspace(0.0, m_max, 24)
        freqs = []
        for g in grid:
            cfg = dataclasses.replace(rest, masses=list(rest.masses) + [
                {"name": "x", "x_mm": x_mm, "mass_g": float(g)}])
            freqs.append(cfg.fe_model(n_elements=60).elastic_frequency(1))
        curve(pw, grid, freqs, theme.ACCENT, width=2)
        cfg = dataclasses.replace(rest, masses=list(rest.masses) + [
            {"name": "x", "x_mm": x_mm, "mass_g": m_now}])
        self._mass_decorations(pw, m_now, cfg.fe_model(n_elements=60).elastic_frequency(1), limit)

    def _mass_decorations(self, pw, m_g: float, f_now: float, limit: float) -> None:
        lim = pg.InfiniteLine(pos=limit, angle=0, pen=pg.mkPen(
            theme.BAD, width=1, style=Qt.DashLine))
        lim.label = pg.InfLineLabel(lim, text=f"fps/{self.oversampling.value():g}",
                                    position=0.95, color=theme.BAD,
                                    anchors=[(1, 1), (1, 1)])
        pw.addItem(lim)
        sel = pg.ScatterPlotItem([m_g], [f_now], size=9,
                                 brush=pg.mkBrush(theme.ACCENT), pen=pg.mkPen(theme.SURFACE))
        pw.addItem(sel)
        mark = vline(theme.FAINT, Qt.DotLine)
        mark.setPos(m_g)
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
