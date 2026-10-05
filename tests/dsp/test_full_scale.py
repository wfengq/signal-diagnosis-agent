"""T-CX349: full-scale sample counting."""

import numpy as np
import pytest

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.dsp.full_scale import FullScaleCount, count_full_scale_samples
from signal_diag.signal import generate_sine


def test_t_cx349_counts_runs_and_isolated_samples() -> None:
    x = np.array(
        [0.0, 0.995, 0.5, 0.99, 0.991, 0.2, -1.0, -0.99, -0.995, 0.1],
        dtype=np.float32,
    )
    got = count_full_scale_samples(x, full_scale_threshold=0.99)
    assert got == FullScaleCount(
        counted_samples=5,
        over_threshold_uncounted=1,
        peak_abs=1.0,
        analyzed_samples=10,
    )


@pytest.mark.parametrize(
    "freq,amp",
    [
        (100.0, 0.9905),
        (997.0, 0.991),
        (997.0, 0.9925),
        (2000.0, 1.0),
        (100.0, 0.5),
        (440.0, 0.9),
    ],
)
def test_t_cx349_matches_existing_full_scale_mechanism(freq: float, amp: float) -> None:
    x = generate_sine(
        frequency_hz=freq, sample_rate_hz=48_000, duration_s=2.0, amplitude=amp
    ).record.samples[:, 0]
    got = count_full_scale_samples(x, full_scale_threshold=0.99)
    ref = analyze_clipping(x, full_scale_threshold=0.99)
    assert (got.counted_samples > 0) == ref.full_scale_detected
    assert got.peak_abs == ref.peak_abs
    assert got.counted_samples + got.over_threshold_uncounted == int(
        np.count_nonzero(np.abs(x) >= 0.99)
    )


def test_t_cx349_isolated_peaks_are_uncounted() -> None:
    x = generate_sine(
        frequency_hz=2000.0, sample_rate_hz=48_000, duration_s=2.0, amplitude=1.0
    ).record.samples[:, 0]
    got = count_full_scale_samples(x, full_scale_threshold=0.99)
    assert got.counted_samples == 0 and got.over_threshold_uncounted == 8000


def test_t_cx349_rejects_bad_parameters() -> None:
    x = np.zeros(8, dtype=np.float32)
    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            count_full_scale_samples(x, full_scale_threshold=bad)
    for bad in (1, True, 2.0):
        with pytest.raises(ValueError):
            count_full_scale_samples(x, full_scale_threshold=0.99, min_consecutive_samples=bad)
