"""V0.3 Workstream B — harmonic validity gate (T-B-001..T-B-008). Contract tests only."""

from __future__ import annotations

import pytest

from signal_diag.dsp import analyze_harmonic_distortion
from signal_diag.signal import SyntheticCase, extract_segment
from tests.dsp.v03_prerequisite_helpers import (
    fundamental_relative_energy_reference,
    inject_second_harmonic_ampnorm_reference,
    make_high_thd_but_valid_sine,
    make_pure_sine,
    make_subharmonic_lock_sine,
)

# Phase 1 candidate only — NOT a production default until dev evidence + sign-off.
_CANDIDATE_MIN_FUNDAMENTAL_RELATIVE_ENERGY = None  # set after Phase 1 report approval


def _require_fre_field(result: object) -> float:
    assert hasattr(result, "fundamental_relative_energy"), (
        "HarmonicAnalysis must expose fundamental_relative_energy (EV-C026)"
    )
    value = result.fundamental_relative_energy
    assert value is not None
    return float(value)


def test_t_b_001_invalid_when_fundamental_bin_lacks_energy() -> None:
    samples = make_subharmonic_lock_sine(700.0)
    result = analyze_harmonic_distortion(
        samples,
        48_000,
        fmin_hz=50.0,
        fmax_hz=1000.0,
    )
    assert not result.valid
    assert result.invalid_reason == "fundamental_bin_energy_below_reliability_threshold"


def test_t_b_002_valid_for_high_thd_signal() -> None:
    """THD > 100% with sufficient fundamental energy must remain valid (no THD clamp)."""
    samples = make_high_thd_but_valid_sine(200.0)
    result = analyze_harmonic_distortion(
        samples,
        48_000,
        fundamental_hz=200.0,
        max_harmonic_order=5,
    )
    assert result.valid
    assert result.thd_percent is not None
    assert result.thd_percent > 100.0


def test_t_b_003_valid_for_injected_second_harmonic() -> None:
    clean = make_pure_sine(440.0)
    distorted = inject_second_harmonic_ampnorm_reference(clean, alpha=0.50, post_gain=0.8)
    result = analyze_harmonic_distortion(
        distorted,
        48_000,
        fundamental_hz=440.0,
        max_harmonic_order=5,
    )
    assert result.valid
    assert result.thd_percent is not None
    assert result.thd_percent > 5.0


def test_t_b_004_invalid_reason_string_exact() -> None:
    samples = make_subharmonic_lock_sine(700.0)
    result = analyze_harmonic_distortion(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert result.invalid_reason == "fundamental_bin_energy_below_reliability_threshold"


def test_t_b_005_v02_synthetic_benchmark_regression(
    sine_case: SyntheticCase,
    harmonic_case: SyntheticCase,
    clipped_case: SyntheticCase,
) -> None:
    """Gate must not invalidate existing V0.2 synthetic fixtures."""
    for case in (sine_case, harmonic_case, clipped_case):
        result = analyze_harmonic_distortion(
            extract_segment(case.record),
            48_000,
            max_harmonic_order=5,
        )
        assert result.valid, f"regression on {case.record.meta.signal_id}"


def test_t_b_006_fundamental_relative_energy_bounded() -> None:
    samples = make_pure_sine(440.0)
    result = analyze_harmonic_distortion(samples, 48_000, fundamental_hz=440.0)
    fre = _require_fre_field(result)
    assert 0.0 <= fre <= 1.0


def test_t_b_007_fundamental_relative_energy_reproducible() -> None:
    samples = make_pure_sine(440.0)
    f0 = 440.0
    a = fundamental_relative_energy_reference(samples, 48_000, f0)
    b = fundamental_relative_energy_reference(samples, 48_000, f0)
    assert a == b


def test_t_b_008_denominator_uses_positive_frequency_bins_only() -> None:
    """Reference helper matches design: sum of |X[k]|^2 for k=1..N/2."""
    samples = make_pure_sine(440.0)
    result = analyze_harmonic_distortion(samples, 48_000, fundamental_hz=440.0)
    fre_prod = _require_fre_field(result)
    fre_ref = fundamental_relative_energy_reference(samples, 48_000, 440.0)
    assert fre_prod == pytest.approx(fre_ref, rel=1e-9, abs=1e-12)
