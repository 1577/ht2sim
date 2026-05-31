from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import constants as C
from .auth import AuthContext, strategy_for
from .commands import Command, CommandType
from .config import ReadOnlyMode
from .frame import (
    Frame,
    eq_frame,
    error_frame,
    gap_frame,
    tag_ack_frame,
    tag_response_frame,
)
from .memory import TransponderMemory


class State(Enum):
    WAIT = "WAIT"
    AUTHORIZED = "AUTHORIZED"
    HALT = "HALT"
    READ_ONLY = "READ_ONLY"


@dataclass
class ExecResult:

    frames: list[Frame] = field(default_factory=list)
    ok: bool = False


class Transponder:
    def __init__(self, memory: TransponderMemory | None = None) -> None:
        self.memory = memory if memory is not None else TransponderMemory.delivery_default()
        self.state = State.WAIT


    def reset(self) -> None:
        self.state = State.WAIT

    def _fail(self, label: str, **meta) -> ExecResult:
        self.state = State.WAIT
        return ExecResult(frames=[error_frame(label, **meta)], ok=False)

    def _terminate_during_tr(self, label: str, **meta) -> ExecResult:
        self.state = State.WAIT
        return ExecResult(
            frames=[gap_frame(C.T_WAIT_TR.nominal, "tWAIT,Tr"), error_frame(label, **meta)],
            ok=False,
        )


    def execute(
        self,
        command: Command,
        *,
        reader_psw_b: int | None = None,
        write_value: int | None = None,
    ) -> ExecResult:
        if self.state is State.HALT:
            return ExecResult(frames=[], ok=False)

        if command.type is CommandType.START_AUTH:
            return self._start_auth(reader_psw_b)
        if command.type is CommandType.READ_PAGE:
            return self._read_page(command, inverted=False)
        if command.type is CommandType.READ_PAGE_INV:
            return self._read_page(command, inverted=True)
        if command.type is CommandType.WRITE_PAGE:
            return self._write_page(command, write_value)
        if command.type is CommandType.HALT:
            return self._halt(command)
        return self._fail(f"unsupported command {command.type.value}")


    def _start_auth(self, reader_psw_b: int | None) -> ExecResult:
        if self.state is not State.WAIT:
            return self._fail("START_AUTH rejected: not in WAIT state")
        if reader_psw_b is None:
            return self._fail("START_AUTH requires a basestation password (PSW_B)")
        strategy = strategy_for(self.memory)
        outcome = strategy.run(AuthContext(self.memory, reader_psw_b))
        self.state = State.AUTHORIZED if outcome.authorized else State.WAIT
        return ExecResult(frames=outcome.frames, ok=outcome.authorized)


    def _read_page(self, command: Command, *, inverted: bool) -> ExecResult:
        if self.state is not State.AUTHORIZED:
            return self._fail(f"{command.type.value} rejected: not AUTHORIZED")
        page = command.page
        assert page is not None
        if self._read_protected(page):
            return self._terminate_during_tr(
                f"{command.type.value}[{page}] rejected: read-protected", page=page
            )

        bits = self.memory.read_page(page).to_bits()
        if inverted:
            bits = [1 - b for b in bits]
        value = self.memory.read_page(page).value
        shown = (~value) & 0xFFFFFFFF if inverted else value
        label = f"Page {page} {'~' if inverted else ''}data = 0x{shown:08X}"
        return ExecResult(
            frames=[
                gap_frame(C.T_WAIT_TR.nominal, "tWAIT,Tr"),
                eq_frame(),
                tag_response_frame(label, bits),
                gap_frame(C.T_WAIT_BS.nominal, "tWAIT,Bs"),
            ],
            ok=True,
        )


    def _write_page(self, command: Command, write_value: int | None) -> ExecResult:
        if self.state is not State.AUTHORIZED:
            return self._fail("WRITE_PAGE rejected: not AUTHORIZED")
        page = command.page
        assert page is not None
        if write_value is None:
            return self._fail(f"WRITE_PAGE[{page}] requires data")
        if self._write_protected(page):
            return self._terminate_during_tr(
                f"WRITE_PAGE[{page}] rejected: write-protected", page=page
            )

        self.memory.write_page(page, write_value)
        echo = command.sequence_bits()
        return ExecResult(
            frames=[
                gap_frame(C.T_WAIT_TR.nominal, "tWAIT,Tr"),
                eq_frame(),
                tag_ack_frame(f"WRITE ack (echo) page {page}", echo),
                gap_frame(C.T_PROG.nominal, "tPROG"),
                gap_frame(C.T_WAIT_BS.nominal, "tWAIT,Bs"),
            ],
            ok=True,
        )


    def _halt(self, command: Command) -> ExecResult:
        if self.state is not State.AUTHORIZED:
            return self._fail("HALT rejected: not AUTHORIZED")
        echo = command.sequence_bits()
        frames = [
            gap_frame(C.T_WAIT_TR.nominal, "tWAIT,Tr"),
            eq_frame(),
            tag_ack_frame("HALT ack (echo)", echo),
        ]
        self.state = State.HALT
        return ExecResult(frames=frames, ok=True)


    def _read_protected(self, page: int) -> bool:
        return page == C.PAGE_PSW_B and self.memory.tmcf.skl == 1

    def _write_protected(self, page: int) -> bool:
        tmcf = self.memory.tmcf
        if page == C.PAGE_IDE:
            return True
        if page == C.PAGE_PSW_B:
            return tmcf.skl == 1
        if page == C.PAGE_INTERNAL:
            return True
        if page == C.PAGE_CONFIG:
            return tmcf.pg3l == 1
        return tmcf.user_write_protected(page)


    @property
    def read_only_mode(self) -> ReadOnlyMode:
        return self.memory.tmcf.read_only_mode

    def __repr__(self) -> str:
        return f"Transponder(state={self.state.value})"
