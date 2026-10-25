"""Minimal black theme: pure black background, near-black panels, one accent,
and a fixed colour per source (video = blue, accelerometer = orange) used
consistently on every plot. Exported figures/videos keep a white background
(they go into the printed thesis and slides)."""

from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

BG = "#000000"
SURFACE = "#0D0D0F"          # panels, plots
HOVER = "#18181B"
BORDER = "#232327"
AXIS = "#3F3F46"             # plot axis lines
SCROLL = "#3F3F46"
TEXT = "#EDEDEF"
MUTED = "#8B8B94"
FAINT = "#56565E"
ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"
ACCENT_SOFT = "#0F1E36"      # selected items
ACCENT_DIM = "#1E3A66"       # disabled primary button, slider fill
VIDEO = "#3B82F6"
ACCEL = "#F97316"
REFERENCE = "#71717A"
OK = "#22C55E"
BAD = "#EF4444"
WARN = "#F59E0B"

# extra series colours (several ROIs)
SERIES = ["#3B82F6", "#14B8A6", "#A78BFA", "#F472B6", "#84CC16", "#22D3EE"]

# Fusion derives the check-box outline from the window colour, which is
# invisible on black, so the indicator is drawn by the stylesheet instead
CHECK_ICON = (Path(__file__).parent / "assets" / "check.svg").as_posix()

QSS = f"""
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QWidget#Page, QWidget#Body {{ background: {BG}; }}
QWidget#Header {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QWidget#Sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QListWidget#Nav {{ border: none; background: transparent; outline: 0; }}
QListWidget#Nav::item {{ padding: 8px 14px; margin: 1px 8px; border-radius: 6px; color: {MUTED}; }}
QListWidget#Nav::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
QListWidget#Nav::item:hover:!selected {{ background: {HOVER}; color: {TEXT}; }}
QFrame#Panel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; }}
QLabel#Section {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; padding-top: 6px; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Title {{ font-size: 12pt; font-weight: 600; }}
QLabel#Big {{ font-size: 16pt; font-weight: 600; }}
QLabel#Empty {{ color: {FAINT}; font-size: 11pt; }}
QLineEdit#SessionName {{ border: 1px solid transparent; background: transparent;
    font-size: 11pt; font-weight: 600; padding: 2px 4px; }}
QLineEdit#SessionName:hover {{ border: 1px solid {BORDER}; }}
QLineEdit#SessionName:focus {{ border: 1px solid {ACCENT}; background: {SURFACE}; }}
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 5px 12px; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {FAINT}; }}
QPushButton#Primary {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT};
    font-weight: 600; }}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#Primary:disabled {{ background: {ACCENT_DIM}; border-color: {ACCENT_DIM};
    color: {MUTED}; }}
QPushButton#Flat, QToolButton#Flat {{ border: none; background: transparent; color: {MUTED};
    padding: 4px 8px; }}
QPushButton#Flat:hover, QToolButton#Flat:hover {{ color: {TEXT}; background: {HOVER}; }}
QToolButton#Flat::menu-indicator {{ image: none; }}
QLineEdit, QAbstractSpinBox, QComboBox, QPlainTextEdit, QTextBrowser {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 5px; padding: 3px 6px;
    selection-background-color: {ACCENT}; }}
QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT}; }}
QAbstractSpinBox QLineEdit {{ border: none; padding: 0; background: transparent; }}
/* Arrow buttons hidden by width only: with Qt 6.12, styling a spin box
   that uses setButtonSymbols(NoButtons) collapses its editor to 1 px. */
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT}; outline: 0; }}
QListWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 5px; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 6px 12px; margin-right: 2px; color: {MUTED};
    border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QTableWidget {{ border: none; gridline-color: {BORDER}; background: {SURFACE};
    alternate-background-color: #111114; selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT}; }}
QHeaderView::section {{ background: {SURFACE}; border: none; border-bottom: 1px solid {BORDER};
    padding: 4px 8px; color: {MUTED}; font-weight: 600; }}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}
QProgressBar {{ border: none; background: {BORDER}; border-radius: 3px; max-height: 6px;
    text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {SCROLL}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {SCROLL}; border-radius: 4px; min-width: 24px; }}
QSplitter::handle {{ background: {BG}; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 12px; margin: -5px 0; border-radius: 6px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT_DIM}; border-radius: 2px; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QStatusBar QLabel {{ color: {MUTED}; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {SCROLL}; border-radius: 3px;
    background: {SURFACE}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT};
    image: url({CHECK_ICON}); }}
QCheckBox::indicator:disabled {{ border-color: {BORDER}; }}
QToolTip {{ background: {HOVER}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px; }}
QMessageBox, QInputDialog {{ background: {BG}; }}
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QDialog {{ background: {BG}; }}
"""


def apply(app: QApplication) -> None:
    try:   # dark window frame / native dialogs on Windows 11 (Qt >= 6.8)
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    except AttributeError:
        pass
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    # full palette, so what the stylesheet doesn't cover (Fusion arrows,
    # check marks, message boxes) is dark too
    pal = QPalette()
    roles = {
        QPalette.Window: BG, QPalette.WindowText: TEXT, QPalette.Base: SURFACE,
        QPalette.AlternateBase: HOVER, QPalette.Text: TEXT, QPalette.Button: SURFACE,
        QPalette.ButtonText: TEXT, QPalette.BrightText: "#FFFFFF",
        QPalette.Highlight: ACCENT, QPalette.HighlightedText: "#FFFFFF",
        QPalette.ToolTipBase: HOVER, QPalette.ToolTipText: TEXT,
        QPalette.PlaceholderText: FAINT, QPalette.Link: ACCENT,
        QPalette.Light: AXIS, QPalette.Midlight: BORDER, QPalette.Mid: BORDER,
        QPalette.Dark: BG, QPalette.Shadow: BG,
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        pal.setColor(QPalette.Disabled, role, QColor(FAINT))
    app.setPalette(pal)
    app.setStyleSheet(QSS)

    pg.setConfigOptions(
        imageAxisOrder="row-major",
        background=SURFACE,
        foreground=MUTED,
        antialias=True,
    )
