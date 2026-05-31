from __future__ import annotations

from PySide6 import QtWidgets

from ..core import constants as C
from ..core.frame import Frame
from ..core.memory import bits_to_int


class InspectorPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.text.setText("Hover the waveform to inspect a frame.")
        layout.addWidget(self.text)

    def show_frame(self, frame: Frame | None) -> None:
        if frame is None:
            self.text.setText("-")
            return
        self.text.setHtml(self._format(frame))

    @staticmethod
    def _format(f: Frame) -> str:
        t0_us = f.t_start_to * C.TO_SECONDS * 1e6
        t1_us = f.t_end_to * C.TO_SECONDS * 1e6
        rows = [
            ("kind", f.kind.value),
            ("direction", f.direction.value),
            ("label", f.label),
            (
                "time",
                f"{f.t_start_to:.0f} - {f.t_end_to:.0f} TO "
                f"({t0_us:.1f} - {t1_us:.1f} µs)",
            ),
            ("duration", f"{f.duration_to:.0f} TO ({f.duration_us:.1f} µs)"),
        ]
        if f.bits:
            rows.append(("bits", f"{len(f.bits)}: {f.bitstring}"))
            if len(f.bits) % 4 == 0:
                value = bits_to_int(f.bits)
                rows.append(("hex", f"0x{value:0{len(f.bits) // 4}X}"))
        if f.meta:
            rows.append(("meta", ", ".join(f"{k}={v}" for k, v in f.meta.items())))

        body = "".join(
            f"<tr><td style='color:#666;padding-right:10px;vertical-align:top'>{k}</td>"
            f"<td><b>{_esc(str(v))}</b></td></tr>"
            for k, v in rows
        )
        return f"<table style='font-family:monospace'>{body}</table>"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
