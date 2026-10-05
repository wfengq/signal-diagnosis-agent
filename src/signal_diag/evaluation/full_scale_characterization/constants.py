"""Frozen B-section grids for layer-1 characterization (single source of truth)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict


class HarmonicSet(BaseModel):
    """Relative harmonic amplitudes keyed by order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    coefficients: tuple[tuple[int, float], ...] = ()

    def __init__(self, mapping: dict[int, float] | None = None, **data: Any) -> None:
        if mapping is not None:
            coeffs = tuple(sorted((int(k), float(v)) for k, v in mapping.items()))
            super().__init__(coefficients=coeffs, **data)
        else:
            super().__init__(**data)

    def as_dict(self) -> dict[int, float]:
        return dict(self.coefficients)


def _odd_harmonics_through(order: int) -> HarmonicSet:
    coeffs: dict[int, float] = {}
    for n in range(3, order + 1, 2):
        coeffs[n] = 1.0 / float(n)
    return HarmonicSet(coeffs)


class M9ChannelLayout(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    left_family: str
    right_family: str
    left_amplitude: float | None = None
    left_level: float | None = None
    left_depth: float | None = None
    right_amplitude: float | None = None
    right_level: float | None = None
    right_depth: float | None = None
    swap_channels: bool = False


class CharacterizationConstants(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    round_id: str
    full_scale_threshold: float = 0.99
    file_duration_s: float = 2.0
    sample_rates: tuple[int, ...]
    calibration_f0: tuple[float, ...]
    validation_f0_heldout: tuple[float, ...]
    calibration_range_lengths_s: tuple[float, ...]
    validation_range_lengths_s: tuple[float, ...]
    calibration_start_phases_rad: tuple[float, ...]
    validation_start_phases_heldout_rad: tuple[float, ...]
    validation_fixed_start_phases_rad: tuple[float, ...]
    calibration_seeds: tuple[int, ...]
    validation_seeds: tuple[int, ...]
    m1_calibration_amplitudes: tuple[float, ...]
    m1_validation_amplitudes_heldout: tuple[float, ...]
    m2_calibration_peaks: tuple[float, ...]
    m2_validation_peaks_heldout: tuple[float, ...]
    m3_calibration_levels: tuple[float, ...]
    m3_calibration_depths: tuple[float, ...]
    m3_validation_levels_heldout: tuple[float, ...]
    m3_validation_depths_heldout: tuple[float, ...]
    m4_calibration_levels: tuple[float, ...]
    m4_calibration_depths: tuple[float, ...]
    m4_validation_levels_heldout: tuple[float, ...]
    m4_validation_depths_heldout: tuple[float, ...]
    m5_calibration_harmonics: tuple[HarmonicSet, ...]
    m5_calibration_levels: tuple[float, ...]
    m5_calibration_depths: tuple[float, ...]
    m5_validation_harmonics_heldout: tuple[HarmonicSet, ...]
    m5_validation_depths_heldout: tuple[float, ...]
    m6_calibration_harmonics: tuple[HarmonicSet, ...]
    m6_validation_harmonics: tuple[HarmonicSet, ...]
    validation_fixed_f0: tuple[float, ...]
    validation_fixed_m2_peaks: tuple[float, ...]
    validation_fixed_m3_levels: tuple[float, ...]
    validation_fixed_m3_depths: tuple[float, ...]
    validation_fixed_m4_levels: tuple[float, ...]
    validation_fixed_m4_depths: tuple[float, ...]
    validation_fixed_m5_harmonics: tuple[HarmonicSet, ...]
    validation_fixed_m5_levels: tuple[float, ...]
    validation_fixed_m5_depths: tuple[float, ...]
    m9_calibration_layouts: tuple[M9ChannelLayout, ...]
    m9_validation_layouts: tuple[M9ChannelLayout, ...]
    m9_validation_f0_only: tuple[float, ...]
    p1_calibration_offsets: tuple[int, ...]
    p1_validation_offsets: tuple[int, ...]
    p3_calibration_deltas_rad: tuple[float, ...]
    p3_validation_deltas_rad: tuple[float, ...]
    p5_calibration_gains: tuple[float, ...]
    p5_validation_gains: tuple[float, ...]
    p5t_calibration_gains: tuple[float, ...]
    p5t_validation_gains: tuple[float, ...]
    p6_calibration_rms: tuple[float, ...]
    p6_validation_rms: tuple[float, ...]
    onset_calibration_depths: tuple[float, ...]
    onset_validation_specs: tuple[tuple[float, float], ...]
    aggravation_relative_peaks: tuple[float, ...]
    # Sub-full-scale blind pairs: for each level, depth old -> new at the same level (B.4).
    blind_sublevel_levels: tuple[float, ...]
    blind_sublevel_depths: tuple[float, float]
    # Single-sample blind pair: (f0, new-side level, new-side pre-clip peak); the old side
    # is an unclipped sine of ``blind_single_sample_old_amplitude`` at the same f0.
    blind_single_sample: tuple[float, float, float]
    blind_single_sample_old_amplitude: float
    validation_max_pair_ratio_to_calibration: float = 2.0
    scale_limit_enabled: bool = True


def constants_digest(constants: CharacterizationConstants) -> str:
    payload = constants.model_dump(mode="json")
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_round_1_constants() -> CharacterizationConstants:
    m6_cal = HarmonicSet({3: 0.3})
    m6_cal_odd = _odd_harmonics_through(7)
    m6_val = _odd_harmonics_through(15)
    return CharacterizationConstants(
        round_id="round_1",
        sample_rates=(44_100, 48_000),
        calibration_f0=(100.0, 440.0, 880.0, 2000.0, 4000.0, 8000.0),
        validation_f0_heldout=(220.0, 3000.0, 50.0, 997.0, 12000.0),
        calibration_range_lengths_s=(2.0, 0.1, 0.01, 0.005),
        validation_range_lengths_s=(2.0, 0.005, 1.0, 0.02, 0.002),
        calibration_start_phases_rad=(0.0, 1.0, 2.0),
        validation_start_phases_heldout_rad=(0.5, 3.0),
        validation_fixed_start_phases_rad=(0.0, 2.0),
        calibration_seeds=(1001, 1002, 1003, 1004, 1005),
        validation_seeds=(2001, 2002, 2003, 2004, 2005),
        m1_calibration_amplitudes=(0.05, 0.5, 0.9),
        m1_validation_amplitudes_heldout=(0.2, 0.01),
        m2_calibration_peaks=(
            0.98,
            0.989,
            0.9899,
            0.99,
            0.9901,
            0.9905,
            0.991,
            0.992,
            0.993,
            0.994,
            0.995,
            0.9975,
            1.0,
        ),
        m2_validation_peaks_heldout=(0.9897, 0.9915, 0.9925, 0.996, 0.97),
        m3_calibration_levels=(0.9901, 0.995, 1.0),
        m3_calibration_depths=(0.999, 0.99, 0.9, 0.7),
        m3_validation_levels_heldout=(0.991, 0.99),
        m3_validation_depths_heldout=(0.95, 0.9999, 0.5),
        m4_calibration_levels=(0.5, 0.9),
        m4_calibration_depths=(0.999, 0.99, 0.9, 0.7),
        m4_validation_levels_heldout=(0.7, 0.98, 0.1),
        m4_validation_depths_heldout=(0.95, 0.9999, 0.5),
        m5_calibration_harmonics=(HarmonicSet({2: 0.1}), HarmonicSet({3: 0.1})),
        m5_calibration_levels=(0.995, 0.9),
        m5_calibration_depths=(0.99, 0.9),
        m5_validation_harmonics_heldout=(HarmonicSet({2: 0.3}),),
        m5_validation_depths_heldout=(0.95,),
        m6_calibration_harmonics=(m6_cal, m6_cal_odd),
        m6_validation_harmonics=(m6_val,),
        validation_fixed_f0=(100.0, 880.0, 4000.0),
        validation_fixed_m2_peaks=(0.9899, 0.99, 0.9905, 0.992, 0.995, 1.0),
        validation_fixed_m3_levels=(0.9901, 0.995, 1.0),
        validation_fixed_m3_depths=(0.99, 0.9),
        validation_fixed_m4_levels=(0.5, 0.9),
        validation_fixed_m4_depths=(0.99, 0.9),
        validation_fixed_m5_harmonics=(HarmonicSet({2: 0.1}), HarmonicSet({3: 0.1})),
        validation_fixed_m5_levels=(0.995, 0.9),
        validation_fixed_m5_depths=(0.9,),
        m9_calibration_layouts=(
            M9ChannelLayout(
                left_family="M1",
                left_amplitude=0.5,
                right_family="M3",
                right_level=0.995,
                right_depth=0.9,
            ),
            M9ChannelLayout(
                left_family="M3",
                left_level=0.995,
                left_depth=0.9,
                right_family="M1",
                right_amplitude=0.5,
            ),
        ),
        m9_validation_layouts=(
            M9ChannelLayout(
                left_family="M4",
                left_level=0.9,
                left_depth=0.9,
                right_family="M3",
                right_level=0.995,
                right_depth=0.9,
            ),
        ),
        m9_validation_f0_only=(220.0, 997.0, 3000.0),
        p1_calibration_offsets=(1, 3, 37),
        p1_validation_offsets=(2, 101),
        p3_calibration_deltas_rad=(0.1, 1.0, 2.0),
        p3_validation_deltas_rad=(0.5, 3.0),
        p5_calibration_gains=(-5e-3, -1e-3, -1e-4, 1e-4, 1e-3, 5e-3),
        p5_validation_gains=(-1e-2, -3e-4, 3e-4, 1e-2),
        p5t_calibration_gains=(1e-5, -1e-5),
        p5t_validation_gains=(3e-5, -3e-5),
        p6_calibration_rms=(1e-5, 1e-4, 1e-3),
        p6_validation_rms=(3e-5, 3e-4, 3e-3),
        onset_calibration_depths=(0.9995, 0.999, 0.99, 0.9),
        onset_validation_specs=(
            (0.995, 0.9999),
            (0.9901, 0.9995),
            (0.9901, 0.999),
            (0.9901, 0.99),
            (0.9901, 0.9),
        ),
        aggravation_relative_peaks=(1e-4, 1e-3, 1e-2, 5e-2, 1e-1),
        blind_sublevel_levels=(0.9, 0.98),
        blind_sublevel_depths=(0.99, 0.9),
        blind_single_sample=(997.0, 0.9905, 0.991),
        blind_single_sample_old_amplitude=0.9,
        validation_max_pair_ratio_to_calibration=2.0,
        scale_limit_enabled=True,
    )


ROUND_1 = make_round_1_constants()
