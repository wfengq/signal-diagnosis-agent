"""Synthesis helpers and effective-parameter utilities for manifest generation."""

from __future__ import annotations

import math

import numpy as np

from signal_diag.evaluation.full_scale_characterization.constants import M9ChannelLayout
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    SideGenerationSpec,
)
from signal_diag.evaluation.full_scale_characterization.synthesis import (
    clipped,
    harmonic_sine,
    sine,
)


def normalize_phase(phase_rad: float) -> float:
    tau = 2.0 * math.pi
    value = float(phase_rad) % tau
    if value < 0.0:
        value += tau
    return value


def compute_m7_marked(
    params: EffectiveMaterialParams,
    *,
    duration_s: float,
    threshold: float,
) -> bool:
    """M7 marker (B.2): some peak of the generated material has 1-3 samples at or over threshold.

    Counted per peak as maximal runs of consecutive samples with ``|x| >= threshold``
    on the material synthesised from its generation parameters (M2, M3, M5; other
    families are never marked).
    """
    if params.family not in {"M2", "M3", "M5"}:
        return False
    wave = synthesize_mono(params, duration_s=duration_s)
    over = np.abs(wave) >= threshold
    if not over.any():
        return False
    edges = np.diff(np.concatenate(([0], over.astype(np.int8), [0])))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    lengths = stops - starts
    return bool(np.any((lengths >= 1) & (lengths <= 3)))


def _synthesize_mono_core(
    params: EffectiveMaterialParams,
    *,
    duration_s: float,
    gain_factor: float,
    noise_rms: float | None,
    noise_seed: int | None,
) -> np.ndarray:
    phase = params.phase_rad
    sr = params.sample_rate_hz
    f0 = params.f0_hz
    family = params.family
    if family in {"M1", "M2", "M11"}:
        amp = params.amplitude if family == "M1" else params.peak
        assert amp is not None
        wave = sine(f0=f0, sr=sr, duration_s=duration_s, amplitude=amp, phase_rad=phase)
    elif family == "M6":
        wave = harmonic_sine(
            f0=f0,
            sr=sr,
            duration_s=duration_s,
            fundamental=0.5,
            harmonics=dict(params.harmonics),
            phase_rad=phase,
        )
    elif family in {"M3", "M4", "M5"}:
        assert params.level is not None and params.depth is not None
        harmonics = dict(params.harmonics) if params.harmonics else None
        wave = clipped(
            f0=f0,
            sr=sr,
            duration_s=duration_s,
            level=params.level,
            depth=params.depth,
            phase_rad=phase,
            harmonics=harmonics,
        )
    else:
        msg = f"unsupported mono family for synthesis: {family}"
        raise ValueError(msg)

    if gain_factor != 1.0:
        wave = np.clip(wave * gain_factor, -1.0, 1.0)
    if noise_rms is not None:
        if noise_seed is None:
            raise ValueError("noise_rms requires noise_seed")
        rng = np.random.default_rng(noise_seed)
        noise = rng.normal(0.0, noise_rms, size=wave.shape[0])
        wave = np.clip(wave + noise, -1.0, 1.0)
    return wave.astype(np.float64)


def synthesize_mono(
    params: EffectiveMaterialParams,
    *,
    duration_s: float,
    sample_offset: int = 0,
    gain_factor: float = 1.0,
    noise_rms: float | None = None,
    noise_seed: int | None = None,
) -> np.ndarray:
    if sample_offset > 0:
        total_s = duration_s + sample_offset / float(params.sample_rate_hz)
        extended = _synthesize_mono_core(
            params,
            duration_s=total_s,
            gain_factor=gain_factor,
            noise_rms=noise_rms,
            noise_seed=noise_seed,
        )
        base_len = round(duration_s * params.sample_rate_hz)
        return extended[sample_offset : sample_offset + base_len]
    return _synthesize_mono_core(
        params,
        duration_s=duration_s,
        gain_factor=gain_factor,
        noise_rms=noise_rms,
        noise_seed=noise_seed,
    )


def codes_for_analysis_range(
    wave: np.ndarray,
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> np.ndarray:
    n = round(range_length_s * sample_rate_hz)
    n = min(n, wave.shape[0])
    segment = wave[:n]
    q = np.rint(segment * 32768.0)
    return np.clip(q, -32768, 32767).astype(np.int64)


def effective_params_equal(a: EffectiveMaterialParams, b: EffectiveMaterialParams) -> bool:
    return (
        a.family == b.family
        and a.f0_hz == b.f0_hz
        and a.sample_rate_hz == b.sample_rate_hz
        and normalize_phase(a.phase_rad) == normalize_phase(b.phase_rad)
        and a.amplitude == b.amplitude
        and a.peak == b.peak
        and a.level == b.level
        and a.depth == b.depth
        and a.harmonics == b.harmonics
    )


def _layout_channel_params(
    layout: M9ChannelLayout,
    *,
    f0_hz: float,
    sample_rate_hz: int,
    phase_rad: float,
) -> tuple[EffectiveMaterialParams, EffectiveMaterialParams]:
    if layout.left_family == "M1":
        left = EffectiveMaterialParams(
            family="M1",
            f0_hz=f0_hz,
            sample_rate_hz=sample_rate_hz,
            phase_rad=phase_rad,
            amplitude=layout.left_amplitude,
        )
    elif layout.left_family == "M3":
        left = EffectiveMaterialParams(
            family="M3",
            f0_hz=f0_hz,
            sample_rate_hz=sample_rate_hz,
            phase_rad=phase_rad,
            level=layout.left_level,
            depth=layout.left_depth,
        )
    else:
        left = EffectiveMaterialParams(
            family="M4",
            f0_hz=f0_hz,
            sample_rate_hz=sample_rate_hz,
            phase_rad=phase_rad,
            level=layout.left_level,
            depth=layout.left_depth,
        )
    if layout.right_family == "M1":
        right = EffectiveMaterialParams(
            family="M1",
            f0_hz=f0_hz,
            sample_rate_hz=sample_rate_hz,
            phase_rad=phase_rad,
            amplitude=layout.right_amplitude,
        )
    elif layout.right_family == "M3":
        right = EffectiveMaterialParams(
            family="M3",
            f0_hz=f0_hz,
            sample_rate_hz=sample_rate_hz,
            phase_rad=phase_rad,
            level=layout.right_level,
            depth=layout.right_depth,
        )
    else:
        right = EffectiveMaterialParams(
            family="M4",
            f0_hz=f0_hz,
            sample_rate_hz=sample_rate_hz,
            phase_rad=phase_rad,
            level=layout.right_level,
            depth=layout.right_depth,
        )
    if layout.swap_channels:
        return right, left
    return left, right


def params_from_group_record(record) -> EffectiveMaterialParams:
    return EffectiveMaterialParams(
        family=record.family,
        f0_hz=record.f0_hz,
        sample_rate_hz=record.sample_rate_hz,
        phase_rad=record.start_phase_rad,
        amplitude=record.amplitude,
        peak=record.peak,
        level=record.level,
        depth=record.depth,
        harmonics=record.harmonics,
        m7_marked=record.m7_marked,
    )


def synthesize_side_waveform(
    spec: SideGenerationSpec,
    *,
    file_duration_s: float,
    m9_layout: M9ChannelLayout | None = None,
) -> tuple[np.ndarray, ...]:
    """Return one mono buffer or stereo (left, right) buffers for a pair side.

    Internal: called by the executor (behind the validation gate) and by the R0
    A.15 scan. Do not use it to generate validation materials directly.
    """
    eff = spec.effective
    if eff.family == "M9":
        if m9_layout is None:
            raise ValueError("M9 synthesis requires m9_layout")
        left_params, right_params = _layout_channel_params(
            m9_layout,
            f0_hz=eff.f0_hz,
            sample_rate_hz=eff.sample_rate_hz,
            phase_rad=eff.phase_rad,
        )
        return (
            synthesize_mono(
                left_params,
                duration_s=file_duration_s,
                sample_offset=spec.sample_offset,
                gain_factor=spec.gain_factor,
                noise_rms=spec.noise_rms,
                noise_seed=spec.noise_seed,
            ),
            synthesize_mono(
                right_params,
                duration_s=file_duration_s,
                sample_offset=spec.sample_offset,
                gain_factor=spec.gain_factor,
                noise_rms=spec.noise_rms,
                noise_seed=spec.noise_seed,
            ),
        )
    return (
        synthesize_mono(
            eff,
            duration_s=file_duration_s,
            sample_offset=spec.sample_offset,
            gain_factor=spec.gain_factor,
            noise_rms=spec.noise_rms,
            noise_seed=spec.noise_seed,
        ),
    )


def channel_effectives_from_group(record) -> list[EffectiveMaterialParams]:
    if record.family == "M9" and record.m9_layout is not None:
        layout = M9ChannelLayout.model_validate(record.m9_layout)
        left, right = _layout_channel_params(
            layout,
            f0_hz=record.f0_hz,
            sample_rate_hz=record.sample_rate_hz,
            phase_rad=record.start_phase_rad,
        )
        return [left, right]
    return [params_from_group_record(record)]
