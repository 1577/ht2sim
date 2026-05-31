from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import constants as C


class ReadOnlyMode(Enum):

    ISO_11784_5 = "ISO 11784/5"
    MIRO = "MIRO"
    PCF7931 = "PCF7931/30/35"
    DISABLED = "disabled"


class Coding(Enum):

    MANCHESTER = "manchester"
    CDP = "cdp"


@dataclass(frozen=True)
class TMCF:

    skl: int = 0
    pg3l: int = 0
    pwp1: int = 0
    pwp0: int = 0
    enc: int = 0
    ms1: int = 0
    ms0: int = 0
    dcs: int = 0


    @classmethod
    def from_byte(cls, byte: int) -> "TMCF":
        if not 0 <= byte <= 0xFF:
            raise ValueError(f"TMCF byte out of range: {byte:#x}")
        return cls(
            skl=(byte >> 7) & 1,
            pg3l=(byte >> 6) & 1,
            pwp1=(byte >> 5) & 1,
            pwp0=(byte >> 4) & 1,
            enc=(byte >> 3) & 1,
            ms1=(byte >> 2) & 1,
            ms0=(byte >> 1) & 1,
            dcs=byte & 1,
        )

    def to_byte(self) -> int:
        return (
            (self.skl << 7)
            | (self.pg3l << 6)
            | (self.pwp1 << 5)
            | (self.pwp0 << 4)
            | (self.enc << 3)
            | (self.ms1 << 2)
            | (self.ms0 << 1)
            | self.dcs
        )


    @property
    def is_password_mode(self) -> bool:
        return self.enc == 0

    @property
    def is_cipher_mode(self) -> bool:
        return self.enc == 1

    @property
    def coding(self) -> Coding:
        return Coding.MANCHESTER if self.dcs == 0 else Coding.CDP

    @property
    def read_only_mode(self) -> ReadOnlyMode:
        return {
            (0, 0): ReadOnlyMode.ISO_11784_5,
            (0, 1): ReadOnlyMode.MIRO,
            (1, 0): ReadOnlyMode.PCF7931,
            (1, 1): ReadOnlyMode.DISABLED,
        }[(self.ms1, self.ms0)]

    @property
    def read_only_enabled(self) -> bool:
        return self.read_only_mode is not ReadOnlyMode.DISABLED

    def user_write_protected(self, page: int) -> bool:
        if page in (C.PAGE_USER0, C.PAGE_USER1):
            return self.pwp1 == 1
        if page in (C.PAGE_USER2, C.PAGE_USER3):
            return self.pwp0 == 1
        return False

    def __str__(self) -> str:
        mode = "password" if self.is_password_mode else "cipher"
        return (
            f"TMCF(0x{self.to_byte():02X}: {mode}, {self.coding.value}, "
            f"read-only={self.read_only_mode.value}, "
            f"pwp1={self.pwp1}, pwp0={self.pwp0}, skl={self.skl}, pg3l={self.pg3l})"
        )
