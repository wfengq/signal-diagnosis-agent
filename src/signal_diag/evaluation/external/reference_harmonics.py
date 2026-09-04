"""Evaluator-only harmonic and F0 analysis (EV-C032 independent of production DSP).

This module duplicates the V0.2 reference measurement algorithm using numpy only.
It MUST NOT import ``signal_diag.dsp.harmonics``, ``signal_diag.dsp.pitch``, or tool
adapters. Qualification gates use this path so product detector changes cannot
contaminate dataset labeling.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class _ReferenceHarmonicComponent:
    order: int
    target_frequency_hz: float
    measured_frequency_hz: float
    relative_amplitude: float


@dataclass(frozen=True, slots=True)
class ReferenceHarmonicResult:
    valid: bool
    f0_hz: float | None
    f0_confidence: float
    f0_voiced: bool
    thd_percent: float | None
    order_2_relative_amplitude: float | None
    fundamental_relative_energy: float | None
    series_kind: str | None = None



_SERIES_KIND_PRESENT_FLOOR = 0.01
_MULTI_PARTIAL_H2_MIN_RELATIVE_AMPLITUDE = 1.0


def _classify_series_kind(
    *,
    valid: bool,
    components: tuple[_ReferenceHarmonicComponent, ...],
) -> str | None:
    """Local duplicate of the production series_kind classifier (no dsp.harmonics import)."""
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
        return "even_order_present"
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
    return np.ascontiguousarray(samples, dtype=np.float64)


def _remove_dc(values: np.ndarray) -> np.ndarray:
    return values - float(np.mean(values))


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(values * values)))


def estimate_f0_reference(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    voicing_threshold: float = 0.3,
) -> tuple[float | None, float, bool]:
    """Autocorrelation F0 estimate (reference copy, independent of ``dsp.pitch``)."""
    values = _validated_1d(samples)
    working = _remove_dc(values)
    if _rms(working) <= np.finfo(np.float64).eps:
        return None, 0.0, False

    windowed = working * np.hanning(len(working))
    min_lag = max(1, int(np.floor(sample_rate_hz / fmax_hz)))
    max_lag = min(len(windowed) - 1, int(np.ceil(sample_rate_hz / fmin_hz)))
    if min_lag > max_lag:
        return None, 0.0, False

    n_fft = 1 << (2 * len(windowed) - 1).bit_length()
    power = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
    autocorrelation = np.fft.irfft(power, n=n_fft)[: len(windowed)]
    acf_zero = float(autocorrelation[0])
    if acf_zero <= 0.0 or not np.isfinite(acf_zero):
        return None, 0.0, False
    autocorrelation = autocorrelation / acf_zero

    search = autocorrelation[min_lag : max_lag + 1]
    candidate_lag = min_lag + int(np.argmax(search))
    confidence = max(0.0, float(autocorrelation[candidate_lag]))
    if confidence < voicing_threshold:
        return None, confidence, False

    return float(sample_rate_hz / candidate_lag), confidence, True


def fundamental_relative_energy_reference(
    samples: np.ndarray,
    sample_rate_hz: int,
    estimated_f0_hz: float,
) -> float:
    """EV-C026 definition for reference qualification measurements."""
    working = _remove_dc(_validated_1d(samples))
    window = np.hanning(len(working))
    spectrum = np.fft.rfft(working * window)
    linear = np.abs(spectrum)
    freqs = np.fft.rfftfreq(len(working), d=1.0 / sample_rate_hz)
    k_f0 = int(np.argmin(np.abs(freqs - estimated_f0_hz)))
    numerator = float(linear[k_f0] ** 2)
    denominator = float(np.sum(linear[1:] ** 2))
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


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


def analyze_harmonic_reference(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fundamental_hz: float | None = None,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    max_harmonic_order: int = 5,
) -> ReferenceHarmonicResult:
    """Measure THD and order-2 amplitude for external study qualification."""
    values = _validated_1d(samples)
    working = _remove_dc(values)
    if _rms(working) <= np.finfo(np.float64).eps:
        return ReferenceHarmonicResult(
            valid=False,
            f0_hz=None,
            f0_confidence=0.0,
            f0_voiced=False,
            thd_percent=None,
            order_2_relative_amplitude=None,
            fundamental_relative_energy=None,
            series_kind="not_applicable",
        )

    if fundamental_hz is None:
        f0_hz, confidence, voiced = estimate_f0_reference(
            values,
            sample_rate_hz,
            fmin_hz=fmin_hz,
            fmax_hz=fmax_hz,
        )
        if not voiced or f0_hz is None:
            return ReferenceHarmonicResult(
                valid=False,
                f0_hz=None,
                f0_confidence=confidence,
                f0_voiced=False,
                thd_percent=None,
                order_2_relative_amplitude=None,
                fundamental_relative_energy=None,
                series_kind="not_applicable",
            )
        resolved_f0 = f0_hz
    else:
        f0_hz, confidence, voiced = estimate_f0_reference(
            values,
            sample_rate_hz,
            fmin_hz=fmin_hz,
            fmax_hz=fmax_hz,
        )
        resolved_f0 = float(fundamental_hz)

    nyquist_hz = sample_rate_hz / 2.0
    if resolved_f0 > nyquist_hz:
        return ReferenceHarmonicResult(
            valid=False,
            f0_hz=f0_hz,
            f0_confidence=confidence,
            f0_voiced=voiced,
            thd_percent=None,
            order_2_relative_amplitude=None,
            fundamental_relative_energy=None,
            series_kind="not_applicable",
        )

    window_values = np.hanning(len(working))
    window_sum = float(np.sum(window_values))
    spectrum = np.fft.rfft(working * window_values)
    linear = np.abs(spectrum)
    frequencies = np.fft.rfftfreq(len(working), d=1.0 / sample_rate_hz)

    fundamental_amplitude, _ = _nearest_peak_amplitude(
        linear,
        frequencies,
        resolved_f0,
        window_sum,
    )
    fre = fundamental_relative_energy_reference(values, sample_rate_hz, resolved_f0)
    if fundamental_amplitude <= np.finfo(np.float64).eps:
        return ReferenceHarmonicResult(
            valid=False,
            f0_hz=f0_hz,
            f0_confidence=confidence,
            f0_voiced=voiced,
            thd_percent=None,
            order_2_relative_amplitude=None,
            fundamental_relative_energy=fre,
            series_kind="not_applicable",
        )

    components: list[_ReferenceHarmonicComponent] = []
    harmonic_amplitudes: list[float] = []
    for order in range(2, max_harmonic_order + 1):
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
        components.append(
            _ReferenceHarmonicComponent(
                order=order,
                target_frequency_hz=target_hz,
                measured_frequency_hz=measured_hz,
                relative_amplitude=relative_amplitude,
            )
        )

    thd_percent = (
        100.0
        * float(np.sqrt(np.sum(np.square(harmonic_amplitudes))))
        / fundamental_amplitude
    )
    order_2 = next(
        (component.relative_amplitude for component in components if component.order == 2),
        None,
    )
    resolved_components = tuple(components)
    return ReferenceHarmonicResult(
        valid=True,
        f0_hz=f0_hz if fundamental_hz is None else resolved_f0,
        f0_confidence=confidence,
        f0_voiced=voiced,
        thd_percent=thd_percent,
        order_2_relative_amplitude=order_2,
        fundamental_relative_energy=fre,
        series_kind=_classify_series_kind(valid=True, components=resolved_components),
    )
