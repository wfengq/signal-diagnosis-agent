"""Tests for deterministic full-scale and flat-top clipping detection."""

import numpy as np
import pytest

from signal_diag.dsp import analyze_clipping
from signal_diag.signal import SyntheticCase, extract_segment


def test_t028_clean_sine_and_low_level_constants_are_not_clipping(
    sine_case: SyntheticCase,
) -> None:
    clean = analyze_clipping(extract_segment(sine_case.record))
    constant = analyze_clipping(np.full(32, 0.1, dtype=np.float32))
    silence = analyze_clipping(np.zeros(32, dtype=np.float32))

    for result in (clean, constant, silence):
        assert not result.detected
        assert result.clipped_samples == 0
        assert result.clipping_events == 0
        assert result.longest_event_samples == 0
        assert not result.full_scale_detected
        assert not result.flat_top_detected


def test_t029_full_scale_clipping_is_detected(
    full_scale_clipped_case: SyntheticCase,
) -> None:
    result = analyze_clipping(extract_segment(full_scale_clipped_case.record))

    assert result.detected
    assert result.full_scale_detected
    assert result.clipped_samples > 0
    assert result.clipping_events > 0
    assert result.longest_event_samples > 0


def test_t030_sub_full_scale_flat_top_is_detected(
    clipped_case: SyntheticCase,
) -> None:
    result = analyze_clipping(extract_segment(clipped_case.record))

    assert result.detected
    assert result.flat_top_detected
    assert not result.full_scale_detected


def test_t031_overlapping_masks_use_union_count() -> None:
    samples = np.array([0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0])

    result = analyze_clipping(samples)

    assert result.full_scale_detected
    assert result.flat_top_detected
    assert result.clipped_samples == 3
    assert result.clipping_ratio == 3 / len(samples)
    assert result.clipping_events == 1
    assert result.longest_event_samples == 3


def test_t032_validation_and_input_mutation_safety() -> None:
    invalid_samples = (
        np.array([]),
        np.array([0.0, np.nan]),
        np.array([0.0, np.inf]),
        np.array([[0.0], [1.0]]),
    )
    for samples in invalid_samples:
        with pytest.raises(ValueError):
            analyze_clipping(samples)

    samples = np.array([0.0, 0.5, 1.0, 1.0, 0.5], dtype=np.float32)
    before = samples.tobytes()
    analyze_clipping(samples)
    assert samples.tobytes() == before

    invalid_parameters = (
        {"full_scale_threshold": 0.0},
        {"min_consecutive_samples": 1},
        {"flat_top_tolerance": -1.0},
        {"min_flat_top_samples": 1},
    )
    for parameters in invalid_parameters:
        with pytest.raises(ValueError):
            analyze_clipping(samples, **parameters)
