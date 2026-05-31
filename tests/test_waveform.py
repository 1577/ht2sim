import numpy as np

from ht2sim.signal.waveform import Segment, Waveform


def make_wave():
    return Waveform(
        "tag",
        [Segment(0, 2, 1.0), Segment(2, 1, 0.0), Segment(3, 2, 1.0)],
    )


def test_total_duration():
    assert make_wave().total_duration_to == 5


def test_step_points_double_each_segment_edge():
    xs, ys = make_wave().step_points()
    assert xs == [0, 2, 2, 3, 3, 5]
    assert ys == [1.0, 1.0, 0.0, 0.0, 1.0, 1.0]


def test_sample_shape_and_levels():
    wave = make_wave()
    t, y = wave.sample(samples_per_to=2.0)
    assert len(t) == len(y) == 10
    low = y[(t >= 2.0) & (t < 3.0)]
    assert np.all(low == 0.0)
    assert y[0] == 1.0


def test_sample_empty_waveform():
    t, y = Waveform("reader", []).sample()
    assert len(t) == len(y)
    assert np.all(y == 0.0)
