"""Step 2 — Vídeo: import, pre-checks, calibration, ROIs, phase-based
tracking and modal analysis (planejamento R3, R4, R5, R7)."""

from __future__ import annotations

import copy
import os
import re
import time
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGraphicsRectItem,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QTabWidget,
    QWidget,
)

from vibrometry.report import spectrum_xmax
from vibrometry.spectral import stft_spectrogram
from vibrometry.video_io import FrameReader, probe_video
from vibrometry.workflow import load_track_cache, run_video, save_track_cache

from . import theme
from .playback import PlaybackPanel
from .state import AppState
from .widgets import (
    OptSpin,
    Panel,
    Table,
    Worker,
    curve,
    debounce,
    dspin,
    empty_state,
    fmt,
    form,
    hbox,
    ispin,
    muted,
    plot,
    region,
    scroll,
    section,
    vbox,
    vline,
)

VIDEO_FILTER = "Vídeos (*.mp4 *.mov *.avi *.mkv *.m4v *.lrf *.MP4 *.MOV *.LRF);;Todos (*.*)"
# s between live-view updates while tracking (0 = off). Measured on a 1920-frame
# clip: off 11.8 s, 0.2 s 11.8 s, 0.1 s 13.2 s, 0.05 s 17.4 s.
PREVIEW_INTERVAL = 0.1


def roi_color(i: int, is_ref: bool) -> str:
    return theme.REFERENCE if is_ref else theme.SERIES[i % len(theme.SERIES)]


def distinct_peaks(ms, n: int = 3) -> list:
    """Strongest peaks at least 3 resolution bins (3 / window length) apart,
    so the side lobes of the main peak are not labelled."""
    span = max(ms.window[1] - ms.window[0], 1e-9)
    kept = []
    for p in ms.peaks:
        if all(abs(p.frequency - q.frequency) > 3.0 / span for q in kept):
            kept.append(p)
        if len(kept) == n:
            break
    return kept


class VideoPage(QWidget):
    # (frame index, gray frame, displacements) from the tracking thread
    _preview = Signal(int, object, object)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.state = state
        self.reader: FrameReader | None = None
        self.roi_items: list[dict] = []
        self.track_items: dict[str, QGraphicsRectItem] = {}
        self.cal_roi: pg.LineSegmentROI | None = None
        self.worker: Worker | None = None
        self._loading = False
        self._t_start = 0.0

        self._build_controls()
        self._build_views()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(scroll(self.controls, 340))
        lay.addWidget(self.tabs, 1)

        self._frame_timer = debounce(self, 15, self._show_current_frame)
        self._window_timer = debounce(self, 200, self._apply_window)

        state.sessionReplaced.connect(self.load_session)
        state.analysisChanged.connect(self._draw_results)
        self.load_session()

    # ================================================================== #
    # UI construction
    # ================================================================== #
    def _build_controls(self) -> None:
        self.open_btn = QPushButton("Abrir vídeo…")
        self.file_label = QLabel("Nenhum vídeo")
        self.file_label.setObjectName("Title")
        self.file_label.setWordWrap(True)
        self.info_label = muted()

        self.start = dspin(0, 0, 1e6, 3, 0.1, "s")
        self.end = OptSpin("fim do vídeo", 0, 1e6, 3, 0.1, "s")
        self.start_here = QPushButton("← quadro atual")
        self.end_here = QPushButton("← quadro atual")
        for b in (self.start_here, self.end_here):
            b.setObjectName("Flat")
        self.fps = OptSpin("automático", 0, 100000, 3, 1, "fps")
        self.resize = OptSpin("original", 0, 10000, 0, 10, "px")
        self.resize.setDecimals(0)

        self.add_meas = QPushButton("+ Medição")
        self.add_ref = QPushButton("+ Referência")
        self.del_roi = QPushButton("Remover")
        self.del_roi.setObjectName("Flat")
        self.roi_list = QListWidget()
        self.roi_list.setFixedHeight(84)
        self.roi_list.setEditTriggers(QListWidget.DoubleClicked)
        self.roi_pos = OptSpin("não informada", 0, 100000, 1, 10, "mm")
        self.roi_pos.setEnabled(False)

        self.scale = OptSpin("sem escala (px)", 0, 1000, 5, 0.001, "mm/px")
        self.cal_btn = QPushButton("Medir na imagem")
        self.cal_btn.setCheckable(True)
        self.cal_len = dspin(100, 0.001, 1e5, 2, 1, "mm")
        self.cal_px = muted("Arraste as extremidades do segmento sobre o objeto de "
                            "comprimento conhecido.")
        self.cal_apply = QPushButton("Aplicar escala")
        self.cal_apply.setEnabled(False)

        self.axis = QComboBox()
        self.axis.addItem("automático (maior variância)", "auto")
        self.axis.addItem("x — horizontal", "x")
        self.axis.addItem("y — vertical", "y")
        self.compensate = QCheckBox("Subtrair movimento da ROI de referência")
        self.wavelengths = QLineEdit()
        self.wavelengths.setPlaceholderText("8, 16")
        self.margin = ispin(60, 4, 4000, "px")

        self.run_btn = QPushButton("Processar vídeo")
        self.run_btn.setObjectName("Primary")
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setVisible(False)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.run_info = muted()

        self.controls = QWidget()
        cl = vbox(self.controls, spacing=8)

        p = Panel()
        p.lay.addWidget(self.open_btn)
        p.lay.addWidget(self.file_label)
        p.lay.addWidget(self.info_label)
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Trecho e amostragem"))
        f = form()
        f.addRow("Início", hbox(self.start, self.start_here))
        f.addRow("Fim", hbox(self.end, self.end_here))
        f.addRow("Taxa real", self.fps)
        f.addRow("Reduzir para", self.resize)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Informe a taxa real se o arquivo foi gravado em câmera "
                              "lenta e reetiquetado (ex.: 240 fps salvo como 30 fps)."))
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Regiões de interesse"))
        p.lay.addLayout(hbox(self.add_meas, self.add_ref, self.del_roi))
        p.lay.addWidget(self.roi_list)
        p.lay.addLayout(hbox(muted("Posição da ROI na barra", wrap=False), self.roi_pos))
        p.lay.addWidget(muted("Distância da raiz até a ROI selecionada: com duas ou mais ROIs "
                              "posicionadas, o relatório compara a razão das amplitudes com a "
                              "forma modal do modelo."))
        p.lay.addWidget(muted("Desenhe as ROIs no quadro inicial do trecho. A ROI de "
                              "medição deve conter só o alvo (ex.: o marcador); a de "
                              "referência, um ponto fixo com textura."))
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Escala"))
        f = form()
        f.addRow("Fator", self.scale)
        p.lay.addLayout(f)
        p.lay.addLayout(hbox(self.cal_btn, self.cal_len))
        p.lay.addWidget(self.cal_px)
        p.lay.addWidget(self.cal_apply)
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(section("Método de fase"))
        f = form()
        f.addRow("Componente", self.axis)
        f.addRow("λ dos filtros", self.wavelengths)
        f.addRow("Margem de busca", self.margin)
        p.lay.addLayout(f)
        p.lay.addWidget(self.compensate)
        cl.addWidget(p)

        p = Panel()
        p.lay.addWidget(self.run_btn)
        p.lay.addWidget(self.progress)
        p.lay.addWidget(self.cancel_btn)
        p.lay.addWidget(self.run_info)
        cl.addWidget(p)
        cl.addStretch(1)

        self.open_btn.clicked.connect(self.choose_video)
        self.start_here.clicked.connect(lambda: self.start.setValue(self._current_time()))
        self.end_here.clicked.connect(lambda: self.end.put(self._current_time()))
        self.start.valueChanged.connect(self._start_changed)
        for w in (self.end, self.fps, self.resize, self.scale):
            w.valueChanged.connect(self._params_changed)
        self.margin.valueChanged.connect(self._params_changed)
        self.axis.currentIndexChanged.connect(self._analysis_changed)
        self.compensate.toggled.connect(self._analysis_changed)
        self.wavelengths.editingFinished.connect(self._params_changed)
        self.add_meas.clicked.connect(lambda: self._new_roi(False))
        self.add_ref.clicked.connect(lambda: self._new_roi(True))
        self.del_roi.clicked.connect(self._delete_roi)
        self.roi_list.itemChanged.connect(self._roi_renamed)
        self.roi_list.currentRowChanged.connect(self._highlight_roi)
        self.roi_list.currentRowChanged.connect(self._load_roi_pos)
        self.roi_pos.valueChanged.connect(self._roi_pos_changed)
        self.cal_btn.toggled.connect(self._toggle_calibration)
        self.cal_len.valueChanged.connect(self._calibration_moved)
        self.cal_apply.clicked.connect(self._apply_calibration)
        self.run_btn.clicked.connect(self.run)
        self.cancel_btn.clicked.connect(self._cancel)

    def _build_views(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # --- frame viewer ---------------------------------------------- #
        self.gw = pg.GraphicsLayoutWidget()
        self.vb = self.gw.addViewBox(lockAspect=True, invertY=True, enableMenu=False)
        self.img = pg.ImageItem()
        self.vb.addItem(self.img)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        for b in (self.prev_btn, self.next_btn):
            b.setObjectName("Flat")
            b.setFixedWidth(28)
            b.setAutoRepeat(True)
        self.frame_label = muted("", wrap=False)
        self.frame_label.setMinimumWidth(170)
        frame_tab = QWidget()
        fl = vbox(frame_tab, spacing=6)
        fl.addWidget(self.gw, 1)
        fl.addLayout(hbox(self.prev_btn, self.slider, self.next_btn, self.frame_label))
        self.frame_stack_empty = empty_state("Abra um vídeo para começar.")
        self.slider.valueChanged.connect(lambda _: self._frame_timer.start())
        self.prev_btn.clicked.connect(lambda: self.slider.setValue(self.slider.value() - 1))
        self.next_btn.clicked.connect(lambda: self.slider.setValue(self.slider.value() + 1))

        # --- displacement + modal table --------------------------------- #
        self.disp_plot = plot("Tempo [s]", "Deslocamento", legend=True)
        self.region = region()
        self.region.sigRegionChanged.connect(self._region_moved)
        self.cursor = vline(theme.FAINT, Qt.DotLine)
        self.full_window = QPushButton("Janela inteira")
        self.full_window.setObjectName("Flat")
        self.full_window.clicked.connect(self._reset_window)
        self.window_label = muted("", wrap=False)
        self.modal_table = Table(["ROI", "Eixo", "f [Hz]", "A", "ζ meia-pot.",
                                  "ζ decr. log.", "σ", "f prevista [Hz]", "Erro [%]"])
        disp_tab = QWidget()
        dl = vbox(disp_tab, spacing=6)
        dl.addWidget(self.disp_plot, 1)
        dl.addLayout(hbox(self.window_label, None, self.full_window))
        dl.addWidget(self.modal_table)

        # --- spectrum ---------------------------------------------------- #
        self.spec_plot = plot("Frequência [Hz]", "Amplitude", legend=True)
        self.spec_log = QCheckBox("Escala log")
        self.spec_log.toggled.connect(lambda on: self.spec_plot.setLogMode(y=on))
        spec_tab = QWidget()
        sl = vbox(spec_tab, spacing=6)
        sl.addWidget(self.spec_plot, 1)
        sl.addLayout(hbox(muted("Espectro de amplitude (Hann) na janela de análise.",
                                wrap=False), None, self.spec_log))

        # --- spectrogram ------------------------------------------------- #
        self.sgram_roi = QComboBox()
        self.sgram_glw = pg.GraphicsLayoutWidget()
        self.sgram_plot = self.sgram_glw.addPlot()
        self.sgram_plot.setLabel("bottom", "Tempo [s]")
        self.sgram_plot.setLabel("left", "Frequência [Hz]")
        self.sgram_plot.setMenuEnabled(False)
        self.sgram_img = pg.ImageItem()
        self.sgram_img.setColorMap(pg.colormap.get("magma"))
        self.sgram_plot.addItem(self.sgram_img)
        self.sgram_roi.currentIndexChanged.connect(self._draw_spectrogram)
        sg_tab = QWidget()
        gl = vbox(sg_tab, spacing=6)
        gl.addLayout(hbox(muted("ROI", wrap=False), self.sgram_roi, None))
        gl.addWidget(self.sgram_glw, 1)

        # --- quality ----------------------------------------------------- #
        self.quality_table = Table(["Verificação", "Valor"])
        self.quality_warn = QLabel()
        self.quality_warn.setWordWrap(True)
        self.bright_plot = plot("Tempo [s]", "Brilho médio")
        self.score_plot = plot("Tempo [s]", "Correlação (NCC)", legend=True)
        q_tab = QWidget()
        ql = QHBoxLayout(q_tab)
        ql.setContentsMargins(0, 6, 0, 0)
        left = QWidget()
        lv = vbox(left)
        lv.addWidget(self.quality_warn)
        lv.addWidget(self.quality_table, 1)
        right = QWidget()
        rv = vbox(right)
        rv.addWidget(self.bright_plot)
        rv.addWidget(self.score_plot)
        ql.addWidget(left, 1)
        ql.addWidget(right, 1)

        # --- video + plot side by side (live while tracking, then playback)
        self.playback = PlaybackPanel(self.state)
        self._preview.connect(self.playback.live_update)

        self.tabs.addTab(frame_tab, "Quadro")
        self.tabs.addTab(self.playback, "Reprodução")
        self.tabs.addTab(disp_tab, "Deslocamento")
        self.tabs.addTab(spec_tab, "Espectro")
        self.tabs.addTab(sg_tab, "Espectrograma")
        self.tabs.addTab(q_tab, "Qualidade")

    # ================================================================== #
    # session <-> widgets
    # ================================================================== #
    def load_session(self) -> None:
        self._loading = True
        v = self.state.session.video
        self.start.setValue(v.start_s)
        self.end.put(v.end_s)
        self.fps.put(v.fps_override)
        self.resize.put(v.resize_width)
        self.scale.put(v.scale_mm_per_px)
        i = self.axis.findData(v.axis)
        self.axis.setCurrentIndex(max(0, i))
        self.compensate.setChecked(v.compensate)
        self.wavelengths.setText(", ".join(f"{w:g}" for w in v.wavelengths))
        self.margin.setValue(v.search_margin)
        if v.calibration:
            self.cal_len.setValue(v.calibration.get("length_mm", 100.0))
        self._loading = False

        self._clear_rois()
        self.cal_btn.setChecked(False)
        if v.path and os.path.exists(v.path):
            self._open(v.path)
            track = load_track_cache(self.state.session)
            if track is not None:
                self.run_info.setText("Resultado do rastreamento carregado do cache.")
                self.state.set_track(track)
        else:
            self._close_video()
            if v.path:
                self.file_label.setText("Vídeo não encontrado")
                self.info_label.setText(v.path)
        for d in v.rois:
            self._add_roi_item(d["name"], d["x"], d["y"], d["w"], d["h"],
                               d.get("is_reference", False))
        self._load_roi_pos(self.roi_list.currentRow())
        self._set_stale(False)

    def _params_changed(self) -> None:
        if self._loading:
            return
        v = self.state.session.video
        v.end_s = self.end.get()
        v.fps_override = self.fps.get()
        r = self.resize.get()
        v.resize_width = int(r) if r else None
        v.search_margin = self.margin.value()
        try:
            lams = [float(x) for x in re.split(r"[;,\s]+", self.wavelengths.text()) if x]
            if lams and all(x >= 2 for x in lams):
                v.wavelengths = lams
        except ValueError:
            pass
        self.wavelengths.setText(", ".join(f"{w:g}" for w in v.wavelengths))
        scale_changed = v.scale_mm_per_px != self.scale.get()
        v.scale_mm_per_px = self.scale.get()
        self.state.mark_dirty()
        if self.sender() is self.fps and self.reader is not None:
            self._refresh_info()
        if scale_changed and self.sender() is self.scale:
            self.state.reanalyze()
        else:
            self._set_stale(True)

    def _start_changed(self) -> None:
        if self._loading:
            return
        self.state.session.video.start_s = self.start.value()
        self.state.mark_dirty()
        self._set_stale(True)
        if self.reader is not None:
            self.slider.setValue(self._frame_of(self.start.value()))

    def _analysis_changed(self) -> None:
        if self._loading:
            return
        v = self.state.session.video
        v.axis = self.axis.currentData()
        v.compensate = self.compensate.isChecked()
        self.state.mark_dirty()
        self.state.reanalyze()

    def _set_stale(self, stale: bool) -> None:
        if stale and self.state.track is not None:
            self.run_btn.setText("Processar novamente")
            self.run_info.setText("Parâmetros alterados desde o último processamento.")
        elif not stale:
            self.run_btn.setText("Processar vídeo")

    # ================================================================== #
    # video file
    # ================================================================== #
    def choose_video(self) -> None:
        start = os.path.dirname(self.state.session.video.path or self.state.session.file or "")
        path, _ = QFileDialog.getOpenFileName(self, "Abrir vídeo", start, VIDEO_FILTER)
        if not path:
            return
        s = self.state.session
        s.video.path = path
        s.video.start_s, s.video.end_s, s.video.window = 0.0, None, None
        if not s.name:
            stem = Path(path).stem
            s.name = re.sub(r"_(osmo|iphone|cam\w*|video)$", "", stem, flags=re.I)
            self.state.nameChanged.emit()
        self._loading = True
        self.start.setValue(0)
        self.end.put(None)
        self._loading = False
        self.state.mark_dirty()
        self.state.set_track(None)
        self._open(path)

    def _open(self, path: str) -> None:
        self._close_video()
        try:
            self.state.video_info = probe_video(path, self.state.session.video.fps_override)
            self.reader = FrameReader(path)
        except Exception as exc:
            QMessageBox.warning(self, "Vídeo", f"Não foi possível abrir o vídeo:\n{exc}")
            self.state.video_info = None
            return
        info = self.state.video_info
        self.file_label.setText(Path(path).name)
        self._refresh_info()
        self.slider.setEnabled(True)
        self.slider.setRange(0, max(0, info.n_frames - 1))
        self.slider.setValue(self._frame_of(self.state.session.video.start_s))
        self._show_current_frame()
        self.vb.autoRange(padding=0.01)
        self.tabs.setCurrentIndex(0)

    def _refresh_info(self) -> None:
        info = self.state.video_info
        if info is None:
            return
        fps = self.state.session.video.fps_override or info.fps
        source = {"override": "informada", "container": "contêiner",
                  "measured": "medida pelos timestamps"}.get(
            "override" if self.state.session.video.fps_override else info.fps_source)
        lines = [
            f"{info.width} × {info.height} px · {info.codec or 'codec ?'}",
            f"{fmt(fps, 3)} fps ({source}) · {info.n_frames} quadros · "
            f"{fmt(info.n_frames / fps, 2)} s",
            f"Nyquist {fmt(fps / 2, 2)} Hz · limite fps/10 = {fmt(fps / 10, 2)} Hz",
        ]
        if info.measured_fps and abs(info.measured_fps - info.declared_fps) > 0.01 * info.declared_fps:
            lines.append(f"⚠ declarado {fmt(info.declared_fps, 3)} fps, medido "
                         f"{fmt(info.measured_fps, 3)} fps")
        self.info_label.setText("\n".join(lines))

    def _close_video(self) -> None:
        if self.reader is not None:
            self.reader.close()
        self.reader = None
        self.img.clear()
        self.slider.setEnabled(False)
        self.file_label.setText("Nenhum vídeo")
        self.info_label.setText("")
        self.frame_label.setText("")

    def _fps(self) -> float:
        info = self.state.video_info
        return self.state.session.video.fps_override or (info.fps if info else 30.0)

    def _frame_of(self, t: float) -> int:
        return int(round(t * self._fps()))

    def _current_time(self) -> float:
        return self.slider.value() / self._fps()

    def _show_current_frame(self) -> None:
        if self.reader is None:
            return
        k = self.slider.value()
        frame = self.reader.read(k)
        if frame is None:
            return
        self.img.setImage(frame, autoLevels=False, levels=(0, 255))
        t = k / self._fps()
        self.frame_label.setText(f"quadro {k} · {fmt(t, 3)} s")
        self._update_track_overlay(k)
        tr = self.state.track
        if tr is not None:
            self.cursor.setPos(t - tr.t0)

    # ================================================================== #
    # ROIs
    # ================================================================== #
    def _unique_name(self, base: str) -> str:
        names = {d["name"] for d in self.roi_items}
        if base not in names:
            return base
        i = 2
        while f"{base}_{i}" in names:
            i += 1
        return f"{base}_{i}"

    def _new_roi(self, is_ref: bool) -> None:
        if self.reader is None:
            return
        if is_ref and any(d["is_ref"] for d in self.roi_items):
            QMessageBox.information(self, "ROI", "Já existe uma ROI de referência.")
            return
        (x0, x1), (y0, y1) = self.vb.viewRange()
        info = self.state.video_info
        w = h = max(16, int(min(x1 - x0, y1 - y0) / 8))
        x = int(np.clip((x0 + x1) / 2 - w / 2, 0, info.width - w))
        y = int(np.clip((y0 + y1) / 2 - h / 2, 0, info.height - h))
        name = self._unique_name("referencia" if is_ref else "ponta")
        self._add_roi_item(name, x, y, w, h, is_ref)
        self._rois_changed()
        self.tabs.setCurrentIndex(0)

    def _add_roi_item(self, name, x, y, w, h, is_ref) -> None:
        idx = sum(1 for d in self.roi_items if not d["is_ref"])
        color = roi_color(idx, is_ref)
        pen = pg.mkPen(color, width=2)
        item = pg.RectROI([x, y], [w, h], pen=pen, hoverPen=pg.mkPen(color, width=3),
                          handlePen=pg.mkPen(color), handleHoverPen=pg.mkPen(color, width=2),
                          movable=True, rotatable=False, removable=False,
                          snapSize=1, translateSnap=True, scaleSnap=True)
        item.addScaleHandle([0, 0], [1, 1])
        label = pg.TextItem(name, color=color, anchor=(0, 1))
        self.vb.addItem(item)
        self.vb.addItem(label)
        d = {"name": name, "is_ref": is_ref, "item": item, "label": label, "color": color}
        self.roi_items.append(d)
        item.sigRegionChanged.connect(lambda _=None, d=d: self._place_label(d))
        item.sigRegionChangeFinished.connect(lambda _=None: self._rois_changed())
        self._place_label(d)
        li = QListWidgetItem(f"{name}" + ("  (referência)" if is_ref else ""))
        li.setData(Qt.UserRole, name)
        li.setForeground(QColor(color))
        li.setFlags(li.flags() | Qt.ItemIsEditable)
        self.roi_list.blockSignals(True)
        self.roi_list.addItem(li)
        self.roi_list.blockSignals(False)

    def _place_label(self, d: dict) -> None:
        pos = d["item"].pos()
        d["label"].setPos(pos[0], pos[1])

    def _clear_rois(self) -> None:
        for d in self.roi_items:
            self.vb.removeItem(d["item"])
            self.vb.removeItem(d["label"])
        self.roi_items.clear()
        self.roi_list.clear()
        self._clear_track_overlay()

    def _delete_roi(self) -> None:
        row = self.roi_list.currentRow()
        if row < 0:
            return
        d = self.roi_items.pop(row)
        self.state.session.video.roi_positions_mm.pop(d["name"], None)
        self.vb.removeItem(d["item"])
        self.vb.removeItem(d["label"])
        self.roi_list.takeItem(row)
        self._rois_changed()

    def _roi_renamed(self, li: QListWidgetItem) -> None:
        row = self.roi_list.row(li)
        d = self.roi_items[row]
        new = re.sub(r"\s+\(referência\)$", "", li.text()).strip()
        new = re.sub(r"[^\w\-]+", "_", new) or d["name"]
        if new != d["name"]:
            new = self._unique_name(new)
        pos = self.state.session.video.roi_positions_mm
        if d["name"] in pos and new != d["name"]:
            pos[new] = pos.pop(d["name"])
        d["name"] = new
        d["label"].setText(new)
        self.roi_list.blockSignals(True)
        li.setText(new + ("  (referência)" if d["is_ref"] else ""))
        self.roi_list.blockSignals(False)
        self._rois_changed()

    def _load_roi_pos(self, row: int) -> None:
        """Show the position along the beam of the selected ROI."""
        ok = 0 <= row < len(self.roi_items) and not self.roi_items[row]["is_ref"]
        self.roi_pos.blockSignals(True)
        self.roi_pos.setEnabled(ok)
        pos = self.state.session.video.roi_positions_mm
        self.roi_pos.put(pos.get(self.roi_items[row]["name"]) if ok else None)
        self.roi_pos.blockSignals(False)

    def _roi_pos_changed(self) -> None:
        row = self.roi_list.currentRow()
        if self._loading or not 0 <= row < len(self.roi_items):
            return
        name = self.roi_items[row]["name"]
        pos = self.state.session.video.roi_positions_mm
        v = self.roi_pos.get()
        if v is None:
            pos.pop(name, None)
        else:
            pos[name] = v
        self.state.mark_dirty()

    def _highlight_roi(self, row: int) -> None:
        for i, d in enumerate(self.roi_items):
            d["item"].setPen(pg.mkPen(d["color"], width=3.5 if i == row else 2))

    def _rois_changed(self) -> None:
        rois = []
        for d in self.roi_items:
            pos, size = d["item"].pos(), d["item"].size()
            rois.append({"name": d["name"], "x": int(round(pos[0])), "y": int(round(pos[1])),
                         "w": int(round(size[0])), "h": int(round(size[1])),
                         "is_reference": d["is_ref"]})
        self.state.session.video.rois = rois
        if self.state.session.compare.roi not in [r["name"] for r in rois]:
            self.state.session.compare.roi = None
        self.state.mark_dirty()
        self._set_stale(True)

    def _clear_track_overlay(self) -> None:
        for it in self.track_items.values():
            self.vb.removeItem(it)
        self.track_items.clear()

    def _update_track_overlay(self, k: int) -> None:
        tr = self.state.track
        if tr is None:
            self._clear_track_overlay()
            return
        i = k - tr.params.start_frame
        for name, res in tr.tracks.items():
            it = self.track_items.get(name)
            if it is None:
                it = QGraphicsRectItem()
                color = theme.REFERENCE if res.roi.is_reference else theme.ACCENT
                it.setPen(pg.mkPen(color, width=1.5, style=Qt.DashLine))
                self.vb.addItem(it)
                self.track_items[name] = it
            if 0 <= i < len(res.displacement):
                r = res.roi
                dx, dy = res.displacement[i]
                it.setRect(r.x + dx, r.y + dy, r.w, r.h)
                it.setVisible(True)
            else:
                it.setVisible(False)

    # ================================================================== #
    # calibration
    # ================================================================== #
    def _toggle_calibration(self, on: bool) -> None:
        if self.cal_roi is not None:
            self.vb.removeItem(self.cal_roi)
            self.cal_roi = None
        self.cal_apply.setEnabled(on)
        if not on or self.reader is None:
            return
        cal = self.state.session.video.calibration
        if cal:
            p1, p2 = cal["p1"], cal["p2"]
        else:
            (x0, x1), (y0, y1) = self.vb.viewRange()
            yc = (y0 + y1) / 2
            p1, p2 = [x0 + 0.3 * (x1 - x0), yc], [x0 + 0.7 * (x1 - x0), yc]
        self.cal_roi = pg.LineSegmentROI([p1, p2], pen=pg.mkPen(theme.WARN, width=2.5),
                                         hoverPen=pg.mkPen(theme.WARN, width=3.5))
        self.vb.addItem(self.cal_roi)
        self.cal_roi.sigRegionChanged.connect(self._calibration_moved)
        self._calibration_moved()

    def _cal_points(self):
        return [self.cal_roi.mapToParent(h.pos()) for h in self.cal_roi.getHandles()]

    def _calibration_moved(self) -> None:
        if self.cal_roi is None:
            return
        p1, p2 = self._cal_points()
        d = float(np.hypot(p2.x() - p1.x(), p2.y() - p1.y()))
        if d > 0:
            self.cal_px.setText(f"{fmt(d, 1)} px  →  {fmt(self.cal_len.value() / d, 5)} mm/px")

    def _apply_calibration(self) -> None:
        if self.cal_roi is None:
            return
        p1, p2 = self._cal_points()
        d = float(np.hypot(p2.x() - p1.x(), p2.y() - p1.y()))
        if d <= 0:
            return
        v = self.state.session.video
        v.calibration = {"p1": [p1.x(), p1.y()], "p2": [p2.x(), p2.y()],
                         "length_mm": self.cal_len.value(), "length_px": d}
        self.scale.put(self.cal_len.value() / d)   # triggers reanalysis
        self.cal_btn.setChecked(False)
        self.state.message.emit(f"Escala aplicada: {fmt(v.scale_mm_per_px, 5)} mm/px")

    # ================================================================== #
    # processing
    # ================================================================== #
    def run(self) -> None:
        s = self.state.session
        if self.reader is None:
            QMessageBox.information(self, "Vídeo", "Abra um vídeo primeiro.")
            return
        if not any(not r.get("is_reference") for r in s.video.rois):
            QMessageBox.information(self, "Vídeo", "Adicione ao menos uma ROI de medição.")
            return
        snapshot = copy.deepcopy(s)
        self._t_start = time.time()
        info = self.state.video_info
        fps = s.video.fps_override or info.fps
        first = self._frame_of(s.video.start_s)
        last = self._frame_of(s.video.end_s) if s.video.end_s else info.n_frames
        self.playback.begin_live(s.video.rois, max(1, min(last, info.n_frames) - first),
                                 fps, s.video.scale_mm_per_px, s.video.axis,
                                 s.video.compensate)
        self.tabs.setCurrentWidget(self.playback)
        emit = self._preview.emit if PREVIEW_INTERVAL else None
        self.worker = Worker(
            lambda progress, stop: run_video(snapshot, progress, stop, preview=emit,
                                             preview_interval=PREVIEW_INTERVAL or 1.0),
            parent=self)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self._busy(True)
        self.worker.start()

    def _busy(self, on: bool) -> None:
        for w in self.controls.findChildren(QWidget):
            if w not in (self.cancel_btn, self.progress, self.run_info):
                w.setEnabled(not on)
        self.run_btn.setVisible(not on)
        self.cancel_btn.setVisible(on)
        self.cancel_btn.setEnabled(on)
        self.progress.setVisible(on)
        self.progress.setValue(0)
        for d in self.roi_items:
            d["item"].translatable = not on
        if on:
            self.run_info.setText("Rastreando…")
        else:
            self.cal_apply.setEnabled(self.cal_btn.isChecked())

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        el = time.time() - self._t_start
        eta = el / max(done, 1) * (total - done)
        self.run_info.setText(f"{done}/{total} quadros · {fmt(done / max(el, 1e-9), 0)} "
                              f"quadros/s · restam ~{fmt(eta, 0)} s")

    def _cancel(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.cancel_btn.setEnabled(False)

    def _done(self, track) -> None:
        self._busy(False)
        el = time.time() - self._t_start
        stopped = self.worker is not None and self.worker.should_stop()
        self.worker = None
        self.run_info.setText(
            f"{track.n_frames} quadros em {fmt(el, 1)} s"
            + (" (interrompido)" if stopped else "") + ".")
        self._set_stale(False)
        self.playback.end_live()
        self.state.set_track(track)
        if self.state.session.file:
            try:
                save_track_cache(self.state.session, track)
            except OSError:
                pass
        self.tabs.setCurrentWidget(self.playback)

    def _failed(self, msg: str) -> None:
        self._busy(False)
        self.worker = None
        self.playback.end_live()
        self.playback.load()
        self.run_info.setText("Falhou.")
        QMessageBox.warning(self, "Processamento", msg)

    # ================================================================== #
    # results
    # ================================================================== #
    def _region_moved(self) -> None:
        if not self._loading:
            self._window_timer.start()

    def _apply_window(self) -> None:
        a = self.state.analysis
        if a is None:
            return
        t0, t1 = self.region.getRegion()
        t = a.times
        full = t0 <= t[0] + 1e-9 and t1 >= t[-1] - 1e-9
        self.state.session.video.window = None if full else [float(t0), float(t1)]
        self.state.mark_dirty()
        self.state.reanalyze()

    def _reset_window(self) -> None:
        self.state.session.video.window = None
        self.state.mark_dirty()
        self.state.reanalyze()

    def _draw_results(self) -> None:
        a = self.state.analysis
        self.disp_plot.clear()
        self.spec_plot.clear()
        self.modal_table.set_rows([])
        self.quality_table.set_rows([])
        self.bright_plot.clear()
        self.score_plot.clear()
        self._clear_track_overlay()
        if a is None:
            self.sgram_img.clear()
            self.window_label.setText("")
            return
        u = a.unit
        t = a.times
        self.disp_plot.setLabel("left", f"Deslocamento [{u}]")
        for i, (name, x) in enumerate(a.signals.items()):
            curve(self.disp_plot, t, x, theme.SERIES[i % len(theme.SERIES)],
                  f"{name} ({a.axes[name]})")
        self.disp_plot.addItem(self.region, ignoreBounds=True)
        self.disp_plot.addItem(self.cursor, ignoreBounds=True)
        first = next(iter(a.modal.values()))
        self._loading = True
        self.region.setBounds((t[0], t[-1]))
        self.region.setRegion(first.window)
        self._loading = False
        self.window_label.setText(
            f"Janela de análise {fmt(first.window[0], 2)}–{fmt(first.window[1], 2)} s "
            f"(arraste as bordas da faixa azul)")

        # decay envelope of each ROI
        for i, (name, ms) in enumerate(a.modal.items()):
            if ms.decay is None:
                continue
            x = a.signals[name]
            m = (t >= ms.window[0]) & (t <= ms.window[1])
            mean_w = float(x[m].mean())
            d = ms.decay
            a0, lam = d.envelope
            tp = d.peak_times + ms.window[0]
            te = np.linspace(tp[0], ms.window[1], 200)
            env = a0 * np.exp(-lam * (te - tp[0]))
            for sgn in (1, -1):
                curve(self.disp_plot, te, mean_w + sgn * env, theme.TEXT, width=1,
                      style=Qt.DashLine)
            self.disp_plot.plot(tp, d.peak_amplitudes + mean_w, pen=None, symbol="o",
                                symbolSize=5, symbolBrush=theme.BAD, symbolPen=None)

        rows = []
        for name, ms in a.modal.items():
            err = ms.error_predicted_percent
            crit = self.state.session.compare.crit_eb_pct
            rows.append([
                name, a.axes[name], fmt(ms.f_n, 3), fmt(ms.amplitude, 4),
                fmt(ms.zeta_half_power, 4), fmt(ms.zeta_log_decrement, 4),
                fmt(ms.std, 4), fmt(ms.f_predicted, 2),
                (fmt(err, 2), theme.OK if abs(err) <= crit else theme.BAD)
                if err is not None else "—",
            ])
        self.modal_table.set_rows(rows)
        self.modal_table.fit_height(6)

        # spectrum
        fs = a.fps
        self.spec_plot.setLabel("left", f"Amplitude [{u}]")
        for i, (name, ms) in enumerate(a.modal.items()):
            if ms.freqs is None:
                continue
            c = theme.SERIES[i % len(theme.SERIES)]
            curve(self.spec_plot, ms.freqs, ms.spectrum, c, name)
            for p in distinct_peaks(ms):
                self.spec_plot.plot([p.frequency], [p.amplitude], pen=None, symbol="t",
                                    symbolSize=9, symbolBrush=c, symbolPen=None)
                ti = pg.TextItem(f"{fmt(p.frequency, 2)} Hz", color=c, anchor=(0, 1))
                ti.setPos(p.frequency, p.amplitude)
                self.spec_plot.addItem(ti)
        if first.f_predicted:
            ln = vline(theme.OK, Qt.DashLine, f"previsto {fmt(first.f_predicted, 2)} Hz")
            ln.setPos(first.f_predicted)
            self.spec_plot.addItem(ln)
        ln = vline(theme.FAINT, Qt.DotLine, f"Nyquist {fmt(fs / 2, 1)} Hz")
        ln.setPos(fs / 2)
        self.spec_plot.addItem(ln)
        self.spec_plot.setXRange(0, spectrum_xmax(fs, first.f_n, first.f_predicted),
                                 padding=0)

        # spectrogram selector
        self.sgram_roi.blockSignals(True)
        current = self.sgram_roi.currentText()
        self.sgram_roi.clear()
        self.sgram_roi.addItems(list(a.signals))
        if current in a.signals:
            self.sgram_roi.setCurrentText(current)
        self.sgram_roi.blockSignals(False)
        self._draw_spectrogram()
        self._draw_quality()
        self._update_track_overlay(self.slider.value())

    def _draw_spectrogram(self) -> None:
        a = self.state.analysis
        name = self.sgram_roi.currentText()
        if a is None or name not in a.signals:
            self.sgram_img.clear()
            return
        x = a.signals[name]
        nper = int(min(len(x), max(32, 2 ** round(np.log2(a.fps)))))
        st, sf, sm = stft_spectrogram(x, a.fps, nperseg=nper, hop=max(1, nper // 8))
        floor = max(sm.max() * 1e-4, 1e-12)
        db = 20 * np.log10(np.maximum(sm, floor))
        self.sgram_img.setImage(db, autoLevels=True)
        dt = st[1] - st[0] if st.size > 1 else 1.0
        df = sf[1] - sf[0] if sf.size > 1 else 1.0
        self.sgram_img.setRect(pg.QtCore.QRectF(st[0] - dt / 2, sf[0] - df / 2,
                                                dt * st.size, df * sf.size))
        self.sgram_plot.autoRange()

    def _draw_quality(self) -> None:
        tr = self.state.track
        if tr is None:
            return
        q = tr.quality
        info = tr.info
        nominal = 1e3 / tr.fps
        rows = [
            ["Taxa usada", f"{fmt(tr.fps, 3)} fps ({tr.fps_source})"],
            ["Taxa declarada / medida", f"{fmt(info.declared_fps, 3)} / "
                                         f"{fmt(info.measured_fps, 3)} fps"],
            ["Quadros processados", f"{tr.n_frames} (a partir de {fmt(tr.t0, 3)} s)"],
            ["Redução de resolução", "não" if tr.resize_factor == 1 else
             f"{fmt(tr.resize_factor, 3)}×"],
            ["Intervalo entre quadros", f"{fmt(q.frame_interval_ms, 3)} ms "
                                        f"(nominal {fmt(nominal, 3)} ms)"],
            ["Jitter de tempo", f"{fmt(q.frame_jitter_ms, 3)} ms"],
            ["Quadros perdidos", (f"{tr.dropped_frames} — sinais reamostrados no tempo real "
                                  f"({fmt(float(tr.frame_times[-1]), 3)} s)"
                                  if tr.irregular else "0",
                                  theme.WARN if tr.irregular else theme.OK)],
            ["Cintilação de brilho", (f"{fmt(q.flicker_percent, 2)} % em "
                                      f"{fmt(q.flicker_hz, 2)} Hz",
                                      theme.WARN if q.flicker_percent > 1 else theme.OK)],
        ]
        for name in tr.tracks:
            rows.append([f"{name}: foco (var. Laplaciano)", fmt(q.focus[name], 0)])
            rows.append([f"{name}: pixels saturados",
                         (f"{fmt(q.saturation[name], 2)} %",
                          theme.WARN if q.saturation[name] > 2 else theme.OK)])
            rows.append([f"{name}: NCC mínimo / quadros perdidos",
                         (f"{fmt(q.min_score[name], 3)} / {q.lost_frames[name]}",
                          theme.BAD if q.lost_frames[name] else theme.OK)])
        self.quality_table.set_rows(rows)
        warns = q.warnings()
        self.quality_warn.setText("⚠ " + "; ".join(warns) if warns else
                                  "✓ Nenhum problema detectado no clipe.")
        self.quality_warn.setStyleSheet(f"color: {theme.WARN if warns else theme.OK};")

        t = tr.times
        curve(self.bright_plot, t, q.brightness, theme.MUTED)
        for i, (name, res) in enumerate(tr.tracks.items()):
            c = theme.REFERENCE if res.roi.is_reference else theme.SERIES[i % len(theme.SERIES)]
            curve(self.score_plot, t, res.score, c, name)
        self.score_plot.setYRange(0, 1.02)
