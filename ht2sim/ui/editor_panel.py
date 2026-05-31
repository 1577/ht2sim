from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..core.config import TMCF
from ..core.scenario import Scenario, TagConfig
from ..core.session import (
    Halt,
    ReadPage,
    ReadPageInv,
    StartAuth,
    WritePage,
)

_RO_MODES = [
    ("Disabled", (1, 1)),
    ("ISO 11784/5", (0, 0)),
    ("MIRO", (0, 1)),
    ("PCF7931", (1, 0)),
]
_STEP_TYPES = ["START_AUTH", "READ_PAGE", "READ_PAGE_INV", "WRITE_PAGE", "HALT"]


def parse_hex(text: str, default: int = 0) -> int:
    try:
        return int(text.strip().lower().replace("0x", ""), 16)
    except ValueError:
        return default


def format_action(a) -> str:
    if isinstance(a, StartAuth):
        return f"START_AUTH   psw_b=0x{a.psw_b:08X}"
    if isinstance(a, ReadPage):
        return f"READ_PAGE   page {a.page}"
    if isinstance(a, ReadPageInv):
        return f"READ_PAGE_INV   page {a.page}"
    if isinstance(a, WritePage):
        return f"WRITE_PAGE   page {a.page} = 0x{a.value:08X}"
    if isinstance(a, Halt):
        return "HALT"
    return str(a)


class EditorPanel(QtWidgets.QWidget):
    scenarioChanged = QtCore.Signal()

    def __init__(self, scenario: Scenario | None = None, parent=None) -> None:
        super().__init__(parent)
        self.scenario = scenario or Scenario.default()

        outer = QtWidgets.QVBoxLayout(self)
        outer.addWidget(self._build_tag_group())
        outer.addWidget(self._build_program_group())
        outer.addStretch(1)

        self._load_from_scenario()


    def _build_tag_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Transponder (password mode)")
        form = QtWidgets.QFormLayout(box)

        self.ide_edit = QtWidgets.QLineEdit()
        self.pswb_edit = QtWidgets.QLineEdit()
        self.pswt_edit = QtWidgets.QLineEdit()
        for w in (self.ide_edit, self.pswb_edit, self.pswt_edit):
            w.setMaximumWidth(100)
            w.editingFinished.connect(self._on_tag_changed)
        form.addRow("IDE (page 0)", self.ide_edit)
        form.addRow("PSW_B (page 1)", self.pswb_edit)
        form.addRow("PSW_T (24-bit)", self.pswt_edit)

        self.dcs_check = QtWidgets.QCheckBox("DCS - CDP coding")
        self.pwp1_check = QtWidgets.QCheckBox("PWP1 - protect 4,5")
        self.pwp0_check = QtWidgets.QCheckBox("PWP0 - protect 6,7")
        self.skl_check = QtWidgets.QCheckBox("SKL - lock PSW_B")
        self.pg3l_check = QtWidgets.QCheckBox("PG3L - lock page 3")
        self.ro_combo = QtWidgets.QComboBox()
        for label, _ in _RO_MODES:
            self.ro_combo.addItem(label)
        for w in (
            self.dcs_check, self.pwp1_check, self.pwp0_check,
            self.skl_check, self.pg3l_check,
        ):
            w.toggled.connect(self._on_tag_changed)
        self.ro_combo.currentIndexChanged.connect(self._on_tag_changed)

        form.addRow("Read-only mode (MS)", self.ro_combo)
        form.addRow(self.dcs_check)
        form.addRow(self.pwp1_check)
        form.addRow(self.pwp0_check)
        form.addRow(self.skl_check)
        form.addRow(self.pg3l_check)
        self.tmcf_label = QtWidgets.QLabel()
        self.tmcf_label.setStyleSheet("color:#666")
        self.tmcf_label.setWordWrap(True)
        form.addRow("TMCF", self.tmcf_label)

        self.user_edits = []
        for i in range(4):
            edit = QtWidgets.QLineEdit()
            edit.setMaximumWidth(100)
            edit.editingFinished.connect(self._on_tag_changed)
            self.user_edits.append(edit)
            form.addRow(f"USER {i} (page {4 + i})", edit)

        reset = QtWidgets.QPushButton("Reset to delivery default")
        reset.clicked.connect(self._reset_tag)
        form.addRow(reset)
        return box


    def _build_program_group(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Reader program")
        v = QtWidgets.QVBoxLayout(box)

        self.step_list = QtWidgets.QListWidget()
        v.addWidget(self.step_list)

        row = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Remove", self._remove_step),
            ("Up", lambda: self._move_step(-1)),
            ("Down", lambda: self._move_step(+1)),
        ):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        v.addLayout(row)

        add = QtWidgets.QGridLayout()
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(_STEP_TYPES)
        self.type_combo.currentIndexChanged.connect(self._update_param_enabled)
        self.page_spin = QtWidgets.QSpinBox()
        self.page_spin.setRange(0, 7)
        self.param_edit = QtWidgets.QLineEdit()
        self.param_edit.setPlaceholderText("hex")
        add_btn = QtWidgets.QPushButton("Add step")
        add_btn.clicked.connect(self._add_step)

        add.addWidget(QtWidgets.QLabel("Type"), 0, 0)
        add.addWidget(self.type_combo, 0, 1)
        add.addWidget(QtWidgets.QLabel("Page"), 1, 0)
        add.addWidget(self.page_spin, 1, 1)
        self.param_label = QtWidgets.QLabel("PSW_B")
        add.addWidget(self.param_label, 2, 0)
        add.addWidget(self.param_edit, 2, 1)
        add.addWidget(add_btn, 3, 0, 1, 2)
        v.addLayout(add)
        self._update_param_enabled()
        return box


    def set_scenario(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self._load_from_scenario()

    def _load_from_scenario(self) -> None:
        self._loading = True
        tag = self.scenario.tag
        self.ide_edit.setText(f"{tag.ide:08X}")
        self.pswb_edit.setText(f"{tag.psw_b:08X}")
        self.pswt_edit.setText(f"{tag.psw_t:06X}")
        tmcf = TMCF.from_byte(tag.tmcf & 0xFF)
        self.dcs_check.setChecked(bool(tmcf.dcs))
        self.pwp1_check.setChecked(bool(tmcf.pwp1))
        self.pwp0_check.setChecked(bool(tmcf.pwp0))
        self.skl_check.setChecked(bool(tmcf.skl))
        self.pg3l_check.setChecked(bool(tmcf.pg3l))
        self.ro_combo.setCurrentIndex(
            next(i for i, (_, ms) in enumerate(_RO_MODES) if ms == (tmcf.ms1, tmcf.ms0))
        )
        for edit, value in zip(self.user_edits, tag.user):
            edit.setText(f"{value:08X}")
        self._loading = False
        self._refresh_tmcf_label()
        self._refresh_step_list()

    def _tmcf_byte(self) -> int:
        ms1, ms0 = _RO_MODES[self.ro_combo.currentIndex()][1]
        return (
            (int(self.skl_check.isChecked()) << 7)
            | (int(self.pg3l_check.isChecked()) << 6)
            | (int(self.pwp1_check.isChecked()) << 5)
            | (int(self.pwp0_check.isChecked()) << 4)
            | (0 << 3)
            | (ms1 << 2)
            | (ms0 << 1)
            | int(self.dcs_check.isChecked())
        )

    def _on_tag_changed(self) -> None:
        if getattr(self, "_loading", False):
            return
        tag = self.scenario.tag
        tag.ide = parse_hex(self.ide_edit.text()) & 0xFFFFFFFF
        tag.psw_b = parse_hex(self.pswb_edit.text()) & 0xFFFFFFFF
        tag.psw_t = parse_hex(self.pswt_edit.text()) & 0xFFFFFF
        tag.tmcf = self._tmcf_byte()
        tag.user = [parse_hex(e.text()) & 0xFFFFFFFF for e in self.user_edits]
        self._refresh_tmcf_label()
        self.scenarioChanged.emit()

    def _refresh_tmcf_label(self) -> None:
        self.tmcf_label.setText(str(TMCF.from_byte(self._tmcf_byte())))

    def _reset_tag(self) -> None:
        self.scenario.tag = TagConfig.delivery_default()
        self._load_from_scenario()
        self.scenarioChanged.emit()


    def _refresh_step_list(self) -> None:
        self.step_list.clear()
        for action in self.scenario.program:
            self.step_list.addItem(format_action(action))

    def _update_param_enabled(self) -> None:
        kind = self.type_combo.currentText()
        page_used = kind in ("READ_PAGE", "READ_PAGE_INV", "WRITE_PAGE")
        self.page_spin.setEnabled(page_used)
        if kind == "START_AUTH":
            self.param_label.setText("PSW_B")
            self.param_edit.setEnabled(True)
        elif kind == "WRITE_PAGE":
            self.param_label.setText("Data")
            self.param_edit.setEnabled(True)
        else:
            self.param_label.setText("-")
            self.param_edit.setEnabled(False)

    def _add_step(self) -> None:
        kind = self.type_combo.currentText()
        page = self.page_spin.value()
        param = parse_hex(self.param_edit.text())
        action = {
            "START_AUTH": lambda: StartAuth(param & 0xFFFFFFFF),
            "READ_PAGE": lambda: ReadPage(page),
            "READ_PAGE_INV": lambda: ReadPageInv(page),
            "WRITE_PAGE": lambda: WritePage(page, param & 0xFFFFFFFF),
            "HALT": Halt,
        }[kind]()
        self.scenario.program.append(action)
        self._refresh_step_list()
        self.scenarioChanged.emit()

    def _remove_step(self) -> None:
        row = self.step_list.currentRow()
        if 0 <= row < len(self.scenario.program):
            del self.scenario.program[row]
            self._refresh_step_list()
            self.scenarioChanged.emit()

    def _move_step(self, delta: int) -> None:
        row = self.step_list.currentRow()
        new = row + delta
        prog = self.scenario.program
        if 0 <= row < len(prog) and 0 <= new < len(prog):
            prog[row], prog[new] = prog[new], prog[row]
            self._refresh_step_list()
            self.step_list.setCurrentRow(new)
            self.scenarioChanged.emit()
