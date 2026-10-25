"""Application state shared by the pages: the session being edited and the
results derived from it. Pages talk to each other only through these
signals."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from vibrometry.accelerometer import AccelRecord, TableData, build_record
from vibrometry.session import Session
from vibrometry.streaming import VideoTrack
from vibrometry.video_io import VideoInfo
from vibrometry.workflow import (
    ComparisonData,
    ModalSummary,
    VideoAnalysis,
    accel_modal,
    accel_settings,
    analyze_video,
    build_comparison,
)


class AppState(QObject):
    sessionReplaced = Signal()      # new / opened session: pages reload
    nameChanged = Signal()          # session name set from a page
    specimenChanged = Signal()      # plan inputs changed (predictions)
    trackChanged = Signal()         # tracking result set or cleared
    analysisChanged = Signal()      # video signals / modal results
    accelChanged = Signal()         # accelerometer record / summary
    comparisonChanged = Signal()
    dirtyChanged = Signal(bool)
    message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.session = Session()
        self.video_info: VideoInfo | None = None
        self.track: VideoTrack | None = None
        self.analysis: VideoAnalysis | None = None
        self.table: TableData | None = None
        self.accel: AccelRecord | None = None
        self.accel_summary: ModalSummary | None = None
        self.comparison: ComparisonData | None = None
        self.dirty = False

    # ------------------------------------------------------------------ #
    def mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self.dirtyChanged.emit(True)

    def mark_clean(self) -> None:
        if self.dirty:
            self.dirty = False
            self.dirtyChanged.emit(False)

    def replace_session(self, session: Session) -> None:
        self.session = session
        self.video_info = None
        self.track = None
        self.analysis = None
        self.table = None
        self.accel = None
        self.accel_summary = None
        self.comparison = None
        self.sessionReplaced.emit()
        self.mark_clean()
        for sig in (self.trackChanged, self.analysisChanged,
                    self.accelChanged, self.comparisonChanged):
            sig.emit()

    # ------------------------------------------------------------------ #
    def set_track(self, track: VideoTrack | None) -> None:
        self.track = track
        self.trackChanged.emit()
        self.reanalyze()

    def reanalyze(self) -> None:
        """Recompute video signals and modal results (cheap: no tracking)."""
        self.analysis = (analyze_video(self.session, self.track)
                         if self.track is not None else None)
        self.analysisChanged.emit()
        self.recompare()

    def set_table(self, table: TableData | None) -> None:
        self.table = table
        self.rebuild_accel()

    def rebuild_accel(self) -> None:
        self.accel = None
        self.accel_summary = None
        if self.table is not None:
            try:
                self.accel = build_record(self.table, accel_settings(self.session))
                self.accel_summary = accel_modal(self.session, self.accel)
            except Exception as exc:
                self.message.emit(f"Acelerômetro: {exc}")
        self.accelChanged.emit()
        self.recompare()

    def recompare(self) -> None:
        self.comparison = None
        if self.analysis is not None and self.accel is not None:
            try:
                self.comparison = build_comparison(self.session, self.analysis,
                                                   self.accel)
            except Exception as exc:
                self.message.emit(f"Comparação: {exc}")
        self.comparisonChanged.emit()
