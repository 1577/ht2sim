from __future__ import annotations

import sys

from PySide6 import QtWidgets

from .main_window import MainWindow


def run(argv: list[str] | None = None) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        argv if argv is not None else sys.argv
    )
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
