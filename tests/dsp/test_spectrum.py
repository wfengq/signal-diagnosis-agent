"""Tests for deterministic windowed real-FFT spectrum analysis."""

import numpy as np
import pytest

from signal_diag.dsp import analyze_fft
from signal_diag.signal import SyntheticCase, extract_segment, generate_sine


def test_t033_sine_dominant_frequency_and_resolution(
    sine_case: SyntheticCase,
) -> None:
    result = analyze_fft(extract_segment(sine_case.record), 48_000)

    assert result.dominant_frequency_hz == pytest.approx(200.0, abs=1.0)
    assert result.frequency_resolution_hz == pytest.approx(0.5, abs=1e-6)
    assert result.dominant_magnitude_db == pytest.approx(0.0, abs=1e-6)


def test_t034_dc_removal_preserves_dominant_frequency() -> None:
    case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.5,
        dc_offset=0.75,
    )

    result = analyze_fft(extract_segment(case.record), 48_000)

    assert result.dominant_frequency_hz == pytest.approx(200.0, abs=1.0)


def test_t035_strongest_finite_magnitude_is_zero_db(
    sine_case: SyntheticCase,
) -> None:
    result = analyze_fft(extract_segment(sine_case.record), 48_000)
    finite_magnitudes = result.magnitude_db[np.isfinite(result.magnitude_db)]

    assert finite_magnitudes.size > 0
    assert np.max(finite_magnitudes) == pytest.approx(0.0, abs=1e-6)
    assert len(result.peaks) <= 10
    assert all(
        left.magnitude_db >= right.magnitude_db
        for left, right in zip(result.peaks, result.peaks[1:])
    )


def test_t036_explicit_n_fft_zero_pads_with_real_fft_shape(
    sine_case: SyntheticCase,
) -> None:
    samples = extract_segment(sine_case.record)
    n_fft = 131_072

    result = analyze_fft(samples, 48_000, n_fft=n_fft)

    assert len(result.frequencies_hz) == n_fft // 2 + 1
    assert len(result.magnitude_db) == n_fft // 2 + 1
    assert result.frequency_resolution_hz == pytest.approx(
        48_000 / n_fft,
        abs=1e-6,
    )
    assert result.frequencies_hz[-1] == pytest.approx(24_000.0, abs=1e-6)


def test_t037_silence_has_no_fabricated_spectral_measurements() -> None:
    result = analyze_fft(np.zeros(48_000, dtype=np.float32), 48_000)

    assert result.dominant_frequency_hz is None
    assert result.dominant_magnitude_db is None
    assert result.spectral_centroid_hz is None
    assert result.peaks == ()
    assert not np.any(np.isnan(result.magnitude_db))
    assert np.all(np.isneginf(result.magnitude_db))


def test_t038_validation_and_input_mutation_safety() -> None:
    samples = np.array([0.0, 1.0, 0.0, -1.0], dtype=np.float32)
    before = samples.tobytes()

    analyze_fft(samples, 48_000, window="boxcar", remove_dc_component=False)
    assert samples.tobytes() == before

    invalid_calls = (
        (np.array([0.0, 1.0]), 48_000, {}),
        (np.array([[0.0], [1.0], [0.0]]), 48_000, {}),
        (np.array([0.0, np.nan, 1.0]), 48_000, {}),
        (samples, 0, {}),
        (samples, 48_000, {"window": "blackman"}),
        (samples, 48_000, {"n_fft": 0}),
        (samples, 48_000, {"n_fft": len(samples) - 1}),
        (samples, 48_000, {"max_peaks": 0}),
    )
    for invalid_samples, sample_rate_hz, options in invalid_calls:
        with pytest.raises(ValueError):
            analyze_fft(invalid_samples, sample_rate_hz, **options)
