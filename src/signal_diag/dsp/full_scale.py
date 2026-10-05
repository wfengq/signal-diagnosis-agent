"""Deterministic full-scale sample counting (qualified runs only)."""

from dataclasses import dataclass

import numpy as np

from .clipping import _qualified_runs
from .preprocess import _validated_1d


@dataclass(frozen=True, slots=True)
class FullScaleCount:
    counted_samples: int
    over_threshold_uncounted: int
    peak_abs: float
    analyzed_samples: int


def count_full_scale_samples(
    samples: np.ndarray,
    *,
    full_scale_threshold: float,
    min_consecutive_samples: int = 2,
) -> FullScaleCount:
    """Count samples in full-scale qualified runs vs isolated over-threshold samples."""
    values = _validated_1d(samples)
    if not np.isfinite(full_scale_threshold) or full_scale_threshold <= 0.0:
        raise ValueError("full_scale_threshold must be finite and positive")
    if (
        not isinstance(min_consecutive_samples, (int, np.integer))
        or isinstance(min_consecutive_samples, (bool, np.bool_))
        or min_consecutive_samples < 2
    ):
        raise ValueError("min_consecutive_samples must be an integer of at least 2")

    peak = float(np.max(np.abs(values)))
    over_threshold = np.abs(values) >= full_scale_threshold
    qualified = _qualified_runs(over_threshold, int(min_consecutive_samples))
    counted = int(np.count_nonzero(qualified))
    over_total = int(np.count_nonzero(over_threshold))
    return FullScaleCount(
        counted_samples=counted,
        over_threshold_uncounted=over_total - counted,
        peak_abs=peak,
        analyzed_samples=len(values),
    )
