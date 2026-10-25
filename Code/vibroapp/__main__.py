"""Entry point: ``python -m vibroapp [sessao.vibro.json]`` from Code/."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Vibrometria")
    theme.apply(app)
    win = MainWindow()
    win.show()
    if len(sys.argv) > 1:
        win.open_session(sys.argv[1])
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
