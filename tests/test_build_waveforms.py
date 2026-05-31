import numpy as np

from ht2sim.core.config import Coding
from ht2sim.core.frame import FrameKind
from ht2sim.signal.builder import build_waveforms
from ht2sim.signal.waveform import FIELD_FULL, AnnotationKind
from ht2sim.core.session import ReadPage, Session, StartAuth

DEFAULT_PSW_B = 0x4D494B52
_ACTIVE = {
    FrameKind.COMMAND,
    FrameKind.PARAM,
    FrameKind.EQ,
    FrameKind.RESPONSE,
    FrameKind.ACK,
}


def run_session():
    result = Session.from_default_tag([StartAuth(DEFAULT_PSW_B), ReadPage(0)]).run()
    return result


def level_at(wave, t):
    ts, ys = wave.sample(samples_per_to=8.0)
    return ys[np.searchsorted(ts, t, side="right") - 1]


def window_levels(wave, t0, t1):
    ts, ys = wave.sample(samples_per_to=8.0)
    mask = (ts >= t0) & (ts < t1)
    return ys[mask]


def test_both_channels_span_full_timeline():
    result = run_session()
    ws = build_waveforms(result.frames, Coding.MANCHESTER)
    total = result.total_duration_to
    assert abs(ws.reader.total_duration_to - total) < 1e-6
    assert abs(ws.tag.total_duration_to - total) < 1e-6


def test_reader_idle_high_while_tag_responds():
    result = run_session()
    ws = build_waveforms(result.frames, Coding.MANCHESTER)
    ide = next(f for f in result.frames if f.label.startswith("IDE"))
    assert np.all(window_levels(ws.reader, ide.t_start_to, ide.t_end_to) == FIELD_FULL)
    assert np.any(window_levels(ws.tag, ide.t_start_to, ide.t_end_to) < FIELD_FULL)


def test_tag_idle_high_while_reader_sends_command():
    result = run_session()
    ws = build_waveforms(result.frames, Coding.MANCHESTER)
    cmd = result.frames[0]
    assert cmd.kind is FrameKind.COMMAND
    assert np.all(window_levels(ws.tag, cmd.t_start_to, cmd.t_end_to) == FIELD_FULL)
    assert np.any(window_levels(ws.reader, cmd.t_start_to, cmd.t_end_to) < FIELD_FULL)


def test_annotation_counts():
    result = run_session()
    ws = build_waveforms(result.frames, Coding.MANCHESTER)
    frame_anns = ws.annotations_of(AnnotationKind.FRAME)
    bit_anns = ws.annotations_of(AnnotationKind.BIT)
    assert len(frame_anns) == len(result.frames)
    expected_bits = sum(len(f.bits) for f in result.frames if f.kind in _ACTIVE)
    assert len(bit_anns) == expected_bits


def test_cdp_coding_also_builds_consistently():
    result = run_session()
    ws = build_waveforms(result.frames, Coding.CDP)
    total = result.total_duration_to
    assert abs(ws.tag.total_duration_to - total) < 1e-6
    assert abs(ws.reader.total_duration_to - total) < 1e-6


def test_bit_annotation_aligns_with_frame():
    result = run_session()
    ws = build_waveforms(result.frames, Coding.MANCHESTER)
    cmd = result.frames[0]
    cmd_bits = [
        a for a in ws.annotations_of(AnnotationKind.BIT)
        if cmd.t_start_to <= a.t_start_to < cmd.t_end_to and a.channel == "reader"
    ]
    assert len(cmd_bits) == len(cmd.bits)
    assert [int(a.text) for a in cmd_bits] == cmd.bits
