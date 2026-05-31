from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from . import constants as C
from .frame import (
    Frame,
    eq_frame,
    error_frame,
    gap_frame,
    reader_param_frame,
    tag_response_frame,
)
from .memory import TransponderMemory, int_to_bits


@dataclass
class AuthContext:

    memory: TransponderMemory
    reader_psw_b: int


@dataclass
class AuthOutcome:

    frames: list[Frame] = field(default_factory=list)
    authorized: bool = False


class AuthStrategy(ABC):

    @abstractmethod
    def run(self, ctx: AuthContext) -> AuthOutcome:
        pass


class PasswordAuth(AuthStrategy):

    def run(self, ctx: AuthContext) -> AuthOutcome:
        mem = ctx.memory
        frames: list[Frame] = []

        frames.append(gap_frame(C.T_WAIT_TR.nominal, "tWAIT,Tr"))
        frames.append(eq_frame())
        frames.append(
            tag_response_frame(f"IDE = 0x{mem.ide.value:08X}", mem.ide.to_bits())
        )

        frames.append(gap_frame(C.T_WAIT_BS.nominal, "tWAIT,Bs"))
        frames.append(
            reader_param_frame(
                f"PSW_B = 0x{ctx.reader_psw_b:08X}",
                int_to_bits(ctx.reader_psw_b, 32),
            )
        )

        if ctx.reader_psw_b == mem.psw_b:
            frames.append(gap_frame(C.T_WAIT_TR.nominal, "tWAIT,Tr"))
            frames.append(eq_frame())
            cfg = mem.config_page
            frames.append(
                tag_response_frame(
                    f"Page 3 (TMCF+PSW_T) = 0x{cfg.value:08X}", cfg.to_bits()
                )
            )
            frames.append(gap_frame(C.T_WAIT_BS.nominal, "tWAIT,Bs"))
            return AuthOutcome(frames=frames, authorized=True)

        frames.append(
            error_frame(
                "Auth failed: PSW_B mismatch",
                reason="psw_b_mismatch",
                expected=mem.psw_b,
                received=ctx.reader_psw_b,
            )
        )
        return AuthOutcome(frames=frames, authorized=False)


def strategy_for(memory: TransponderMemory) -> AuthStrategy:
    if memory.tmcf.is_cipher_mode:
        raise NotImplementedError(
            "cipher mode is not implemented (this project is password-mode only)"
        )
    return PasswordAuth()
