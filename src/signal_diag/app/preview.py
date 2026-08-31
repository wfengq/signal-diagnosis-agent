"""Deterministic visualization-only waveform downsampling."""

from __future__ import annotations

from itertools import pairwise

import numpy as np

from signal_diag.app.errors import InvalidRequestError
from signal_diag.app.models import AppErrorDetail, WaveformPoint, WaveformPreview


def _reject(message: str) -> None:
    raise InvalidRequestError(AppErrorDetail(code="invalid_request", message=message))


def _bucket_indices(values: np.ndarray) -> tuple[int, ...]:
    minimum = int(np.argmin(values))
    maximum = int(np.argmax(values))
    return (minimum,) if minimum == maximum else tuple(sorted((minimum, maximum)))


def _validate_preview_input(
    samples: np.ndarray,
    *,
    sample_rate_hz: int,
    max_points: int,
) -> None:
    if not isinstance(samples, np.ndarray) or samples.ndim != 1:
        _reject("preview samples must be a one-dimensional array")
    if samples.size == 0:
        _reject("preview samples must not be empty")
    if not np.isfinite(samples).all():
        _reject("preview samples must be finite")
    if sample_rate_hz <= 0:
        _reject("sample_rate_hz must be positive")
    if max_points < 2 or max_points > 1_000:
        _reject("max_points must be between 2 and 1000 inclusive")


def _points_for_indices(
    samples: np.ndarray,
    indices: list[int],
    sample_rate_hz: int,
) -> tuple[WaveformPoint, ...]:
    return tuple(
        WaveformPoint(
            sample_index=index,
            time_s=index / sample_rate_hz,
            amplitude=float(samples[index]),
        )
        for index in indices
    )


def _downsample_indices(samples: np.ndarray, max_points: int) -> list[int]:
    bucket_count = max_points // 2
    edges = np.linspace(0, len(samples), bucket_count + 1, dtype=np.int64)
    indices: list[int] = []
    seen: set[int] = set()
    for start, end in pairwise(edges):
        start_index = int(start)
        end_index = int(end)
        if start_index == end_index:
            continue
        for local in _bucket_indices(samples[start_index:end_index]):
            absolute = start_index + local
            if absolute in seen:
                continue
            seen.add(absolute)
            indices.append(absolute)
    return indices


def build_waveform_preview(
    samples: np.ndarray,
    *,
    sample_rate_hz: int,
    max_points: int = 1_000,
) -> WaveformPreview:
    _validate_preview_input(
        samples,
        sample_rate_hz=sample_rate_hz,
        max_points=max_points,
    )
    if len(samples) <= max_points:
        selected = list(range(len(samples)))
    else:
        selected = _downsample_indices(samples, max_points)
    return WaveformPreview(
        label="visualization_only",
        sample_rate_hz=sample_rate_hz,
        original_num_samples=len(samples),
        points=_points_for_indices(samples, selected, sample_rate_hz),
    )
