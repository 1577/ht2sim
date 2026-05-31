from __future__ import annotations

from dataclasses import dataclass

from . import constants as C
from .config import TMCF

WORD_MASK = 0xFFFFFFFF


def int_to_bits(value: int, width: int, *, msb_first: bool = True) -> list[int]:
    if value < 0 or value >> width:
        raise ValueError(f"value {value:#x} does not fit in {width} bits")
    bits = [(value >> i) & 1 for i in range(width - 1, -1, -1)]
    return bits if msb_first else bits[::-1]


def bits_to_int(bits: list[int] | tuple[int, ...], *, msb_first: bool = True) -> int:
    seq = list(bits) if msb_first else list(bits)[::-1]
    value = 0
    for b in seq:
        value = (value << 1) | (b & 1)
    return value


@dataclass
class Page:

    value: int = 0

    def __post_init__(self) -> None:
        self.value &= WORD_MASK

    def to_bits(self, *, msb_first: bool = True) -> list[int]:
        return int_to_bits(self.value, 32, msb_first=msb_first)

    @classmethod
    def from_bits(cls, bits: list[int], *, msb_first: bool = True) -> "Page":
        return cls(bits_to_int(bits, msb_first=msb_first))

    @classmethod
    def from_bytes(cls, data: bytes) -> "Page":
        if len(data) != 4:
            raise ValueError("a page is exactly 4 bytes")
        return cls(int.from_bytes(data, "big"))

    def bit(self, index: int) -> int:
        if not 0 <= index <= 31:
            raise ValueError("bit index must be 0..31")
        return (self.value >> index) & 1

    @property
    def bytes_(self) -> bytes:
        return self.value.to_bytes(4, "big")

    def hex(self) -> str:
        return f"{self.value:08X}"

    def __int__(self) -> int:
        return self.value

    def __index__(self) -> int:
        return self.value

    def __repr__(self) -> str:
        return f"Page(0x{self.value:08X})"


class TransponderMemory:

    def __init__(self, pages: list[Page] | None = None) -> None:
        if pages is None:
            pages = [Page(0) for _ in range(C.NUM_PAGES)]
        if len(pages) != C.NUM_PAGES:
            raise ValueError(f"expected {C.NUM_PAGES} pages, got {len(pages)}")
        self.pages: list[Page] = list(pages)


    def read_page(self, n: int) -> Page:
        self._check_index(n)
        return self.pages[n]

    def write_page(self, n: int, value: int | Page) -> None:
        self._check_index(n)
        self.pages[n] = Page(int(value))

    @staticmethod
    def _check_index(n: int) -> None:
        if not 0 <= n < C.NUM_PAGES:
            raise ValueError(f"page index must be 0..{C.NUM_PAGES - 1}")


    @property
    def ide(self) -> Page:
        return self.pages[C.PAGE_IDE]

    @property
    def product_id(self) -> int:
        return (self.ide.value >> 4) & 0xF

    @property
    def psw_b(self) -> int:
        return self.pages[C.PAGE_PSW_B].value

    @property
    def config_page(self) -> Page:
        return self.pages[C.PAGE_CONFIG]

    @property
    def tmcf(self) -> TMCF:
        return TMCF.from_byte((self.config_page.value >> 24) & 0xFF)

    @property
    def psw_t(self) -> int:
        return self.config_page.value & 0xFFFFFF


    @classmethod
    def delivery_default(cls) -> "TransponderMemory":
        pages = [Page(0) for _ in range(C.NUM_PAGES)]
        pages[C.PAGE_IDE] = Page(0x12345610)
        pages[C.PAGE_PSW_B] = Page(0x4D494B52)
        pages[C.PAGE_INTERNAL] = Page(0x00000000)
        pages[C.PAGE_CONFIG] = Page(0x06AA4854)
        pages[C.PAGE_USER0] = Page(0x00000000)
        pages[C.PAGE_USER1] = Page(0x00000000)
        pages[C.PAGE_USER2] = Page(0x00000000)
        pages[C.PAGE_USER3] = Page(0x00000000)
        return cls(pages)

    def __repr__(self) -> str:
        body = ", ".join(f"{i}:{p.hex()}" for i, p in enumerate(self.pages))
        return f"TransponderMemory({body})"
