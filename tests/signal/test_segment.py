"""Acceptance tests for time segment and channel extraction."""

import numpy as np
import pytest

from signal_diag.signal import (
    InvalidTimeRangeError,
    TimeRange,
    UnsupportedChannelError,
    build_signal_record,
    extract_segment,
)


@pytest.fixture
def three_second_record() -> tuple[np.ndarray, object]:
    samples = np.arange(3 * 48_000, dtype=np.float32)
    record = build_signal_record(
        samples,
        sample_rate_hz=48_000,
        source_type="generated",
        signal_id="sig_three_seconds",
    )
    return samples, record


def test_t012_extracts_left_closed_right_open_time_range(
    three_second_record: tuple[np.ndarray, object],
) -> None:
    source, record = three_second_record

    segment = extract_segment(record, time_range=TimeRange(start_s=1.0, end_s=2.0))

    assert segment.shape == (48_000,)
    np.testing.assert_array_equal(segment, source[48_000:96_000])


def test_t013_clamps_end_beyond_record_duration(
    three_second_record: tuple[np.ndarray, object],
) -> None:
    source, record = three_second_record

    segment = extract_segment(record, time_range=TimeRange(start_s=2.0, end_s=10.0))

    np.testing.assert_array_equal(segment, source[96_000:])


@pytest.mark.parametrize(
    "time_range",
    [
        TimeRange.model_construct(start_s=1.0, end_s=1.0),
        TimeRange.model_construct(start_s=2.0, end_s=1.0),
        TimeRange(start_s=3.0),
        TimeRange(start_s=4.0),
    ],
)
def test_t014_invalid_or_empty_ranges_raise_invalid_time_range_error(
    three_second_record: tuple[np.ndarray, object], time_range: TimeRange
) -> None:
    _, record = three_second_record

    with pytest.raises(InvalidTimeRangeError):
        extract_segment(record, time_range=time_range)


def test_t015_mono_channel_selection_and_isolation() -> None:
    samples = np.array([0.0, 0.25, -0.5], dtype=np.float32)
    record = build_signal_record(
        samples,
        sample_rate_hz=48_000,
        source_type="generated",
    )

    left = extract_segment(record, channel="left")
    mixdown = extract_segment(record, channel="mixdown")

    np.testing.assert_array_equal(left, samples)
    np.testing.assert_array_equal(mixdown, samples)
    for result in (left, mixdown):
        assert result.ndim == 1
        assert result.dtype == np.float32
        assert result.flags.writeable
        assert not np.shares_memory(result, record.samples)
    with pytest.raises(UnsupportedChannelError):
        extract_segment(record, channel="right")


def test_t016_stereo_selection_and_float64_mixdown_are_writable_copies() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    left = np.sin(2 * np.pi * 200 * t)
    right = np.sin(2 * np.pi * 400 * t)
    record = build_signal_record(
        np.column_stack([left, right]),
        sample_rate_hz=sample_rate_hz,
        source_type="generated",
    )

    selected_left = extract_segment(record, channel="left")
    selected_right = extract_segment(record, channel="right")
    mixdown = extract_segment(record, channel="mixdown")

    np.testing.assert_allclose(selected_left, left.astype(np.float32), atol=1e-6)
    np.testing.assert_allclose(selected_right, right.astype(np.float32), atol=1e-6)
    np.testing.assert_allclose(
        mixdown,
        ((left + right) / 2).astype(np.float32),
        atol=1e-6,
    )
    for result in (selected_left, selected_right, mixdown):
        assert result.ndim == 1
        assert result.dtype == np.float32
        assert result.flags.writeable
        assert not np.shares_memory(result, record.samples)


def test_left_and_right_are_unsupported_for_more_than_two_channels() -> None:
    record = build_signal_record(
        np.zeros((4, 3), dtype=np.float32),
        sample_rate_hz=48_000,
        source_type="generated",
    )

    for channel in ("left", "right"):
        with pytest.raises(UnsupportedChannelError):
            extract_segment(record, channel=channel)
