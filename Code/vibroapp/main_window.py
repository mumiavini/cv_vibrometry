"""Main window: header (session name, open/save), step navigation and the
six pages."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vibrometry.session import SESSION_SUFFIX, Session
from vibrometry.workflow import save_track_cache

from . import theme
from .dialogs import SyntheticDialog
from .page_accel import AccelPage
from .page_batch import BatchPage
from .page_compare import ComparePage
from .page_plan import PlanPage
from .page_report import ReportPage
from .page_video import VideoPage
from .state import AppState
from .widgets import debounce, tidy

APP_NAME = "Vibrometria"
STEPS = ["Planejar", "Vídeo", "Acelerômetro", "Comparar", "Lote", "Relatório"]
CODE_DIR = Path(__file__).resolve().parents[1]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = AppState()
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        # ---------------- header ---------------- #
        header = QWidget()
        header.setObjectName("Header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 12, 8)
        hl.setSpacing(8)
        brand = QLabel(APP_NAME)
        brand.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        sep = QLabel("/")
        sep.setStyleSheet(f"color: {theme.FAINT};")
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("SessionName")
        self.name_edit.setPlaceholderText("sessão sem nome")
        self.name_edit.setMinimumWidth(420)
        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet(f"color: {theme.FAINT};")
        new_btn = QPushButton("Nova")
        open_btn = QPushButton("Abrir")
        save_btn = QPushButton("Salvar")
        for b in (new_btn, open_btn):
            b.setObjectName("Flat")
        more = QToolButton()
        more.setObjectName("Flat")
        more.setText("···")
        more.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(more)
        menu.addAction("Salvar como…", self.save_as)
        menu.addAction("Abrir pasta da sessão", self.open_session_folder)
        menu.addSeparator()
        menu.addAction("Gerar dados sintéticos de validação…", self.synthetic)
        menu.addSeparator()
        menu.addAction("Sobre", self.about)
        more.setMenu(menu)
        hl.addWidget(brand)
        hl.addWidget(sep)
        hl.addWidget(self.name_edit)
        hl.addWidget(self.dirty_label)
        hl.addStretch(1)
        hl.addWidget(new_btn)
        hl.addWidget(open_btn)
        hl.addWidget(save_btn)
        hl.addWidget(more)

        # ---------------- navigation + pages ---------------- #
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(190)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 12, 0, 12)
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for i, name in enumerate(STEPS, 1):
            self.nav.addItem(f"{i}   {name}")
        sl.addWidget(self.nav)
        hint = QLabel("Ctrl+1…6 alterna as etapas")
        hint.setStyleSheet(f"color: {theme.FAINT}; font-size: 8.5pt; padding: 0 16px;")
        sl.addWidget(hint)

        self.pages = QStackedWidget()
        self.plan = PlanPage(self.state)
        self.video = VideoPage(self.state)
        self.accel = AccelPage(self.state)
        self.compare = ComparePage(self.state)
        self.batch = BatchPage(self.state)
        self.report = ReportPage(self.state)
        for p in (self.plan, self.video, self.accel, self.compare, self.batch, self.report):
            tidy(p)
            self.pages.addWidget(p)

        body = QWidget()
        body.setObjectName("Body")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(side)
        bl.addWidget(self.pages, 1)

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(header)
        cl.addWidget(body, 1)
        self.setCentralWidget(central)

        self.file_label = QLabel()
        self.statusBar().addPermanentWidget(self.file_label)
        self.statusBar().setSizeGripEnabled(False)

        # ---------------- wiring ---------------- #
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        new_btn.clicked.connect(self.new_session)
        open_btn.clicked.connect(self.open_dialog)
        save_btn.clicked.connect(self.save)
        self.name_edit.editingFinished.connect(self._name_edited)
        self.state.nameChanged.connect(self.refresh_title)
        self.state.sessionReplaced.connect(self.refresh_title)
        self.state.dirtyChanged.connect(lambda _: self.refresh_title())
        self.state.message.connect(lambda m: self.statusBar().showMessage(m, 6000))
        self.batch.openSession.connect(self._open_from_batch)
        self._reanalyze = debounce(self, 300, self._specimen_changed)
        self.state.specimenChanged.connect(self._reanalyze.start)

        for seq, fn in ((QKeySequence.New, self.new_session),
                        (QKeySequence.Open, self.open_dialog),
                        (QKeySequence.Save, self.save),
                        (QKeySequence("Ctrl+Shift+S"), self.save_as)):
            act = QAction(self)
            act.setShortcut(seq)
            act.triggered.connect(fn)
            self.addAction(act)
        for i in range(len(STEPS)):
            act = QAction(self)
            act.setShortcut(QKeySequence(f"Ctrl+{i + 1}"))
            act.triggered.connect(lambda _=False, i=i: self.nav.setCurrentRow(i))
            self.addAction(act)
        self.refresh_title()
        self.nav.setFocus()

    # ------------------------------------------------------------------ #
    def refresh_title(self) -> None:
        s = self.state.session
        if self.name_edit.text() != s.name:
            self.name_edit.setText(s.name)
        self.dirty_label.setText("● não salvo" if self.state.dirty else "")
        self.file_label.setText(s.file or "sessão não salva")
        self.setWindowTitle(f"{s.name or 'sessão sem nome'}{' *' if self.state.dirty else ''}"
                            f" — {APP_NAME}")

    def _name_edited(self) -> None:
        name = self.name_edit.text().strip()
        if name != self.state.session.name:
            self.state.session.name = name
            self.state.mark_dirty()
            self.state.nameChanged.emit()

    def _specimen_changed(self) -> None:
        self.state.reanalyze()
        if self.state.table is not None:
            self.state.rebuild_accel()

    # ------------------------------------------------------------------ #
    def _confirm_discard(self) -> bool:
        if not self.state.dirty:
            return True
        r = QMessageBox.question(
            self, APP_NAME, "A sessão atual tem alterações não salvas. Salvar antes?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def new_session(self) -> None:
        if self._confirm_discard():
            self.state.replace_session(Session())
            self.nav.setCurrentRow(0)

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        start = os.path.dirname(self.state.session.file or "") or str(CODE_DIR)
        path, _ = QFileDialog.getOpenFileName(self, "Abrir sessão", start,
                                              f"Sessões (*{SESSION_SUFFIX});;Todos (*.*)")
        if path:
            self.open_session(path)

    def open_session(self, path: str) -> None:
        try:
            session = Session.load(path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Não foi possível abrir a sessão:\n{exc}")
            return
        self.state.replace_session(session)
        self.statusBar().showMessage(f"Sessão aberta: {Path(path).name}", 5000)
        self.nav.setCurrentRow(3 if self.state.comparison is not None else
                               1 if session.video.path else 0)

    def _open_from_batch(self, path: str) -> None:
        if self._confirm_discard():
            self.open_session(path)

    def save(self) -> bool:
        if not self.state.session.file:
            return self.save_as()
        return self._write(self.state.session.file)

    def save_as(self) -> bool:
        s = self.state.session
        base = os.path.dirname(s.file or s.video.path or "") or str(CODE_DIR)
        name = (s.name or "sessao") + SESSION_SUFFIX
        path, _ = QFileDialog.getSaveFileName(self, "Salvar sessão", os.path.join(base, name),
                                              f"Sessões (*{SESSION_SUFFIX})")
        return self._write(path) if path else False

    def _write(self, path: str) -> bool:
        s = self.state.session
        try:
            saved = s.save(path)
            if self.state.track is not None:
                save_track_cache(s, self.state.track)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Não foi possível salvar:\n{exc}")
            return False
        self.state.mark_clean()
        self.refresh_title()
        self.statusBar().showMessage(f"Sessão salva: {saved.name}", 5000)
        return True

    def open_session_folder(self) -> None:
        s = self.state.session
        d = os.path.dirname(s.file or s.video.path or "")
        if d:
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def synthetic(self) -> None:
        if not self._confirm_discard():
            return
        dlg = SyntheticDialog(self, str(CODE_DIR / "vibrometry" / "outputs" / "sintetico"))
        if dlg.exec() and dlg.session_path:
            self.open_session(dlg.session_path)
            self.nav.setCurrentRow(1)
            self.statusBar().showMessage(
                "Dados sintéticos gerados. Processe o vídeo e compare com a verdade "
                "registrada nas observações (passo 1).", 10000)

    def about(self) -> None:
        QMessageBox.about(
            self, APP_NAME,
            f"<b>{APP_NAME}</b><br>Vibrometria óptica por fase (filtros de Gabor) com "
            "comparação contra acelerômetro.<br><br>TCC — Vinicius Andrade Trento, PUCPR.")

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
