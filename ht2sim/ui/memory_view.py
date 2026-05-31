from __future__ import annotations

from PySide6 import QtGui, QtWidgets

from ..core.memory import TransponderMemory

_NAMES = {
    0: "IDE / serial",
    1: "PSW_B",
    2: "(internal)",
    3: "TMCF + PSW_T",
    4: "USER 0",
    5: "USER 1",
    6: "USER 2",
    7: "USER 3",
}


class MemoryView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QtWidgets.QTableWidget(8, 3)
        self.table.setHorizontalHeaderLabels(["Pg", "Name", "Hex"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self._mono = QtGui.QFont("Consolas")
        self._mono.setStyleHint(QtGui.QFont.Monospace)

    def show_memory(self, memory: TransponderMemory) -> None:
        for n in range(8):
            value = memory.read_page(n).value
            cells = [str(n), _NAMES[n], f"0x{value:08X}"]
            for col, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if col in (0, 2):
                    item.setFont(self._mono)
                self.table.setItem(n, col, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
