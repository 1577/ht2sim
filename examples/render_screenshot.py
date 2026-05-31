import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from ht2sim.ui.main_window import MainWindow


def main() -> None:
    argv = sys.argv[1:]
    out = argv[0] if len(argv) > 0 else "phase_screenshot.png"
    mode = argv[1] if len(argv) > 1 else "split"
    t0 = float(argv[2]) if len(argv) > 2 else None
    t1 = float(argv[3]) if len(argv) > 3 else None

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    win = MainWindow()
    win.resize(1400, 700)
    win.show()

    win.mode_box.setCurrentIndex(1 if mode == "merged" else 0)
    if t0 is not None and t1 is not None:
        win.plot.set_x_range(t0, t1)

    for _ in range(10):
        app.processEvents()
    win.grab().save(out)
    print(f"saved {out}  (mode={mode})")


if __name__ == "__main__":
    main()
