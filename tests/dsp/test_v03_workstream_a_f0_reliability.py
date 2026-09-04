"""V0.3 Workstream A — F0 reliability (T-A-001..T-A-005). Contract tests only."""

from __future__ import annotations

import pytest

from signal_diag.dsp import estimate_f0_autocorrelation
from tests.dsp.v03_prerequisite_helpers import (
    make_pure_sine,
    make_subharmonic_lock_sine,
)


def _require_f0_reliability_field(estimate: object) -> bool:
    """Design EV-C029: reliability indicator alongside F0 estimate."""
    return hasattr(estimate, "f0_reliability")


def _require_octave_ambiguity_flag(estimate: object) -> bool:
    return hasattr(estimate, "octave_ambiguity_detected")


def test_t_a_001_f0_reliability_field_present() -> None:
    samples = make_pure_sine(440.0)
    estimate = estimate_f0_autocorrelation(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert estimate.voiced
    assert _require_f0_reliability_field(estimate), (
        "F0Estimate must expose f0_reliability once Workstream A is implemented"
    )


def test_t_a_002_octave_ambiguity_flag_without_changing_f0() -> None:
    """Signal energy at 2×F0 only; ACF may lock subharmonic — flag ambiguity, keep F0."""
    samples = make_subharmonic_lock_sine(700.0)  # Phase 1: locks ~350 Hz, FRE≈0
    estimate = estimate_f0_autocorrelation(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert estimate.voiced
    assert _require_octave_ambiguity_flag(estimate)
    assert estimate.octave_ambiguity_detected is True
    # Selected F0 must remain the autocorrelation argmax, not energy-re-ranked.
    assert estimate.f0_hz == pytest.approx(350.0, abs=5.0)


def test_t_a_003_reliable_when_fundamental_bin_has_energy() -> None:
    samples = make_pure_sine(440.0)
    estimate = estimate_f0_autocorrelation(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert estimate.voiced
    assert getattr(estimate, "f0_reliability", None) == "reliable"


def test_t_a_004_unreliable_when_fundamental_bin_lacks_energy() -> None:
    """Synthesized subharmonic-lock regime: little energy at selected F0 bin."""
    samples = make_subharmonic_lock_sine(700.0)
    estimate = estimate_f0_autocorrelation(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert estimate.voiced
    assert getattr(estimate, "f0_reliability", None) == "unreliable"


def test_t_a_005_pure_sinusoid_no_octave_ambiguity() -> None:
    samples = make_pure_sine(440.0)
    estimate = estimate_f0_autocorrelation(samples, 48_000, fmin_hz=50.0, fmax_hz=1000.0)
    assert estimate.voiced
    assert estimate.f0_hz == pytest.approx(440.0, abs=2.0)
    assert getattr(estimate, "octave_ambiguity_detected", True) is False
