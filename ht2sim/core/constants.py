from __future__ import annotations

from typing import NamedTuple


TO_SECONDS = 1.0 / 125_000.0

TBIT_TO = 32


class TimeSpec(NamedTuple):

    min: float | None = None
    typ: float | None = None
    max: float | None = None

    @property
    def nominal(self) -> float:
        if self.typ is not None:
            return float(self.typ)
        if self.min is not None and self.max is not None:
            return (self.min + self.max) / 2.0
        if self.min is not None:
            return float(self.min)
        if self.max is not None:
            return float(self.max)
        raise ValueError("TimeSpec has no defined value")


T_WAIT_TR = TimeSpec(min=199, max=206)
T_WAIT_BS = TimeSpec(min=90)
T_PROG = TimeSpec(typ=615)
T_IDLE_MS = 80.0


T_WRP = TimeSpec(min=4, max=10)
T_LOG_0 = TimeSpec(min=18, max=22)
T_LOG_1 = TimeSpec(min=26, max=32)
T_STOP = TimeSpec(min=36)


T_START_US = 80.0
T_INIT = TimeSpec(typ=225)
T_RESET_SETUP_MS = 5.0
T_WAIT_SA = TimeSpec(typ=320)
T_WAIT_RO = TimeSpec(typ=326)


EQ_PATTERN: tuple[int, ...] = (1, 1, 1, 1, 1)


PAGE_IDE = 0
PAGE_PSW_B = 1
PAGE_INTERNAL = 2
PAGE_CONFIG = 3
PAGE_USER0 = 4
PAGE_USER1 = 5
PAGE_USER2 = 6
PAGE_USER3 = 7

NUM_PAGES = 8

PRODUCT_ID_NIBBLE = 0x1
