"""Tests for frozen external harmonic alpha selection."""

from __future__ import annotations

import numpy as np
import pytest

from signal_diag.evaluation.external.models import EXTERNAL_TRANSFORM_VERSION_AMPNORM
from signal_diag.evaluation.external.reference import analyze_reference
from signal_diag.evaluation.external.transform_selection import (
    ALPHA_CANDIDATES,
    passes_clean_master_gate,
    passes_harmonic_alpha_gate,
    select_smallest_passing_alpha,
)
from signal_diag.evaluation.external.transforms import (
    inject_second_harmonic,
    inject_second_harmonic_amplitude_normalized,
)

_SAMPLE_RATE_HZ = 48_000


def _sine(amplitude: float = 0.5) -> np.ndarray:
    samples = np.sin(
        2.0 * np.pi * 200.0 * np.arange(960, dtype=np.float64) / _SAMPLE_RATE_HZ,
        dtype=np.float64,
    )
    return (samples * amplitude).astype(np.float32)


def test_passes_clean_master_gate_accepts_low_thd_sine() -> None:
    summary = analyze_reference(_sine(), _SAMPLE_RATE_HZ)
    assert passes_clean_master_gate(summary)


def test_passes_harmonic_alpha_gate_rejects_even_order_transform() -> None:
    summary = analyze_reference(_sine(), _SAMPLE_RATE_HZ)
    assert not passes_harmonic_alpha_gate(summary)


def test_ampnorm_selects_smallest_alpha_on_validation_masters() -> None:
    masters = (
        ("master_val_01", _sine(0.5), _SAMPLE_RATE_HZ),
        ("master_val_02", _sine(0.35), _SAMPLE_RATE_HZ),
    )
    result = select_smallest_passing_alpha(
        masters,
        transform_version=EXTERNAL_TRANSFORM_VERSION_AMPNORM,
    )
    assert result.alpha_selection == "passed"
    assert result.selected_alpha == min(ALPHA_CANDIDATES)


def test_even_order_still_fails_on_quiet_validation_master() -> None:
    quiet = _sine(0.02)
    summary = analyze_reference(
        inject_second_harmonic(quiet, 0.20, 0.8).samples,
        _SAMPLE_RATE_HZ,
    )
    assert summary.thd_percent is not None
    assert summary.thd_percent < 5.0

    ampnorm = analyze_reference(
        inject_second_harmonic_amplitude_normalized(quiet, 0.20, 0.8).samples,
        _SAMPLE_RATE_HZ,
    )
    assert ampnorm.thd_percent is not None
    assert ampnorm.thd_percent > 5.0
