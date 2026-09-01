"""Checkpoint E — transforms and pairing (EV-T021–EV-T026)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from signal_diag.evaluation.external.models import (
    EXTERNAL_TRANSFORM_ID,
    EXTERNAL_TRANSFORM_VERSION_AMPNORM,
    EXTERNAL_TRANSFORM_VERSION_EVEN_ORDER,
    TransformConfig,
)
from signal_diag.evaluation.external.transforms import (
    TransformResult,
    apply_combined,
    hard_clip,
    inject_second_harmonic,
    inject_second_harmonic_amplitude_normalized,
)

_SAMPLE_RATE_HZ = 48_000
_BASE = np.sin(
    2.0 * np.pi * 200.0 * np.arange(960, dtype=np.float64) / _SAMPLE_RATE_HZ,
    dtype=np.float64,
).astype(np.float32)
_FROZEN_CONFIG = TransformConfig(
    kind="combined",
    tail_proportion=0.05,
    alpha=0.15,
    post_gain=0.8,
    input_sha256="a" * 64,
    output_sha256="b" * 64,
    parameters_identity="combined_q0.05_a0.15_pg0.8_lower",
)


def _digest(samples: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(samples, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def test_ev_t021_hard_clipping_quantile_method_maps_tail_proportion_to_threshold() -> (
    None
):
    tail_proportion = 0.05
    abs_values = np.abs(_BASE.astype(np.float64))
    expected_threshold = float(
        np.quantile(abs_values, 1.0 - tail_proportion, method="lower"),
    )

    result = hard_clip(_BASE, tail_proportion, quantile_method="lower")

    assert result.parameters["threshold"] == pytest.approx(expected_threshold)
    assert result.parameters["tail_proportion"] == tail_proportion
    assert result.parameters["quantile_method"] == "lower"
    clipped = result.samples.astype(np.float64)
    assert np.all(clipped <= expected_threshold + 1e-6)
    assert np.all(clipped >= -expected_threshold - 1e-6)


def test_ev_t022_second_harmonic_formula_matches_frozen_identity() -> None:
    alpha = 0.15
    post_gain = 0.8
    squared = _BASE.astype(np.float64) ** 2
    expected = (
        _BASE.astype(np.float64) + alpha * (squared - float(np.mean(squared)))
    ) * post_gain

    result = inject_second_harmonic(_BASE, alpha, post_gain)

    np.testing.assert_allclose(
        result.samples, expected.astype(np.float32), rtol=0.0, atol=1e-6
    )
    assert result.kind == "second_harmonic"
    assert result.parameters["alpha"] == alpha
    assert result.parameters["post_gain"] == post_gain


def test_ev_t023_combined_order_is_harmonic_then_clipping() -> None:
    alpha = _FROZEN_CONFIG.alpha
    post_gain = _FROZEN_CONFIG.post_gain
    tail_proportion = _FROZEN_CONFIG.tail_proportion
    assert alpha is not None
    assert post_gain is not None
    assert tail_proportion is not None

    actual = apply_combined(_BASE, _FROZEN_CONFIG).samples
    harmonic = inject_second_harmonic(_BASE, alpha, post_gain).samples
    expected = hard_clip(harmonic, tail_proportion, quantile_method="lower").samples
    np.testing.assert_array_equal(actual, expected)


def test_ev_t024_transforms_do_not_normalize_each_master() -> None:
    low = inject_second_harmonic(_BASE * 0.5, alpha=0.15, post_gain=0.8)
    high = inject_second_harmonic(_BASE, alpha=0.15, post_gain=0.8)
    assert np.max(np.abs(low.samples)) < np.max(np.abs(high.samples))


def test_ev_t025_four_variant_b_family_completeness() -> None:
    alpha = 0.15
    post_gain = 0.8
    tail_proportion = 0.05

    clean = TransformResult(
        samples=_BASE,
        kind="none",
        parameters={"identity": "canonical_base"},
        input_sha256=_digest(_BASE),
        output_sha256=_digest(_BASE),
    )
    clipping = hard_clip(_BASE, tail_proportion, quantile_method="lower")
    harmonic = inject_second_harmonic(_BASE, alpha, post_gain)
    combined = apply_combined(
        _BASE,
        TransformConfig(
            kind="combined",
            tail_proportion=tail_proportion,
            alpha=alpha,
            post_gain=post_gain,
            input_sha256=_digest(_BASE),
            output_sha256="c" * 64,
            parameters_identity="combined_v1",
        ),
    )

    variants = (clean, clipping, harmonic, combined)
    assert {variant.kind for variant in variants} == {
        "none",
        "clipping",
        "second_harmonic",
        "combined",
    }
    digests = {variant.output_sha256 for variant in variants}
    assert len(digests) == 4


def test_ev_t026_transform_digests_are_reproducible() -> None:
    first = hard_clip(_BASE, 0.05, quantile_method="lower")
    second = hard_clip(_BASE, 0.05, quantile_method="lower")

    assert first.input_sha256 == second.input_sha256 == _digest(_BASE)
    assert first.output_sha256 == second.output_sha256
    np.testing.assert_array_equal(first.samples, second.samples)


def test_transform_result_samples_are_read_only_float32() -> None:
    result = hard_clip(_BASE, 0.05, quantile_method="lower")
    assert result.samples.dtype == np.float32
    assert not result.samples.flags.writeable


def test_ev_t027a_amplitude_normalized_formula_matches_frozen_identity() -> None:
    alpha = 0.15
    post_gain = 0.8
    working = _BASE.astype(np.float64)
    peak = float(np.max(np.abs(working)))
    normalized = working / peak
    expected = (
        working + alpha * peak * (normalized**2 - float(np.mean(normalized**2)))
    ) * post_gain

    result = inject_second_harmonic_amplitude_normalized(_BASE, alpha, post_gain)

    np.testing.assert_allclose(
        result.samples, expected.astype(np.float32), rtol=0.0, atol=1e-6
    )
    assert result.parameters["transform_version"] == EXTERNAL_TRANSFORM_VERSION_AMPNORM
    assert result.parameters["a_ref"] == pytest.approx(peak)


def test_ev_t027b_ampnorm_yields_amplitude_invariant_thd_on_scaled_masters() -> None:
    from signal_diag.evaluation.external.reference import analyze_reference

    alpha = 0.15
    post_gain = 0.8
    low = inject_second_harmonic_amplitude_normalized(_BASE * 0.5, alpha, post_gain)
    high = inject_second_harmonic_amplitude_normalized(_BASE, alpha, post_gain)
    low_summary = analyze_reference(low.samples, _SAMPLE_RATE_HZ)
    high_summary = analyze_reference(high.samples, _SAMPLE_RATE_HZ)

    assert low_summary.thd_percent is not None
    assert high_summary.thd_percent is not None
    assert low_summary.thd_percent == pytest.approx(
        high_summary.thd_percent,
        rel=0.05,
        abs=0.5,
    )


def test_ev_t027c_combined_ampnorm_order_is_harmonic_then_clipping() -> None:
    alpha = 0.15
    post_gain = 0.8
    tail_proportion = 0.05
    config = TransformConfig(
        kind="combined",
        transform_version=EXTERNAL_TRANSFORM_VERSION_AMPNORM,
        tail_proportion=tail_proportion,
        alpha=alpha,
        post_gain=post_gain,
        input_sha256=_digest(_BASE),
        output_sha256="e" * 64,
        parameters_identity="combined_ampnorm_v1",
    )

    actual = apply_combined(_BASE, config).samples
    harmonic = inject_second_harmonic_amplitude_normalized(_BASE, alpha, post_gain).samples
    expected = hard_clip(harmonic, tail_proportion, quantile_method="lower").samples
    np.testing.assert_array_equal(actual, expected)


def test_ev_t027d_transform_config_stamps_transform_identity() -> None:
    config = TransformConfig(
        kind="second_harmonic",
        transform_version=EXTERNAL_TRANSFORM_VERSION_AMPNORM,
        alpha=0.15,
        post_gain=0.8,
        input_sha256=_digest(_BASE),
        output_sha256="f" * 64,
        parameters_identity=(
            f"{EXTERNAL_TRANSFORM_ID}/{EXTERNAL_TRANSFORM_VERSION_AMPNORM}/"
            "second_harmonic_ampnorm/a0.15/pg0.8"
        ),
    )

    assert config.transform_id == EXTERNAL_TRANSFORM_ID
    assert config.transform_version == EXTERNAL_TRANSFORM_VERSION_AMPNORM
