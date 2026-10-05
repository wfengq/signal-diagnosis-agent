"""T-CX372: waveform synthesis for layer-1 characterization materials."""

from __future__ import annotations

import numpy as np

from signal_diag.evaluation.full_scale_characterization.synthesis import (
    clipped,
    harmonic_sine,
    sine,
)


def test_t_cx372_sine_amplitude_and_phase() -> None:
    sr = 48_000
    f0 = 100.0
    duration_s = 0.01
    out = sine(f0=f0, sr=sr, duration_s=duration_s, amplitude=0.5, phase_rad=0.0)
    n = int(round(duration_s * sr))
    t = np.arange(n, dtype=np.float64) / sr
    expected = 0.5 * np.sin(2.0 * np.pi * f0 * t)
    np.testing.assert_allclose(out, expected, rtol=0.0, atol=1e-12)
    assert out.dtype == np.float64


def test_t_cx372_clipped_pre_clip_peak_and_output_bound() -> None:
    sr = 48_000
    f0 = 440.0
    duration_s = 0.05
    level = 0.995
    depth = 0.99
    phase_rad = 1.0
    out = clipped(
        f0=f0,
        sr=sr,
        duration_s=duration_s,
        level=level,
        depth=depth,
        phase_rad=phase_rad,
    )
    n = int(round(duration_s * sr))
    t = np.arange(n, dtype=np.float64) / sr
    w = np.sin(2.0 * np.pi * f0 * t + phase_rad)
    peak = float(np.max(np.abs(w)))
    scaled = w * (level / depth) / peak
    np.testing.assert_allclose(float(np.max(np.abs(scaled))), level / depth, rtol=0.0, atol=1e-12)
    assert np.max(np.abs(out)) <= level + 1e-15
    assert np.min(out) >= -level - 1e-15


def test_t_cx372_clipped_m5_harmonics_before_scale_and_clip() -> None:
    sr = 48_000
    f0 = 200.0
    duration_s = 0.02
    level = 0.9
    depth = 0.95
    harmonics = {2: 0.1, 3: 0.1}
    out = clipped(
        f0=f0,
        sr=sr,
        duration_s=duration_s,
        level=level,
        depth=depth,
        phase_rad=0.0,
        harmonics=harmonics,
    )
    n = int(round(duration_s * sr))
    t = np.arange(n, dtype=np.float64) / sr
    w = np.sin(2.0 * np.pi * f0 * t)
    for k, r in harmonics.items():
        w = w + r * np.sin(2.0 * np.pi * k * f0 * t)
    peak = float(np.max(np.abs(w)))
    scaled = w * (level / depth) / peak
    clipped_expected = np.clip(scaled, -level, level)
    np.testing.assert_allclose(out, clipped_expected, rtol=0.0, atol=1e-12)


def test_t_cx372_clipped_level_one_stays_within_full_scale() -> None:
    sr = 48_000
    for depth in (0.999, 0.99, 0.9, 0.7, 0.5):
        out = clipped(
            f0=100.0,
            sr=sr,
            duration_s=0.001,
            level=1.0,
            depth=depth,
            phase_rad=0.0,
        )
        assert np.max(np.abs(out)) <= 1.0 + 1e-15
        assert np.min(out) >= -1.0 - 1e-15


def test_t_cx372_harmonic_sine_m6_no_extra_scaling() -> None:
    sr = 48_000
    f0 = 880.0
    fundamental = 0.5
    harmonics = {3: 0.3, 5: 0.2}
    duration_s = 0.01
    out = harmonic_sine(
        f0=f0,
        sr=sr,
        duration_s=duration_s,
        fundamental=fundamental,
        harmonics=harmonics,
        phase_rad=0.25,
    )
    n = int(round(duration_s * sr))
    t = np.arange(n, dtype=np.float64) / sr
    phase_rad = 0.25
    w = fundamental * np.sin(2.0 * np.pi * f0 * t + phase_rad)
    for k, r in harmonics.items():
        w = w + fundamental * r * np.sin(2.0 * np.pi * k * f0 * t + k * phase_rad)
    np.testing.assert_allclose(out, w, rtol=0.0, atol=1e-12)
