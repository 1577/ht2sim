from ht2sim.core.memory import TransponderMemory
from ht2sim.core.session import ReadPage, ReadPageInv, Session, StartAuth
from ht2sim.signal.builder import build_from_session

TRANSPORT_KEY = 0x4D494B52


def ascii_wave(wave, t0, t1, cols=72):
    span = max(t1 - t0, 1e-9)
    ts = [t0 + (i + 0.5) * span / cols for i in range(cols)]
    samples = []
    for t in ts:
        seg = next((s for s in wave.segments if s.t_start_to <= t < s.t_end_to), None)
        samples.append(1 if (seg and seg.level >= 0.5) else 0)
    top = "".join("_" if v else " " for v in samples)
    bot = "".join(" " if v else "_" for v in samples)
    return top, bot


def main() -> None:
    mem = TransponderMemory.delivery_default()
    print("Transponder (delivery default):")
    print(f"  IDE  (page 0) = 0x{mem.ide.value:08X}  product-id nibble = 0x{mem.product_id:X}")
    print(f"  PSW_B(page 1) = 0x{mem.psw_b:08X}  ({mem.pages[1].bytes_.decode('latin1')!r})")
    print(f"  {mem.tmcf}")
    print(f"  PSW_T = 0x{mem.psw_t:06X}")
    print()

    program = [StartAuth(TRANSPORT_KEY), ReadPage(0), ReadPageInv(0)]
    result = Session(_fresh(mem), program).run()

    print("Frame timeline:")
    for frame in result.frames:
        bits = f"  bits={frame.bitstring}" if frame.bits else ""
        print(f"  {frame}{bits}")

    print()
    print(f"completed = {result.completed}")
    print(
        f"total duration = {result.total_duration_to:.0f} TO "
        f"= {result.total_duration_to * 8:.0f} us"
    )

    ws = build_from_session(result, coding=mem.tmcf.coding)
    print()
    print("Waveforms (envelope: _=field present, low=modulated):")
    print(
        f"  reader channel: {len(ws.reader.segments)} segments | "
        f"tag channel: {len(ws.tag.segments)} segments | "
        f"coding={mem.tmcf.coding.value}"
    )

    cmd = result.frames[0]
    print(f"\n  reader START_AUTH (BPLM), t={cmd.t_start_to:.0f}..{cmd.t_end_to:.0f} TO:")
    for row in ascii_wave(ws.reader, cmd.t_start_to, cmd.t_end_to):
        print("    " + row)

    ide = next(f for f in result.frames if f.label.startswith("IDE"))
    win_end = min(ide.t_start_to + 13 * 32, ide.t_end_to)
    print(f"\n  tag EQ + IDE start (Manchester), t={ide.t_start_to:.0f}..{win_end:.0f} TO:")
    for row in ascii_wave(ws.tag, ide.t_start_to, win_end):
        print("    " + row)


def _fresh(mem: TransponderMemory):
    from ht2sim.core.transponder import Transponder

    return Transponder(mem)


if __name__ == "__main__":
    main()
