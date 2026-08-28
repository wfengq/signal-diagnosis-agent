"""Deterministic full-scale and flat-top clipping analysis."""

import numpy as np

from .models import ClippingAnalysis
from .preprocess import _validated_1d


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    padded = np.pad(mask, (1, 1), constant_values=False)
    edges = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    return [(int(start), int(stop)) for start, stop in zip(starts, stops)]


def _qualified_runs(mask: np.ndarray, minimum_length: int) -> np.ndarray:
    qualified = np.zeros(mask.shape, dtype=bool)
    for start, stop in _runs(mask):
        if stop - start >= minimum_length:
            qualified[start:stop] = True
    return qualified


def _flat_top_mask(
    values: np.ndarray,
    *,
    tolerance: float,
    minimum_length: int,
    peak: float,
) -> np.ndarray:
    mask = np.zeros(values.shape, dtype=bool)
    flat_differences = np.abs(np.diff(values)) <= tolerance

    for difference_start, difference_stop in _runs(flat_differences):
        sample_start = difference_start
        sample_stop = difference_stop + 1
        if sample_stop - sample_start < minimum_length:
            continue

        plateau = values[sample_start:sample_stop]
        if np.max(np.abs(plateau)) < peak - tolerance:
            continue

        neighbors = []
        if sample_start > 0:
            neighbors.append(float(values[sample_start - 1]))
        if sample_stop < len(values):
            neighbors.append(float(values[sample_stop]))
        if not neighbors:
            continue

        level = float(np.mean(plateau))
        is_local_maximum = level > max(neighbors) + tolerance
        is_local_minimum = level < min(neighbors) - tolerance
        if is_local_maximum or is_local_minimum:
            mask[sample_start:sample_stop] = True

    return mask


def analyze_clipping(
    samples: np.ndarray,
    *,
    full_scale_threshold: float = 0.99,
    min_consecutive_samples: int = 2,
    flat_top_tolerance: float = 1e-4,
    min_flat_top_samples: int = 3,
) -> ClippingAnalysis:
    """Measure full-scale and flat-top clipping events."""
    values = _validated_1d(samples)
    if not np.isfinite(full_scale_threshold) or full_scale_threshold <= 0.0:
        raise ValueError("full_scale_threshold must be finite and positive")
    if (
        not isinstance(min_consecutive_samples, (int, np.integer))
        or isinstance(min_consecutive_samples, (bool, np.bool_))
        or min_consecutive_samples < 2
    ):
        raise ValueError("min_consecutive_samples must be an integer of at least 2")
    if not np.isfinite(flat_top_tolerance) or flat_top_tolerance < 0.0:
        raise ValueError("flat_top_tolerance must be finite and non-negative")
    if (
        not isinstance(min_flat_top_samples, (int, np.integer))
        or isinstance(min_flat_top_samples, (bool, np.bool_))
        or min_flat_top_samples < 2
    ):
        raise ValueError("min_flat_top_samples must be an integer of at least 2")

    peak = float(np.max(np.abs(values)))
    full_scale_mask = _qualified_runs(
        np.abs(values) >= full_scale_threshold,
        int(min_consecutive_samples),
    )
    flat_top_mask = _flat_top_mask(
        values,
        tolerance=float(flat_top_tolerance),
        minimum_length=int(min_flat_top_samples),
        peak=peak,
    )
    clipped_mask = np.logical_or(full_scale_mask, flat_top_mask)
    event_runs = _runs(clipped_mask)
    clipped_samples = int(np.count_nonzero(clipped_mask))

    return ClippingAnalysis(
        detected=bool(clipped_samples),
        clipping_ratio=clipped_samples / len(values),
        clipped_samples=clipped_samples,
        clipping_events=len(event_runs),
        longest_event_samples=max(
            (stop - start for start, stop in event_runs),
            default=0,
        ),
        peak_abs=peak,
        full_scale_detected=bool(np.any(full_scale_mask)),
        flat_top_detected=bool(np.any(flat_top_mask)),
    )
