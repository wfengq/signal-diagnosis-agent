"""Frozen validation parameter selection for external B-group transforms."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from signal_diag.evaluation.external.models import (
    EXTERNAL_TRANSFORM_VERSION_AMPNORM,
    EXTERNAL_TRANSFORM_VERSION_EVEN_ORDER,
    ExternalTransformVersion,
)
from signal_diag.evaluation.external.reference import analyze_reference
from signal_diag.evaluation.external.reference_models import ReferenceSummary
from signal_diag.evaluation.external.transforms import (
    TransformResult,
    inject_second_harmonic,
    inject_second_harmonic_amplitude_normalized,
)

ALPHA_CANDIDATES_EVEN_ORDER: tuple[float, ...] = (0.10, 0.15, 0.20)
ALPHA_CANDIDATES_AMPNORM: tuple[float, ...] = (
    0.10,
    0.15,
    0.20,
    0.25,
    0.50,
    0.75,
    1.00,
)
# Backward-compatible alias for transform 1.0.0 callers and tests.
ALPHA_CANDIDATES: tuple[float, ...] = ALPHA_CANDIDATES_EVEN_ORDER
THD_DEMO_THRESHOLD_PERCENT = 5.0
CLIPPING_DEMO_THRESHOLD = 0.01
DEFAULT_POST_GAIN = 0.8
PREEXISTING_ORDER2_THRESHOLD = 0.001

HarmonicInjector = Callable[[np.ndarray, float, float], TransformResult]


def alpha_candidates_for_version(
    transform_version: ExternalTransformVersion,
) -> tuple[float, ...]:
    if transform_version == EXTERNAL_TRANSFORM_VERSION_AMPNORM:
        return ALPHA_CANDIDATES_AMPNORM
    if transform_version == EXTERNAL_TRANSFORM_VERSION_EVEN_ORDER:
        return ALPHA_CANDIDATES_EVEN_ORDER
    msg = f"unsupported transform version: {transform_version}"
    raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CandidateReferenceMetrics:
    alpha: float
    applicable: bool
    thd_percent: float | None
    flat_top_detected: bool | None
    clipping_ratio: float | None
    order_2_relative_amplitude: float | None
    f0_hz: float | None
    passed_gate: bool


@dataclass(frozen=True, slots=True)
class AlphaSelectionResult:
    transform_version: ExternalTransformVersion
    alpha_candidates_tested: tuple[float, ...]
    selected_alpha: float | None
    alpha_selection: Literal["passed", "failed"]
    validation_master_results: tuple[tuple[str, bool], ...]
    candidate_metrics: tuple[tuple[str, tuple[CandidateReferenceMetrics, ...]], ...]


def harmonic_injector_for_version(
    transform_version: ExternalTransformVersion,
) -> HarmonicInjector:
    if transform_version == EXTERNAL_TRANSFORM_VERSION_AMPNORM:
        return inject_second_harmonic_amplitude_normalized
    if transform_version == EXTERNAL_TRANSFORM_VERSION_EVEN_ORDER:
        return inject_second_harmonic
    msg = f"unsupported transform version: {transform_version}"
    raise ValueError(msg)


def passes_clean_master_gate(summary: ReferenceSummary) -> bool:
    """Return True when a canonical base satisfies design §9.1 cleanliness."""
    if not summary.applicable:
        return False
    if summary.thd_percent is None:
        return False
    if summary.thd_percent >= THD_DEMO_THRESHOLD_PERCENT:
        return False
    if summary.flat_top_detected:
        return False
    if summary.clipping_ratio is None:
        return False
    if summary.clipping_ratio > CLIPPING_DEMO_THRESHOLD:
        return False
    return not (
        summary.order_2_relative_amplitude is not None
        and summary.order_2_relative_amplitude > PREEXISTING_ORDER2_THRESHOLD
    )


def passes_harmonic_alpha_gate(summary: ReferenceSummary) -> bool:
    """Return True when a transformed master satisfies design §9.4 validation."""
    if not summary.applicable:
        return False
    if summary.thd_percent is None or summary.thd_percent <= THD_DEMO_THRESHOLD_PERCENT:
        return False
    if summary.flat_top_detected:
        return False
    if summary.clipping_ratio is None:
        return False
    if summary.clipping_ratio > CLIPPING_DEMO_THRESHOLD:
        return False
    return (
        summary.order_2_relative_amplitude is not None
        and summary.order_2_relative_amplitude > 0.0
    )


def _metrics_from_summary(
    *,
    alpha: float,
    summary: ReferenceSummary,
) -> CandidateReferenceMetrics:
    return CandidateReferenceMetrics(
        alpha=alpha,
        applicable=summary.applicable,
        thd_percent=summary.thd_percent,
        flat_top_detected=summary.flat_top_detected,
        clipping_ratio=summary.clipping_ratio,
        order_2_relative_amplitude=summary.order_2_relative_amplitude,
        f0_hz=summary.f0_hz,
        passed_gate=passes_harmonic_alpha_gate(summary),
    )


def evaluate_alpha_candidates(
    validation_masters: Sequence[tuple[str, np.ndarray, int]],
    *,
    transform_version: ExternalTransformVersion,
    post_gain: float = DEFAULT_POST_GAIN,
    sample_rate_hz: int = 48_000,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
) -> tuple[tuple[str, tuple[CandidateReferenceMetrics, ...]], ...]:
    """Record full reference metrics for every alpha on every validation master."""
    injector = harmonic_injector_for_version(transform_version)
    candidates = alpha_candidates_for_version(transform_version)
    per_master: list[tuple[str, tuple[CandidateReferenceMetrics, ...]]] = []

    for master_id, samples, _rate in validation_masters:
        metrics: list[CandidateReferenceMetrics] = []
        for alpha in candidates:
            transformed = injector(samples, alpha, post_gain).samples
            summary = analyze_reference(
                transformed,
                sample_rate_hz,
                fmin_hz=fmin_hz,
                fmax_hz=fmax_hz,
            )
            metrics.append(_metrics_from_summary(alpha=alpha, summary=summary))
        per_master.append((master_id, tuple(metrics)))

    return tuple(per_master)


def select_smallest_passing_alpha(
    validation_masters: Sequence[tuple[str, np.ndarray, int]],
    *,
    transform_version: ExternalTransformVersion,
    post_gain: float = DEFAULT_POST_GAIN,
    sample_rate_hz: int = 48_000,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
) -> AlphaSelectionResult:
    """Choose the smallest global alpha passing every validation master."""
    candidates = alpha_candidates_for_version(transform_version)
    candidate_metrics = evaluate_alpha_candidates(
        validation_masters,
        transform_version=transform_version,
        post_gain=post_gain,
        sample_rate_hz=sample_rate_hz,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )
    selected: float | None = None
    per_master: list[tuple[str, bool]] = []

    for alpha in candidates:
        all_pass = True
        per_master.clear()
        for master_id, metrics in candidate_metrics:
            row = next(item for item in metrics if item.alpha == alpha)
            passed = row.passed_gate
            per_master.append((master_id, passed))
            if not passed:
                all_pass = False
        if all_pass:
            selected = alpha
            break

    if selected is None and per_master == []:
        for master_id, metrics in candidate_metrics:
            per_master.append((master_id, False))

    return AlphaSelectionResult(
        transform_version=transform_version,
        alpha_candidates_tested=candidates,
        selected_alpha=selected,
        alpha_selection="passed" if selected is not None else "failed",
        validation_master_results=tuple(per_master),
        candidate_metrics=candidate_metrics,
    )
