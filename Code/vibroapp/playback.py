"""Video next to its displacement plot, in sync: live while the video is being
tracked, and as a playback (slow motion) afterwards, with MP4 export."""

from __future__ import annotations

import math
import os
import time
from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGraphicsRectItem,
    QHBoxLayout,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QWidget,
)

from vibrometry.render import export_speed, render_side_by_side
from vibrometry.streaming import compose_signals

from . import theme
from .state import AppState
from .widgets import Worker, curve, fmt, hbox, muted, plot, vbox, vline

SPEEDS = [("1/16×", 1 / 16), ("1/8×", 1 / 8), ("1/4×", 1 / 4), ("1/2×", 1 / 2), ("1×", 1.0)]


class PlaybackPanel(QWidget):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.cap: cv2.VideoCapture | None = None
        self.cap_pos = 0
        self.k = 0
        self.series: list[tuple[str, np.ndarray, np.ndarray, str]] = []
        self.curves: list[pg.PlotDataItem] = []
        self.dots: list[pg.ScatterPlotItem] = []
        self.rects: dict[str, QGraphicsRectItem] = {}
        self.live: dict | None = None
        self.worker: Worker | None = None

        # --- views ---------------------------------------------------- #
        self.gw = pg.GraphicsLayoutWidget()
        self.vb = self.gw.addViewBox(lockAspect=True, invertY=True, enableMenu=False)
        self.img = pg.ImageItem()
        self.vb.addItem(self.img)
        self.plot = plot("Tempo [s]", "Deslocamento", legend=True)
        self.cursor = vline(theme.FAINT, Qt.SolidLine)

        # --- controls ------------------------------------------------- #
        self.play_btn = QPushButton("▶  Reproduzir")
        self.play_btn.setObjectName("Primary")
        self.play_btn.setFixedWidth(130)
        self.speed = QComboBox()
        for label, v in SPEEDS:
            self.speed.addItem(label, v)
        self.speed.setCurrentIndex(1)
        self.speed.setToolTip("Velocidade em relação ao tempo real (câmera lenta)")
        self.source = QComboBox()
        self.source.addItem("Vídeo — todas as ROIs", "video")
        self.source.addItem("Vídeo × acelerômetro", "compare")
        self.speed.setMinimumWidth(80)
        self.source.setMinimumWidth(200)
        self.slider = QSlider(Qt.Horizontal)
        self.time_label = muted("", wrap=False)
        self.time_label.setMinimumWidth(150)
        self.export_btn = QPushButton("Exportar vídeo…")
        self.export_progress = QProgressBar()
        self.export_progress.setVisible(False)
        self.export_progress.setFixedWidth(120)
        self.status = muted("Processe o vídeo para acompanhar o rastreamento aqui; "
                            "depois, reproduza vídeo e gráfico lado a lado.", wrap=False)

        views = QHBoxLayout()
        views.setSpacing(8)
        views.addWidget(self.gw, 1)
        views.addWidget(self.plot, 1)
        lay = vbox(self, spacing=6)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.addLayout(views, 1)
        lay.addLayout(hbox(self.play_btn, self.slider, self.time_label))
        lay.addLayout(hbox(muted("Velocidade", wrap=False), self.speed,
                           muted("Gráfico", wrap=False), self.source, None,
                           self.export_progress, self.export_btn))
        lay.addWidget(self.status)

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.play_btn.clicked.connect(self.toggle)
        self.slider.valueChanged.connect(self._slider_moved)
        self.source.currentIndexChanged.connect(self.load)
        self.speed.currentIndexChanged.connect(self._speed_changed)
        self.export_btn.clicked.connect(self.export)
        state.analysisChanged.connect(self.load)
        state.comparisonChanged.connect(self._comparison_changed)
        self._set_enabled(False)

    # ================================================================== #
    # data
    # ================================================================== #
    def _set_enabled(self, on: bool) -> None:
        for w in (self.play_btn, self.slider, self.speed, self.export_btn):
            w.setEnabled(on)
        self.source.setEnabled(on and self.state.comparison is not None)

    def _comparison_changed(self) -> None:
        self.source.setEnabled(self.state.track is not None
                               and self.state.comparison is not None)
        if self.source.currentData() == "compare":
            self.load()

    def _build_series(self) -> tuple[list, str]:
        a = self.state.analysis
        cmp = self.state.comparison
        if self.source.currentData() == "compare" and cmp is not None:
            dom = "Deslocamento" if cmp.domain == "displacement" else "Aceleração"
            return ([(f"vídeo [{cmp.unit_video}]", cmp.t, cmp.video, theme.VIDEO),
                     (f"acelerômetro [{cmp.unit_accel}]", cmp.t, cmp.accel, theme.ACCEL)],
                    f"{dom} (filtrado)")
        out = [(f"{name} ({a.axes[name]})", a.times, x, theme.SERIES[i % len(theme.SERIES)])
               for i, (name, x) in enumerate(a.signals.items())]
        return out, f"Deslocamento [{a.unit}]"

    def _reset_plot(self, labels_colors, ylabel: str, fast: bool = False) -> None:
        """``fast``: 1 px, aliased lines. QPainter strokes wider / antialiased
        paths an order of magnitude slower (~13 ms per path here) and PySide
        holds the GIL while painting, which starved the tracking thread
        (9 s -> 84 s for a 1920-frame clip with the live view on)."""
        self.plot.clear()
        self.curves, self.dots = [], []
        for label, color in labels_colors:
            self.curves.append(curve(self.plot, [], [], color, label,
                                     width=1 if fast else 1.6, antialias=not fast))
            dot = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(color),
                                     pen=pg.mkPen(theme.SURFACE))
            self.plot.addItem(dot)
            self.dots.append(dot)
        self.plot.addItem(self.cursor, ignoreBounds=True)
        self.plot.setLabel("left", ylabel)

    def _reset_rects(self, rois: list[tuple[str, bool]]) -> None:
        for it in self.rects.values():
            self.vb.removeItem(it)
        self.rects.clear()
        for name, is_ref in rois:
            it = QGraphicsRectItem()
            it.setPen(pg.mkPen(theme.REFERENCE if is_ref else theme.ACCENT, width=2))
            self.vb.addItem(it)
            self.rects[name] = it

    def load(self) -> None:
        """(Re)build the playback from the current tracking result."""
        if self.live is not None:
            return
        self.pause()
        tr = self.state.track
        if tr is None or self.state.analysis is None:
            self._close_cap()
            self.plot.clear()
            self.img.clear()
            self._reset_rects([])
            self._set_enabled(False)
            return
        self.series, ylabel = self._build_series()
        self._reset_plot([(s[0], s[3]) for s in self.series], ylabel)
        self._reset_rects([(n, r.roi.is_reference) for n, r in tr.tracks.items()])
        t = tr.times
        vals = np.concatenate([s[2] for s in self.series])
        vals = vals[np.isfinite(vals)]
        self.plot.setXRange(t[0], t[-1], padding=0.01)
        if vals.size:
            lo, hi = float(vals.min()), float(vals.max())
            pad = 0.08 * (hi - lo or 1.0)
            self.plot.setYRange(lo - pad, hi + pad, padding=0)
        self.plot.enableAutoRange(enable=False)
        self._open_cap(tr.info.path)
        self.slider.blockSignals(True)
        self.slider.setRange(0, tr.n_frames - 1)
        self.slider.blockSignals(False)
        self._set_enabled(True)
        self.status.setText("Reprodução sincronizada: o gráfico é desenhado até o instante "
                            "do quadro exibido.")
        first = self.img.image is None
        self.show_frame(min(self.k, tr.n_frames - 1))
        if first:
            self.vb.autoRange(padding=0.01)

    # ================================================================== #
    # video reading (colour, sequential when possible)
    # ================================================================== #
    def _open_cap(self, path: str) -> None:
        self._close_cap()
        self.cap = cv2.VideoCapture(path)
        self.cap_pos = 0

    def _close_cap(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = None

    def _frame(self, k: int) -> np.ndarray | None:
        tr = self.state.track
        if self.cap is None or tr is None:
            return None
        idx = tr.params.start_frame + k
        if idx < self.cap_pos or idx > self.cap_pos + 48:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            self.cap_pos = idx
        while self.cap_pos < idx:          # skip frames cheaply
            self.cap.grab()
            self.cap_pos += 1
        ok, frame = self.cap.read()
        self.cap_pos += 1
        return np.ascontiguousarray(frame[..., ::-1]) if ok else None

    # ================================================================== #
    # display
    # ================================================================== #
    def show_frame(self, k: int) -> None:
        tr = self.state.track
        if tr is None:
            return
        k = int(np.clip(k, 0, tr.n_frames - 1))
        self.k = k
        frame = self._frame(k)
        if frame is not None:
            self.img.setImage(frame, autoLevels=False, levels=(0, 255))
        for name, res in tr.tracks.items():
            r = res.roi
            dx, dy = res.displacement[k]
            self.rects[name].setRect(r.x + dx, r.y + dy, r.w, r.h)
        tk = float(tr.frame_times[k])           # real time of frame k
        for (label, t, y, color), c, dot in zip(self.series, self.curves, self.dots):
            j = int(min(len(t) - 1, np.searchsorted(t, tk + 1e-9) - 1)) if len(t) else 0
            j = max(j, 0)
            c.setData(t[: j + 1], y[: j + 1])
            dot.setData([t[j]], [y[j]] if np.isfinite(y[j]) else [np.nan])
        self.cursor.setPos(tk)
        self.slider.blockSignals(True)
        self.slider.setValue(k)
        self.slider.blockSignals(False)
        self.time_label.setText(f"{fmt(tk, 3)} s · quadro {tr.params.start_frame + k}")

    def _slider_moved(self, k: int) -> None:
        self.pause()
        self.show_frame(k)

    # ================================================================== #
    # playback
    # ================================================================== #
    def toggle(self) -> None:
        if self.timer.isActive():
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        tr = self.state.track
        if tr is None:
            return
        if self.k >= tr.n_frames - 1:
            self.k = 0
        self._k0, self._t0 = self.k, time.perf_counter()
        self.timer.start()
        self.play_btn.setText("❚❚  Pausar")

    def pause(self) -> None:
        self.timer.stop()
        self.play_btn.setText("▶  Reproduzir")

    def _speed_changed(self) -> None:
        if self.timer.isActive():
            self._k0, self._t0 = self.k, time.perf_counter()

    def _tick(self) -> None:
        tr = self.state.track
        if tr is None:
            self.pause()
            return
        target = self._k0 + int((time.perf_counter() - self._t0)
                                * self.speed.currentData() * tr.fps)
        if target >= tr.n_frames - 1:
            self.show_frame(tr.n_frames - 1)
            self.pause()
        elif target != self.k:
            self.show_frame(target)

    # ================================================================== #
    # live view while tracking
    # ================================================================== #
    def begin_live(self, rois: list[dict], n_total: int, fps: float,
                   scale: float | None, axis: str, compensate: bool) -> None:
        self.pause()
        self._close_cap()
        names = [r["name"] for r in rois if not r.get("is_reference")]
        ref = next((r["name"] for r in rois if r.get("is_reference")), None)
        self.live = {"fps": fps, "scale": scale, "axis": axis, "compensate": compensate,
                     "ref": ref, "rois": {r["name"]: r for r in rois}, "n": n_total,
                     "first": True}
        unit = "mm" if scale else "px"
        self._reset_plot([(n, theme.SERIES[i % len(theme.SERIES)])
                          for i, n in enumerate(names)], f"Deslocamento [{unit}]",
                         fast=True)
        self._reset_rects([(r["name"], bool(r.get("is_reference"))) for r in rois])
        self.plot.setXRange(0, n_total / fps, padding=0.01)
        self.plot.enableAutoRange(axis="y", enable=True)
        self._set_enabled(False)
        self.status.setText("Rastreando: o gráfico cresce à medida que os quadros são "
                            "processados.")

    def live_update(self, k: int, frame: np.ndarray, disp: dict) -> None:
        lv = self.live
        if lv is None:
            return
        self.img.setImage(frame, autoLevels=False, levels=(0, 255))
        if lv["first"]:
            self.vb.autoRange(padding=0.01)
            lv["first"] = False
        for name, d in disp.items():
            r = lv["rois"][name]
            dx, dy = d[-1]
            self.rects[name].setRect(r["x"] + dx, r["y"] + dy, r["w"], r["h"])
        signals, _ = compose_signals(disp, lv["ref"], lv["axis"], lv["scale"],
                                     lv["compensate"])
        t = np.arange(k + 1) / lv["fps"]
        for c, dot, y in zip(self.curves, self.dots, signals.values()):
            c.setData(t, y[: k + 1])
            dot.setData([t[-1]], [y[k]])
        self.cursor.setPos(t[-1])
        self.time_label.setText(f"{fmt(t[-1], 3)} s · quadro {k + 1}/{lv['n']}")

    def end_live(self) -> None:
        self.live = None

    # ================================================================== #
    # export
    # ================================================================== #
    def export(self) -> None:
        tr = self.state.track
        if tr is None or not self.series:
            return
        s = self.state.session
        base = os.path.dirname(s.file or s.video.path or "")
        speed = self.speed.currentData()
        default = os.path.join(base, f"{s.name or 'video'}_lado_a_lado.mp4")
        path, _ = QFileDialog.getSaveFileName(self, "Exportar vídeo lado a lado", default,
                                              "Vídeo MP4 (*.mp4)")
        if path:
            self.export_to(path)

    def export_to(self, path: str) -> None:
        tr = self.state.track
        speed = self.speed.currentData()
        out_fps, stride = export_speed(tr.fps, speed)
        series = [(label, y, color) for label, _, y, color in self.series]
        ylabel = self.plot.getPlotItem().getAxis("left").labelText or "Deslocamento"
        self.pause()
        self.worker = Worker(
            lambda progress, stop: render_side_by_side(
                path, tr, series, ylabel=ylabel, out_fps=out_fps, stride=stride,
                progress=progress, should_stop=stop),
            parent=self)
        self.worker.progress.connect(self._export_progress)
        self.worker.done.connect(self._export_done)
        self.worker.failed.connect(self._export_failed)
        self.export_btn.setEnabled(False)
        self.export_progress.setVisible(True)
        self.export_progress.setValue(0)
        duration = math.ceil(tr.n_frames / stride) / out_fps
        self.status.setText(f"Exportando a {self.speed.currentText()} "
                            f"({fmt(out_fps, 1)} fps, {fmt(duration, 1)} s de vídeo)…")
        self.worker.start()

    def _export_progress(self, done: int, total: int) -> None:
        self.export_progress.setMaximum(max(1, total))
        self.export_progress.setValue(done)

    def _export_done(self, path) -> None:
        self.worker = None
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        self.status.setText(f"Vídeo exportado: {Path(path).name}")
        self.state.message.emit(f"Vídeo exportado: {path}")

    def _export_failed(self, msg: str) -> None:
        self.worker = None
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        QMessageBox.warning(self, "Exportar vídeo", msg)
