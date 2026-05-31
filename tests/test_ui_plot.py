import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6 import QtWidgets
from pyqtgraph import PlotDataItem

from ht2sim.core.session import ReadPage, StartAuth
from ht2sim.ui.editor_panel import EditorPanel
from ht2sim.ui.inspector import InspectorPanel
from ht2sim.ui.main_window import MainWindow, default_session_result
from ht2sim.ui.plot_widget import WaveformPlot
from ht2sim.core.scenario import Scenario


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _plot_with_data():
    result = default_session_result()
    widget = WaveformPlot()
    widget.set_exchange(result.frames, Scenario.default().tag.coding)
    return widget, result


def test_split_mode_draws_both_lanes(app):
    widget, _ = _plot_with_data()
    assert widget.mode == "split"
    assert "reader" in widget._plots and "tag" in widget._plots
    assert any(isinstance(i, PlotDataItem) for i in widget._plots["reader"].items)
    assert any(isinstance(i, PlotDataItem) for i in widget._plots["tag"].items)


def test_merged_mode_single_lane(app):
    widget, _ = _plot_with_data()
    widget.set_mode("merged")
    assert set(widget._plots) == {"merged"}
    assert sum(isinstance(i, PlotDataItem) for i in widget._plots["merged"].items) > 1


def test_readout_and_frame_at(app):
    widget, _ = _plot_with_data()
    text = widget.readout_at(0.0)
    assert "TO" in text and "START_AUTH" in text
    frame = widget.frame_at(0.0)
    assert frame is not None and frame.label.startswith("START_AUTH")


def test_scenario_runs_and_reflects_edits():
    scn = Scenario.default()
    assert scn.run().completed
    scn.tag.psw_b = 0xDEADBEEF
    assert not scn.run().completed


def test_editor_emits_on_program_change(app):
    editor = EditorPanel(Scenario.default())
    seen = []
    editor.scenarioChanged.connect(lambda: seen.append(1))
    editor.type_combo.setCurrentText("HALT")
    editor._add_step()
    assert seen
    assert any("HALT" in editor.step_list.item(i).text()
               for i in range(editor.step_list.count()))


def test_editor_tmcf_dcs_toggles_coding(app):
    from ht2sim.core.config import Coding

    editor = EditorPanel(Scenario.default())
    assert editor.scenario.tag.coding is Coding.MANCHESTER
    editor.dcs_check.setChecked(True)
    assert editor.scenario.tag.coding is Coding.CDP


def test_inspector_formats_a_frame(app):
    result = default_session_result()
    command = result.frames[0]
    inspector = InspectorPanel()
    inspector.show_frame(command)
    assert "START_AUTH" in inspector.text.toPlainText()
    inspector.show_frame(None)


def test_main_window_builds_and_toggles_mode(app):
    win = MainWindow()
    assert win.plot.parent() is not None
    win.mode_box.setCurrentIndex(1)
    assert win.plot.mode == "merged"
    win.mode_box.setCurrentIndex(0)
    assert win.plot.mode == "split"


def test_main_window_live_rebuild_on_edit(app):
    win = MainWindow()
    win.editor.type_combo.setCurrentText("READ_PAGE")
    win.editor.page_spin.setValue(4)
    win.editor._add_step()
    assert any("READ_PAGE[4]" in f.label for f in win._result.frames)


def test_set_playhead_emits_frame(app):
    widget, _ = _plot_with_data()
    seen = []
    widget.cursorFrame.connect(seen.append)
    widget.set_playhead(0.0)
    assert seen and seen[-1] is not None and seen[-1].label.startswith("START_AUTH")


def test_reveal_clips_curve_and_hides_later_annotations(app):
    widget, result = _plot_with_data()
    total = result.total_duration_to

    widget.set_reveal(0.0)
    item, xs, ys = widget._reveal_curves[0]
    cx, _ = item.getData()
    assert cx is None or len(cx) <= 1
    late = max(widget._reveal_items, key=lambda it: it[1])[0]
    assert not late.isVisible()

    widget.set_reveal(total)
    cx, _ = widget._reveal_curves[0][0].getData()
    assert cx is not None and len(cx) > 0
    assert late.isVisible()

    widget.set_reveal(None)
    cx, _ = widget._reveal_curves[0][0].getData()
    assert len(cx) == len(widget._reveal_curves[0][1])


def test_state_shows_in_readout(app):
    win = MainWindow()
    win.editor.type_combo.setCurrentText("READ_PAGE")
    win.editor.page_spin.setValue(0)
    win.editor._add_step()
    assert "state: WAIT" in win.plot.readout_at(0.0)
    assert "state: AUTHORIZED" in win.plot.readout_at(win._result.total_duration_to)


def test_playback_reveals_progressively(app):
    win = MainWindow()
    win.speed_box.setCurrentIndex(2)
    win.play_btn.setChecked(True)
    win._on_tick()
    assert win._revealing
    assert win.plot._reveal_t == win._playhead
    win._stop()
    assert not win._revealing
    assert win.plot._reveal_t is None


def test_transport_play_tick_and_stop(app):
    win = MainWindow()
    total = win._result.total_duration_to
    win.speed_box.setCurrentIndex(0)
    win.play_btn.setChecked(True)
    assert win._timer.isActive()
    win._on_tick()
    assert win._playhead > 0.0
    win._stop()
    assert win._playhead == 0.0
    assert not win._timer.isActive()
    assert total > 0


def test_transport_slider_scrubs(app):
    win = MainWindow()
    win.timeline.setValue(500)
    assert win._playhead > 0.0
    assert abs(win._playhead - win._result.total_duration_to / 2) < win._result.total_duration_to * 0.05


def test_memory_view_shows_all_pages(app):
    from ht2sim.ui.memory_view import MemoryView
    from ht2sim.core.memory import TransponderMemory

    view = MemoryView()
    view.show_memory(TransponderMemory.delivery_default())
    assert view.table.columnCount() == 3
    assert view.table.rowCount() == 8
    assert view.table.item(0, 2).text() == "0x12345610"
    assert view.table.item(1, 1).text() == "PSW_B"


def test_memory_view_reflects_write(app):
    from ht2sim.ui.memory_view import MemoryView

    scn = Scenario.default()
    from ht2sim.core.session import WritePage

    scn.program.append(WritePage(4, 0xCAFEBABE))
    _, memory = scn.simulate()
    view = MemoryView()
    view.show_memory(memory)
    assert view.table.item(4, 2).text() == "0xCAFEBABE"


def test_plot_exports_png(app, tmp_path):
    widget, _ = _plot_with_data()
    out = tmp_path / "plot.png"
    assert widget.export_png(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_plot_exports_svg(app, tmp_path):
    widget, _ = _plot_with_data()
    out = tmp_path / "plot.svg"
    widget.export_svg(str(out))
    assert out.exists() and out.stat().st_size > 0
    assert out.read_text(errors="ignore").lstrip().startswith("<?xml")


def test_scenario_load_updates_editor_and_plot(app, tmp_path):
    from ht2sim.io.scenario_io import save_scenario
    from ht2sim.core.scenario import Scenario as Scn

    scn = Scn.default()
    from ht2sim.core.session import Halt

    scn.program.append(Halt())
    path = tmp_path / "s.json"
    save_scenario(scn, str(path))

    win = MainWindow()
    loaded = __import__("ht2sim.io.scenario_io", fromlist=["load_scenario"]).load_scenario(
        str(path)
    )
    win.editor.set_scenario(loaded)
    win._rebuild()
    assert any(f.label.startswith("HALT") for f in win._result.frames)
