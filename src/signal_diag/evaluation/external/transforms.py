"""Canonical semi-real transforms for external WAV validity study."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np

from signal_diag.evaluation.external.models import TransformConfig, TransformKind

_QuantileMethod = Literal[
    "inverted_cdf",
    "averaged_inverted_cdf",
    "closest_observation",
    "interpolated_inverted_cdf",
    "hazen",
    "weibull",
    "linear",
    "median_unbiased",
    "normal_unbiased",
    "lower",
    "higher",
    "midpoint",
    "nearest",
]


@dataclass(frozen=True, slots=True)
class TransformResult:
    samples: np.ndarray
    kind: TransformKind
    parameters: Mapping[str, object]
    input_sha256: str
    output_sha256: str

    def __post_init__(self) -> None:
        copied = np.ascontiguousarray(self.samples, dtype=np.float32)
        copied.setflags(write=False)
        object.__setattr__(self, "samples", copied)


def hard_clip(
    samples: np.ndarray,
    tail_proportion: float,
    *,
    quantile_method: _QuantileMethod = "lower",
) -> TransformResult:
    """Apply symmetric hard clipping using a frozen quantile threshold."""
    values = _validated_1d(samples)
    if not (0.0 < tail_proportion < 1.0):
        msg = "tail_proportion must be between 0 and 1"
        raise ValueError(msg)

    threshold = _clip_threshold(
        values, tail_proportion, quantile_method=quantile_method
    )
    clipped = np.clip(values.astype(np.float64), -threshold, threshold).astype(
        np.float32
    )
    return _checked_result(
        clipped,
        kind="clipping",
        parameters={
            "tail_proportion": tail_proportion,
            "quantile_method": quantile_method,
            "threshold": threshold,
        },
        input_samples=values,
    )


def inject_second_harmonic(
    samples: np.ndarray,
    alpha: float,
    post_gain: float,
) -> TransformResult:
    """Inject even-order harmonic distortion using the frozen nonlinearity."""
    values = _validated_1d(samples)
    if alpha <= 0.0:
        msg = "alpha must be positive"
        raise ValueError(msg)
    if post_gain <= 0.0:
        msg = "post_gain must be positive"
        raise ValueError(msg)

    squared = values.astype(np.float64) ** 2
    transformed = (
        values.astype(np.float64) + alpha * (squared - float(np.mean(squared)))
    ) * post_gain
    return _checked_result(
        transformed.astype(np.float32),
        kind="second_harmonic",
        parameters={"alpha": alpha, "post_gain": post_gain},
        input_samples=values,
    )


def apply_combined(samples: np.ndarray, config: TransformConfig) -> TransformResult:
    """Apply harmonic distortion first and hard clipping second."""
    if config.kind != "combined":
        msg = "TransformConfig.kind must be 'combined'"
        raise ValueError(msg)
    if (
        config.tail_proportion is None
        or config.alpha is None
        or config.post_gain is None
    ):
        msg = "combined transform requires tail_proportion, alpha, and post_gain"
        raise ValueError(msg)

    values = _validated_1d(samples)
    harmonic = inject_second_harmonic(values, config.alpha, config.post_gain)
    clipped = hard_clip(
        harmonic.samples,
        config.tail_proportion,
        quantile_method="lower",
    )
    return TransformResult(
        samples=clipped.samples,
        kind="combined",
        parameters={
            "tail_proportion": config.tail_proportion,
            "alpha": config.alpha,
            "post_gain": config.post_gain,
            "quantile_method": "lower",
            "threshold": clipped.parameters["threshold"],
        },
        input_sha256=_sample_digest(values),
        output_sha256=clipped.output_sha256,
    )


def _clip_threshold(
    samples: np.ndarray,
    tail_proportion: float,
    *,
    quantile_method: _QuantileMethod,
) -> float:
    abs_values = np.abs(samples.astype(np.float64))
    return float(
        np.quantile(abs_values, 1.0 - tail_proportion, method=quantile_method),
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


def _checked_result(
    output_samples: np.ndarray,
    *,
    kind: TransformKind,
    parameters: Mapping[str, object],
    input_samples: np.ndarray,
) -> TransformResult:
    return TransformResult(
        samples=output_samples,
        kind=kind,
        parameters=parameters,
        input_sha256=_sample_digest(input_samples),
        output_sha256=_sample_digest(output_samples),
    )
