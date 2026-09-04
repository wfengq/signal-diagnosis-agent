"""Shared helpers for V0.3 Phase 1 TDD tests (not production code)."""

from __future__ import annotations

import math

import numpy as np

from signal_diag.dsp.preprocess import remove_dc
from signal_diag.signal import extract_segment, generate_sine


def fundamental_relative_energy_reference(
    samples: np.ndarray,
    sample_rate_hz: int,
    estimated_f0_hz: float,
) -> float:
    """EV-C026 reference implementation for tests and Phase 1 verification."""
    working = remove_dc(samples.astype(np.float64))
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


def make_pure_sine(
    frequency_hz: float,
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 1.0,
    amplitude: float = 0.5,
) -> np.ndarray:
    case = generate_sine(
        frequency_hz=frequency_hz,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        amplitude=amplitude,
    )
    return extract_segment(case.record)


def make_subharmonic_lock_sine(
    double_f0_hz: float,
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 1.0,
    amplitude: float = 0.5,
) -> np.ndarray:
    """Pure tone at F1; autocorrelation may lock F0≈F1/2 (Phase 1 verified at 700 Hz)."""
    return make_pure_sine(
        double_f0_hz,
        sample_rate_hz=sample_rate_hz,
        duration_s=duration_s,
        amplitude=amplitude,
    )


def make_high_thd_but_valid_sine(
    fundamental_hz: float = 200.0,
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 1.0,
) -> np.ndarray:
    """Fundamental + strong 2nd harmonic (h2 > h1) → THD > 100%, valid diagnostic regime."""
    t = np.arange(int(sample_rate_hz * duration_s), dtype=np.float64) / sample_rate_hz
    phase = 2.0 * math.pi * fundamental_hz * t
    signal = 0.5 * np.sin(phase) + 0.85 * np.sin(2.0 * phase)
    return signal.astype(np.float32)


def make_square_wave(
    frequency_hz: float,
    *,
    sample_rate_hz: int = 48_000,
    duration_s: float = 1.0,
    amplitude: float = 0.5,
) -> np.ndarray:
    t = np.arange(int(sample_rate_hz * duration_s), dtype=np.float64) / sample_rate_hz
    phase = 2.0 * math.pi * frequency_hz * t
    square = amplitude * np.sign(np.sin(phase))
    return square.astype(np.float32)


def inject_second_harmonic_ampnorm_reference(
    samples: np.ndarray,
    *,
    alpha: float = 0.50,
    post_gain: float = 0.8,
) -> np.ndarray:
    """Reference copy of transform 1.1.0 for test fixtures only."""
    working = samples.astype(np.float64)
    peak = float(np.max(np.abs(working)))
    normalized = working / peak
    normalized_squared = normalized**2
    transformed = (
        working + alpha * peak * (normalized_squared - float(np.mean(normalized_squared)))
    ) * post_gain
    return transformed.astype(np.float32)
