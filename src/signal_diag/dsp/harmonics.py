"""Deterministic harmonic association and THD measurement."""

import math

import numpy as np

from .models import HarmonicAnalysis, HarmonicComponent
from .pitch import estimate_f0_autocorrelation
from .preprocess import _validated_1d, remove_dc, rms


def _invalid(
    reason: str,
    *,
    max_harmonic_order: int,
    frequency_resolution_hz: float,
) -> HarmonicAnalysis:
    return HarmonicAnalysis(
        valid=False,
        invalid_reason=reason,
        fundamental_frequency_hz=None,
        fundamental_amplitude=None,
        thd_percent=None,
        max_harmonic_order=max_harmonic_order,
        frequency_resolution_hz=frequency_resolution_hz,
        components=(),
    )


def _window_values(length: int, window: str) -> np.ndarray:
    if window == "hann":
        return np.hanning(length)
    return np.ones(length, dtype=np.float64)


def _nearest_peak_amplitude(
    linear: np.ndarray,
    frequencies: np.ndarray,
    target_hz: float,
    window_sum: float,
) -> tuple[float, float]:
    center = int(np.argmin(np.abs(frequencies - target_hz)))
    start = max(center - 1, 0)
    end = min(center + 2, linear.size)
    best_index = start + int(np.argmax(linear[start:end]))
    magnitude = float(linear[best_index])
    amplitude = 2.0 * magnitude / window_sum
    return amplitude, float(frequencies[best_index])


def analyze_harmonic_distortion(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fundamental_hz: float | None = None,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    max_harmonic_order: int = 5,
    window: str = "hann",
) -> HarmonicAnalysis:
    """Measure harmonic components and THD from a one-dimensional waveform."""
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
        not isinstance(max_harmonic_order, (int, np.integer))
        or isinstance(max_harmonic_order, (bool, np.bool_))
        or max_harmonic_order < 2
    ):
        raise ValueError("max_harmonic_order must be an integer of at least 2")
    if fundamental_hz is not None and (
        not np.isfinite(fundamental_hz) or fundamental_hz <= 0.0
    ):
        raise ValueError("fundamental_hz must be finite and positive")

    resolved_order = int(max_harmonic_order)
    frequency_resolution_hz = int(sample_rate_hz) / len(values)
    nyquist_hz = int(sample_rate_hz) / 2.0

    working = remove_dc(values)
    if rms(working) <= np.finfo(np.float64).eps:
        return _invalid(
            "insufficient signal energy",
            max_harmonic_order=resolved_order,
            frequency_resolution_hz=frequency_resolution_hz,
        )

    if fundamental_hz is None:
        if not np.isfinite(fmin_hz) or fmin_hz <= 0.0:
            raise ValueError("fmin_hz must be finite and positive")
        if not np.isfinite(fmax_hz) or fmax_hz <= 0.0:
            raise ValueError("fmax_hz must be finite and positive")
        if fmax_hz <= fmin_hz:
            raise ValueError("fmax_hz must be greater than fmin_hz")

        estimate = estimate_f0_autocorrelation(
            values,
            sample_rate_hz,
            fmin_hz=fmin_hz,
            fmax_hz=fmax_hz,
        )
        if not estimate.voiced or estimate.f0_hz is None:
            return _invalid(
                "fundamental could not be estimated reliably",
                max_harmonic_order=resolved_order,
                frequency_resolution_hz=frequency_resolution_hz,
            )
        resolved_f0 = float(estimate.f0_hz)
    else:
        resolved_f0 = float(fundamental_hz)

    if resolved_f0 > nyquist_hz:
        return _invalid(
            "fundamental frequency exceeds Nyquist limit",
            max_harmonic_order=resolved_order,
            frequency_resolution_hz=frequency_resolution_hz,
        )

    window_values = _window_values(len(working), window)
    window_sum = float(np.sum(window_values))
    spectrum = np.fft.rfft(working * window_values)
    linear = np.abs(spectrum)
    frequencies = np.fft.rfftfreq(len(working), d=1.0 / int(sample_rate_hz))

    fundamental_amplitude, _ = _nearest_peak_amplitude(
        linear,
        frequencies,
        resolved_f0,
        window_sum,
    )
    if fundamental_amplitude <= np.finfo(np.float64).eps:
        return _invalid(
            "fundamental spectral amplitude is negligible",
            max_harmonic_order=resolved_order,
            frequency_resolution_hz=frequency_resolution_hz,
        )

    tiny = np.finfo(np.float64).tiny
    components: list[HarmonicComponent] = []
    harmonic_amplitudes: list[float] = []

    for order in range(2, resolved_order + 1):
        target_hz = resolved_f0 * order
        if target_hz > nyquist_hz:
            continue
        amplitude, measured_hz = _nearest_peak_amplitude(
            linear,
            frequencies,
            target_hz,
            window_sum,
        )
        relative_amplitude = amplitude / fundamental_amplitude
        harmonic_amplitudes.append(amplitude)
        safe_relative = max(float(relative_amplitude), float(tiny))
        components.append(
            HarmonicComponent(
                order=order,
                target_frequency_hz=target_hz,
                measured_frequency_hz=measured_hz,
                relative_amplitude=relative_amplitude,
                relative_magnitude_db=20.0 * math.log10(safe_relative),
            )
        )

    thd_percent = (
        100.0
        * float(np.sqrt(np.sum(np.square(harmonic_amplitudes))))
        / fundamental_amplitude
    )

    return HarmonicAnalysis(
        valid=True,
        invalid_reason=None,
        fundamental_frequency_hz=resolved_f0,
        fundamental_amplitude=fundamental_amplitude,
        thd_percent=thd_percent,
        max_harmonic_order=resolved_order,
        frequency_resolution_hz=frequency_resolution_hz,
        components=tuple(components),
    )
