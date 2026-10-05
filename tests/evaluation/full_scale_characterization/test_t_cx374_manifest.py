"""T-CX374: leakage-safe split, exclusions, and scale limits."""

from __future__ import annotations

import pytest

from signal_diag.evaluation.full_scale_characterization.constants import ROUND_1
from signal_diag.evaluation.full_scale_characterization.leakage import (
    ManifestLeakageAbort,
    full_encode_max_code_delta,
    near_duplicate_hit,
    prefilter_near_duplicate,
)
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.materials import (
    effective_params_equal,
    params_from_group_record,
    synthesize_mono,
)
from signal_diag.evaluation.full_scale_characterization.models import (
    EffectiveMaterialParams,
    ScaleLimitExceeded,
)
from signal_diag.evaluation.full_scale_characterization.pairs import (
    COMBO_CODES,
    _r0_description_records,
)
from tests.evaluation.full_scale_characterization.mini_manifest import MINI


def _descriptions(manifest, constants=MINI):
    """All pair descriptions (both sides) minus A.15 exclusions; R0-level access for tests."""
    excluded = {e.pair_id for e in manifest.excluded_near_duplicates}
    return [
        p
        for p in _r0_description_records(manifest.source_groups, constants)
        if p.pair_id not in excluded
    ]


def test_source_group_side_consistency() -> None:
    manifest = build_manifest(MINI)
    group_side = {g.group_key: g.side for g in manifest.source_groups}
    for pair in _descriptions(manifest):
        assert group_side.get(pair.source_group_key, pair.side) == pair.side or pair.is_blind


def test_calibration_only_calibration_range_lengths() -> None:
    manifest = build_manifest(MINI)
    allowed = set(MINI.calibration_range_lengths_s)
    for pair in manifest.pairs:
        if pair.side == "calibration":
            assert pair.range_length_s in allowed


def test_group_key_ignores_filename_seed_perturbation() -> None:
    manifest = build_manifest(MINI)
    keys = {g.group_key for g in manifest.source_groups}
    assert len(keys) == len(manifest.source_groups)
    for pair in manifest.pairs:
        if pair.seed is not None:
            assert pair.source_group_key in keys or pair.is_blind


def test_validation_has_each_family_combo_and_blind() -> None:
    manifest = build_manifest(MINI)
    families = {g.family for g in manifest.source_groups if g.side == "validation"}
    assert {"M1", "M2", "M3", "M4", "M5", "M6", "M9"}.issubset(families)
    combo = [p for p in _descriptions(manifest) if p.perturbation_code in COMBO_CODES]
    assert combo
    blind = [p for p in _descriptions(manifest) if p.is_blind]
    assert blind


def test_no_calibration_effective_params_match_validation_materials() -> None:
    manifest = build_manifest(MINI)
    validation_params = [
        params_from_group_record(g)
        for g in manifest.source_groups
        if g.side == "validation"
    ]
    for pair in manifest.pairs:
        if pair.side != "calibration":
            continue
        for side in (pair.old_side, pair.new_side):
            for val in validation_params:
                assert not effective_params_equal(side.effective, val)


def test_p3_result_phases_disjoint_from_validation_held_out() -> None:
    manifest = build_manifest(MINI)
    held_out = set(MINI.validation_start_phases_heldout_rad) | set(
        MINI.p3_validation_deltas_rad
    )
    for pair in manifest.pairs:
        if pair.perturbation_code != "P3" or pair.side != "calibration":
            continue
        result_phase = pair.new_side.effective.phase_rad
        assert result_phase not in held_out


def test_onset_calibration_depths_exclude_0_9999() -> None:
    assert 0.9999 not in MINI.onset_calibration_depths
    assert 0.9999 not in ROUND_1.onset_calibration_depths


def test_scale_limit_raises_when_exceeded() -> None:
    tight = MINI.model_copy(
        update={
            "validation_max_pair_ratio_to_calibration": 0.01,
            "scale_limit_enabled": True,
        }
    )
    with pytest.raises(ScaleLimitExceeded):
        build_manifest(tight)


def test_round_1_within_scale_limit_or_blocked(round_1_manifest) -> None:
    manifest = round_1_manifest
    cal = manifest.planned_pair_counts.by_side["calibration"]
    val = manifest.planned_pair_counts.by_side["validation"]
    assert val <= 2 * cal


def test_near_duplicate_exclusions_listed_not_silent() -> None:
    manifest = build_manifest(MINI)
    excluded_ids = {e.pair_id for e in manifest.excluded_near_duplicates}
    remaining_sensitivity = [
        p.pair_id
        for p in manifest.pairs
        if p.side == "calibration" and p.perturbation_code == "P5"
    ]
    for entry in manifest.excluded_near_duplicates:
        assert entry.pair_id in excluded_ids
        assert entry.pair_id not in remaining_sensitivity


def test_leakage_abort_on_forbidden_onset_depth() -> None:
    bad = MINI.model_copy(update={"onset_calibration_depths": (0.9999,)})
    with pytest.raises(ManifestLeakageAbort):
        build_manifest(bad)


def test_a15_prefilter_matches_full_encode_on_m3_p5_hit() -> None:
    """Known review hit: M3 level 0.9901 with gain (1-1e-4) vs held-out level 0.99."""
    sr = 48_000
    duration_s = 0.1
    range_len = 0.1
    f0 = 100.0
    cal = EffectiveMaterialParams(
        family="M3",
        f0_hz=f0,
        sample_rate_hz=sr,
        phase_rad=0.0,
        level=0.9901,
        depth=0.99,
    )
    val = EffectiveMaterialParams(
        family="M3",
        f0_hz=f0,
        sample_rate_hz=sr,
        phase_rad=0.0,
        level=0.99,
        depth=0.99,
    )
    cal_wave = synthesize_mono(cal, duration_s=duration_s, gain_factor=1.0 - 1e-4)
    val_wave = synthesize_mono(val, duration_s=duration_s)
    assert prefilter_near_duplicate(
        cal_wave, val_wave, sample_rate_hz=sr, range_length_s=range_len
    )
    hit, delta = near_duplicate_hit(
        cal_wave, val_wave, sample_rate_hz=sr, range_length_s=range_len
    )
    assert hit
    assert delta <= 1
    full_delta = full_encode_max_code_delta(
        cal_wave, val_wave, sample_rate_hz=sr, range_length_s=range_len
    )
    assert full_delta <= 1


def test_prefilter_skips_distant_pairs() -> None:
    sr = 48_000
    a = synthesize_mono(
        EffectiveMaterialParams(
            family="M1",
            f0_hz=100.0,
            sample_rate_hz=sr,
            phase_rad=0.0,
            amplitude=0.5,
        ),
        duration_s=0.05,
    )
    b = synthesize_mono(
        EffectiveMaterialParams(
            family="M1",
            f0_hz=100.0,
            sample_rate_hz=sr,
            phase_rad=0.0,
            amplitude=0.2,
        ),
        duration_s=0.05,
    )
    assert not prefilter_near_duplicate(a, b, sample_rate_hz=sr, range_length_s=0.05)
    assert not near_duplicate_hit(a, b, sample_rate_hz=sr, range_length_s=0.05)[0]
