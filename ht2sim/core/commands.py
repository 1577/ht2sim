from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .memory import bits_to_int


class CommandError(ValueError):
    pass


class CommandType(Enum):
    START_AUTH = "START_AUTH"
    READ_PAGE = "READ_PAGE"
    READ_PAGE_INV = "READ_PAGE_INV"
    WRITE_PAGE = "WRITE_PAGE"
    HALT = "HALT"


_TYPE_BITS = {
    CommandType.READ_PAGE: (1, 1),
    CommandType.READ_PAGE_INV: (0, 1),
    CommandType.WRITE_PAGE: (1, 0),
}
_TYPE_FROM_BITS = {bits: ctype for ctype, bits in _TYPE_BITS.items()}

_HALT_BITS = (0, 0, 0, 0, 1)
_START_AUTH_BITS = (1, 1, 0, 0, 0)

_PAGE_ADDRESSED = {
    CommandType.READ_PAGE,
    CommandType.READ_PAGE_INV,
    CommandType.WRITE_PAGE,
}


@dataclass(frozen=True)
class Command:

    type: CommandType
    page: int | None = None

    def __post_init__(self) -> None:
        if self.type in _PAGE_ADDRESSED:
            if self.page is None or not 0 <= self.page <= 7:
                raise CommandError(f"{self.type.value} requires page 0..7")
        elif self.page is not None:
            raise CommandError(f"{self.type.value} takes no page")


    def bits(self) -> list[int]:
        if self.type is CommandType.START_AUTH:
            return list(_START_AUTH_BITS)
        if self.type is CommandType.HALT:
            return list(_HALT_BITS)
        hi, lo = _TYPE_BITS[self.type]
        pg = self.page or 0
        return [hi, lo, (pg >> 2) & 1, (pg >> 1) & 1, pg & 1]

    def complement_bits(self) -> list[int] | None:
        if self.type is CommandType.START_AUTH:
            return None
        b = self.bits()
        if self.type is CommandType.HALT:
            return [1 - x for x in b]
        return [1 - b[0], 1 - b[1], b[2], b[3], b[4]]

    def sequence_bits(self) -> list[int]:
        comp = self.complement_bits()
        return self.bits() if comp is None else self.bits() + comp

    @property
    def needs_complement(self) -> bool:
        return self.type is not CommandType.START_AUTH


    @classmethod
    def decode(cls, bits: list[int]) -> "Command":
        if len(bits) == 5:
            if tuple(bits) == _START_AUTH_BITS:
                return cls(CommandType.START_AUTH)
            raise CommandError(
                "a lone 5-bit command must be START_AUTH; got "
                f"{''.join(map(str, bits))}"
            )
        if len(bits) != 10:
            raise CommandError(f"command sequence must be 5 or 10 bits, got {len(bits)}")

        cmd_bits, comp_bits = bits[:5], bits[5:]
        type_bits = (cmd_bits[0], cmd_bits[1])

        if type_bits == (0, 0):
            command = cls(CommandType.HALT)
        else:
            try:
                ctype = _TYPE_FROM_BITS[type_bits]
            except KeyError:
                raise CommandError(f"unknown command type bits {type_bits}")
            page = bits_to_int(cmd_bits[2:])
            command = cls(ctype, page)

        expected = command.complement_bits()
        if comp_bits != expected:
            raise CommandError(
                f"complement mismatch for {command.type.value}: "
                f"expected {''.join(map(str, expected))}, "
                f"got {''.join(map(str, comp_bits))}"
            )
        return command


    def mnemonic(self) -> str:
        bitstr = "".join(map(str, self.bits()))
        if self.page is not None:
            return f"{self.type.value}[{self.page}] ({bitstr})"
        return f"{self.type.value} ({bitstr})"

    def __str__(self) -> str:
        return self.mnemonic()
