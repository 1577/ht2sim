from ht2sim.core.config import Coding
from ht2sim.signal.encoders import (
    encode_bplm,
    encode_cdp,
    encode_manchester,
    encode_tag,
)
from ht2sim.signal.timing import TimingProfile
from ht2sim.signal.waveform import FIELD_FULL, FIELD_LOW

T = TimingProfile.nominal()
LOAD_ON = FIELD_LOW
LOAD_OFF = FIELD_FULL


def levels(enc):
    return [s.level for s in enc.segments]


def test_manchester_one_is_load_then_off():
    enc = encode_manchester([1], T)
    assert levels(enc) == [LOAD_ON, LOAD_OFF]
    assert [s.duration_to for s in enc.segments] == [T.half_bit, T.half_bit]
    assert enc.duration_to == T.tbit


def test_manchester_zero_is_off_then_load():
    enc = encode_manchester([0], T)
    assert levels(enc) == [LOAD_OFF, LOAD_ON]


def test_manchester_eq_starts_with_load_on():
    enc = encode_manchester([1, 1, 1, 1, 1], T)
    assert enc.segments[0].level == LOAD_ON
    assert enc.duration_to == 5 * T.tbit


def test_manchester_cells_align_to_bits():
    bits = [1, 0, 1]
    enc = encode_manchester(bits, T)
    assert [c.value for c in enc.cells] == bits
    assert [c.t_start_to for c in enc.cells] == [0, T.tbit, 2 * T.tbit]


def test_cdp_starts_load_on_and_transitions_every_bit_end():
    enc = encode_cdp([1, 1, 1], T)
    assert enc.segments[0].level == LOAD_ON
    assert levels(enc) == [LOAD_ON, LOAD_OFF, LOAD_ON]
    assert all(s.duration_to == T.tbit for s in enc.segments)


def test_cdp_zero_has_mid_bit_transition():
    enc = encode_cdp([0], T)
    assert len(enc.segments) == 2
    assert enc.segments[0].duration_to == T.half_bit
    assert enc.segments[0].level != enc.segments[1].level


def test_cdp_mixed_pattern_levels():
    enc = encode_cdp([1, 0, 1], T)
    assert levels(enc) == [LOAD_ON, LOAD_OFF, LOAD_ON, LOAD_OFF]


def test_bplm_bit_widths_match_tlog():
    enc = encode_bplm([0, 1], T)
    assert [round(c.duration_to, 6) for c in enc.cells] == [T.tlog0, T.tlog1]
    assert enc.duration_to == T.tlog0 + T.tlog1


def test_bplm_each_cell_opens_with_a_low_write_pulse():
    enc = encode_bplm([1], T)
    assert enc.segments[0].level == FIELD_LOW
    assert enc.segments[0].duration_to == T.twrp
    assert enc.segments[1].level == FIELD_FULL
    assert enc.segments[1].duration_to == T.tlog1 - T.twrp


def test_encode_tag_dispatches_on_coding():
    bits = [1, 0]
    assert encode_tag(bits, Coding.MANCHESTER, T).segments == encode_manchester(bits, T).segments
    assert encode_tag(bits, Coding.CDP, T).segments == encode_cdp(bits, T).segments
