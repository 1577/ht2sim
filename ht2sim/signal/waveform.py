from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

FIELD_FULL = 1.0
FIELD_LOW = 0.0


@dataclass(frozen=True)
class Segment:
    t_start_to: float
    duration_to: float
    level: float

    @property
    def t_end_to(self) -> float:
        return self.t_start_to + self.duration_to


class AnnotationKind(str, Enum):
    FRAME = "frame"
    BIT = "bit"


@dataclass(frozen=True)
class Annotation:
    t_start_to: float
    duration_to: float
    text: str
    kind: AnnotationKind
    channel: str

    @property
    def t_end_to(self) -> float:
        return self.t_start_to + self.duration_to


@dataclass
class Waveform:

    channel: str
    segments: list[Segment] = field(default_factory=list)

    @property
    def total_duration_to(self) -> float:
        return sum(s.duration_to for s in self.segments)

    def step_points(self) -> tuple[list[float], list[float]]:
        xs: list[float] = []
        ys: list[float] = []
        for s in self.segments:
            xs.extend((s.t_start_to, s.t_end_to))
            ys.extend((s.level, s.level))
        return xs, ys

    def window_step_points(
        self, t0: float, t1: float
    ) -> tuple[list[float], list[float]]:
        xs: list[float] = []
        ys: list[float] = []
        for s in self.segments:
            if s.t_end_to <= t0 or s.t_start_to >= t1:
                continue
            a = max(s.t_start_to, t0)
            b = min(s.t_end_to, t1)
            xs.extend((a, b))
            ys.extend((s.level, s.level))
        return xs, ys

    def sample(self, samples_per_to: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
        total = self.total_duration_to
        n = max(1, int(round(total * samples_per_to)))
        t = np.linspace(0.0, total, n, endpoint=False)
        if not self.segments:
            return t, np.zeros_like(t)
        starts = np.array([s.t_start_to for s in self.segments])
        levels = np.array([s.level for s in self.segments])
        idx = np.searchsorted(starts, t, side="right") - 1
        idx = np.clip(idx, 0, len(self.segments) - 1)
        return t, levels[idx]


@dataclass
class WaveformSet:

    reader: Waveform
    tag: Waveform
    annotations: list[Annotation] = field(default_factory=list)

    @property
    def total_duration_to(self) -> float:
        return max(self.reader.total_duration_to, self.tag.total_duration_to)

    def annotations_of(self, kind: AnnotationKind) -> list[Annotation]:
        return [a for a in self.annotations if a.kind is kind]
