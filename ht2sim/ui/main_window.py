from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..core.scenario import Scenario
from ..io.export import export_frames_csv, export_waveform_csv
from ..io.scenario_io import load_scenario, save_scenario
from .editor_panel import EditorPanel
from .inspector import InspectorPanel
from .memory_view import MemoryView
from .plot_widget import WaveformPlot


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ht2sim")
        self.resize(1660, 940)

        self.plot = WaveformPlot()
        self.plot.cursorMoved.connect(self.statusBar().showMessage)
        self.plot.cursorFrame.connect(self._on_cursor_frame)

        central = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self.plot, 1)
        col.addWidget(self._build_transport())
        self.setCentralWidget(central)

        self._playhead = 0.0
        self._revealing = False
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)

        self._build_editor_dock()
        self._build_inspector_dock()
        self._build_memory_dock()
        self._build_menu()
        self._build_toolbar()

        self._duration_label = QtWidgets.QLabel()
        self.statusBar().addPermanentWidget(self._duration_label)

        self._rebuild()
        self._apply_default_dock_widths()


    def _build_editor_dock(self) -> None:
        self.editor = EditorPanel(Scenario.default())
        self.editor.scenarioChanged.connect(self._rebuild)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.editor)
        self._editor_dock = QtWidgets.QDockWidget("Editor", self)
        self._editor_dock.setWidget(scroll)
        self._editor_dock.setMinimumWidth(300)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self._editor_dock)

    def _build_inspector_dock(self) -> None:
        self.inspector = InspectorPanel()
        self._inspector_dock = QtWidgets.QDockWidget("Inspector", self)
        self._inspector_dock.setWidget(self.inspector)
        self._inspector_dock.setMinimumWidth(200)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self._inspector_dock)

    def _build_memory_dock(self) -> None:
        self.memory_view = MemoryView()
        self._memory_dock = QtWidgets.QDockWidget("Tag memory", self)
        self._memory_dock.setWidget(self.memory_view)
        self._memory_dock.setMinimumWidth(200)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self._memory_dock)
        self.splitDockWidget(self._inspector_dock, self._memory_dock, QtCore.Qt.Vertical)

    def _build_transport(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(6, 3, 6, 3)

        self.play_btn = QtWidgets.QToolButton()
        self.play_btn.setText("▶ Play")
        self.play_btn.setCheckable(True)
        self.play_btn.toggled.connect(self._on_play_toggled)
        h.addWidget(self.play_btn)

        stop_btn = QtWidgets.QToolButton()
        stop_btn.setText("■ Stop")
        stop_btn.clicked.connect(self._stop)
        h.addWidget(stop_btn)

        h.addWidget(QtWidgets.QLabel("  Speed:"))
        self.speed_box = QtWidgets.QComboBox()
        for label, to_per_s in (
            ("Realtime", 125_000.0),
            ("1/100", 1_250.0),
            ("1/500", 250.0),
            ("1/2000", 62.5),
        ):
            self.speed_box.addItem(label, to_per_s)
        self.speed_box.setCurrentIndex(1)
        h.addWidget(self.speed_box)

        self.timeline = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.timeline.setRange(0, 1000)
        self.timeline.valueChanged.connect(self._on_slider)
        h.addWidget(self.timeline, 1)

        self.time_label = QtWidgets.QLabel("0 TO")
        self.time_label.setMinimumWidth(150)
        h.addWidget(self.time_label)
        return bar

    def _apply_default_dock_widths(self) -> None:
        self.resizeDocks(
            [self._editor_dock, self._inspector_dock],
            [340, 320],
            QtCore.Qt.Horizontal,
        )

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("Open scenario…", self._open_scenario)
        file_menu.addAction("Save scenario…", self._save_scenario)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("Export")
        export_menu.addAction("Plot as PNG…", self._export_png)
        export_menu.addAction("Plot as SVG…", self._export_svg)
        export_menu.addAction("Frames as CSV…", self._export_frames_csv)
        export_menu.addAction("Waveform as CSV…", self._export_waveform_csv)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("View")
        tb.setMovable(False)

        tb.addWidget(QtWidgets.QLabel("Layout: "))
        self.mode_box = QtWidgets.QComboBox()
        self.mode_box.addItem("Split lanes", "split")
        self.mode_box.addItem("Merged", "merged")
        self.mode_box.currentIndexChanged.connect(self._on_mode_changed)
        tb.addWidget(self.mode_box)

        tb.addSeparator()
        tb.addAction("Fit all", self._fit_all)

        self._bits_checkbox = QtWidgets.QCheckBox("Bit labels")
        self._bits_checkbox.setChecked(True)
        self._bits_checkbox.toggled.connect(self.plot.set_bit_labels)
        tb.addWidget(self._bits_checkbox)


    def _rebuild(self) -> None:
        scenario = self.editor.scenario
        self._result, memory = scenario.simulate()
        self.plot.set_exchange(
            self._result.frames,
            scenario.tag.coding,
            self._result.states,
            self._result.final_state,
        )
        self.memory_view.show_memory(memory)
        total = self._result.total_duration_to
        status = "" if self._result.completed else f"  ⚠ {self._result.error}"
        self._duration_label.setText(
            f"total: {total:.0f} TO ≈ {total * 8 / 1000:.2f} ms   "
            f"frames: {len(self._result.frames)}   "
            f"coding: {scenario.tag.coding.value}{status}"
        )
        self.play_btn.setChecked(False)
        self._revealing = False
        self._playhead = 0.0
        self._update_playhead()


    def _on_mode_changed(self, _index: int) -> None:
        self.plot.set_mode(self.mode_box.currentData())
        self._update_playhead()

    def _on_cursor_frame(self, frame) -> None:
        self.inspector.show_frame(frame)

    def _fit_all(self) -> None:
        self.plot.set_x_range(0, self._result.total_duration_to)


    def _on_play_toggled(self, playing: bool) -> None:
        if playing:
            if self._playhead >= self._result.total_duration_to:
                self._playhead = 0.0
            self._revealing = True
            self.play_btn.setText("❚❚ Pause")
            self._update_playhead()
            self._timer.start()
        else:
            self.play_btn.setText("▶ Play")
            self._timer.stop()

    def _stop(self) -> None:
        self.play_btn.setChecked(False)
        self._revealing = False
        self._playhead = 0.0
        self._update_playhead()

    def _on_tick(self) -> None:
        dt = self._timer.interval() / 1000.0
        self._playhead += self.speed_box.currentData() * dt
        if self._playhead >= self._result.total_duration_to:
            self._playhead = self._result.total_duration_to
            self.play_btn.setChecked(False)
        self._update_playhead(follow=True)

    def _on_slider(self, value: int) -> None:
        total = self._result.total_duration_to
        if total > 0:
            self._playhead = value / 1000.0 * total
            self._update_playhead()

    def _update_playhead(self, follow: bool = False) -> None:
        self.plot.set_reveal(self._playhead if self._revealing else None)
        self.plot.set_playhead(self._playhead)
        if follow:
            self.plot.ensure_visible(self._playhead)
        total = self._result.total_duration_to
        if total > 0:
            self.timeline.blockSignals(True)
            self.timeline.setValue(int(self._playhead / total * 1000))
            self.timeline.blockSignals(False)
        self.time_label.setText(f"{self._playhead:.0f} TO / {self._playhead * 8:.1f} µs")


    def _open_scenario(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open scenario", "", "Scenario JSON (*.json)"
        )
        if not path:
            return
        try:
            scenario = load_scenario(path)
        except (OSError, ValueError, KeyError) as exc:
            QtWidgets.QMessageBox.warning(self, "Open failed", str(exc))
            return
        self.editor.set_scenario(scenario)
        self._rebuild()

    def _save_scenario(self) -> None:
        path = self._ask_save("Save scenario", "Scenario JSON (*.json)", ".json")
        if path:
            save_scenario(self.editor.scenario, path)

    def _export_png(self) -> None:
        path = self._ask_save("Export plot as PNG", "PNG image (*.png)", ".png")
        if path:
            self.plot.export_png(path)

    def _export_svg(self) -> None:
        path = self._ask_save("Export plot as SVG", "SVG image (*.svg)", ".svg")
        if path:
            self.plot.export_svg(path)

    def _export_frames_csv(self) -> None:
        path = self._ask_save("Export frames as CSV", "CSV (*.csv)", ".csv")
        if path:
            export_frames_csv(self._result, path)

    def _export_waveform_csv(self) -> None:
        path = self._ask_save("Export waveform as CSV", "CSV (*.csv)", ".csv")
        if path:
            export_waveform_csv(self._result, self.editor.scenario.tag.coding, path)

    def _ask_save(self, title: str, filt: str, suffix: str) -> str | None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, title, "", filt)
        if not path:
            return None
        if not path.lower().endswith(suffix):
            path += suffix
        return path


def default_session_result():
    return Scenario.default().run()
