"""Step 5 — Lote: process many sessions and pool repetitions (planejamento
R9; repeatability CV, section 11)."""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QWidget,
)

from vibrometry.report import group_statistics, latex_batch_table
from vibrometry.session import SESSION_SUFFIX, Session
from vibrometry.workflow import process_session

from . import theme
from .state import AppState
from .widgets import Panel, Table, Worker, fmt, hbox, muted, section, vbox

COLUMNS = [
    ("sessao", "Sessão", None), ("status", "Status", None),
    ("f_video_hz", "f vídeo [Hz]", 3), ("f_acc_hz", "f acel. [Hz]", 3),
    ("erro_f_pct", "ε f [%]", 3), ("A_opt", "A vídeo", 4), ("A_ref", "A acel.", 4),
    ("erro_A_pct", "ε A [%]", 2), ("dfase_graus", "Δφ [°]", 2),
    ("zeta_video", "ζ vídeo", 4), ("erro_prevista_pct", "ε EB [%]", 2),
]
GROUP_COLUMNS = [
    ("grupo", "Grupo", None), ("n", "n", 0),
    ("f_video_hz_media", "f vídeo [Hz]", 3), ("f_video_hz_cv_pct", "CV f [%]", 3),
    ("A_opt_media", "A vídeo", 4), ("A_opt_cv_pct", "CV A [%]", 2),
    ("erro_f_pct_media", "ε f médio [%]", 3), ("erro_A_pct_media", "ε A médio [%]", 2),
    ("dfase_graus_media", "Δφ médio [°]", 2), ("zeta_video_media", "ζ médio", 4),
]


def _process_all(progress, should_stop, paths: list[str], use_cache: bool, emit) -> list:
    results = []
    for i, p in enumerate(paths):
        if should_stop():
            break
        progress(i, len(paths))
        try:
            s = Session.load(p)
            r = process_session(s, should_stop=should_stop, use_cache=use_cache)
            row = r.row()
            row["status"] = "erro" if r.error else ("cache" if r.from_cache else "ok")
        except Exception as exc:
            row = {"sessao": Path(p).name, "status": "erro",
                   "erro": f"{type(exc).__name__}: {exc}"}
        row["_path"] = p
        results.append(row)
        emit(row)
    progress(len(results), len(paths))
    return results


class BatchPage(QWidget):
    openSession = Signal(str)
    _rowReady = Signal(object)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("Page")
        self.state = state
        self.paths: list[str] = []
        self.rows: list[dict] = []
        self.worker: Worker | None = None

        self.add_files = QPushButton("Adicionar sessões…")
        self.add_folder = QPushButton("Adicionar pasta…")
        self.remove = QPushButton("Remover")
        self.clear = QPushButton("Limpar")
        for b in (self.remove, self.clear):
            b.setObjectName("Flat")
        self.use_cache = QCheckBox("Reaproveitar rastreamentos salvos")
        self.use_cache.setChecked(True)
        self.run_btn = QPushButton("Processar lote")
        self.run_btn.setObjectName("Primary")
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setVisible(False)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.info = muted("", wrap=False)
        self.export_csv = QPushButton("Exportar CSV")
        self.export_tex = QPushButton("Exportar LaTeX")

        self.table = Table([c[1] for c in COLUMNS])
        self.groups = Table([c[1] for c in GROUP_COLUMNS])
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"color: {theme.BAD};")

        top = Panel()
        top.lay.addLayout(hbox(self.add_files, self.add_folder, self.remove, self.clear,
                               None, self.use_cache, self.run_btn, self.cancel_btn))
        top.lay.addWidget(self.progress)
        top.lay.addWidget(self.info)

        p1 = Panel()
        p1.lay.addWidget(section("Sessões"))
        p1.lay.addWidget(self.table, 1)
        p1.lay.addWidget(self.error_label)
        p1.lay.addWidget(muted("Duplo clique abre a sessão para revisão."))
        p2 = Panel()
        p2.lay.addWidget(section("Repetições agrupadas (sufixo _r<n> removido)"))
        p2.lay.addWidget(self.groups, 1)
        p2.lay.addLayout(hbox(None, self.export_csv, self.export_tex))

        split = QSplitter(Qt.Vertical)
        split.addWidget(p1)
        split.addWidget(p2)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setChildrenCollapsible(False)

        lay = vbox(self, margins=16, spacing=12)
        lay.addWidget(top)
        lay.addWidget(split, 1)

        self.add_files.clicked.connect(self._add_files)
        self.add_folder.clicked.connect(self._add_folder)
        self.remove.clicked.connect(self._remove)
        self.clear.clicked.connect(self._clear)
        self.run_btn.clicked.connect(self._run)
        self.cancel_btn.clicked.connect(lambda: self.worker and self.worker.stop())
        self.export_csv.clicked.connect(self._export_csv)
        self.export_tex.clicked.connect(self._export_tex)
        self.table.cellDoubleClicked.connect(self._open_row)
        self._rowReady.connect(self._row_done)
        self._refresh()

    # ------------------------------------------------------------------ #
    def _start_dir(self) -> str:
        s = self.state.session
        return os.path.dirname(s.file or s.video.path or "")

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar sessões", self._start_dir(),
            f"Sessões (*{SESSION_SUFFIX});;Todos (*.*)")
        self._extend(paths)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Pasta com sessões", self._start_dir())
        if folder:
            self._extend(sorted(str(p) for p in Path(folder).rglob(f"*{SESSION_SUFFIX}")))

    def _extend(self, paths) -> None:
        for p in paths:
            if p not in self.paths:
                self.paths.append(p)
        self._refresh()

    def _remove(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            if r < len(self.paths):
                path = self.paths.pop(r)
                self.rows = [x for x in self.rows if x.get("_path") != path]
        self._refresh()

    def _clear(self) -> None:
        self.paths.clear()
        self.rows.clear()
        self._refresh()

    def _refresh(self) -> None:
        by_path = {r.get("_path"): r for r in self.rows}
        table_rows = []
        for p in self.paths:
            r = by_path.get(p)
            if r is None:
                table_rows.append([Path(p).name.replace(SESSION_SUFFIX, ""), "pendente"]
                                  + ["" for _ in COLUMNS[2:]])
                continue
            cells = []
            for key, _, nd in COLUMNS:
                v = r.get(key)
                if key == "status":
                    color = {"erro": theme.BAD, "ok": theme.OK, "cache": theme.OK}.get(v)
                    cells.append((v, color) if color else v)
                else:
                    cells.append(v if nd is None else fmt(v, nd))
            table_rows.append(cells)
        self.table.set_rows(table_rows)
        errors = [f"{r['sessao']}: {r['erro']}" for r in self.rows if r.get("erro")]
        self.error_label.setText("\n".join(errors))
        groups = group_statistics([r for r in self.rows if not r.get("erro")])
        self.groups.set_rows([[g.get(k) if nd is None else fmt(g.get(k), nd)
                               for k, _, nd in GROUP_COLUMNS] for g in groups])
        self.info.setText(f"{len(self.paths)} sessão(ões) na lista · "
                          f"{len(self.rows)} processada(s)")
        has = bool(self.rows)
        self.export_csv.setEnabled(has)
        self.export_tex.setEnabled(has)
        self.run_btn.setEnabled(bool(self.paths))

    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        if not self.paths:
            return
        self.rows.clear()
        self._refresh()
        self._t0 = time.time()
        paths = list(self.paths)
        self.worker = Worker(_process_all, paths, self.use_cache.isChecked(),
                             self._rowReady.emit, parent=self)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(lambda msg: (self._done(None),
                                                QMessageBox.warning(self, "Lote", msg)))
        self._busy(True)
        self.worker.start()

    def _busy(self, on: bool) -> None:
        for w in (self.add_files, self.add_folder, self.remove, self.clear, self.use_cache,
                  self.export_csv, self.export_tex):
            w.setEnabled(not on)
        self.run_btn.setVisible(not on)
        self.cancel_btn.setVisible(on)
        self.progress.setVisible(on)

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self.info.setText(f"Processando {min(done + 1, total)}/{total}…")

    def _row_done(self, row: dict) -> None:
        self.rows.append(row)
        self._refresh()

    def _done(self, _result) -> None:
        self._busy(False)
        self.worker = None
        self._refresh()
        self.info.setText(self.info.text() + f" · {fmt(time.time() - self._t0, 1)} s")

    def _open_row(self, row: int, _col: int) -> None:
        if 0 <= row < len(self.paths):
            self.openSession.emit(self.paths[row])

    # ------------------------------------------------------------------ #
    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV",
                                              os.path.join(self._start_dir(), "lote.csv"),
                                              "CSV (*.csv)")
        if not path:
            return
        keys: list[str] = []
        for r in self.rows:
            keys += [k for k in r if k not in keys and not k.startswith("_")]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(self.rows)
        groups = group_statistics([r for r in self.rows if not r.get("erro")])
        gpath = Path(path).with_name(Path(path).stem + "_grupos.csv")
        gkeys: list[str] = []
        for g in groups:
            gkeys += [k for k in g if k not in gkeys]
        with open(gpath, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=gkeys)
            w.writeheader()
            w.writerows(groups)
        self.state.message.emit(f"Exportado: {Path(path).name} e {gpath.name}")

    def _export_tex(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar tabela LaTeX",
                                              os.path.join(self._start_dir(), "tabela_lote.tex"),
                                              "LaTeX (*.tex)")
        if path:
            Path(path).write_text(latex_batch_table([r for r in self.rows if not r.get("erro")]),
                                  encoding="utf-8")
            self.state.message.emit(f"Exportado: {Path(path).name}")
