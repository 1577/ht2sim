from __future__ import annotations

from ..core.config import Coding
from ..core.frame import Direction, Frame, FrameKind
from .encoders import Encoded, encode_bplm, encode_tag
from .timing import TimingProfile
from .waveform import (
    FIELD_FULL,
    Annotation,
    AnnotationKind,
    Segment,
    Waveform,
    WaveformSet,
)

_READER_ACTIVE = {FrameKind.COMMAND, FrameKind.PARAM}
_TAG_ACTIVE = {FrameKind.EQ, FrameKind.RESPONSE, FrameKind.ACK}

_TOLERANCE = 1e-6


def build_waveforms(
    frames: list[Frame],
    coding: Coding = Coding.MANCHESTER,
    timing: TimingProfile | None = None,
) -> WaveformSet:
    timing = timing or TimingProfile.nominal()
    reader_segs: list[Segment] = []
    tag_segs: list[Segment] = []
    annotations: list[Annotation] = []

    for frame in frames:
        enc, channel = _encode_frame(frame, coding, timing)
        t0 = frame.t_start_to
        if channel == "reader" and enc is not None:
            reader_segs.extend(_offset(enc.segments, t0))
            _idle(tag_segs, t0, frame.duration_to)
        elif channel == "tag" and enc is not None:
            tag_segs.extend(_offset(enc.segments, t0))
            _idle(reader_segs, t0, frame.duration_to)
        else:
            _idle(reader_segs, t0, frame.duration_to)
            _idle(tag_segs, t0, frame.duration_to)
        _append_annotations(annotations, frame, enc, channel)

    return WaveformSet(
        reader=Waveform("reader", _coalesce(reader_segs)),
        tag=Waveform("tag", _coalesce(tag_segs)),
        annotations=annotations,
    )


def build_merged_waveform(
    frames: list[Frame],
    coding: Coding = Coding.MANCHESTER,
    timing: TimingProfile | None = None,
) -> tuple[Waveform, list[Annotation]]:
    timing = timing or TimingProfile.nominal()
    segs: list[Segment] = []
    annotations: list[Annotation] = []

    for frame in frames:
        enc, channel = _encode_frame(frame, coding, timing)
        t0 = frame.t_start_to
        if enc is not None:
            segs.extend(_offset(enc.segments, t0))
        else:
            _idle(segs, t0, frame.duration_to)
        _append_annotations(annotations, frame, enc, channel)

    return Waveform("merged", _coalesce(segs)), annotations


def build_annotations(
    frames: list[Frame],
    coding: Coding = Coding.MANCHESTER,
    timing: TimingProfile | None = None,
) -> list[Annotation]:
    timing = timing or TimingProfile.nominal()
    annotations: list[Annotation] = []
    for frame in frames:
        enc, channel = _encode_frame(frame, coding, timing)
        _append_annotations(annotations, frame, enc, channel)
    return annotations


def build_from_session(session_result, coding=Coding.MANCHESTER, timing=None) -> WaveformSet:
    return build_waveforms(session_result.frames, coding=coding, timing=timing)


def _encode_frame(
    frame: Frame, coding: Coding, timing: TimingProfile
) -> tuple[Encoded | None, str]:
    if frame.kind in _READER_ACTIVE:
        enc = encode_bplm(frame.bits, timing)
        _check(enc, frame)
        return enc, "reader"
    if frame.kind in _TAG_ACTIVE:
        enc = encode_tag(frame.bits, coding, timing)
        _check(enc, frame)
        return enc, "tag"
    return None, _channel_of(frame)


def _append_annotations(
    annotations: list[Annotation], frame: Frame, enc: Encoded | None, channel: str
) -> None:
    if enc is not None and channel in ("reader", "tag"):
        for cell in enc.cells:
            annotations.append(
                Annotation(
                    t_start_to=frame.t_start_to + cell.t_start_to,
                    duration_to=cell.duration_to,
                    text=str(cell.value),
                    kind=AnnotationKind.BIT,
                    channel=channel,
                )
            )
    annotations.append(
        Annotation(
            t_start_to=frame.t_start_to,
            duration_to=frame.duration_to,
            text=frame.label,
            kind=AnnotationKind.FRAME,
            channel=_channel_of(frame),
        )
    )


def _offset(segments: list[Segment], t0: float) -> list[Segment]:
    return [Segment(s.t_start_to + t0, s.duration_to, s.level) for s in segments]


def _idle(segs: list[Segment], t0: float, duration: float) -> None:
    if duration > 0:
        segs.append(Segment(t0, duration, FIELD_FULL))


def _channel_of(frame: Frame) -> str:
    if frame.direction is Direction.READER_TO_TAG:
        return "reader"
    if frame.direction is Direction.TAG_TO_READER:
        return "tag"
    return "-"


def _check(enc: Encoded, frame: Frame) -> None:
    if abs(enc.duration_to - frame.duration_to) > _TOLERANCE:
        raise ValueError(
            f"encoder duration {enc.duration_to} != frame duration "
            f"{frame.duration_to} for {frame.label!r}"
        )


def _coalesce(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for s in segments:
        if s.duration_to <= 0:
            continue
        if merged and merged[-1].level == s.level:
            prev = merged[-1]
            merged[-1] = Segment(
                prev.t_start_to, prev.duration_to + s.duration_to, prev.level
            )
        else:
            merged.append(s)
    return merged
