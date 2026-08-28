"""Tests for deterministic harmonic association and THD measurement."""

from dataclasses import fields

import numpy as np
import pytest

from signal_diag.dsp import HarmonicAnalysis, analyze_harmonic_distortion
from signal_diag.signal import SyntheticCase, extract_segment, generate_harmonic_sine


def test_t044_known_harmonic_ratios_produce_expected_thd(
    harmonic_case: SyntheticCase,
) -> None:
    result = analyze_harmonic_distortion(
        extract_segment(harmonic_case.record),
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )

    assert result.valid
    assert result.thd_percent == pytest.approx(11.180339, abs=0.5)


def test_t045_harmonic_components_are_ordered_and_within_one_hz(
    harmonic_case: SyntheticCase,
) -> None:
    result = analyze_harmonic_distortion(
        extract_segment(harmonic_case.record),
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )

    assert result.valid
    orders = [component.order for component in result.components]
    assert orders[:2] == [2, 3]
    assert result.components[0].target_frequency_hz == pytest.approx(400.0, abs=1.0)
    assert result.components[0].measured_frequency_hz == pytest.approx(400.0, abs=1.0)
    assert result.components[1].target_frequency_hz == pytest.approx(600.0, abs=1.0)
    assert result.components[1].measured_frequency_hz == pytest.approx(600.0, abs=1.0)


def test_t046_supplied_fundamental_is_used_consistently(
    harmonic_case: SyntheticCase,
) -> None:
    result = analyze_harmonic_distortion(
        extract_segment(harmonic_case.record),
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )

    assert result.valid
    assert result.fundamental_frequency_hz == pytest.approx(200.0, abs=1.0)
    assert result.fundamental_amplitude == pytest.approx(0.5, abs=1e-2)
    assert result.components[0].relative_amplitude == pytest.approx(0.10, abs=0.02)
    assert result.components[1].relative_amplitude == pytest.approx(0.05, abs=0.02)


def test_t047_omitted_fundamental_is_estimated_and_produces_valid_thd(
    harmonic_case: SyntheticCase,
) -> None:
    result = analyze_harmonic_distortion(
        extract_segment(harmonic_case.record),
        48_000,
        max_harmonic_order=5,
    )

    assert result.valid
    assert result.fundamental_frequency_hz == pytest.approx(200.0, abs=1.0)
    assert result.thd_percent == pytest.approx(11.180339, abs=0.5)


def test_t048_silence_is_invalid_without_numeric_metrics() -> None:
    result = analyze_harmonic_distortion(
        np.zeros(48_000, dtype=np.float32),
        48_000,
        max_harmonic_order=5,
    )

    assert not result.valid
    assert result.invalid_reason
    assert result.fundamental_frequency_hz is None
    assert result.fundamental_amplitude is None
    assert result.thd_percent is None
    assert result.components == ()


def test_t049_seeded_noise_is_invalid_without_fabricated_thd(
    noise_case: SyntheticCase,
) -> None:
    result = analyze_harmonic_distortion(
        extract_segment(noise_case.record),
        48_000,
        max_harmonic_order=5,
    )

    assert not result.valid
    assert result.invalid_reason
    assert result.fundamental_frequency_hz is None
    assert result.fundamental_amplitude is None
    assert result.thd_percent is None
    assert result.components == ()


def test_t050_harmonic_orders_above_nyquist_are_omitted() -> None:
    case = generate_harmonic_sine(
        fundamental_hz=12_000.0,
        harmonic_ratios={2: 0.10, 3: 0.10},
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=0.5,
    )
    result = analyze_harmonic_distortion(
        extract_segment(case.record),
        48_000,
        fundamental_hz=12_000.0,
        max_harmonic_order=5,
    )

    assert result.valid
    orders = [component.order for component in result.components]
    assert orders == [2]
    assert all(
        component.target_frequency_hz <= 24_000.0 for component in result.components
    )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"sample_rate_hz": 0}, "sample_rate_hz must be a positive integer"),
        ({"max_harmonic_order": 1}, "max_harmonic_order must be an integer of at least 2"),
        ({"window": "blackman"}, "window must be 'boxcar' or 'hann'"),
        ({"fundamental_hz": 0.0}, "fundamental_hz must be finite and positive"),
        ({"fundamental_hz": -1.0}, "fundamental_hz must be finite and positive"),
    ],
)
def test_t051_validation_rejects_invalid_parameters(
    harmonic_case: SyntheticCase,
    kwargs: dict[str, object],
    match: str,
) -> None:
    samples = extract_segment(harmonic_case.record)
    sample_rate_hz = int(kwargs.pop("sample_rate_hz", 48_000))
    max_harmonic_order = int(kwargs.pop("max_harmonic_order", 5))

    with pytest.raises(ValueError, match=match):
        analyze_harmonic_distortion(
            samples,
            sample_rate_hz,
            max_harmonic_order=max_harmonic_order,
            **kwargs,
        )


def test_t051_analysis_does_not_mutate_input(harmonic_case: SyntheticCase) -> None:
    samples = extract_segment(harmonic_case.record)
    before = samples.tobytes()

    analyze_harmonic_distortion(
        samples,
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )

    assert samples.tobytes() == before


def test_t052_result_contains_no_pass_fail_or_fault_labels(
    harmonic_case: SyntheticCase,
) -> None:
    result = analyze_harmonic_distortion(
        extract_segment(harmonic_case.record),
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )

    forbidden = {"pass", "fail", "fault", "label", "diagnosis", "verdict"}
    for field in fields(HarmonicAnalysis):
        normalized = field.name.lower()
        assert not any(token in normalized for token in forbidden)

    payload = repr(result).lower()
    assert "pass" not in payload
    assert "fail" not in payload
