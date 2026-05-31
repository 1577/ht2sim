from __future__ import annotations

from dataclasses import dataclass

from ..core.config import Coding
from .timing import TimingProfile
from .waveform import FIELD_FULL, FIELD_LOW, Segment

_LOAD_ON = FIELD_LOW
_LOAD_OFF = FIELD_FULL


@dataclass(frozen=True)
class BitCell:
    t_start_to: float
    duration_to: float
    value: int

    @property
    def t_end_to(self) -> float:
        return self.t_start_to + self.duration_to


@dataclass
class Encoded:
    segments: list[Segment]
    cells: list[BitCell]

    @property
    def duration_to(self) -> float:
        return sum(s.duration_to for s in self.segments)


def encode_manchester(bits: list[int], timing: TimingProfile) -> Encoded:
    half = timing.half_bit
    segments: list[Segment] = []
    cells: list[BitCell] = []
    t = 0.0
    for b in bits:
        first, second = (_LOAD_ON, _LOAD_OFF) if b else (_LOAD_OFF, _LOAD_ON)
        segments.append(Segment(t, half, first))
        segments.append(Segment(t + half, half, second))
        cells.append(BitCell(t, timing.tbit, b))
        t += timing.tbit
    return Encoded(segments, cells)


def encode_cdp(bits: list[int], timing: TimingProfile) -> Encoded:
    half = timing.half_bit
    segments: list[Segment] = []
    cells: list[BitCell] = []
    t = 0.0
    level = _LOAD_ON
    for b in bits:
        if b:
            segments.append(Segment(t, timing.tbit, level))
            level = _toggle(level)
        else:
            segments.append(Segment(t, half, level))
            level = _toggle(level)
            segments.append(Segment(t + half, half, level))
            level = _toggle(level)
        cells.append(BitCell(t, timing.tbit, b))
        t += timing.tbit
    return Encoded(segments, cells)


def encode_bplm(bits: list[int], timing: TimingProfile) -> Encoded:
    segments: list[Segment] = []
    cells: list[BitCell] = []
    t = 0.0
    for b in bits:
        width = timing.reader_bit_width(b)
        pulse = min(timing.twrp, width)
        segments.append(Segment(t, pulse, FIELD_LOW))
        if width - pulse > 0:
            segments.append(Segment(t + pulse, width - pulse, FIELD_FULL))
        cells.append(BitCell(t, width, b))
        t += width
    return Encoded(segments, cells)


def encode_tag(bits: list[int], coding: Coding, timing: TimingProfile) -> Encoded:
    if coding is Coding.MANCHESTER:
        return encode_manchester(bits, timing)
    return encode_cdp(bits, timing)


def _toggle(level: float) -> float:
    return _LOAD_OFF if level == _LOAD_ON else _LOAD_ON
