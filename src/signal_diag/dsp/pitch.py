"""Deterministic autocorrelation fundamental-frequency estimation."""

import numpy as np

from .models import F0Estimate
from .preprocess import _validated_1d, remove_dc, rms
from .spectral_reliability import (
    DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY,
    DEFAULT_OCTAVE_AMBIGUITY_TOLERANCE,
    classify_f0_reliability,
    detect_octave_ambiguity,
    fundamental_relative_energy,
    normalized_autocorrelation,
)


def _unvoiced(confidence: float = 0.0) -> F0Estimate:
    return F0Estimate(
        f0_hz=None,
        confidence=confidence,
        voiced=False,
        method="autocorrelation",
        f0_reliability=None,
        octave_ambiguity_detected=False,
    )


def estimate_f0_autocorrelation(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    voicing_threshold: float = 0.3,
    octave_ambiguity_tolerance: float = DEFAULT_OCTAVE_AMBIGUITY_TOLERANCE,
    min_fundamental_relative_energy: float = DEFAULT_MIN_FUNDAMENTAL_RELATIVE_ENERGY,
) -> F0Estimate:
    """Estimate fundamental frequency using normalized autocorrelation."""
    values = _validated_1d(samples)
    if (
        not isinstance(sample_rate_hz, (int, np.integer))
        or isinstance(sample_rate_hz, (bool, np.bool_))
        or sample_rate_hz <= 0
    ):
        raise ValueError("sample_rate_hz must be a positive integer")
    if not np.isfinite(fmin_hz) or fmin_hz <= 0.0:
        raise ValueError("fmin_hz must be finite and positive")
    if not np.isfinite(fmax_hz) or fmax_hz <= 0.0:
        raise ValueError("fmax_hz must be finite and positive")
    if fmax_hz <= fmin_hz:
        raise ValueError("fmax_hz must be greater than fmin_hz")
    if (
        not np.isfinite(voicing_threshold)
        or voicing_threshold < 0.0
        or voicing_threshold > 1.0
    ):
        raise ValueError("voicing_threshold must be finite and between 0 and 1")
    if (
        not np.isfinite(octave_ambiguity_tolerance)
        or octave_ambiguity_tolerance < 0.0
        or octave_ambiguity_tolerance > 1.0
    ):
        raise ValueError("octave_ambiguity_tolerance must be finite and in [0, 1]")
    if (
        not np.isfinite(min_fundamental_relative_energy)
        or min_fundamental_relative_energy < 0.0
        or min_fundamental_relative_energy > 1.0
    ):
        raise ValueError(
            "min_fundamental_relative_energy must be finite and in [0, 1]"
        )

    working = remove_dc(values)
    if rms(working) <= np.finfo(np.float64).eps:
        return _unvoiced()

    windowed = working * np.hanning(len(working))
    min_lag = max(1, int(np.floor(sample_rate_hz / fmax_hz)))
    max_lag = min(
        len(windowed) - 1,
        int(np.ceil(sample_rate_hz / fmin_hz)),
    )
    if min_lag > max_lag:
        return _unvoiced()

    autocorrelation = normalized_autocorrelation(values)

    search = autocorrelation[min_lag : max_lag + 1]
    candidate_lag = min_lag + int(np.argmax(search))
    confidence = max(0.0, float(autocorrelation[candidate_lag]))
    if confidence < voicing_threshold:
        return _unvoiced(confidence)

    f0_hz = float(sample_rate_hz / candidate_lag)
    octave_ambiguity = detect_octave_ambiguity(
        autocorrelation,
        primary_lag=candidate_lag,
        min_lag=min_lag,
        max_lag=max_lag,
        octave_ambiguity_tolerance=octave_ambiguity_tolerance,
    )
    fre = fundamental_relative_energy(values, sample_rate_hz, f0_hz)
    reliability = classify_f0_reliability(
        fre,
        min_fundamental_relative_energy=min_fundamental_relative_energy,
    )

    return F0Estimate(
        f0_hz=f0_hz,
        confidence=confidence,
        voiced=True,
        method="autocorrelation",
        f0_reliability=reliability,
        octave_ambiguity_detected=octave_ambiguity,
    )
