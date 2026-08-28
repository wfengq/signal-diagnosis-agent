"""Time-range and channel selection for canonical signal records."""

import numpy as np

from .exceptions import InvalidTimeRangeError, UnsupportedChannelError
from .models import ChannelMode, SignalRecord, TimeRange


def _resolve_sample_bounds(record: SignalRecord, time_range: TimeRange) -> tuple[int, int]:
    """Translate a left-closed, right-open time interval into sample bounds."""
    try:
        start = round(time_range.start_s * record.meta.sample_rate_hz)
        end = (
            record.meta.num_samples
            if time_range.end_s is None
            else min(
                round(time_range.end_s * record.meta.sample_rate_hz),
                record.meta.num_samples,
            )
        )
    except (OverflowError, TypeError, ValueError) as error:
        raise InvalidTimeRangeError("time range must resolve to finite sample bounds") from error

    if not 0 <= start < end <= record.meta.num_samples:
        raise InvalidTimeRangeError("time range is empty or outside the record")
    return start, end


def extract_segment(
    record: SignalRecord,
    *,
    time_range: TimeRange | None = None,
    channel: ChannelMode = "mixdown",
) -> np.ndarray:
    """Return a writable, one-dimensional float32 sample selection copy."""
    start, end = _resolve_sample_bounds(record, time_range or TimeRange())
    samples = record.samples[start:end]

    if record.meta.channels == 1:
        if channel == "right":
            raise UnsupportedChannelError("right channel is unavailable for mono signals")
        if channel not in ("left", "mixdown"):
            raise UnsupportedChannelError(f"unsupported channel mode: {channel}")
        selected = samples[:, 0]
    elif record.meta.channels == 2:
        if channel == "left":
            selected = samples[:, 0]
        elif channel == "right":
            selected = samples[:, 1]
        elif channel == "mixdown":
            selected = np.asarray(np.mean(samples, axis=1, dtype=np.float64))
        else:
            raise UnsupportedChannelError(f"unsupported channel mode: {channel}")
    else:
        if channel in ("left", "right"):
            raise UnsupportedChannelError(
                "left and right channel selection is unsupported above stereo"
            )
        if channel != "mixdown":
            raise UnsupportedChannelError(f"unsupported channel mode: {channel}")
        selected = np.asarray(np.mean(samples, axis=1, dtype=np.float64))

    return np.array(selected, dtype=np.float32, order="C", copy=True)
