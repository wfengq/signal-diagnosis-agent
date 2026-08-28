"""Tests for deterministic autocorrelation fundamental estimation."""

import numpy as np
import pytest

from signal_diag.dsp import estimate_f0_autocorrelation
from signal_diag.signal import SyntheticCase, extract_segment


def test_t039_sine_fundamental_is_200_hz(sine_case: SyntheticCase) -> None:
    samples = extract_segment(sine_case.record)

    default_estimate = estimate_f0_autocorrelation(samples, 48_000)
    narrow_estimate = estimate_f0_autocorrelation(
        samples,
        48_000,
        fmin_hz=100.0,
        fmax_hz=400.0,
    )

    for estimate in (default_estimate, narrow_estimate):
        assert estimate.voiced
        assert estimate.f0_hz == pytest.approx(200.0, abs=1.0)
        assert estimate.method == "autocorrelation"
        assert np.isfinite(estimate.confidence)
        assert estimate.confidence >= 0.0


def test_t040_silence_is_unvoiced_without_numeric_f0() -> None:
    estimate = estimate_f0_autocorrelation(
        np.zeros(48_000, dtype=np.float32),
        48_000,
    )

    assert not estimate.voiced
    assert estimate.f0_hz is None
    assert np.isfinite(estimate.confidence)
    assert estimate.confidence >= 0.0
    assert estimate.method == "autocorrelation"


def test_t041_seeded_noise_is_unvoiced_without_numeric_f0(
    noise_case: SyntheticCase,
) -> None:
    estimate = estimate_f0_autocorrelation(
        extract_segment(noise_case.record),
        48_000,
    )

    assert not estimate.voiced
    assert estimate.f0_hz is None
    assert np.isfinite(estimate.confidence)
    assert estimate.confidence >= 0.0


@pytest.mark.parametrize(
    ("sample_rate_hz", "fmin_hz", "fmax_hz"),
    [
        (0, 50.0, 1000.0),
        (-1, 50.0, 1000.0),
        (True, 50.0, 1000.0),
        (48_000, 0.0, 1000.0),
        (48_000, -1.0, 1000.0),
        (48_000, 50.0, 0.0),
        (48_000, 50.0, -1.0),
        (48_000, 200.0, 200.0),
        (48_000, 400.0, 100.0),
    ],
)
def test_t042_invalid_rate_or_bounds_raise(
    sample_rate_hz: int,
    fmin_hz: float,
    fmax_hz: float,
) -> None:
    samples = np.ones(1_024, dtype=np.float32)

    with pytest.raises(ValueError):
        estimate_f0_autocorrelation(
            samples,
            sample_rate_hz,
            fmin_hz=fmin_hz,
            fmax_hz=fmax_hz,
        )


def test_t043_estimation_does_not_mutate_input(sine_case: SyntheticCase) -> None:
    samples = extract_segment(sine_case.record)
    before = samples.tobytes()

    estimate_f0_autocorrelation(samples, 48_000)

    assert samples.tobytes() == before
