"""Synthetic validation dataset dialog (planejamento section 10, software
tests before real data)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
)

from vibrometry.synthetic import generate_validation_dataset

from .widgets import Panel, Worker, dspin, form, hbox, muted, section, tidy, vbox


class SyntheticDialog(QDialog):
    """Generates video + accelerometer CSV + session with known ground truth
    and returns the session path in ``self.session_path``."""

    def __init__(self, parent, default_folder: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dados sintéticos de validação")
        self.setMinimumWidth(460)
        self.session_path: str | None = None
        self.worker: Worker | None = None

        self.kind = QComboBox()
        self.kind.addItem("Excitação senoidal + batida de sincronismo", "forced")
        self.kind.addItem("Vibração livre (puxar e soltar)", "free")
        self.f = dspin(8.0, 0.1, 500, 3, 0.5, "Hz")
        self.amp = dspin(2.0, 0.001, 100, 3, 0.1, "mm")
        self.zeta = dspin(0.01, 0.0, 0.5, 4, 0.001)
        self.scale = dspin(0.25, 0.001, 100, 4, 0.01, "mm/px")
        self.fps = dspin(240, 1, 10000, 1, 30, "fps")
        self.dur = dspin(8.0, 1, 120, 1, 1, "s")
        self.offset = dspin(0.8374, -60, 60, 4, 0.01, "s")
        self.acc_fs = dspin(1000, 10, 100000, 0, 100, "Hz")
        self.vnoise = dspin(1.5, 0, 50, 2, 0.5, "níveis de cinza")
        self.anoise = dspin(0.002, 0, 10, 4, 0.001, "g")
        self.folder = QLineEdit(default_folder)
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        self.go = QPushButton("Gerar e abrir")
        self.go.setObjectName("Primary")
        cancel = QPushButton("Fechar")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        p = Panel()
        p.lay.addWidget(section("Movimento imposto"))
        f = form()
        f.addRow("Tipo", self.kind)
        f.addRow("Frequência", self.f)
        f.addRow("Amplitude", self.amp)
        f.addRow("Amortecimento ζ", self.zeta)
        p.lay.addLayout(f)
        p.lay.addWidget(section("Câmera"))
        f = form()
        f.addRow("Escala", self.scale)
        f.addRow("Taxa", self.fps)
        f.addRow("Duração", self.dur)
        f.addRow("Ruído", self.vnoise)
        p.lay.addLayout(f)
        p.lay.addWidget(section("Acelerômetro"))
        f = form()
        f.addRow("Taxa", self.acc_fs)
        f.addRow("Atraso (verdade)", self.offset)
        f.addRow("Ruído", self.anoise)
        p.lay.addLayout(f)
        p.lay.addWidget(muted("Os valores impostos ficam registrados nas observações da "
                              "sessão, para conferir o que o app recupera."))
        p.lay.addLayout(hbox(self.folder, browse))

        lay = vbox(self, margins=16, spacing=10)
        lay.addWidget(p)
        lay.addWidget(self.progress)
        lay.addLayout(hbox(None, cancel, self.go))

        self.kind.currentIndexChanged.connect(
            lambda: self.zeta.setEnabled(self.kind.currentData() == "free"))
        self.zeta.setEnabled(False)
        tidy(self)
        browse.clicked.connect(self._browse)
        cancel.clicked.connect(self.reject)
        self.go.clicked.connect(self._generate)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta de destino", self.folder.text())
        if d:
            self.folder.setText(d)

    def _generate(self) -> None:
        kwargs = dict(
            kind=self.kind.currentData(), f=self.f.value(), amplitude_mm=self.amp.value(),
            zeta=self.zeta.value(), scale_mm_per_px=self.scale.value(), fps=self.fps.value(),
            duration=self.dur.value(), video_noise=self.vnoise.value(),
            acc_fs=self.acc_fs.value(), acc_offset_s=self.offset.value(),
            acc_noise_g=self.anoise.value(),
        )
        folder = Path(self.folder.text())
        self.worker = Worker(lambda _p, _s: generate_validation_dataset(folder, **kwargs),
                             parent=self)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.go.setEnabled(False)
        self.progress.setVisible(True)
        self.worker.start()

    def _done(self, result: dict) -> None:
        self.session_path = str(result["session"])
        self.accept()

    def _failed(self, msg: str) -> None:
        self.go.setEnabled(True)
        self.progress.setVisible(False)
        QMessageBox.warning(self, "Dados sintéticos", msg)
