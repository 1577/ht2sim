from __future__ import annotations

from dataclasses import dataclass

from ..core import constants as C


@dataclass(frozen=True)
class TimingProfile:
    tbit: float = float(C.TBIT_TO)
    tlog0: float = C.T_LOG_0.nominal
    tlog1: float = C.T_LOG_1.nominal
    twrp: float = C.T_WRP.nominal

    @classmethod
    def nominal(cls) -> "TimingProfile":
        return cls()

    @property
    def half_bit(self) -> float:
        return self.tbit / 2.0

    def reader_bit_width(self, bit: int) -> float:
        return self.tlog1 if bit else self.tlog0
