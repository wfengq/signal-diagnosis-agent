"""Evaluator-only deterministic reference analysis for external WAV study."""

from __future__ import annotations

import hashlib

import numpy as np

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.dsp.harmonics import analyze_harmonic_distortion
from signal_diag.dsp.models import HarmonicComponent
from signal_diag.dsp.pitch import estimate_f0_autocorrelation
from signal_diag.evaluation.external.reference_models import ReferenceSummary


def analyze_reference(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
) -> ReferenceSummary:
    """Measure clipping, F0, THD, and order-2 amplitude for one analysis WAV."""
    values = _validated_1d(samples)
    input_digest = _sample_digest(values)

    clipping = analyze_clipping(values)
    f0 = estimate_f0_autocorrelation(
        values,
        sample_rate_hz,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )
    harmonic = analyze_harmonic_distortion(
        values,
        sample_rate_hz,
        fundamental_hz=f0.f0_hz if f0.voiced else None,
        fmin_hz=fmin_hz,
        fmax_hz=fmax_hz,
    )

    applicable = bool(f0.voiced and harmonic.valid)
    order_2_relative_amplitude = _order_2_relative_amplitude(harmonic.components)

    return ReferenceSummary(
        input_sha256=input_digest,
        applicable=applicable,
        clipping_ratio=clipping.clipping_ratio if applicable else None,
        flat_top_detected=clipping.flat_top_detected if applicable else None,
        f0_hz=f0.f0_hz if applicable else None,
        thd_percent=harmonic.thd_percent if applicable else None,
        order_2_relative_amplitude=(order_2_relative_amplitude if applicable else None),
    )


def _order_2_relative_amplitude(
    components: tuple[HarmonicComponent, ...],
) -> float | None:
    for component in components:
        if component.order == 2:
            return float(component.relative_amplitude)
    return None


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
