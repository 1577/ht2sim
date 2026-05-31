import pytest

from ht2sim.core.commands import Command, CommandError, CommandType


def bits(s: str) -> list[int]:
    return [int(c) for c in s]


def test_start_auth_opcode_and_no_complement():
    cmd = Command(CommandType.START_AUTH)
    assert cmd.bits() == bits("11000")
    assert cmd.complement_bits() is None
    assert cmd.sequence_bits() == bits("11000")
    assert not cmd.needs_complement


def test_read_page_opcode_and_partial_complement():
    cmd = Command(CommandType.READ_PAGE, page=5)
    assert cmd.bits() == bits("11101")
    assert cmd.complement_bits() == bits("00101")
    assert cmd.sequence_bits() == bits("1110100101")


def test_read_page_inv_opcode():
    cmd = Command(CommandType.READ_PAGE_INV, page=2)
    assert cmd.bits() == bits("01010")
    assert cmd.complement_bits() == bits("10010")


def test_write_page_opcode():
    cmd = Command(CommandType.WRITE_PAGE, page=4)
    assert cmd.bits() == bits("10100")
    assert cmd.complement_bits() == bits("01100")


def test_halt_full_inversion():
    cmd = Command(CommandType.HALT)
    assert cmd.bits() == bits("00001")
    assert cmd.complement_bits() == bits("11110")
    assert cmd.sequence_bits() == bits("0000111110")


def test_decode_roundtrip_for_all_page_commands():
    for ctype in (CommandType.READ_PAGE, CommandType.READ_PAGE_INV, CommandType.WRITE_PAGE):
        for page in range(8):
            cmd = Command(ctype, page)
            decoded = Command.decode(cmd.sequence_bits())
            assert decoded == cmd


def test_decode_start_auth_and_halt():
    assert Command.decode(bits("11000")) == Command(CommandType.START_AUTH)
    assert Command.decode(bits("0000111110")) == Command(CommandType.HALT)


def test_decode_rejects_complement_mismatch():
    with pytest.raises(CommandError):
        Command.decode(bits("1110100111"))


def test_decode_rejects_bad_lengths_and_lone_nonauth():
    with pytest.raises(CommandError):
        Command.decode(bits("110"))
    with pytest.raises(CommandError):
        Command.decode(bits("11101"))


def test_page_command_requires_valid_page():
    with pytest.raises(CommandError):
        Command(CommandType.READ_PAGE)
    with pytest.raises(CommandError):
        Command(CommandType.START_AUTH, page=1)
