from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import constants as C


class Direction(Enum):
    READER_TO_TAG = "reader->tag"
    TAG_TO_READER = "tag->reader"
    NONE = "-"


class FrameKind(str, Enum):
    COMMAND = "command"
    PARAM = "param"
    EQ = "eq"
    RESPONSE = "response"
    ACK = "ack"
    GAP = "gap"
    ERROR = "error"


def reader_bits_duration_to(bits: list[int]) -> float:
    t0 = C.T_LOG_0.nominal
    t1 = C.T_LOG_1.nominal
    return sum(t1 if b else t0 for b in bits)


def tag_bits_duration_to(num_bits: int) -> float:
    return num_bits * C.TBIT_TO


@dataclass
class Frame:
    direction: Direction
    kind: FrameKind
    label: str
    bits: list[int] = field(default_factory=list)
    duration_to: float = 0.0
    t_start_to: float = 0.0
    meta: dict = field(default_factory=dict)

    @property
    def t_end_to(self) -> float:
        return self.t_start_to + self.duration_to

    @property
    def t_start_us(self) -> float:
        return self.t_start_to * C.TO_SECONDS * 1e6

    @property
    def duration_us(self) -> float:
        return self.duration_to * C.TO_SECONDS * 1e6

    @property
    def bitstring(self) -> str:
        return "".join(map(str, self.bits))

    def __str__(self) -> str:
        return (
            f"[{self.t_start_to:7.1f} TO +{self.duration_to:6.1f}] "
            f"{self.direction.value:>11} {self.kind.value:<8} {self.label}"
        )


def reader_command_frame(label: str, bits: list[int]) -> Frame:
    return Frame(
        Direction.READER_TO_TAG,
        FrameKind.COMMAND,
        label,
        bits=list(bits),
        duration_to=reader_bits_duration_to(bits),
    )


def reader_param_frame(label: str, bits: list[int]) -> Frame:
    return Frame(
        Direction.READER_TO_TAG,
        FrameKind.PARAM,
        label,
        bits=list(bits),
        duration_to=reader_bits_duration_to(bits),
    )


def eq_frame() -> Frame:
    bits = list(C.EQ_PATTERN)
    return Frame(
        Direction.TAG_TO_READER,
        FrameKind.EQ,
        "EQ (11111)",
        bits=bits,
        duration_to=tag_bits_duration_to(len(bits)),
    )


def tag_response_frame(label: str, bits: list[int]) -> Frame:
    return Frame(
        Direction.TAG_TO_READER,
        FrameKind.RESPONSE,
        label,
        bits=list(bits),
        duration_to=tag_bits_duration_to(len(bits)),
    )


def tag_ack_frame(label: str, bits: list[int]) -> Frame:
    return Frame(
        Direction.TAG_TO_READER,
        FrameKind.ACK,
        label,
        bits=list(bits),
        duration_to=tag_bits_duration_to(len(bits)),
    )


def gap_frame(duration_to: float, label: str) -> Frame:
    return Frame(Direction.NONE, FrameKind.GAP, label, duration_to=duration_to)


def error_frame(label: str, **meta) -> Frame:
    return Frame(Direction.NONE, FrameKind.ERROR, label, meta=meta)
