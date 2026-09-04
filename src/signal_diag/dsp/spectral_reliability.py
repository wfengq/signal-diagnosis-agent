"""Shared spectral reliability helpers for F0 and harmonic analysis (V0.3)."""

from __future__ import annotations

import numpy as np

from .preprocess import _validated_1d, remove_dc

# Theoretical equal-noise per-bin floor: 2/N for Hann-windowed N-sample frame.
_THEORETICAL_EQUAL_NOISE_FLOOR = 2.0

# Engineering default for Workstream B validity gate (EV-C026).
#
# Formula: FRE = |X[k_f0]|^2 / sum_{k=1}^{N/2} |X[k]|^2  (Hann-windowed RFFT)
#
# Theoretical equal-noise floor ≈ 2/N. Pure sines under this window cluster ≈ 0.63–0.67
# (not 1.0). Unreliable F0 locks produce FRE ≪ 10^-4.
#
# Default 0.15: highest Round-1 synthesized scan with zero missed-unreliable, confirmed
# on real dev WAV; NOT derived from V0.2 failure F0 values. Full derivation:
# docs/evaluations/v0_3/prerequisites/fre_theoretical_derivation.md
DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY = 0.15

# Upper-octave partner peak ratio at which subharmonic ACF lock is flagged.
# Validated on synthesized table in octave_ambiguity_validation.json.
DEFAULT_OCTAVE_AMBIGUITY_TOLERANCE = 0.95


def fundamental_relative_energy(
    samples: np.ndarray,
    sample_rate_hz: int,
    estimated_f0_hz: float,
) -> float:
    """EV-C026: fraction of positive-frequency spectral energy at estimated F0."""
    working = remove_dc(_validated_1d(samples).astype(np.float64))
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


def normalized_autocorrelation(samples: np.ndarray) -> np.ndarray:
    """Return lag-normalized autocorrelation for a mono signal."""
    working = remove_dc(_validated_1d(samples).astype(np.float64))
    windowed = working * np.hanning(len(working))
    n_fft = 1 << (2 * len(windowed) - 1).bit_length()
    power = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
    autocorrelation = np.fft.irfft(power, n=n_fft)[: len(windowed)]
    acf_zero = float(autocorrelation[0])
    if acf_zero <= 0.0 or not np.isfinite(acf_zero):
        return autocorrelation
    return autocorrelation / acf_zero


def detect_octave_ambiguity(
    autocorrelation: np.ndarray,
    *,
    primary_lag: int,
    min_lag: int,
    max_lag: int,
    octave_ambiguity_tolerance: float = 0.95,
    octave_ratio_tolerance: float = 0.08,
    partner_search_radius: int = 3,
) -> bool:
    """Detect subharmonic/octave ACF ambiguity via upper-octave partner peaks.

    Flags when the selected (lower-frequency) lag has a same-height local maximum
    at approximately half the lag (2× frequency partner). Pure sines at the true
    fundamental do not flag because the 2×-frequency ACF partner is a negative
    trough, not a competing peak.
    """
    if (
        not np.isfinite(octave_ambiguity_tolerance)
        or octave_ambiguity_tolerance < 0.0
        or octave_ambiguity_tolerance > 1.0
    ):
        raise ValueError("octave_ambiguity_tolerance must be finite and in [0, 1]")
    if primary_lag < min_lag or primary_lag > max_lag:
        return False

    primary_peak = float(autocorrelation[primary_lag])
    if primary_peak <= 0.0:
        return False

    partner_lag = primary_lag // 2
    if partner_lag < min_lag or partner_lag > max_lag:
        return False

    measured_ratio = primary_lag / partner_lag if partner_lag > 0 else float("inf")
    if abs(measured_ratio - 2.0) > octave_ratio_tolerance:
        return False

    start = max(min_lag, partner_lag - partner_search_radius)
    stop = min(max_lag, partner_lag + partner_search_radius)
    partner_peak = max(float(autocorrelation[lag]) for lag in range(start, stop + 1))
    if partner_peak <= 0.0:
        return False
    return partner_peak / primary_peak >= octave_ambiguity_tolerance


def classify_f0_reliability(
    fundamental_relative_energy_value: float,
    *,
    min_fundamental_relative_energy: float,
) -> str:
    if fundamental_relative_energy_value >= min_fundamental_relative_energy:
        return "reliable"
    return "unreliable"
