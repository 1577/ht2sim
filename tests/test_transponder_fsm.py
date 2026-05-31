import pytest

from ht2sim.core.commands import Command, CommandType
from ht2sim.core.frame import FrameKind
from ht2sim.core.memory import Page, TransponderMemory, int_to_bits
from ht2sim.core.transponder import State, Transponder

DEFAULT_PSW_B = 0x4D494B52


def authed_transponder(memory=None) -> Transponder:
    t = Transponder(memory or TransponderMemory.delivery_default())
    res = t.execute(Command(CommandType.START_AUTH), reader_psw_b=DEFAULT_PSW_B)
    assert res.ok and t.state is State.AUTHORIZED
    return t


def response_bits(frames):
    return [f.bits for f in frames if f.kind is FrameKind.RESPONSE]


def test_start_auth_success_enters_authorized():
    t = Transponder(TransponderMemory.delivery_default())
    assert t.state is State.WAIT
    res = t.execute(Command(CommandType.START_AUTH), reader_psw_b=DEFAULT_PSW_B)
    assert res.ok
    assert t.state is State.AUTHORIZED
    assert len(response_bits(res.frames)) == 2


def test_start_auth_wrong_password_returns_to_wait():
    t = Transponder(TransponderMemory.delivery_default())
    res = t.execute(Command(CommandType.START_AUTH), reader_psw_b=0xDEADBEEF)
    assert not res.ok
    assert t.state is State.WAIT
    assert any(f.kind is FrameKind.ERROR for f in res.frames)


def test_start_auth_rejected_outside_wait():
    t = authed_transponder()
    res = t.execute(Command(CommandType.START_AUTH), reader_psw_b=DEFAULT_PSW_B)
    assert not res.ok
    assert t.state is State.WAIT


def test_read_in_wait_is_rejected():
    t = Transponder(TransponderMemory.delivery_default())
    res = t.execute(Command(CommandType.READ_PAGE, 0))
    assert not res.ok
    assert t.state is State.WAIT


def test_read_and_write_in_authorized():
    t = authed_transponder()
    res = t.execute(Command(CommandType.READ_PAGE, 0))
    assert res.ok and t.state is State.AUTHORIZED

    res = t.execute(Command(CommandType.WRITE_PAGE, 4), write_value=0xCAFEBABE)
    assert res.ok and t.state is State.AUTHORIZED
    assert t.memory.read_page(4).value == 0xCAFEBABE


def test_write_ends_with_tprog_then_basestation_turnaround():
    t = authed_transponder()
    res = t.execute(Command(CommandType.WRITE_PAGE, 4), write_value=0x1)
    labels = [f.label for f in res.frames]
    assert "tPROG" in labels
    assert labels[-1] == "tWAIT,Bs"
    assert labels.index("tPROG") < labels.index("tWAIT,Bs")


def test_protected_write_burns_twait_tr_before_wait():
    mem = TransponderMemory.delivery_default()
    mem.write_page(3, 0x26AA4854)
    t = authed_transponder(mem)
    res = t.execute(Command(CommandType.WRITE_PAGE, 4), write_value=0x1)
    assert not res.ok and t.state is State.WAIT
    assert any(f.label == "tWAIT,Tr" for f in res.frames)
    assert not any(f.kind is FrameKind.RESPONSE for f in res.frames)


def test_read_page_inv_returns_inverted_bits():
    t = authed_transponder()
    res = t.execute(Command(CommandType.READ_PAGE_INV, 0))
    expected = int_to_bits((~0x12345610) & 0xFFFFFFFF, 32)
    assert response_bits(res.frames) == [expected]


def test_write_to_protected_user_page_drops_to_wait():
    mem = TransponderMemory.delivery_default()
    mem.write_page(3, 0x26AA4854)
    t = authed_transponder(mem)
    res = t.execute(Command(CommandType.WRITE_PAGE, 4), write_value=0x1)
    assert not res.ok
    assert t.state is State.WAIT


def test_write_to_identifier_page_is_rejected():
    t = authed_transponder()
    res = t.execute(Command(CommandType.WRITE_PAGE, 0), write_value=0x1)
    assert not res.ok
    assert t.state is State.WAIT


def test_halt_then_muted():
    t = authed_transponder()
    res = t.execute(Command(CommandType.HALT))
    assert res.ok
    assert t.state is State.HALT
    res2 = t.execute(Command(CommandType.READ_PAGE, 0))
    assert not res2.ok
    assert res2.frames == []
    assert t.state is State.HALT


def test_cipher_mode_raises_not_implemented():
    mem = TransponderMemory.delivery_default()
    mem.write_page(3, 0x0EAA4854)
    t = Transponder(mem)
    with pytest.raises(NotImplementedError):
        t.execute(Command(CommandType.START_AUTH), reader_psw_b=DEFAULT_PSW_B)
