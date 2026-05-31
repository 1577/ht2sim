from __future__ import annotations

from dataclasses import dataclass, field

from .config import TMCF, Coding
from .memory import Page, TransponderMemory
from .session import Action, Session, StartAuth
from .transponder import Transponder

TRANSPORT_KEY = 0x4D494B52


@dataclass
class TagConfig:

    ide: int = 0x12345610
    psw_b: int = 0x4D494B52
    tmcf: int = 0x06
    psw_t: int = 0xAA4854
    user: list[int] = field(default_factory=lambda: [0, 0, 0, 0])

    @classmethod
    def delivery_default(cls) -> "TagConfig":
        return cls()

    @property
    def coding(self) -> Coding:
        return TMCF.from_byte(self.tmcf & 0xFF).coding

    def memory(self) -> TransponderMemory:
        pages = [
            Page(self.ide),
            Page(self.psw_b),
            Page(0),
            Page(((self.tmcf & 0xFF) << 24) | (self.psw_t & 0xFFFFFF)),
            Page(self.user[0]),
            Page(self.user[1]),
            Page(self.user[2]),
            Page(self.user[3]),
        ]
        return TransponderMemory(pages)


@dataclass
class Scenario:
    tag: TagConfig = field(default_factory=TagConfig)
    program: list[Action] = field(default_factory=list)

    @classmethod
    def default(cls) -> "Scenario":
        return cls(
            tag=TagConfig.delivery_default(),
            program=[StartAuth(TRANSPORT_KEY)],
        )

    def run(self):
        return self.simulate()[0]

    def simulate(self):
        memory = self.tag.memory()
        result = Session(Transponder(memory), list(self.program)).run()
        return result, memory
