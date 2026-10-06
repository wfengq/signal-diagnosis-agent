"""Deterministic harmonic association and THD measurement."""

import math

import numpy as np

from .models import HarmonicAnalysis, HarmonicComponent
from .pitch import estimate_f0_autocorrelation
from .preprocess import _validated_1d, remove_dc, rms
from .spectral_reliability import (
    DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY,
    DEFAULT_OCTAVE_AMBIGUITY_TOLERANCE,
    detect_octave_ambiguity,
    fundamental_relative_energy,
    normalized_autocorrelation,
)

# Presence floor for "order present" (noise floor, not a planner threshold).
_SERIES_KIND_PRESENT_FLOOR = 0.01
_MULTI_PARTIAL_H2_MIN_RELATIVE_AMPLITUDE = 1.0


def classify_series_kind(
    *,
    valid: bool,
    components: tuple[HarmonicComponent, ...],
) -> str | None:
    """Classify observable harmonic series structure from already-computed orders.

    Returned labels are operational spectral-structure Evidence, not ground-truth
    injection provenance. In particular, ``even_order_present`` means one or more
    even-order components exceed the presence floor; it does not prove that an
    external distortion process injected those harmonics.
    """
    if not valid:
        return "not_applicable"
    present = [
        component
        for component in components
        if component.relative_amplitude >= _SERIES_KIND_PRESENT_FLOOR
    ]
    odd = [component for component in present if component.order % 2 == 1]
    even = [component for component in present if component.order % 2 == 0]
    h2 = next((component for component in present if component.order == 2), None)
    if h2 is not None and h2.relative_amplitude + 1e-6 >= _MULTI_PARTIAL_H2_MIN_RELATIVE_AMPLITUDE:
        return "multi_partial"
    if odd and not even:
        return "native_odd_series"
    if even:
        # Operational even-order structure label (not injection provenance).
        return "even_order_present"
    return None


def _invalid(
    reason: str,
    *,
    max_harmonic_order: int,
    frequency_resolution_hz: float,
    fundamental_relative_energy: float | None = None,
    octave_ambiguity_detected: bool = False,
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
        fundamental_relative_energy=fundamental_relative_energy,
        octave_ambiguity_detected=octave_ambiguity_detected,
        series_kind="not_applicable",
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
    min_fundamental_relative_energy: float = DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY,
    octave_ambiguity_tolerance: float = DEFAULT_OCTAVE_AMBIGUITY_TOLERANCE,
    subharmonic_guard: bool | None = None,
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
        not np.isfinite(min_fundamental_relative_energy)
        or min_fundamental_relative_energy < 0.0
        or min_fundamental_relative_energy > 1.0
    ):
        raise ValueError(
            "min_fundamental_relative_energy must be finite and in [0, 1]"
        )
    if (
        not np.isfinite(octave_ambiguity_tolerance)
        or octave_ambiguity_tolerance < 0.0
        or octave_ambiguity_tolerance > 1.0
    ):
        raise ValueError("octave_ambiguity_tolerance must be finite and in [0, 1]")
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

    octave_ambiguity_detected = False

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
            octave_ambiguity_tolerance=octave_ambiguity_tolerance,
            min_fundamental_relative_energy=min_fundamental_relative_energy,
            subharmonic_guard=subharmonic_guard,
        )
        if not estimate.voiced or estimate.f0_hz is None:
            return _invalid(
                "fundamental could not be estimated reliably",
                max_harmonic_order=resolved_order,
                frequency_resolution_hz=frequency_resolution_hz,
            )
        resolved_f0 = float(estimate.f0_hz)
        octave_ambiguity_detected = estimate.octave_ambiguity_detected
    else:
        resolved_f0 = float(fundamental_hz)
        min_lag = max(1, int(np.floor(sample_rate_hz / fmax_hz)))
        max_lag = min(
            len(values) - 1,
            int(np.ceil(sample_rate_hz / fmin_hz)),
        )
        primary_lag = round(sample_rate_hz / resolved_f0)
        autocorrelation = normalized_autocorrelation(values)
        octave_ambiguity_detected = detect_octave_ambiguity(
            autocorrelation,
            primary_lag=primary_lag,
            min_lag=min_lag,
            max_lag=max_lag,
            octave_ambiguity_tolerance=octave_ambiguity_tolerance,
        )

    fre = fundamental_relative_energy(values, sample_rate_hz, resolved_f0)
    if fre < min_fundamental_relative_energy:
        return _invalid(
            "fundamental_bin_energy_below_reliability_threshold",
            max_harmonic_order=resolved_order,
            frequency_resolution_hz=frequency_resolution_hz,
            fundamental_relative_energy=fre,
            octave_ambiguity_detected=octave_ambiguity_detected,
        )

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
            fundamental_relative_energy=fre,
            octave_ambiguity_detected=octave_ambiguity_detected,
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

    resolved_components = tuple(components)
    return HarmonicAnalysis(
        valid=True,
        invalid_reason=None,
        fundamental_frequency_hz=resolved_f0,
        fundamental_amplitude=fundamental_amplitude,
        thd_percent=thd_percent,
        max_harmonic_order=resolved_order,
        frequency_resolution_hz=frequency_resolution_hz,
        components=resolved_components,
        fundamental_relative_energy=fre,
        octave_ambiguity_detected=octave_ambiguity_detected,
        series_kind=classify_series_kind(valid=True, components=resolved_components),
    )
