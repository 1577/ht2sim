from __future__ import annotations

import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from ..core import constants as C
from ..core.config import Coding
from ..core.frame import Frame
from ..signal.builder import build_merged_waveform, build_waveforms
from ..signal.waveform import AnnotationKind

pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")
pg.setConfigOptions(antialias=True)

READER_COLOR = "#1f77b4"
TAG_COLOR = "#d62728"
IDLE_COLOR = "#9aa0a6"
BIT_COLOR = "#555555"
FRAME_COLOR = "#222222"
GAP_BRUSH = pg.mkBrush(0, 0, 0, 18)
CURSOR_PEN = pg.mkPen("#0a8f3c", width=1, style=QtCore.Qt.DashLine)

WAVE_AMPLITUDE = 0.55

_Y_RANGE = (-0.3, 1.45)
_Y_BITS = 0.80
_Y_FRAME = 1.12

_CHANNEL_COLOR = {"reader": READER_COLOR, "tag": TAG_COLOR}


def _scaled(ys: list[float]) -> list[float]:
    return [y * WAVE_AMPLITUDE for y in ys]


def _prefix(xs: list[float], ys: list[float], t: float) -> tuple[list[float], list[float]]:
    cx: list[float] = []
    cy: list[float] = []
    for x, y in zip(xs, ys):
        if x <= t:
            cx.append(x)
            cy.append(y)
        else:
            break
    if not cx:
        return [], []
    if cx[-1] < t:
        cx.append(t)
        cy.append(cy[-1])
    return cx, cy


class _MicrosecondAxis(pg.AxisItem):

    def tickStrings(self, values, scale, spacing):
        return [f"{v * C.TO_SECONDS * 1e6:.0f}" for v in values]


class WaveformPlot(QtWidgets.QWidget):
    cursorMoved = QtCore.Signal(str)
    cursorFrame = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._frames: list[Frame] = []
        self._coding = Coding.MANCHESTER
        self._states: list = []
        self._final_state = "WAIT"
        self._mode = "split"
        self._show_bits = True
        self._total = 0.0
        self._frame_anns: list = []
        self._bit_anns: list = []
        self._plots: dict[str, pg.PlotItem] = {}
        self._cursors: list[pg.InfiniteLine] = []
        self._reveal_curves: list[tuple] = []
        self._reveal_items: list[tuple] = []
        self._reveal_t: float | None = None

        self.glw = pg.GraphicsLayoutWidget()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.glw)
        self.glw.scene().sigMouseMoved.connect(self._on_mouse_moved)

        self._build_layout()


    def set_exchange(
        self,
        frames: list[Frame],
        coding: Coding,
        states: list | None = None,
        final_state: str = "WAIT",
    ) -> None:
        self._frames = list(frames)
        self._coding = coding
        self._states = list(states) if states else []
        self._final_state = final_state
        self._total = max((f.t_end_to for f in frames), default=0.0)
        self._render()
        self.set_x_range(0, self._total)

    def set_mode(self, mode: str) -> None:
        if mode not in ("split", "merged"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode == self._mode:
            return
        self._mode = mode
        self._build_layout()
        self._render()
        self.set_x_range(0, self._total)

    def set_bit_labels(self, show: bool) -> None:
        self._show_bits = show
        self._render()

    def set_x_range(self, t0: float, t1: float) -> None:
        if self._plots:
            next(iter(self._plots.values())).setXRange(t0, t1, padding=0.02)


    def set_playhead(self, x: float) -> None:
        x = max(0.0, min(x, self._total))
        for line in self._cursors:
            line.setPos(x)
        self.cursorMoved.emit(self.readout_at(x))
        self.cursorFrame.emit(self.frame_at(x))

    def ensure_visible(self, x: float) -> None:
        if not self._plots:
            return
        vb = next(iter(self._plots.values())).vb
        (t0, t1), _ = vb.viewRange()
        width = t1 - t0
        if width <= 0 or width >= self._total:
            return
        if x < t0 or x > t1:
            new0 = min(max(0.0, x - 0.15 * width), self._total - width)
            self.set_x_range(new0, new0 + width)

    @property
    def mode(self) -> str:
        return self._mode


    def export_png(self, path: str) -> bool:
        return bool(self.glw.grab().save(str(path)))

    def export_svg(self, path: str) -> None:
        from PySide6.QtGui import QPainter
        from PySide6.QtSvg import QSvgGenerator

        size = self.glw.size()
        generator = QSvgGenerator()
        generator.setFileName(str(path))
        generator.setSize(size)
        generator.setViewBox(self.glw.rect())
        painter = QPainter(generator)
        try:
            self.glw.render(painter)
        finally:
            painter.end()


    def _build_layout(self) -> None:
        self.glw.clear()
        self._plots.clear()
        if self._mode == "split":
            p_reader = self.glw.addPlot(
                row=0, col=0, axisItems={"top": _MicrosecondAxis(orientation="top")}
            )
            p_tag = self.glw.addPlot(row=1, col=0)
            self._setup_plot(p_reader, "reader", top_axis=True, bottom_axis=False)
            self._setup_plot(p_tag, "tag", top_axis=False, bottom_axis=True)
            p_tag.setXLink(p_reader)
            p_reader.getAxis("top").setLabel("time (µs)")
            p_tag.getAxis("bottom").setLabel("time (TO = carrier periods)")
            self._plots = {"reader": p_reader, "tag": p_tag}
        else:
            p = self.glw.addPlot(
                row=0, col=0, axisItems={"top": _MicrosecondAxis(orientation="top")}
            )
            self._setup_plot(p, "reader + tag", top_axis=True, bottom_axis=True)
            p.getAxis("top").setLabel("time (µs)")
            p.getAxis("bottom").setLabel("time (TO = carrier periods)")
            self._plots = {"merged": p}

    def _setup_plot(self, plot, lane, *, top_axis, bottom_axis) -> None:
        plot.setMouseEnabled(x=True, y=False)
        plot.setYRange(*_Y_RANGE, padding=0)
        plot.showGrid(x=True, y=False, alpha=0.15)
        plot.setLabel("left", lane)
        plot.getAxis("left").setStyle(showValues=False)
        plot.getAxis("left").setWidth(70)
        plot.showAxis("top") if top_axis else plot.hideAxis("top")
        plot.showAxis("bottom") if bottom_axis else plot.hideAxis("bottom")


    def _render(self) -> None:
        for plot in self._plots.values():
            plot.clear()
        self._reveal_curves = []
        self._reveal_items = []
        if not self._frames:
            self._frame_anns, self._bit_anns = [], []
            return

        if self._mode == "split":
            ws = build_waveforms(self._frames, self._coding)
            self._frame_anns = ws.annotations_of(AnnotationKind.FRAME)
            self._bit_anns = ws.annotations_of(AnnotationKind.BIT)
            self._draw_step(self._plots["reader"], ws.reader, READER_COLOR)
            self._draw_step(self._plots["tag"], ws.tag, TAG_COLOR)
        else:
            merged, anns = build_merged_waveform(self._frames, self._coding)
            self._frame_anns = [a for a in anns if a.kind is AnnotationKind.FRAME]
            self._bit_anns = [a for a in anns if a.kind is AnnotationKind.BIT]
            self._draw_merged(self._plots["merged"], merged)

        self._add_cursors()
        self._draw_annotations()
        self.set_reveal(self._reveal_t)

    def _draw_step(self, plot, wave, color) -> None:
        xs, ys = wave.step_points()
        if xs:
            ys = _scaled(ys)
            item = plot.plot(xs, ys, pen=pg.mkPen(color, width=2))
            self._reveal_curves.append((item, list(xs), ys))

    def _draw_merged(self, plot, merged) -> None:
        xs, ys = merged.step_points()
        if xs:
            ys = _scaled(ys)
            item = plot.plot(xs, ys, pen=pg.mkPen(IDLE_COLOR, width=2))
            self._reveal_curves.append((item, list(xs), ys))
        for ann in self._frame_anns:
            color = _CHANNEL_COLOR.get(ann.channel)
            if color is None:
                continue
            wx, wy = merged.window_step_points(ann.t_start_to, ann.t_end_to)
            if wx:
                wy = _scaled(wy)
                item = plot.plot(wx, wy, pen=pg.mkPen(color, width=2))
                self._reveal_curves.append((item, list(wx), wy))


    def _draw_annotations(self) -> None:
        for ann in self._frame_anns:
            plot = self._plot_for(ann.channel)
            if ann.channel in ("reader", "tag"):
                color = _CHANNEL_COLOR[ann.channel] if self._mode == "merged" else FRAME_COLOR
                self._add_frame_label(plot, ann, color)
            else:
                for p in self._plots.values():
                    self._add_gap_region(p, ann)
        if self._show_bits:
            for ann in self._bit_anns:
                self._add_bit_label(self._plot_for(ann.channel), ann)

    def _plot_for(self, channel: str):
        if self._mode == "merged":
            return self._plots["merged"]
        return self._plots.get(channel, self._plots["reader"])

    def _add_frame_label(self, plot, ann, color) -> None:
        center = ann.t_start_to + ann.duration_to / 2.0
        text = pg.TextItem(ann.text, color=color, anchor=(0.5, 0))
        text.setPos(center, _Y_FRAME)
        plot.addItem(text, ignoreBounds=True)
        self._reveal_items.append((text, ann.t_start_to))
        for x in (ann.t_start_to, ann.t_end_to):
            line = pg.InfiniteLine(x, angle=90, pen=pg.mkPen(220, 220, 220, width=1))
            plot.addItem(line, ignoreBounds=True)
            self._reveal_items.append((line, x))

    def _add_gap_region(self, plot, ann) -> None:
        if ann.duration_to <= 0:
            return
        region = pg.LinearRegionItem(
            values=(ann.t_start_to, ann.t_end_to),
            movable=False,
            brush=GAP_BRUSH,
            pen=pg.mkPen(None),
        )
        region.setZValue(-10)
        plot.addItem(region, ignoreBounds=True)
        self._reveal_items.append((region, ann.t_start_to))

    def _add_bit_label(self, plot, ann) -> None:
        center = ann.t_start_to + ann.duration_to / 2.0
        color = _CHANNEL_COLOR.get(ann.channel, BIT_COLOR) if self._mode == "merged" else BIT_COLOR
        text = pg.TextItem(ann.text, color=color, anchor=(0.5, 0.5))
        text.setPos(center, _Y_BITS)
        plot.addItem(text, ignoreBounds=True)
        self._reveal_items.append((text, ann.t_start_to))

    def set_reveal(self, t: float | None) -> None:
        self._reveal_t = t
        for item, xs, ys in self._reveal_curves:
            if t is None:
                item.setData(xs, ys)
            else:
                cx, cy = _prefix(xs, ys, t)
                item.setData(cx, cy)
        for item, start in self._reveal_items:
            item.setVisible(t is None or start <= t)


    def _add_cursors(self) -> None:
        self._cursors = []
        for plot in self._plots.values():
            line = pg.InfiniteLine(0, angle=90, movable=False, pen=CURSOR_PEN)
            plot.addItem(line, ignoreBounds=True)
            self._cursors.append(line)

    def _on_mouse_moved(self, pos) -> None:
        x = None
        for plot in self._plots.values():
            if plot.sceneBoundingRect().contains(pos):
                x = plot.vb.mapSceneToView(pos).x()
                break
        if x is None:
            return
        for line in self._cursors:
            line.setPos(x)
        self.cursorMoved.emit(self.readout_at(x))
        self.cursorFrame.emit(self.frame_at(x))

    def readout_at(self, x: float) -> str:
        parts = [
            f"t = {x:.0f} TO ({x * C.TO_SECONDS * 1e6:.1f} µs)",
            f"state: {self.state_at(x)}",
        ]
        frame = self._containing(self._frame_anns, x)
        if frame is not None:
            parts.append(frame.text)
        bit = self._containing(self._bit_anns, x)
        if bit is not None:
            parts.append(f"bit '{bit.text}' [{bit.channel}]")
        return "   |   ".join(parts)

    def state_at(self, x: float) -> str:
        for span in self._states:
            if span.t_start_to <= x < span.t_end_to:
                return span.state
        return self._final_state

    def frame_at(self, x: float) -> Frame | None:
        for f in self._frames:
            if f.t_start_to <= x < f.t_end_to:
                return f
        return None

    @staticmethod
    def _containing(anns, x: float):
        for a in anns:
            if a.t_start_to <= x < a.t_end_to:
                return a
        return None
