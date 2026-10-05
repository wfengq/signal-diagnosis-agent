"""Float64 waveform synthesis for layer-1 characterization materials (B.2)."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np


def _time_axis(sr: int, duration_s: float) -> np.ndarray:
    n = int(round(duration_s * sr))
    return np.arange(n, dtype=np.float64) / float(sr)


def sine(
    *,
    f0: float,
    sr: int,
    duration_s: float,
    amplitude: float,
    phase_rad: float,
) -> np.ndarray:
    """``amplitude * sin(2π f0 t + φ)`` on a uniform grid."""
    t = _time_axis(sr, duration_s)
    return (amplitude * np.sin(2.0 * np.pi * f0 * t + phase_rad)).astype(np.float64)


def harmonic_sine(
    *,
    f0: float,
    sr: int,
    duration_s: float,
    fundamental: float,
    harmonics: Mapping[int, float],
    phase_rad: float,
) -> np.ndarray:
    """Fundamental plus relative harmonics without extra peak normalization (M6)."""
    t = _time_axis(sr, duration_s)
    w = fundamental * np.sin(2.0 * np.pi * f0 * t + phase_rad)
    for order, relative in harmonics.items():
        w = w + fundamental * relative * np.sin(
            2.0 * np.pi * order * f0 * t + order * phase_rad
        )
    return w.astype(np.float64)


def clipped(
    *,
    f0: float,
    sr: int,
    duration_s: float,
    level: float,
    depth: float,
    phase_rad: float,
    harmonics: Mapping[int, float] | None = None,
) -> np.ndarray:
    """Scale pre-clip peak to ``level / depth``, then hard-clip to ``±level`` (M3/M5)."""
    t = _time_axis(sr, duration_s)
    w = np.sin(2.0 * np.pi * f0 * t + phase_rad)
    if harmonics:
        for order, relative in harmonics.items():
            w = w + relative * np.sin(2.0 * np.pi * order * f0 * t + order * phase_rad)
    peak = float(np.max(np.abs(w)))
    if peak > 0.0:
        w = w * (level / depth) / peak
    return np.clip(w, -level, level).astype(np.float64)
