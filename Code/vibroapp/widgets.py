"""Small reusable widgets and helpers."""

from __future__ import annotations

import math
import traceback
from typing import Any, Callable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import theme


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #
def fmt(x: Any, nd: int = 3, unit: str = "") -> str:
    """Number with decimal comma; "—" when missing."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    s = f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")
    return f"{s} {unit}".rstrip() if unit else s


# --------------------------------------------------------------------------- #
# layout helpers
# --------------------------------------------------------------------------- #
class Panel(QFrame):
    """White rounded card."""

    def __init__(self, parent: QWidget | None = None, margins: int = 14,
                 spacing: int = 8) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(margins, margins, margins, margins)
        self.lay.setSpacing(spacing)


def section(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setObjectName("Section")
    return lab


def muted(text: str = "", wrap: bool = True) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("Muted")
    lab.setWordWrap(wrap)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


def form() -> QFormLayout:
    f = QFormLayout()
    f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    f.setHorizontalSpacing(12)
    f.setVerticalSpacing(6)
    f.setContentsMargins(0, 0, 0, 0)
    return f


def hbox(*widgets, spacing: int = 6, stretch_last: bool = False) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    if stretch_last:
        lay.addStretch(1)
    return lay


def scroll(widget: QWidget, width: int | None = None) -> QScrollArea:
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setFrameShape(QFrame.NoFrame)
    if width:
        area.setFixedWidth(width)
    return area


def empty_state(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("Empty")
    lab.setAlignment(Qt.AlignCenter)
    lab.setWordWrap(True)
    return lab


# --------------------------------------------------------------------------- #
# spin boxes
# --------------------------------------------------------------------------- #
def dspin(value: float = 0.0, lo: float = 0.0, hi: float = 1e9, decimals: int = 3,
          step: float = 1.0, suffix: str = "") -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSingleStep(step)
    s.setValue(value)
    s.setKeyboardTracking(False)
    s.setAccelerated(True)
    if suffix:
        s.setSuffix(f" {suffix}")
    return s


def ispin(value: int = 0, lo: int = 0, hi: int = 10 ** 9, suffix: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    s.setKeyboardTracking(False)
    if suffix:
        s.setSuffix(f" {suffix}")
    return s


class OptSpin(QDoubleSpinBox):
    """Double spin box whose minimum means "not set" (shown as ``special``)."""

    def __init__(self, special: str, lo: float = 0.0, hi: float = 1e9,
                 decimals: int = 3, step: float = 1.0, suffix: str = "") -> None:
        super().__init__()
        self.setRange(lo, hi)
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setSpecialValueText(special)
        self.setKeyboardTracking(False)
        if suffix:
            self.setSuffix(f" {suffix}")
        self.setValue(lo)

    def get(self) -> float | None:
        v = self.value()
        return None if v <= self.minimum() else float(v)

    def put(self, v: float | None) -> None:
        self.setValue(self.minimum() if v is None else float(v))


# --------------------------------------------------------------------------- #
# plots
# --------------------------------------------------------------------------- #
def plot(xlabel: str = "", ylabel: str = "", legend: bool = False) -> pg.PlotWidget:
    w = pg.PlotWidget()
    w.setMenuEnabled(False)
    item = w.getPlotItem()
    item.showGrid(x=True, y=True, alpha=0.12)
    for ax in ("left", "bottom"):
        a = item.getAxis(ax)
        a.setPen(pg.mkPen(theme.AXIS))
        a.setTextPen(pg.mkPen(theme.MUTED))
        a.enableAutoSIPrefix(False)   # keep values in the stated unit (no "x0.001")
    if xlabel:
        item.setLabel("bottom", xlabel)
    if ylabel:
        item.setLabel("left", ylabel)
    if legend:
        bg = QColor(theme.SURFACE)
        bg.setAlpha(230)
        lg = item.addLegend(offset=(-10, 10), labelTextColor=theme.TEXT,
                            brush=pg.mkBrush(bg))
        lg.setPen(pg.mkPen(theme.BORDER))
    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return w


def curve(pw: pg.PlotWidget, x, y, color: str, name: str | None = None,
          width: float = 1.3, style=Qt.SolidLine, **kw) -> pg.PlotDataItem:
    c = pw.plot(np.asarray(x), np.asarray(y),
                pen=pg.mkPen(color, width=width, style=style), name=name, **kw)
    c.setDownsampling(auto=True, method="peak")
    c.setClipToView(True)
    return c


def region(color: str = theme.ACCENT) -> pg.LinearRegionItem:
    q = QColor(color)
    r = pg.LinearRegionItem(
        brush=pg.mkBrush(q.red(), q.green(), q.blue(), 26),
        hoverBrush=pg.mkBrush(q.red(), q.green(), q.blue(), 46),
        pen=pg.mkPen(q.red(), q.green(), q.blue(), 140, width=1.5),
    )
    r.setZValue(-10)
    return r


def vline(color: str = theme.FAINT, style=Qt.DashLine, label: str | None = None) -> pg.InfiniteLine:
    line = pg.InfiniteLine(angle=90, movable=False,
                           pen=pg.mkPen(color, width=1, style=style))
    if label:
        line.label = pg.InfLineLabel(line, text=label, position=0.92,
                                     color=color, anchors=[(0, 0), (0, 0)])
    return line


# --------------------------------------------------------------------------- #
# tables
# --------------------------------------------------------------------------- #
class Table(QTableWidget):
    """Read-only, compact table. Cells may be (text, colour) tuples."""

    def __init__(self, headers: list[str], stretch_first: bool = True) -> None:
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.verticalHeader().setDefaultSectionSize(26)
        h = self.horizontalHeader()
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i in range(len(headers)):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        if stretch_first:
            h.setSectionResizeMode(0, QHeaderView.Stretch)
        else:
            h.setStretchLastSection(True)

    def set_rows(self, rows: list[list]) -> None:
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                color = None
                if isinstance(cell, tuple):
                    cell, color = cell
                item = QTableWidgetItem("" if cell is None else str(cell))
                if j > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if color:
                    item.setForeground(QColor(color))
                self.setItem(i, j, item)

    def fit_height(self, max_rows: int = 12) -> None:
        n = min(self.rowCount(), max_rows)
        self.setFixedHeight(self.horizontalHeader().height()
                            + n * self.verticalHeader().defaultSectionSize() + 4)


def status_cell(ok: bool | None, text: str | None = None):
    if ok is None:
        return (text or "—", theme.FAINT)
    return (text or ("✓ atende" if ok else "✗ não atende"), theme.OK if ok else theme.BAD)


class Chip(QLabel):
    """Small coloured status text."""

    def set(self, text: str, ok: bool | None = None) -> None:
        color = theme.MUTED if ok is None else (theme.OK if ok else theme.BAD)
        self.setText(text)
        self.setStyleSheet(f"color: {color};")


# --------------------------------------------------------------------------- #
# background work
# --------------------------------------------------------------------------- #
class Worker(QThread):
    """Runs ``fn(progress, should_stop, *args)`` in a thread.

    progress(done, total) is forwarded as the ``progress`` signal; the return
    value arrives in ``done`` and exceptions (with traceback) in ``failed``.
    """

    progress = Signal(int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.fn = fn
        self.args = args
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def should_stop(self) -> bool:
        return self._stop

    def run(self) -> None:
        try:
            result = self.fn(lambda d, t: self.progress.emit(int(d), int(t)),
                             self.should_stop, *self.args)
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.done.emit(result)


def debounce(parent: QObject, ms: int, fn: Callable) -> QTimer:
    """Single-shot timer: call ``.start()`` repeatedly, ``fn`` runs once."""
    t = QTimer(parent)
    t.setSingleShot(True)
    t.setInterval(ms)
    t.timeout.connect(fn)
    return t


def tidy(root: QWidget, min_width: int = 72) -> None:
    """Let form fields shrink: by default a spin box's minimum width comes from
    its *maximum* value (e.g. 1e9) and a combo box's from its longest item,
    which makes the fixed-width control column overflow."""
    for sb in root.findChildren(QAbstractSpinBox):
        sb.setMinimumWidth(min_width)
        sb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        editor = sb.findChild(QLineEdit)
        if editor is not None:   # QSS padding is ignored for the inner editor
            editor.setTextMargins(5, 0, 0, 0)
    for cb in root.findChildren(QComboBox):
        cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cb.setMinimumContentsLength(6)
        cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


def vbox(widget: QWidget | None = None, margins: int = 0, spacing: int = 8) -> QVBoxLayout:
    lay = QVBoxLayout(widget) if widget is not None else QVBoxLayout()
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.setSpacing(spacing)
    return lay
