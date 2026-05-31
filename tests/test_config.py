import pytest

from ht2sim.core.config import TMCF, Coding, ReadOnlyMode


def test_default_byte_0x06():
    tmcf = TMCF.from_byte(0x06)
    assert tmcf.is_password_mode
    assert not tmcf.is_cipher_mode
    assert tmcf.coding is Coding.MANCHESTER
    assert tmcf.read_only_mode is ReadOnlyMode.DISABLED
    assert not tmcf.read_only_enabled
    assert not any(tmcf.user_write_protected(p) for p in (4, 5, 6, 7))


def test_each_bit_position():
    assert TMCF.from_byte(0x80).skl == 1
    assert TMCF.from_byte(0x40).pg3l == 1
    assert TMCF.from_byte(0x20).pwp1 == 1
    assert TMCF.from_byte(0x10).pwp0 == 1
    assert TMCF.from_byte(0x08).enc == 1
    assert TMCF.from_byte(0x04).ms1 == 1
    assert TMCF.from_byte(0x02).ms0 == 1
    assert TMCF.from_byte(0x01).dcs == 1


def test_enc_selects_cipher_mode():
    assert TMCF.from_byte(0x08).is_cipher_mode
    assert not TMCF.from_byte(0x08).is_password_mode


def test_dcs_selects_coding():
    assert TMCF.from_byte(0x00).coding is Coding.MANCHESTER
    assert TMCF.from_byte(0x01).coding is Coding.CDP


def test_read_only_mode_table():
    assert TMCF.from_byte(0x00).read_only_mode is ReadOnlyMode.ISO_11784_5
    assert TMCF.from_byte(0x02).read_only_mode is ReadOnlyMode.MIRO
    assert TMCF.from_byte(0x04).read_only_mode is ReadOnlyMode.PCF7931
    assert TMCF.from_byte(0x06).read_only_mode is ReadOnlyMode.DISABLED


def test_user_write_protection_mapping():
    pwp1_only = TMCF.from_byte(0x20)
    assert pwp1_only.user_write_protected(4)
    assert pwp1_only.user_write_protected(5)
    assert not pwp1_only.user_write_protected(6)
    assert not pwp1_only.user_write_protected(7)

    pwp0_only = TMCF.from_byte(0x10)
    assert pwp0_only.user_write_protected(6)
    assert pwp0_only.user_write_protected(7)
    assert not pwp0_only.user_write_protected(4)


def test_byte_roundtrip():
    for byte in range(256):
        assert TMCF.from_byte(byte).to_byte() == byte


def test_out_of_range_byte_rejected():
    with pytest.raises(ValueError):
        TMCF.from_byte(0x100)
