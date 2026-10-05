"""Leakage checks and near-duplicate exclusion for manifest generation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from signal_diag.evaluation.full_scale_characterization.constants import (
    CharacterizationConstants,
)
from signal_diag.evaluation.full_scale_characterization.materials import (
    channel_effectives_from_group,
    codes_for_analysis_range,
    normalize_phase,
    params_from_group_record,
    synthesize_mono,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    EncodingSpec,
    ExcludedNearDuplicate,
    ManifestLeakageAbort,
    PairRecord,
    SideGenerationSpec,
    SourceGroupRecord,
)
from signal_diag.evaluation.full_scale_characterization.pairs import (
    _identity_dict_to_pair_record,
    _pair_id,
    is_sensitivity_pair,
    is_tolerance_pair,
)


def _as_pair_record(pair: PairRecord | dict) -> PairRecord:
    if isinstance(pair, dict):
        return _identity_dict_to_pair_record(pair)
    return pair

if TYPE_CHECKING:
    from numpy.typing import NDArray

ParamBucketKey = tuple[str, float, int, float]

_WAVE_CACHE: dict[tuple, NDArray[np.float64]] = {}


def clear_wave_cache() -> None:
    _WAVE_CACHE.clear()


def _bucket_key(params) -> ParamBucketKey:
    return (
        params.family,
        params.f0_hz,
        params.sample_rate_hz,
        normalize_phase(params.phase_rad),
    )


def _cache_key_for_side(side_spec: SideGenerationSpec, *, duration_s: float) -> tuple:
    eff = side_spec.effective
    return (
        eff.family,
        eff.f0_hz,
        eff.sample_rate_hz,
        normalize_phase(eff.phase_rad),
        eff.amplitude,
        eff.peak,
        eff.level,
        eff.depth,
        eff.harmonics,
        duration_s,
        side_spec.sample_offset,
        side_spec.gain_factor,
        side_spec.noise_rms,
        side_spec.noise_seed,
        side_spec.phase_delta_rad,
    )


def _side_wave_cached(
    side_spec: SideGenerationSpec,
    *,
    duration_s: float,
) -> NDArray[np.float64]:
    key = _cache_key_for_side(side_spec, duration_s=duration_s)
    cached = _WAVE_CACHE.get(key)
    if cached is not None:
        return cached
    wave = synthesize_mono(
        side_spec.effective,
        duration_s=duration_s,
        sample_offset=side_spec.sample_offset,
        gain_factor=side_spec.gain_factor,
        noise_rms=side_spec.noise_rms,
        noise_seed=side_spec.noise_seed,
    )
    _WAVE_CACHE[key] = wave
    return wave


def _analysis_segment(
    wave: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> NDArray[np.float64]:
    n = round(range_length_s * sample_rate_hz)
    n = min(n, wave.shape[0])
    return wave[:n]


def max_abs_diff_scaled(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> float:
    seg_a = _analysis_segment(wave_a, sample_rate_hz=sample_rate_hz, range_length_s=range_length_s)
    seg_b = _analysis_segment(wave_b, sample_rate_hz=sample_rate_hz, range_length_s=range_length_s)
    if seg_a.shape != seg_b.shape:
        return float("inf")
    if seg_a.size == 0:
        return 0.0
    return float(np.max(np.abs(seg_a - seg_b)))


def prefilter_near_duplicate(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> bool:
    """True when float prefilter passes (worth 16-bit code comparison). A.15."""
    d = max_abs_diff_scaled(
        wave_a,
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    return d * 32768.0 <= 2.0


def full_encode_max_code_delta(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> int:
    codes_a = codes_for_analysis_range(
        wave_a,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    codes_b = codes_for_analysis_range(
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    if codes_a.shape != codes_b.shape:
        return 10**9
    if codes_a.size == 0:
        return 0
    return int(max(abs(int(a) - int(b)) for a, b in zip(codes_a, codes_b, strict=True)))


def near_duplicate_hit(
    wave_a: NDArray[np.float64],
    wave_b: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
) -> tuple[bool, int]:
    if not prefilter_near_duplicate(
        wave_a,
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    ):
        return False, 10**9
    delta = full_encode_max_code_delta(
        wave_a,
        wave_b,
        sample_rate_hz=sample_rate_hz,
        range_length_s=range_length_s,
    )
    return delta <= 1, delta


def _validation_wave_index(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
) -> dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]]:
    index: dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]] = {}
    for group in groups:
        if group.side != "validation":
            continue
        for params in channel_effectives_from_group(group):
            side_spec = SideGenerationSpec(encoding=EncodingSpec(bits=16), effective=params)
            wave = _side_wave_cached(side_spec, duration_s=c.file_duration_s)
            key = _bucket_key(params)
            index.setdefault(key, []).append((wave, group.group_key))
    return index


def _min_delta_for_bucket(
    wave: NDArray[np.float64],
    *,
    sample_rate_hz: int,
    range_length_s: float,
    bucket: list[tuple[NDArray[np.float64], str]],
) -> tuple[int, str | None]:
    best = 10**9
    hit: str | None = None
    for val_wave, val_key in bucket:
        is_hit, delta = near_duplicate_hit(
            wave,
            val_wave,
            sample_rate_hz=sample_rate_hz,
            range_length_s=range_length_s,
        )
        if is_hit and delta < best:
            best = delta
            hit = val_key
    return best, hit


def _effective_key(params) -> tuple:
    return (
        params.family,
        params.f0_hz,
        params.sample_rate_hz,
        normalize_phase(params.phase_rad),
        params.amplitude,
        params.peak,
        params.level,
        params.depth,
        params.harmonics,
    )


def build_validation_effective_index(
    groups: tuple[SourceGroupRecord, ...],
) -> dict[tuple, str]:
    index: dict[tuple, str] = {}
    for group in groups:
        if group.side != "validation":
            continue
        for ch in channel_effectives_from_group(group):
            index[_effective_key(ch)] = group.group_key
    return index


def _effective_from_pair_side(side: SideGenerationSpec | dict) -> object:
    if isinstance(side, dict):
        from signal_diag.evaluation.full_scale_characterization.models import (
            EffectiveMaterialParams,
        )

        return EffectiveMaterialParams(**side["effective"])
    return side.effective


def assert_no_param_leakage(
    pairs: Sequence[PairRecord | dict[str, Any]],
    validation_index: dict[tuple, str],
) -> None:
    for pair in pairs:
        side = pair["side"] if isinstance(pair, dict) else pair.side
        family = pair["family"] if isinstance(pair, dict) else pair.family
        pair_id = pair["pair_id"] if isinstance(pair, dict) else pair.pair_id
        if side != "calibration" or family == "M9":
            continue
        old = pair["old_side"] if isinstance(pair, dict) else pair.old_side
        new = pair["new_side"] if isinstance(pair, dict) else pair.new_side
        for label, side_spec in (("old", old), ("new", new)):
            hit_key = validation_index.get(_effective_key(_effective_from_pair_side(side_spec)))
            if hit_key is not None:
                msg = (
                    f"calibration pair {pair_id} {label} side matches "
                    f"validation material {hit_key}"
                )
                raise ManifestLeakageAbort(msg)


def scan_calibration_near_duplicate_exclusions(
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
    *,
    wave_index: dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]],
) -> tuple[frozenset[str], tuple[ExcludedNearDuplicate, ...], list[tuple[str, str]]]:
    """A.15 for ROUND_1: scan only calibration P5 / P5t candidates (no full pair walk)."""
    excluded_ids: set[str] = set()
    excluded_entries: list[ExcludedNearDuplicate] = []
    excluded_families: list[tuple[str, str]] = []
    enc16 = EncodingSpec(bits=16, rounding="round")

    for group in groups:
        if group.side != "calibration":
            continue
        base_eff = params_from_group_record(group)
        for range_len in c.calibration_range_lengths_s:
            for gain in c.p5t_calibration_gains:
                for side_spec in (
                    SideGenerationSpec(encoding=enc16, effective=base_eff, gain_factor=1.0),
                    SideGenerationSpec(
                        encoding=enc16, effective=base_eff, gain_factor=1.0 + gain
                    ),
                ):
                    bucket = wave_index.get(_bucket_key(side_spec.effective))
                    if not bucket:
                        continue
                    wave = _side_wave_cached(side_spec, duration_s=c.file_duration_s)
                    delta, val_key = _min_delta_for_bucket(
                        wave,
                        sample_rate_hz=side_spec.effective.sample_rate_hz,
                        range_length_s=range_len,
                        bucket=bucket,
                    )
                    if delta <= 1 and val_key is not None:
                        pid = _pair_id(group.group_key, "P5t", str(gain), str(range_len))
                        raise ManifestLeakageAbort(
                            f"tolerance near-duplicate on pair {pid} vs validation {val_key}"
                        )

            for gain in c.p5_calibration_gains:
                pair_id = _pair_id(group.group_key, "P5", str(gain), str(range_len))
                new_side = SideGenerationSpec(
                    encoding=enc16,
                    effective=base_eff,
                    gain_factor=1.0 + gain,
                )
                bucket = wave_index.get(_bucket_key(new_side.effective))
                if not bucket:
                    continue
                wave = _side_wave_cached(new_side, duration_s=c.file_duration_s)
                delta, val_key = _min_delta_for_bucket(
                    wave,
                    sample_rate_hz=new_side.effective.sample_rate_hz,
                    range_length_s=range_len,
                    bucket=bucket,
                )
                if delta <= 1 and val_key is not None:
                    excluded_ids.add(pair_id)
                    excluded_entries.append(
                        ExcludedNearDuplicate(
                            pair_id=pair_id,
                            validation_group_key=val_key,
                            max_code_delta=delta,
                        )
                    )
                    excluded_families.append((group.family, "P5"))

    return frozenset(excluded_ids), tuple(excluded_entries), excluded_families


def exclude_near_duplicate_sensitivity_pairs(
    pairs: Sequence[PairRecord],
    groups: tuple[SourceGroupRecord, ...],
    c: CharacterizationConstants,
    *,
    wave_index: dict[ParamBucketKey, list[tuple[NDArray[np.float64], str]]] | None = None,
) -> tuple[list[PairRecord], tuple[ExcludedNearDuplicate, ...]]:
    if wave_index is None:
        wave_index = _validation_wave_index(groups, c)
    kept: list[PairRecord] = []
    excluded: list[ExcludedNearDuplicate] = []

    for pair in pairs:
        if pair.side != "calibration":
            kept.append(pair)
            continue

        if is_tolerance_pair(pair) and pair.perturbation_code == "P5t":
            for side_spec in (pair.old_side, pair.new_side):
                bucket = wave_index.get(_bucket_key(side_spec.effective))
                if not bucket:
                    continue
                wave = _side_wave_cached(side_spec, duration_s=c.file_duration_s)
                delta, val_key = _min_delta_for_bucket(
                    wave,
                    sample_rate_hz=side_spec.effective.sample_rate_hz,
                    range_length_s=pair.range_length_s,
                    bucket=bucket,
                )
                if delta <= 1 and val_key is not None:
                    raise ManifestLeakageAbort(
                        f"tolerance near-duplicate on pair {pair.pair_id} vs validation {val_key}"
                    )
            kept.append(pair)
            continue

        if is_sensitivity_pair(pair) and pair.perturbation_code == "P5":
            hit: ExcludedNearDuplicate | None = None
            for side_spec in (pair.new_side,):
                bucket = wave_index.get(_bucket_key(side_spec.effective))
                if not bucket:
                    continue
                wave = _side_wave_cached(side_spec, duration_s=c.file_duration_s)
                delta, val_key = _min_delta_for_bucket(
                    wave,
                    sample_rate_hz=side_spec.effective.sample_rate_hz,
                    range_length_s=pair.range_length_s,
                    bucket=bucket,
                )
                if delta <= 1 and val_key is not None:
                    hit = ExcludedNearDuplicate(
                        pair_id=pair.pair_id,
                        validation_group_key=val_key,
                        max_code_delta=delta,
                    )
                    break
            if hit is not None:
                excluded.append(hit)
            else:
                kept.append(pair)
            continue

        kept.append(pair)

    return kept, tuple(excluded)


def assert_p3_phases_disjoint(c: CharacterizationConstants) -> None:
    cal_phases = {round(v, 12) for v in c.p3_calibration_deltas_rad}
    val_phases = {round(v, 12) for v in c.validation_start_phases_heldout_rad}
    val_phases |= {round(v, 12) for v in c.p3_validation_deltas_rad}
    overlap = cal_phases & val_phases
    if overlap:
        raise ManifestLeakageAbort(f"P3 calibration result phases overlap validation: {overlap}")


def assert_onset_depths(c: CharacterizationConstants) -> None:
    if any(abs(d - 0.9999) < 1e-12 for d in c.onset_calibration_depths):
        raise ManifestLeakageAbort("calibration onset depths must not include 0.9999")
