"""Acceptance tests for deterministic synthetic signal generation."""

import numpy as np
import pytest

from signal_diag.signal import (
    SyntheticCase,
    generate_clipped_sine,
    generate_white_noise,
)


def test_t017_clean_sine_matches_shape_amplitude_and_ground_truth(
    sine_case: SyntheticCase,
) -> None:
    record = sine_case.record

    assert record.meta.num_samples == 96_000
    assert record.meta.channels == 1
    assert record.meta.sample_rate_hz == 48_000
    assert record.meta.source_type == "generated"
    assert record.meta.duration_s == pytest.approx(2.0, abs=1e-12)

    t = np.arange(96_000, dtype=np.float64) / 48_000
    np.testing.assert_allclose(
        record.samples[:, 0],
        (0.5 * np.sin(2 * np.pi * 200.0 * t)).astype(np.float32),
        atol=1e-6,
    )
    assert np.max(np.abs(record.samples)) == pytest.approx(0.5, abs=1e-4)

    assert sine_case.ground_truth.generator == "sine"
    assert sine_case.ground_truth.fault_labels == ()
    assert sine_case.ground_truth.parameters == {
        "sample_rate_hz": 48_000,
        "duration_s": 2.0,
        "frequency_hz": 200.0,
        "amplitude": 0.5,
        "phase_rad": 0.0,
        "dc_offset": 0.0,
    }


@pytest.mark.parametrize(("amplitude", "clip_level"), [(0.9, 0.5), (1.2, 1.0)])
def test_t018_clipped_sine_peak_equals_clip_level(amplitude: float, clip_level: float) -> None:
    case = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=amplitude,
        clip_level=clip_level,
    )
    samples = case.record.samples[:, 0]

    assert np.max(np.abs(samples)) == pytest.approx(clip_level, abs=1e-4)
    assert np.count_nonzero(np.abs(samples) >= clip_level) > 0
    assert np.count_nonzero(np.abs(samples) < clip_level) > 0

    assert case.ground_truth.generator == "clipped_sine"
    assert case.ground_truth.fault_labels == ("clipping",)
    assert case.ground_truth.parameters == {
        "sample_rate_hz": 48_000,
        "duration_s": 2.0,
        "frequency_hz": 200.0,
        "input_amplitude": amplitude,
        "clip_level": clip_level,
    }


def test_t019_white_noise_is_reproducible_per_seed() -> None:
    first = generate_white_noise(sample_rate_hz=48_000, duration_s=2.0, rms=0.1, seed=1234)
    repeated = generate_white_noise(sample_rate_hz=48_000, duration_s=2.0, rms=0.1, seed=1234)
    different = generate_white_noise(sample_rate_hz=48_000, duration_s=2.0, rms=0.1, seed=5678)

    np.testing.assert_array_equal(first.record.samples, repeated.record.samples)
    assert not np.array_equal(first.record.samples, different.record.samples)


def test_t020_seeded_noise_has_expected_distribution(noise_case: SyntheticCase) -> None:
    samples = noise_case.record.samples[:, 0].astype(np.float64)

    assert noise_case.record.meta.num_samples == 96_000
    assert float(np.mean(samples)) == pytest.approx(0.0, abs=0.01)
    assert float(np.sqrt(np.mean(samples**2))) == pytest.approx(0.1, rel=0.03)

    assert noise_case.ground_truth.generator == "white_noise"
    assert noise_case.ground_truth.fault_labels == ("noise",)
    assert noise_case.ground_truth.parameters == {
        "sample_rate_hz": 48_000,
        "duration_s": 2.0,
        "rms": 0.1,
        "seed": 1234,
    }
