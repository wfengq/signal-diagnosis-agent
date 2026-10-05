"""Pair enumeration templates for characterization manifests."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterator
from typing import Literal

from signal_diag.evaluation.full_scale_characterization.constants import (
    CharacterizationConstants,
)
from signal_diag.evaluation.full_scale_characterization.materials import (
    normalize_phase,
    params_from_group_record,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    EncodingSpec,
    PairRecord,
    SideGenerationSpec,
    SourceGroupRecord,
)

Side = Literal["calibration", "validation"]
BitDepth = Literal[8, 16, 24, 32]
StepBits = Literal[16, 24, 32]
RoundingMode = Literal[
    "round", "trunc", "away_one_step", "toward_one_step", "random_one_step"
]

_EMPTY_BIT_DEPTHS: tuple[Literal[16, 24, 32], ...] = (16, 24, 32)
# (coarser bit depth, finer bit depth); plan B.3 / C.1: the coarser side is old.
_P4_COMBOS: tuple[tuple[Literal[16, 24], Literal[24, 32]], ...] = (
    (24, 32),
    (16, 32),
    (16, 24),
)
_P9_COMBOS: tuple[tuple[Literal[16, 24], Literal[24, 32]], ...] = (
    (16, 32),
    (16, 24),
    (24, 32),
)
_P7_ONE_STEP: tuple[tuple[str, RoundingMode], ...] = (
    ("P7a", "away_one_step"),
    ("P7b", "toward_one_step"),
    ("P7c", "trunc"),
)
_P9_VARIANTS: tuple[tuple[str, RoundingMode], ...] = (
    ("P9a", "away_one_step"),
    ("P9b", "toward_one_step"),
    ("P9c", "trunc"),
)
_P8_COARSE: tuple[Literal[16, 32], ...] = (16, 32)
TOLERANCE_CODES = frozenset(
    {
        "P0",
        "P4",
        "P7a",
        "P7b",
        "P7c",
        "P7d",
        "P9a",
        "P9b",
        "P9c",
        "P5t",
    }
)
SENSITIVITY_CODES = frozenset({"P1", "P3", "P5", "P6", "P8"})
COMBO_CODES = frozenset({"COMBO_P1_P6", "COMBO_P4_P5", "COMBO_P6_DUAL"})


def _base_effective(group: SourceGroupRecord) -> EffectiveMaterialParams:
    return params_from_group_record(group)


def _side_spec(
    effective: EffectiveMaterialParams,
    *,
    encoding: EncodingSpec,
    sample_offset: int = 0,
    gain_factor: float = 1.0,
    noise_rms: float | None = None,
    noise_seed: int | None = None,
    phase_delta_rad: float = 0.0,
) -> SideGenerationSpec:
    eff = effective.model_copy(
        update={"phase_rad": normalize_phase(effective.phase_rad + phase_delta_rad)}
    )
    return SideGenerationSpec(
        encoding=encoding,
        effective=eff,
        sample_offset=sample_offset,
        gain_factor=gain_factor,
        noise_rms=noise_rms,
        noise_seed=noise_seed,
        phase_delta_rad=phase_delta_rad,
    )




def _emit_identity(
    pair_counter: list[dict],
    *,
    old_side: SideGenerationSpec,
    new_side: SideGenerationSpec,
    **fields: object,
) -> None:
    pair_counter.append(
        {
            **fields,
            "old_side": _side_to_json(old_side),
            "new_side": _side_to_json(new_side),
        }
    )


def _identity_dict_to_pair_record(d: dict) -> PairRecord:
    def _side_from_json(side: dict) -> SideGenerationSpec:
        enc = side["encoding"]
        eff = side["effective"]
        return SideGenerationSpec(
            encoding=EncodingSpec(
                bits=enc["bits"],
                rounding=enc.get("rounding", "round"),
                step_bits=enc.get("step_bits"),
                seed=enc.get("seed"),
                filename=enc.get("filename", "material.wav"),
            ),
            effective=EffectiveMaterialParams(**eff),
            sample_offset=side.get("sample_offset", 0),
            gain_factor=side.get("gain_factor", 1.0),
            noise_rms=side.get("noise_rms"),
            noise_seed=side.get("noise_seed"),
            phase_delta_rad=side.get("phase_delta_rad", 0.0),
        )

    return PairRecord(
        pair_id=d["pair_id"],
        side=d["side"],
        kind=d["kind"],
        family=d["family"],
        source_group_key=d["source_group_key"],
        perturbation_code=d["perturbation_code"],
        perturbation_detail=d["perturbation_detail"],
        range_length_s=d["range_length_s"],
        f0_hz=d["f0_hz"],
        sample_rate_hz=d["sample_rate_hz"],
        seed=d.get("seed"),
        old_side=_side_from_json(d["old_side"]),
        new_side=_side_from_json(d["new_side"]),
        is_combo=d.get("is_combo", False),
        is_blind=d.get("is_blind", False),
    )

def _pair_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:24]


def _range_lengths_for_side(c: CharacterizationConstants, side: Side) -> tuple[float, ...]:
    if side == "calibration":
        return c.calibration_range_lengths_s
    return c.validation_range_lengths_s


def _seeds_for_side(c: CharacterizationConstants, side: Side) -> tuple[int, ...]:
    return c.calibration_seeds if side == "calibration" else c.validation_seeds


def _append_empty_pairs(
    group: SourceGroupRecord,
    c: CharacterizationConstants,
    *,
    pair_counter: list[dict],
) -> None:
    side = group.side
    ranges = _range_lengths_for_side(c, side)
    seeds = _seeds_for_side(c, side)
    base = _base_effective(group)
    for range_len in ranges:
        for bits in _EMPTY_BIT_DEPTHS:
            enc = EncodingSpec(bits=bits)
            old = _side_spec(base, encoding=enc)
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(group.group_key, "P0", str(bits), str(range_len)),
                    side=side,
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="P0",
                    perturbation_detail=f"bits={bits}",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=old,
            )

        for coarse, fine in _P4_COMBOS:
            old = _side_spec(base, encoding=EncodingSpec(bits=coarse))
            new = _side_spec(base, encoding=EncodingSpec(bits=fine))
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(
                        group.group_key, "P4", f"coarse{coarse}-fine{fine}", str(range_len)
                    ),
                    side=side,
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="P4",
                    perturbation_detail=f"coarse{coarse}<-fine{fine}",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
            )

        for bits in _EMPTY_BIT_DEPTHS:
            round_enc = EncodingSpec(bits=bits, rounding="round")
            for code, rounding in _P7_ONE_STEP:
                old = _side_spec(base, encoding=round_enc)
                new = _side_spec(
                    base,
                    encoding=EncodingSpec(bits=bits, rounding=rounding, step_bits=bits),
                )
                _emit_identity(
                pair_counter,
                pair_id=_pair_id(group.group_key, code, str(bits), str(range_len)),
                side=side,
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code=code,
                perturbation_detail=f"bits={bits}",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                old_side=old,
                new_side=new,
                    )
            for seed in seeds:
                old = _side_spec(base, encoding=round_enc)
                new = _side_spec(
                    base,
                    encoding=EncodingSpec(
                        bits=bits, rounding="random_one_step", step_bits=bits, seed=seed
                    ),
                )
                _emit_identity(
                pair_counter,
                pair_id=_pair_id(group.group_key, "P7d", str(bits), str(seed), str(range_len)),
                side=side,
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code="P7d",
                perturbation_detail=f"bits={bits};seed={seed}",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                seed=seed,
                old_side=old,
                new_side=new,
                    )

        for code, rounding in _P9_VARIANTS:
            for coarse, fine in _P9_COMBOS:
                if code == "P9c":
                    # Coarser-depth truncation (old) vs finer-depth rounding (new).
                    old = _side_spec(base, encoding=EncodingSpec(bits=coarse, rounding="trunc"))
                    new = _side_spec(base, encoding=EncodingSpec(bits=fine, rounding="round"))
                else:
                    # Coarser-depth rounding (old) vs finer-depth rounding shifted by one
                    # coarser-depth step on the finer-depth file (new).
                    old = _side_spec(base, encoding=EncodingSpec(bits=coarse, rounding="round"))
                    new = _side_spec(
                        base,
                        encoding=EncodingSpec(
                            bits=fine,
                            rounding=rounding,
                            step_bits=coarse,
                        ),
                    )
                _emit_identity(
                pair_counter,
                pair_id=_pair_id(
                    group.group_key, code, f"coarse{coarse}-fine{fine}", str(range_len)
                ),
                side=side,
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code=code,
                perturbation_detail=f"coarse{coarse}<-fine{fine}",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                old_side=old,
                new_side=new,
                    )

        gains = (
            c.p5t_calibration_gains if side == "calibration" else c.p5t_validation_gains
        )
        for gain in gains:
            enc = EncodingSpec(bits=16, rounding="round")
            old = _side_spec(base, encoding=enc)
            new = _side_spec(base, encoding=enc, gain_factor=1.0 + gain)
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(group.group_key, "P5t", str(gain), str(range_len)),
                    side=side,
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="P5t",
                    perturbation_detail=f"gain={gain}",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
            )


def _append_sensitivity_pairs(
    group: SourceGroupRecord,
    c: CharacterizationConstants,
    *,
    pair_counter: list[dict],
) -> None:
    side = group.side
    ranges = _range_lengths_for_side(c, side)
    seeds = _seeds_for_side(c, side)
    base = _base_effective(group)
    enc16 = EncodingSpec(bits=16, rounding="round")

    offsets = c.p1_calibration_offsets if side == "calibration" else c.p1_validation_offsets
    for range_len in ranges:
        for offset in offsets:
            old = _side_spec(base, encoding=enc16)
            new = _side_spec(base, encoding=enc16, sample_offset=offset)
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(group.group_key, "P1", str(offset), str(range_len)),
                    side=side,
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="P1",
                    perturbation_detail=f"offset={offset}",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
            )

        if abs(group.start_phase_rad) < 1e-12:
            deltas = (
                c.p3_calibration_deltas_rad
                if side == "calibration"
                else c.p3_validation_deltas_rad
            )
            for delta in deltas:
                old = _side_spec(base, encoding=enc16)
                new = _side_spec(base, encoding=enc16, phase_delta_rad=delta)
                _emit_identity(
                pair_counter,
                pair_id=_pair_id(group.group_key, "P3", str(delta), str(range_len)),
                side=side,
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code="P3",
                perturbation_detail=f"delta={delta}",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                old_side=old,
                new_side=new,
                    )

        gains = c.p5_calibration_gains if side == "calibration" else c.p5_validation_gains
        for gain in gains:
            old = _side_spec(base, encoding=enc16)
            new = _side_spec(base, encoding=enc16, gain_factor=1.0 + gain)
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(group.group_key, "P5", str(gain), str(range_len)),
                    side=side,
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="P5",
                    perturbation_detail=f"gain={gain}",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
            )

        rms_values = c.p6_calibration_rms if side == "calibration" else c.p6_validation_rms
        for rms in rms_values:
            for seed in seeds:
                old = _side_spec(base, encoding=enc16)
                new = _side_spec(base, encoding=enc16, noise_rms=rms, noise_seed=seed)
                _emit_identity(
                pair_counter,
                pair_id=_pair_id(group.group_key, "P6", str(rms), str(seed), str(range_len)),
                side=side,
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code="P6",
                perturbation_detail=f"rms={rms};seed={seed}",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                seed=seed,
                old_side=old,
                new_side=new,
                    )

        for coarse in _P8_COARSE:
            old = _side_spec(base, encoding=EncodingSpec(bits=coarse, rounding="round"))
            new = _side_spec(base, encoding=EncodingSpec(bits=8, rounding="round"))
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(group.group_key, "P8", f"{coarse}-8", str(range_len)),
                    side=side,
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="P8",
                    perturbation_detail=f"{coarse}->8",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
            )


def _append_combo_pairs(
    group: SourceGroupRecord,
    c: CharacterizationConstants,
    *,
    pair_counter: list[dict],
) -> None:
    if group.side != "validation":
        return
    base = _base_effective(group)
    enc16 = EncodingSpec(bits=16, rounding="round")
    seeds = _seeds_for_side(c, "validation")
    for range_len in _range_lengths_for_side(c, "validation"):
        old = _side_spec(base, encoding=enc16)
        new = _side_spec(
            base,
            encoding=enc16,
            sample_offset=1,
            noise_rms=1e-4,
            noise_seed=seeds[0],
        )
        _emit_identity(
                pair_counter,
                pair_id=_pair_id(group.group_key, "COMBO_P1_P6", str(range_len)),
                side="validation",
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code="COMBO_P1_P6",
                perturbation_detail="P1(1)+P6(1e-4)",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                seed=seeds[0],
                old_side=old,
                new_side=new,
                is_combo=True,
        )
        old = _side_spec(base, encoding=EncodingSpec(bits=32, rounding="round"))
        new = _side_spec(
            base,
            encoding=EncodingSpec(bits=16, rounding="round"),
            gain_factor=1.0 + 1e-4,
        )
        _emit_identity(
                pair_counter,
                pair_id=_pair_id(group.group_key, "COMBO_P4_P5", str(range_len)),
                side="validation",
                kind="empty",
                family=group.family,
                source_group_key=group.group_key,
                perturbation_code="COMBO_P4_P5",
                perturbation_detail="P4(32->16)+P5(1e-4)",
                range_length_s=range_len,
                f0_hz=group.f0_hz,
                sample_rate_hz=group.sample_rate_hz,
                old_side=old,
                new_side=new,
                is_combo=True,
        )
        if len(seeds) >= 2:
            old = _side_spec(base, encoding=enc16, noise_rms=1e-4, noise_seed=seeds[0])
            new = _side_spec(base, encoding=enc16, noise_rms=1e-4, noise_seed=seeds[1])
            _emit_identity(
                pair_counter,
                    pair_id=_pair_id(group.group_key, "COMBO_P6_DUAL", str(range_len)),
                    side="validation",
                    kind="empty",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="COMBO_P6_DUAL",
                    perturbation_detail="dual_noise_1e-4",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
                    is_combo=True,
            )


def _append_change_pairs(
    group: SourceGroupRecord,
    c: CharacterizationConstants,
    *,
    pair_counter: list[dict],
) -> None:
    side = group.side
    ranges = _range_lengths_for_side(c, side)
    enc16 = EncodingSpec(bits=16, rounding="round")

    if group.family == "M1" and group.amplitude == 0.9:
        base = _base_effective(group)
        depths = c.onset_calibration_depths if side == "calibration" else ()
        specs = c.onset_validation_specs if side == "validation" else ()
        for range_len in ranges:
            if side == "calibration":
                for depth in depths:
                    old = _side_spec(base, encoding=enc16)
                    new_eff = EffectiveMaterialParams(
                        family="M3",
                        f0_hz=group.f0_hz,
                        sample_rate_hz=group.sample_rate_hz,
                        phase_rad=group.start_phase_rad,
                        level=0.995,
                        depth=depth,
                    )
                    new = _side_spec(new_eff, encoding=enc16)
                    _emit_identity(
                        pair_counter,
                        pair_id=_pair_id(group.group_key, "ONSET", str(depth), str(range_len)),
                        side=side,
                        kind="onset_change",
                        family=group.family,
                        source_group_key=group.group_key,
                        perturbation_code="ONSET",
                        perturbation_detail=f"depth={depth}",
                        range_length_s=range_len,
                        f0_hz=group.f0_hz,
                        sample_rate_hz=group.sample_rate_hz,
                        old_side=old,
                        new_side=new,
                    )
            else:
                for level, depth in specs:
                    old = _side_spec(base, encoding=enc16)
                    new_eff = EffectiveMaterialParams(
                        family="M3",
                        f0_hz=group.f0_hz,
                        sample_rate_hz=group.sample_rate_hz,
                        phase_rad=group.start_phase_rad,
                        level=level,
                        depth=depth,
                    )
                    new = _side_spec(new_eff, encoding=enc16)
                    _emit_identity(
                        pair_counter,
                        pair_id=_pair_id(
                            group.group_key, "ONSET", str(level), str(depth), str(range_len)
                        ),
                        side=side,
                        kind="onset_change",
                        family=group.family,
                        source_group_key=group.group_key,
                        perturbation_code="ONSET",
                        perturbation_detail=f"level={level};depth={depth}",
                        range_length_s=range_len,
                        f0_hz=group.f0_hz,
                        sample_rate_hz=group.sample_rate_hz,
                        old_side=old,
                        new_side=new,
                    )

    if group.family == "M3" and group.level is not None and group.depth is not None:
        base = _base_effective(group)
        for range_len in ranges:
            for rel in c.aggravation_relative_peaks:
                old = _side_spec(base, encoding=enc16)
                aggravated = base.model_copy(
                    update={"depth": group.depth / (1.0 + rel)}
                )
                new = _side_spec(aggravated, encoding=enc16)
                _emit_identity(
                    pair_counter,
                    pair_id=_pair_id(group.group_key, "AGGR", str(rel), str(range_len)),
                    side=side,
                    kind="aggravation_change",
                    family=group.family,
                    source_group_key=group.group_key,
                    perturbation_code="AGGR",
                    perturbation_detail=f"rel_peak={rel}",
                    range_length_s=range_len,
                    f0_hz=group.f0_hz,
                    sample_rate_hz=group.sample_rate_hz,
                    old_side=old,
                    new_side=new,
                )


def _append_blind_pairs(c: CharacterizationConstants, *, pair_counter: list[dict]) -> None:
    enc16 = EncodingSpec(bits=16, rounding="round")
    for range_len in _range_lengths_for_side(c, "validation"):
        for old_level, new_level, old_depth, new_depth in c.blind_sublevel_change:
            for sr in c.sample_rates:
                for f0 in c.validation_fixed_f0:
                    old_eff = EffectiveMaterialParams(
                        family="M4",
                        f0_hz=f0,
                        sample_rate_hz=sr,
                        phase_rad=0.0,
                        level=old_level,
                        depth=old_depth,
                    )
                    new_eff = EffectiveMaterialParams(
                        family="M4",
                        f0_hz=f0,
                        sample_rate_hz=sr,
                        phase_rad=0.0,
                        level=new_level,
                        depth=new_depth,
                    )
                    key = f"blind_sub|{f0}|{sr}|{old_level}|{new_level}"
                    _emit_identity(
                        pair_counter,
                        pair_id=_pair_id(key, str(range_len)),
                        side="validation",
                        kind="blind_change",
                        family="M4",
                        source_group_key=key,
                        perturbation_code="BLIND_SUB",
                        perturbation_detail="sublevel",
                        range_length_s=range_len,
                        f0_hz=f0,
                        sample_rate_hz=sr,
                        old_side=_side_spec(old_eff, encoding=enc16),
                        new_side=_side_spec(new_eff, encoding=enc16),
                        is_blind=True,
                    )
        f0, level, pre_peak = c.blind_single_sample
        for sr in c.sample_rates:
            depth = pre_peak / level if level else 1.0
            old_eff = EffectiveMaterialParams(
                family="M3",
                f0_hz=f0,
                sample_rate_hz=sr,
                phase_rad=0.0,
                level=level,
                depth=depth,
            )
            new_eff = old_eff
            key = f"blind_single|{f0}|{sr}"
            _emit_identity(
                pair_counter,
                pair_id=_pair_id(key, str(range_len)),
                side="validation",
                kind="blind_change",
                family="M3",
                source_group_key=key,
                perturbation_code="BLIND_SINGLE",
                perturbation_detail="single_sample",
                range_length_s=range_len,
                f0_hz=f0,
                sample_rate_hz=sr,
                old_side=_side_spec(old_eff, encoding=enc16),
                new_side=_side_spec(new_eff, encoding=enc16),
                is_blind=True,
            )


def _pairs_for_group(group: SourceGroupRecord, c: CharacterizationConstants) -> list[dict]:
    pairs: list[dict] = []
    _append_empty_pairs(group, c, pair_counter=pairs)
    _append_sensitivity_pairs(group, c, pair_counter=pairs)
    _append_combo_pairs(group, c, pair_counter=pairs)
    _append_change_pairs(group, c, pair_counter=pairs)
    return pairs


def enumerate_pairs(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
) -> list[PairRecord]:
    pairs: list[dict] = []
    for group in groups:
        pairs.extend(_pairs_for_group(group, c))
    _append_blind_pairs(c, pair_counter=pairs)
    return [_identity_dict_to_pair_record(d) for d in pairs]


def enumerate_pair_batches(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
    *,
    batch_size: int = 512,
) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for group in groups:
        batch.extend(_pairs_for_group(group, c))
        while len(batch) >= batch_size:
            yield batch[:batch_size]
            batch = batch[batch_size:]
    blind: list[dict] = []
    _append_blind_pairs(c, pair_counter=blind)
    batch.extend(blind)
    if batch:
        yield batch


def count_perturbations_for_pair(pair: PairRecord) -> list[str]:
    if pair.is_combo:
        return [pair.perturbation_code]
    return [pair.perturbation_code]


def is_sensitivity_pair(pair: PairRecord | dict) -> bool:
    return (pair.perturbation_code if hasattr(pair, 'perturbation_code') else pair['perturbation_code']) in SENSITIVITY_CODES


def is_tolerance_pair(pair: PairRecord | dict) -> bool:
    return (pair.perturbation_code if hasattr(pair, 'perturbation_code') else pair['perturbation_code']) in TOLERANCE_CODES


def default_pair_templates():
    from signal_diag.evaluation.full_scale_characterization.models import (
        PairExpansionTemplates,
    )

    return PairExpansionTemplates(
        tolerance_codes=tuple(sorted(TOLERANCE_CODES)),
        sensitivity_codes=tuple(sorted(SENSITIVITY_CODES)),
        validation_combo_codes=tuple(sorted(COMBO_CODES)),
        change_codes=("ONSET", "AGGR"),
        blind_codes=("BLIND_SUB", "BLIND_SINGLE"),
    )


def planned_pair_counts_from_formulas(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
):
    from signal_diag.evaluation.full_scale_characterization.models import (
        PlannedPairCounts,
    )

    by_side: dict[str, int] = defaultdict(int)
    by_side_family: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_side_family_perturbation: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    def bump(side: str, family: str, perturbation: str, n: int) -> None:
        if n <= 0:
            return
        by_side[side] += n
        by_side_family[side][family] += n
        by_side_family_perturbation[side][family][perturbation] += n

    for group in groups:
        side = group.side
        family = group.family
        ranges = len(_range_lengths_for_side(c, side))
        seeds = len(_seeds_for_side(c, side))
        p5t = (
            c.p5t_calibration_gains if side == "calibration" else c.p5t_validation_gains
        )
        bump(side, family, "P0", ranges * 3)
        bump(side, family, "P4", ranges * 3)
        bump(side, family, "P7a", ranges * 3)
        bump(side, family, "P7b", ranges * 3)
        bump(side, family, "P7c", ranges * 3)
        bump(side, family, "P7d", ranges * 3 * seeds)
        bump(side, family, "P9a", ranges * 3)
        bump(side, family, "P9b", ranges * 3)
        bump(side, family, "P9c", ranges * 3)
        bump(side, family, "P5t", ranges * len(p5t))

        offsets = c.p1_calibration_offsets if side == "calibration" else c.p1_validation_offsets
        bump(side, family, "P1", ranges * len(offsets))
        if abs(group.start_phase_rad) < 1e-12:
            deltas = (
                c.p3_calibration_deltas_rad
                if side == "calibration"
                else c.p3_validation_deltas_rad
            )
            bump(side, family, "P3", ranges * len(deltas))
        gains = c.p5_calibration_gains if side == "calibration" else c.p5_validation_gains
        bump(side, family, "P5", ranges * len(gains))
        rms_values = c.p6_calibration_rms if side == "calibration" else c.p6_validation_rms
        bump(side, family, "P6", ranges * len(rms_values) * seeds)
        bump(side, family, "P8", ranges * 2)

        if side == "validation":
            bump(side, family, "COMBO_P1_P6", ranges)
            bump(side, family, "COMBO_P4_P5", ranges)
            if seeds >= 2:
                bump(side, family, "COMBO_P6_DUAL", ranges)

        if group.family == "M1" and group.amplitude == 0.9:
            if side == "calibration":
                bump(side, family, "ONSET", ranges * len(c.onset_calibration_depths))
            else:
                bump(side, family, "ONSET", ranges * len(c.onset_validation_specs))
        if group.family == "M3" and group.level is not None and group.depth is not None:
            bump(side, family, "AGGR", ranges * len(c.aggravation_relative_peaks))

    blind_ranges = len(_range_lengths_for_side(c, "validation"))
    sub = len(c.blind_sublevel_change) * len(c.sample_rates) * len(c.validation_fixed_f0)
    single = len(c.sample_rates)
    bump("validation", "M4", "BLIND_SUB", blind_ranges * sub)
    bump("validation", "M3", "BLIND_SINGLE", blind_ranges * single)

    return PlannedPairCounts(
        by_side=dict(by_side),
        by_side_family={k: dict(v) for k, v in by_side_family.items()},
        by_side_family_perturbation={
            side: {fam: dict(perts) for fam, perts in families.items()}
            for side, families in by_side_family_perturbation.items()
        },
    )


def _encoding_to_json(enc: EncodingSpec) -> dict:
    return {
        "bits": enc.bits,
        "rounding": enc.rounding,
        "step_bits": enc.step_bits,
        "seed": enc.seed,
        "filename": enc.filename,
    }


def _effective_to_json(eff: EffectiveMaterialParams) -> dict:
    return {
        "family": eff.family,
        "f0_hz": eff.f0_hz,
        "sample_rate_hz": eff.sample_rate_hz,
        "phase_rad": eff.phase_rad,
        "amplitude": eff.amplitude,
        "peak": eff.peak,
        "level": eff.level,
        "depth": eff.depth,
        "harmonics": eff.harmonics,
        "m7_marked": eff.m7_marked,
    }


def _side_to_json(side: SideGenerationSpec) -> dict:
    return {
        "encoding": _encoding_to_json(side.encoding),
        "effective": _effective_to_json(side.effective),
        "sample_offset": side.sample_offset,
        "gain_factor": side.gain_factor,
        "noise_rms": side.noise_rms,
        "noise_seed": side.noise_seed,
        "phase_delta_rad": side.phase_delta_rad,
    }


def pair_tuple_for_hash(pair: PairRecord | dict) -> dict:
    if isinstance(pair, dict):
        return dict(pair)
    return {
        "pair_id": pair.pair_id,
        "side": pair.side,
        "kind": pair.kind,
        "family": pair.family,
        "source_group_key": pair.source_group_key,
        "perturbation_code": pair.perturbation_code,
        "perturbation_detail": pair.perturbation_detail,
        "range_length_s": pair.range_length_s,
        "f0_hz": pair.f0_hz,
        "sample_rate_hz": pair.sample_rate_hz,
        "seed": pair.seed,
        "is_combo": pair.is_combo,
        "is_blind": pair.is_blind,
        "old_side": _side_to_json(pair.old_side),
        "new_side": _side_to_json(pair.new_side),
    }


def iter_pair_identity_tuples(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
    *,
    skip_pair_ids: frozenset[str] = frozenset(),
):
    """Yield canonical pair dicts without constructing PairRecord (ROUND_1 hash path)."""
    for batch in enumerate_pair_batches(groups, c, batch_size=2048):
        for pair in batch:
            if pair["pair_id"] in skip_pair_ids:
                continue
            yield pair


def iter_pair_tuples(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
):
    """Yield canonical pair dicts in deterministic expansion order."""
    for batch in enumerate_pair_batches(groups, c, batch_size=2048):
        for pair in batch:
            yield pair_tuple_for_hash(pair)


def canonical_pair_tuple_bytes(pair_dict: dict) -> bytes:
    return json.dumps(
        pair_dict, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
