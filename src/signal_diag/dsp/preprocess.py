"""Shared preprocessing helpers for one-dimensional DSP inputs."""

import numpy as np


def _validated_1d(samples: np.ndarray) -> np.ndarray:
    values = np.asarray(samples)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("samples must be finite, non-empty, and one-dimensional")
    return values.astype(np.float64, copy=False)


def remove_dc(samples: np.ndarray) -> np.ndarray:
    """Return a copy of samples with its mean removed."""
    values = _validated_1d(samples)
    return values - np.mean(values)


def rms(samples: np.ndarray) -> float:
    """Return the root-mean-square amplitude of samples."""
    values = _validated_1d(samples)
    return float(np.sqrt(np.mean(values**2)))


def peak_abs(samples: np.ndarray) -> float:
    """Return the maximum absolute amplitude of samples."""
    values = _validated_1d(samples)
    return float(np.max(np.abs(values)))
