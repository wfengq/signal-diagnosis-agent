"""T-CX393: B2 segment scan is deterministic and counts tool calls."""

from __future__ import annotations

import numpy as np

from signal_diag.evaluation.agent_increment.segment_baseline import (
    B2_HOP_S,
    B2_PARAMETER_ID,
    B2_WINDOW_S,
    scan_signal,
)
from signal_diag.signal import build_signal_record


def _clipped_segment() -> object:
    sample_rate = 8000
    duration_s = 2.0
    times = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    wave = 0.5 * np.sin(2.0 * np.pi * 440.0 * times)
    clip = (times >= 1.0) & (times < 1.05)
    wave[clip] = 0.995
    samples = wave.astype(np.float32).reshape(-1, 1)
    return build_signal_record(samples, sample_rate_hz=sample_rate, source_type="generated")


def test_t_cx393_parameters_are_frozen() -> None:
    assert B2_PARAMETER_ID == "b2-segment-scan-1.0"
    assert B2_WINDOW_S == 0.25
    assert B2_HOP_S == 0.125


def test_t_cx393_scan_is_deterministic_and_counts_calls() -> None:
    record = _clipped_segment()
    first = scan_signal(record)
    second = scan_signal(record)
    assert first == second
    assert first.tool_calls == 30
    assert any(
        item.fault == "clipping" and item.time_range is not None and item.time_range.start_s <= 1.0 < item.time_range.end_s
        for item in first.supports
    )
    assert all(item.channel == "mixdown" for item in first.supports)
