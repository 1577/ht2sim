from ht2sim.core.memory import Page, TransponderMemory, bits_to_int, int_to_bits


def test_delivery_default_page1_is_transport_key_mikr():
    mem = TransponderMemory.delivery_default()
    assert mem.psw_b == 0x4D494B52
    assert mem.pages[1].bytes_ == b"MIKR"


def test_delivery_default_page3_decodes_to_tmcf_and_psw_t():
    mem = TransponderMemory.delivery_default()
    assert mem.config_page.value == 0x06AA4854
    assert mem.tmcf.to_byte() == 0x06
    assert mem.psw_t == 0xAA4854


def test_product_id_nibble_is_one():
    mem = TransponderMemory.delivery_default()
    assert mem.product_id == 0x1


def test_page_msb_first_bit_ordering():
    page = Page(0x80000001)
    bits = page.to_bits(msb_first=True)
    assert bits[0] == 1
    assert bits[-1] == 1
    assert bits[1:31] == [0] * 30
    assert Page.from_bits(bits).value == 0x80000001


def test_page_bit_indexing_lsb_is_zero():
    page = Page(0xA0000003)
    assert page.bit(0) == 1
    assert page.bit(1) == 1
    assert page.bit(31) == 1
    assert page.bit(30) == 0


def test_int_bits_roundtrip_both_orders():
    for value, width in [(0x06, 8), (0xAA4854, 24), (0x12345610, 32)]:
        msb = int_to_bits(value, width, msb_first=True)
        lsb = int_to_bits(value, width, msb_first=False)
        assert bits_to_int(msb, msb_first=True) == value
        assert bits_to_int(lsb, msb_first=False) == value
        assert msb == lsb[::-1]


def test_write_page_masks_to_32_bits():
    mem = TransponderMemory.delivery_default()
    mem.write_page(4, 0xDEADBEEF)
    assert mem.read_page(4).value == 0xDEADBEEF
