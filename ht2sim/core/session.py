from __future__ import annotations

from dataclasses import dataclass, field

from .commands import Command, CommandType
from .frame import Frame, reader_command_frame, reader_param_frame
from .memory import TransponderMemory, int_to_bits
from .transponder import Transponder


@dataclass(frozen=True)
class StartAuth:

    psw_b: int


@dataclass(frozen=True)
class ReadPage:
    page: int


@dataclass(frozen=True)
class ReadPageInv:
    page: int


@dataclass(frozen=True)
class WritePage:
    page: int
    value: int


@dataclass(frozen=True)
class Halt:
    pass


Action = StartAuth | ReadPage | ReadPageInv | WritePage | Halt


@dataclass(frozen=True)
class StateSpan:

    t_start_to: float
    t_end_to: float
    state: str


@dataclass
class SessionResult:
    frames: list[Frame] = field(default_factory=list)
    completed: bool = True
    error: str | None = None
    states: list[StateSpan] = field(default_factory=list)
    final_state: str = "WAIT"

    @property
    def total_duration_to(self) -> float:
        return self.frames[-1].t_end_to if self.frames else 0.0

    def state_at(self, t: float) -> str:
        for span in self.states:
            if span.t_start_to <= t < span.t_end_to:
                return span.state
        return self.final_state


class Session:
    def __init__(self, transponder: Transponder, program: list[Action]) -> None:
        self.transponder = transponder
        self.program = program

    @classmethod
    def from_default_tag(cls, program: list[Action]) -> "Session":
        return cls(Transponder(TransponderMemory.delivery_default()), program)


    def run(self) -> SessionResult:
        frames: list[Frame] = []
        result = SessionResult(frames=frames)
        marks: list[tuple[int, str]] = []

        for action in self.program:
            reader_frames, command, kwargs = self._reader_side(action)
            frames.extend(reader_frames)
            exec_result = self.transponder.execute(command, **kwargs)
            frames.extend(exec_result.frames)
            marks.append((len(frames), self.transponder.state.name))
            if not exec_result.ok:
                result.completed = False
                result.error = self._first_error_label(exec_result.frames, action)
                break

        self._assign_timeline(frames)
        result.final_state = self.transponder.state.name
        result.states = self._build_states(frames, marks)
        return result


    def _reader_side(self, action: Action):
        if isinstance(action, StartAuth):
            cmd = Command(CommandType.START_AUTH)
            frame = reader_command_frame(cmd.mnemonic(), cmd.bits())
            return [frame], cmd, {"reader_psw_b": action.psw_b}

        if isinstance(action, (ReadPage, ReadPageInv)):
            ctype = (
                CommandType.READ_PAGE
                if isinstance(action, ReadPage)
                else CommandType.READ_PAGE_INV
            )
            cmd = Command(ctype, action.page)
            frame = reader_command_frame(cmd.mnemonic(), cmd.sequence_bits())
            return [frame], cmd, {}

        if isinstance(action, WritePage):
            cmd = Command(CommandType.WRITE_PAGE, action.page)
            cmd_frame = reader_command_frame(cmd.mnemonic(), cmd.sequence_bits())
            data_frame = reader_param_frame(
                f"Write data = 0x{action.value & 0xFFFFFFFF:08X}",
                int_to_bits(action.value & 0xFFFFFFFF, 32),
            )
            return [cmd_frame, data_frame], cmd, {"write_value": action.value}

        if isinstance(action, Halt):
            cmd = Command(CommandType.HALT)
            frame = reader_command_frame(cmd.mnemonic(), cmd.sequence_bits())
            return [frame], cmd, {}

        raise TypeError(f"unknown action: {action!r}")

    @staticmethod
    def _first_error_label(frames: list[Frame], action: Action) -> str:
        for f in frames:
            if f.kind.value == "error":
                return f.label
        return f"action {action!r} rejected"

    @staticmethod
    def _assign_timeline(frames: list[Frame]) -> None:
        t = 0.0
        for f in frames:
            f.t_start_to = t
            t += f.duration_to

    @staticmethod
    def _build_states(frames: list[Frame], marks: list[tuple[int, str]]) -> list[StateSpan]:
        spans: list[StateSpan] = []
        prev = "WAIT"
        seg_start = 0.0
        for end_index, state_after in marks:
            t_end = frames[end_index - 1].t_end_to if end_index > 0 else seg_start
            if t_end > seg_start:
                spans.append(StateSpan(seg_start, t_end, prev))
            seg_start = t_end
            prev = state_after
        return spans
