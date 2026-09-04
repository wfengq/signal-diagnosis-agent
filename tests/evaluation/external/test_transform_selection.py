"""Tests for frozen external harmonic alpha selection."""

from __future__ import annotations

import numpy as np

from signal_diag.evaluation.external.models import (
    EXTERNAL_TRANSFORM_VERSION_AMPNORM,
    EXTERNAL_TRANSFORM_VERSION_EVEN_ORDER,
)
from signal_diag.evaluation.external.reference import analyze_reference
from signal_diag.evaluation.external.transform_selection import (
    ALPHA_CANDIDATES_AMPNORM,
    ALPHA_CANDIDATES_EVEN_ORDER,
    alpha_candidates_for_version,
    evaluate_alpha_candidates,
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


def test_alpha_candidates_are_version_specific() -> None:
    assert alpha_candidates_for_version(EXTERNAL_TRANSFORM_VERSION_EVEN_ORDER) == (
        0.10,
        0.15,
        0.20,
    )
    assert alpha_candidates_for_version(EXTERNAL_TRANSFORM_VERSION_AMPNORM) == (
        0.10,
        0.15,
        0.20,
        0.25,
        0.50,
        0.75,
        1.00,
    )
    assert ALPHA_CANDIDATES_EVEN_ORDER == (0.10, 0.15, 0.20)
    assert len(ALPHA_CANDIDATES_AMPNORM) == 7


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
    assert result.selected_alpha == min(ALPHA_CANDIDATES_AMPNORM)


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


def test_ev_t027e_ampnorm_injected_harmonic_is_monotonic_in_alpha() -> None:
    base = _sine(0.35)
    prior_thd: float | None = None
    for alpha in ALPHA_CANDIDATES_AMPNORM:
        transformed = inject_second_harmonic_amplitude_normalized(base, alpha, 0.8).samples
        assert np.all(np.isfinite(transformed))
        summary = analyze_reference(transformed, _SAMPLE_RATE_HZ)
        assert summary.thd_percent is not None
        if prior_thd is not None:
            assert summary.thd_percent >= prior_thd
        prior_thd = summary.thd_percent
        if summary.order_2_relative_amplitude is not None:
            assert summary.order_2_relative_amplitude >= 0.0


def test_ev_t027f_ampnorm_outputs_remain_finite_with_bounded_amplitude() -> None:
    base = _sine(0.5)
    for alpha in ALPHA_CANDIDATES_AMPNORM:
        transformed = inject_second_harmonic_amplitude_normalized(base, alpha, 0.8).samples
        assert np.all(np.isfinite(transformed))
        peak = float(np.max(np.abs(transformed)))
        assert peak <= 2.5


def test_ev_t027g_evaluate_alpha_candidates_records_every_candidate() -> None:
    masters = (("master_val_01", _sine(0.5), _SAMPLE_RATE_HZ),)
    metrics = evaluate_alpha_candidates(
        masters,
        transform_version=EXTERNAL_TRANSFORM_VERSION_AMPNORM,
    )
    assert len(metrics) == 1
    master_id, rows = metrics[0]
    assert master_id == "master_val_01"
    assert len(rows) == len(ALPHA_CANDIDATES_AMPNORM)
    assert {row.alpha for row in rows} == set(ALPHA_CANDIDATES_AMPNORM)
    for row in rows:
        assert row.thd_percent is not None
        assert row.applicable is True

    result = select_smallest_passing_alpha(
        masters,
        transform_version=EXTERNAL_TRANSFORM_VERSION_AMPNORM,
    )
    assert len(result.candidate_metrics) == 1
    _, recorded = result.candidate_metrics[0]
    assert len(recorded) == len(ALPHA_CANDIDATES_AMPNORM)
