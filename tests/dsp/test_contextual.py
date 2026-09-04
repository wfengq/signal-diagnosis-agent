"""T-CX011–T-CX030: deterministic contextual DSP."""

from __future__ import annotations

import numpy as np
import pytest

from signal_diag.dsp.contextual import analyze_contextual_distortion
from signal_diag.signal.synthetic import (
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
)


def _tone(hz: float = 440.0, seconds: float = 1.0, sr: int = 48_000, amp: float = 0.5) -> np.ndarray:
    case = generate_sine(
        sample_rate_hz=sr,
        duration_s=seconds,
        frequency_hz=hz,
        amplitude=amp,
    )
    return np.asarray(case.record.samples[:, 0], dtype=np.float64)


def _with_h2(hz: float = 440.0, alpha: float = 0.25, amp: float = 0.5) -> np.ndarray:
    case = generate_harmonic_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        fundamental_hz=hz,
        fundamental_amplitude=amp,
        harmonic_ratios={2: alpha},
    )
    return np.asarray(case.record.samples[:, 0], dtype=np.float64)


def test_t_cx011_paired_clean_is_valid_with_low_growth() -> None:
    reference = _tone()
    result = analyze_contextual_distortion(
        reference.copy(),
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert result.valid
    assert result.even_harmonic_growth_percent is not None
    assert result.even_harmonic_growth_percent < 0.5


def test_t_cx012_sample_rate_mismatch_is_invalid() -> None:
    reference = _tone()
    result = analyze_contextual_distortion(
        reference,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=44_100,
    )
    assert not result.valid
    assert result.invalid_reason == "sample_rate_mismatch"


def test_t_cx013_h2_injection_shows_positive_even_growth() -> None:
    reference = _tone(amp=0.5)
    test = _with_h2(alpha=0.3, amp=0.5)
    result = analyze_contextual_distortion(
        test,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert result.valid
    assert result.even_harmonic_growth_percent is not None
    assert result.even_harmonic_growth_percent > 5.0


def test_t_cx014_even_harmonic_growth_is_gain_invariant() -> None:
    reference = _tone(amp=0.8)
    test = _with_h2(alpha=0.25, amp=0.8)
    a = analyze_contextual_distortion(
        test * 0.4,
        48_000,
        mode="paired_reference",
        reference_samples=reference * 0.8,
        reference_sample_rate_hz=48_000,
    )
    b = analyze_contextual_distortion(
        test * 0.55,
        48_000,
        mode="paired_reference",
        reference_samples=reference * 0.35,
        reference_sample_rate_hz=48_000,
    )
    assert a.valid and b.valid
    assert a.even_harmonic_growth_percent == pytest.approx(
        b.even_harmonic_growth_percent, rel=0.08, abs=0.5
    )


def test_t_cx015_bounded_delay_still_compares() -> None:
    reference = _tone()
    delayed = np.concatenate([np.zeros(120, dtype=np.float64), reference[:-120]])
    result = analyze_contextual_distortion(
        delayed,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert result.valid
    assert result.alignment_lag_samples is not None
    assert abs(int(result.alignment_lag_samples)) >= 100


def test_t_cx016_natural_even_reference_has_no_new_growth() -> None:
    natural_even = _with_h2(alpha=0.2, amp=0.5)
    delayed_copy = np.concatenate(
        [np.zeros(40, dtype=np.float64), natural_even[:-40]]
    )
    result = analyze_contextual_distortion(
        delayed_copy,
        48_000,
        mode="paired_reference",
        reference_samples=natural_even,
        reference_sample_rate_hz=48_000,
    )
    assert result.valid
    assert result.even_harmonic_growth_percent is not None
    assert result.even_harmonic_growth_percent < 1.0


def test_t_cx017_reference_clipping_invalidates_comparison() -> None:
    clean = _tone(amp=0.4)
    clipped = generate_clipped_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=1.2,
        clip_level=0.99,
    ).record.samples[:, 0].astype(np.float64)
    result = analyze_contextual_distortion(
        clean,
        48_000,
        mode="paired_reference",
        reference_samples=clipped,
        reference_sample_rate_hz=48_000,
    )
    assert not result.valid
    assert result.invalid_reason == "reference_clipping_invalidates_comparison"


def test_t_cx018_test_clipping_metrics_still_reported() -> None:
    reference = _tone(amp=0.4)
    clipped = generate_clipped_sine(
        sample_rate_hz=48_000,
        duration_s=1.0,
        frequency_hz=440.0,
        amplitude=1.2,
        clip_level=0.99,
    ).record.samples[:, 0].astype(np.float64)
    result = analyze_contextual_distortion(
        clipped,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert result.test_clipping_ratio > 0.0


def test_t_cx019_f0_mismatch_is_invalid() -> None:
    reference = _tone(hz=220.0)
    test = _tone(hz=440.0)
    result = analyze_contextual_distortion(
        test,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert not result.valid
    assert result.invalid_reason == "fundamental_incompatible"


def test_t_cx020_unvoiced_test_is_invalid() -> None:
    reference = _tone()
    noise = np.random.default_rng(0).normal(0.0, 1e-4, size=48_000)
    result = analyze_contextual_distortion(
        noise,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert not result.valid


def test_t_cx021_too_short_is_invalid() -> None:
    reference = _tone()
    result = analyze_contextual_distortion(
        reference[:64],
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert not result.valid
    assert result.invalid_reason == "test_too_short"


def test_t_cx022_nominal_mode_accepts_matching_tone() -> None:
    test = _with_h2(alpha=0.2)
    result = analyze_contextual_distortion(
        test,
        48_000,
        mode="nominal_single_tone",
        nominal_fundamental_hz=440.0,
    )
    assert result.valid
    assert result.even_harmonic_growth_percent is not None
    assert result.even_harmonic_growth_percent > 1.0


def test_t_cx023_nominal_mode_rejects_frequency_mismatch() -> None:
    test = _tone(hz=200.0)
    result = analyze_contextual_distortion(
        test,
        48_000,
        mode="nominal_single_tone",
        nominal_fundamental_hz=440.0,
    )
    assert not result.valid
    assert result.invalid_reason in {
        "fundamental_incompatible_with_declaration",
        "test_fundamental_invalid",
    }


def test_t_cx024_determinism() -> None:
    reference = _tone()
    test = _with_h2(alpha=0.22)
    a = analyze_contextual_distortion(
        test,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    b = analyze_contextual_distortion(
        test,
        48_000,
        mode="paired_reference",
        reference_samples=reference,
        reference_sample_rate_hz=48_000,
    )
    assert a == b


def test_t_cx025_programmer_error_on_bad_mode() -> None:
    with pytest.raises(ValueError):
        analyze_contextual_distortion(
            _tone(),
            48_000,
            mode="single_signal",  # type: ignore[arg-type]
        )
