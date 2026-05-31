from ht2sim.core.frame import Direction, FrameKind
from ht2sim.core.session import ReadPage, Session, StartAuth

DEFAULT_PSW_B = 0x4D494B52


def test_full_auth_and_read_frame_order():
    session = Session.from_default_tag(
        [StartAuth(DEFAULT_PSW_B), ReadPage(0)]
    )
    result = session.run()
    frames = result.frames

    assert result.completed
    assert result.error is None

    assert frames[0].kind is FrameKind.COMMAND
    assert frames[0].direction is Direction.READER_TO_TAG
    assert frames[0].label.startswith("START_AUTH")

    responses = [f for f in frames if f.kind is FrameKind.RESPONSE]
    assert len(responses) == 3
    assert responses[0].label.startswith("IDE")
    assert "Page 3" in responses[1].label
    assert "Page 0" in responses[2].label


def test_eq_precedes_every_tag_response():
    result = Session.from_default_tag([StartAuth(DEFAULT_PSW_B), ReadPage(0)]).run()
    frames = result.frames
    for i, f in enumerate(frames):
        if f.kind in (FrameKind.RESPONSE, FrameKind.ACK):
            assert i > 0 and frames[i - 1].kind is FrameKind.EQ, (
                f"frame {i} ({f.label}) not preceded by EQ"
            )


def test_timeline_is_monotonic_and_contiguous():
    result = Session.from_default_tag([StartAuth(DEFAULT_PSW_B), ReadPage(0)]).run()
    frames = result.frames
    assert frames[0].t_start_to == 0.0
    for prev, nxt in zip(frames, frames[1:]):
        assert nxt.t_start_to == prev.t_end_to
    assert result.total_duration_to == frames[-1].t_end_to


def test_directions_are_consistent():
    result = Session.from_default_tag([StartAuth(DEFAULT_PSW_B), ReadPage(0)]).run()
    for f in result.frames:
        if f.kind in (FrameKind.COMMAND, FrameKind.PARAM):
            assert f.direction is Direction.READER_TO_TAG
        elif f.kind in (FrameKind.EQ, FrameKind.RESPONSE, FrameKind.ACK):
            assert f.direction is Direction.TAG_TO_READER


def test_state_timeline_wait_then_authorized():
    result = Session.from_default_tag([StartAuth(DEFAULT_PSW_B), ReadPage(0)]).run()
    assert result.final_state == "AUTHORIZED"
    assert result.state_at(0.0) == "WAIT"
    read_cmd = next(f for f in result.frames if f.label.startswith("READ_PAGE"))
    assert result.state_at(read_cmd.t_start_to) == "AUTHORIZED"


def test_state_timeline_auth_failure_stays_wait():
    result = Session.from_default_tag([StartAuth(0xBADBAD00)]).run()
    assert result.final_state == "WAIT"
    assert result.state_at(result.total_duration_to) == "WAIT"


def test_auth_failure_stops_program():
    result = Session.from_default_tag([StartAuth(0xBADBAD00), ReadPage(0)]).run()
    assert not result.completed
    assert result.error is not None
    assert not any("READ_PAGE" in f.label for f in result.frames)
    assert any(f.kind is FrameKind.ERROR for f in result.frames)
