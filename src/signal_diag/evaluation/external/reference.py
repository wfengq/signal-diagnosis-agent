"""Evaluator-only deterministic reference analysis for external WAV study."""

from __future__ import annotations

import hashlib

import numpy as np

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.evaluation.external.reference_harmonics import (
    analyze_harmonic_reference,
)
from signal_diag.evaluation.external.reference_models import (
    REFERENCE_ANALYZER_VERSION_V02,
    REFERENCE_ANALYZER_VERSION_V03,
    ReferenceAnalyzerVersion,
    ReferenceSummary,
)


def analyze_reference(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
) -> ReferenceSummary:
    """Measure clipping, F0, THD, and order-2 amplitude (V0.2 identity 1.0.0)."""
    return _analyze_reference_impl(
        samples,
        sample_rate_hz,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
        reference_analyzer_version=REFERENCE_ANALYZER_VERSION_V02,
    )


def analyze_reference_v03(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
) -> ReferenceSummary:
    """Independent reference path for V0.3 dev/val qualification (identity 1.1.0)."""
    return _analyze_reference_impl(
        samples,
        sample_rate_hz,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
        reference_analyzer_version=REFERENCE_ANALYZER_VERSION_V03,
    )


def _analyze_reference_impl(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float,
    fmax_hz: float,
    reference_analyzer_version: ReferenceAnalyzerVersion,
) -> ReferenceSummary:
    values = _validated_1d(samples)
    input_digest = _sample_digest(values)

    clipping = analyze_clipping(values)
    harmonic = analyze_harmonic_reference(
        values,
        sample_rate_hz,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )
    # Local one-liner from existing clipping flags; do not import dsp.harmonics.
    full_scale_threshold = 0.99
    clipping_mechanism = bool(
        clipping.full_scale_detected
        or (clipping.flat_top_detected and clipping.peak_abs >= full_scale_threshold)
    )

    applicable = bool(harmonic.f0_voiced and harmonic.valid)
    return ReferenceSummary(
        reference_analyzer_version=reference_analyzer_version,
        input_sha256=input_digest,
        applicable=applicable,
        clipping_ratio=clipping.clipping_ratio if applicable else None,
        flat_top_detected=clipping.flat_top_detected if applicable else None,
        f0_hz=harmonic.f0_hz if applicable else None,
        thd_percent=harmonic.thd_percent if applicable else None,
        order_2_relative_amplitude=(
            harmonic.order_2_relative_amplitude if applicable else None
        ),
        series_kind=harmonic.series_kind,
        clipping_mechanism=clipping_mechanism if applicable else None,
    )


def _validated_1d(samples: np.ndarray) -> np.ndarray:
    if samples.ndim != 1:
        msg = "samples must be a mono 1-D array"
        raise ValueError(msg)
    if samples.size == 0:
        msg = "samples must be non-empty"
        raise ValueError(msg)
    if not np.all(np.isfinite(samples)):
        msg = "samples must be finite"
        raise ValueError(msg)
    return np.ascontiguousarray(samples, dtype=np.float32)


def _sample_digest(samples: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(samples, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()
