"""Deterministic windowed real-FFT spectrum analysis."""

import numpy as np

from .models import FFTAnalysis, SpectrumPeak
from .preprocess import _validated_1d, remove_dc


def _resolved_n_fft(n_fft: int | None, sample_count: int) -> int:
    if n_fft is None:
        return sample_count
    if (
        not isinstance(n_fft, (int, np.integer))
        or isinstance(n_fft, (bool, np.bool_))
        or n_fft <= 0
    ):
        raise ValueError("n_fft must be a positive integer")
    if n_fft < sample_count:
        raise ValueError("n_fft must be at least the selected sample count")
    return int(n_fft)


def _local_peak_indices(linear: np.ndarray) -> np.ndarray:
    center = linear[1:-1]
    left = linear[:-2]
    right = linear[2:]
    local = (center >= left) & (center >= right) & (
        (center > left) | (center > right)
    )
    return np.flatnonzero(local) + 1


def analyze_fft(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    window: str = "hann",
    n_fft: int | None = None,
    remove_dc_component: bool = True,
    max_peaks: int = 10,
) -> FFTAnalysis:
    """Measure a windowed real-FFT spectrum and its diagnostic summary."""
    values = _validated_1d(samples)
    if len(values) < 3:
        raise ValueError("samples must contain at least three values")
    if (
        not isinstance(sample_rate_hz, (int, np.integer))
        or isinstance(sample_rate_hz, (bool, np.bool_))
        or sample_rate_hz <= 0
    ):
        raise ValueError("sample_rate_hz must be a positive integer")
    if window not in {"boxcar", "hann"}:
        raise ValueError("window must be 'boxcar' or 'hann'")
    if (
        not isinstance(max_peaks, (int, np.integer))
        or isinstance(max_peaks, (bool, np.bool_))
        or max_peaks < 1
    ):
        raise ValueError("max_peaks must be an integer of at least 1")

    resolved_n_fft = _resolved_n_fft(n_fft, len(values))
    working = (
        remove_dc(values)
        if remove_dc_component
        else values.astype(np.float64, copy=True)
    )
    window_values = (
        np.hanning(len(working))
        if window == "hann"
        else np.ones(len(working), dtype=np.float64)
    )
    spectrum = np.fft.rfft(working * window_values, n=resolved_n_fft)
    linear = np.abs(spectrum)
    frequencies = np.fft.rfftfreq(
        resolved_n_fft,
        d=1.0 / int(sample_rate_hz),
    )
    maximum = float(np.max(linear))

    if maximum == 0.0:
        return FFTAnalysis(
            frequencies_hz=frequencies,
            magnitude_db=np.full(linear.shape, -np.inf, dtype=np.float64),
            frequency_resolution_hz=int(sample_rate_hz) / resolved_n_fft,
            dominant_frequency_hz=None,
            dominant_magnitude_db=None,
            spectral_centroid_hz=None,
            peaks=(),
        )

    relative = linear / maximum
    magnitude_db = 20.0 * np.log10(
        np.maximum(relative, np.finfo(np.float64).tiny)
    )
    non_dc = linear[1:]
    if non_dc.size and float(np.max(non_dc)) > 0.0:
        dominant_index = int(np.argmax(non_dc)) + 1
        dominant_frequency_hz = float(frequencies[dominant_index])
        dominant_magnitude_db = float(magnitude_db[dominant_index])
    else:
        dominant_frequency_hz = None
        dominant_magnitude_db = None

    linear_sum = float(np.sum(linear))
    spectral_centroid_hz = float(np.dot(frequencies, linear) / linear_sum)
    peak_indices = _local_peak_indices(linear)
    ordered_peak_indices = sorted(
        (int(index) for index in peak_indices),
        key=lambda index: (-float(magnitude_db[index]), float(frequencies[index])),
    )
    peaks = tuple(
        SpectrumPeak(
            frequency_hz=float(frequencies[index]),
            magnitude_db=float(magnitude_db[index]),
        )
        for index in ordered_peak_indices[: int(max_peaks)]
    )

    return FFTAnalysis(
        frequencies_hz=frequencies,
        magnitude_db=magnitude_db,
        frequency_resolution_hz=int(sample_rate_hz) / resolved_n_fft,
        dominant_frequency_hz=dominant_frequency_hz,
        dominant_magnitude_db=dominant_magnitude_db,
        spectral_centroid_hz=spectral_centroid_hz,
        peaks=peaks,
    )
