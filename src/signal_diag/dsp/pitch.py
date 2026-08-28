"""Deterministic autocorrelation fundamental-frequency estimation."""

import numpy as np

from .models import F0Estimate
from .preprocess import _validated_1d, remove_dc, rms


def _unvoiced(confidence: float = 0.0) -> F0Estimate:
    return F0Estimate(
        f0_hz=None,
        confidence=confidence,
        voiced=False,
        method="autocorrelation",
    )


def estimate_f0_autocorrelation(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    fmin_hz: float = 50.0,
    fmax_hz: float = 1000.0,
    voicing_threshold: float = 0.3,
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

    n_fft = 1 << (2 * len(windowed) - 1).bit_length()
    power = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
    autocorrelation = np.fft.irfft(power, n=n_fft)[: len(windowed)]
    autocorrelation = autocorrelation / autocorrelation[0]

    search = autocorrelation[min_lag : max_lag + 1]
    candidate_lag = min_lag + int(np.argmax(search))
    confidence = max(0.0, float(autocorrelation[candidate_lag]))
    if confidence < voicing_threshold:
        return _unvoiced(confidence)

    return F0Estimate(
        f0_hz=float(sample_rate_hz / candidate_lag),
        confidence=confidence,
        voiced=True,
        method="autocorrelation",
    )
