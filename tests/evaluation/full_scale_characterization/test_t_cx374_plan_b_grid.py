"""T-CX374: materials follow plan B.2 / B.4 (validation sub-grid by rule, change pairs, M9, blind pairs)."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    CharacterizationConstants,
    M9ChannelLayout,
)
from signal_diag.evaluation.full_scale_characterization.groups import (
    enumerate_source_groups,
)
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from signal_diag.evaluation.full_scale_characterization.materials import (
    _layout_channel_params,
    synthesize_mono,
)
from signal_diag.evaluation.full_scale_characterization.models import SourceGroupRecord
from signal_diag.evaluation.full_scale_characterization.pairs import (
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


def _held_out_dims(g: SourceGroupRecord, c: CharacterizationConstants) -> tuple[set[str], bool]:
    """Held-out dimensions of a validation group and whether the other dims sit in the fixed subsets."""
    held: set[str] = set()
    fixed_ok = True

    def dim(name: str, value: object, heldout: tuple, fixed: tuple) -> None:
        nonlocal fixed_ok
        if value in heldout:
            held.add(name)
        elif value not in fixed:
            fixed_ok = False

    if g.family == "M9":
        return {"m9"}, g.f0_hz in c.m9_validation_f0_only
    dim("f0", g.f0_hz, c.validation_f0_heldout, c.validation_fixed_f0)
    if g.family in {"M2", "M3", "M5"}:
        dim("phase", g.start_phase_rad, c.validation_start_phases_heldout_rad, c.validation_fixed_start_phases_rad)
    elif g.start_phase_rad != 0.0:
        fixed_ok = False
    harm = dict(g.harmonics)
    if g.family == "M1":
        dim("amp", g.amplitude, c.m1_validation_amplitudes_heldout, c.m1_calibration_amplitudes)
    elif g.family == "M2":
        dim("peak", g.peak, c.m2_validation_peaks_heldout, c.validation_fixed_m2_peaks)
    elif g.family == "M3":
        dim("level", g.level, c.m3_validation_levels_heldout, c.validation_fixed_m3_levels)
        dim("depth", g.depth, c.m3_validation_depths_heldout, c.validation_fixed_m3_depths)
    elif g.family == "M4":
        dim("level", g.level, c.m4_validation_levels_heldout, c.validation_fixed_m4_levels)
        dim("depth", g.depth, c.m4_validation_depths_heldout, c.validation_fixed_m4_depths)
    elif g.family == "M5":
        dim(
            "harm",
            harm,
            tuple(h.as_dict() for h in c.m5_validation_harmonics_heldout),
            tuple(h.as_dict() for h in c.validation_fixed_m5_harmonics),
        )
        dim("depth", g.depth, c.m5_validation_depths_heldout, c.validation_fixed_m5_depths)
        if g.level not in c.validation_fixed_m5_levels:
            fixed_ok = False
    elif g.family == "M6":
        dim(
            "harm",
            harm,
            tuple(h.as_dict() for h in c.m6_validation_harmonics),
            tuple(h.as_dict() for h in c.m6_calibration_harmonics),
        )
    return held, fixed_ok


def _rule(g: SourceGroupRecord, c: CharacterizationConstants) -> int:
    held, fixed_ok = _held_out_dims(g, c)
    assert fixed_ok, g.group_key
    if held == {"m9"}:
        return 3
    if len(held) == 1:
        return 1
    assert "f0" in held and "phase" not in held and g.start_phase_rad == 0.0, g.group_key
    return 2


# Hand counts from plan B.2 for ROUND_1 (per sample rate, then x2):
#   rule 1 = one held-out dimension, others fixed; rule 2 = held-out f0 and >= 1 held-out
#   clipping dimension, phase 0; rule 3 = M9 on held-out f0 only.
_ROUND_1_EXPECTED = {
    ("M1", 1): 2 * (3 * 2 + 5 * 3),
    ("M1", 2): 2 * (5 * 2),
    ("M2", 1): 2 * (3 * 2 * 5 + 3 * 2 * 6 + 5 * 2 * 6),
    ("M2", 2): 2 * (5 * 5),
    ("M3", 1): 2 * (3 * 2 * 2 * 2 + 3 * 2 * 3 * 3 + 3 * 2 * 3 * 2 + 5 * 2 * 3 * 2),
    ("M3", 2): 2 * (5 * (2 * 2 + 3 * 3 + 2 * 3)),
    ("M4", 1): 2 * (3 * 3 * 2 + 3 * 2 * 3 + 5 * 2 * 2),
    ("M4", 2): 2 * (5 * (3 * 2 + 2 * 3 + 3 * 3)),
    ("M5", 1): 2 * (3 * 2 * 1 * 2 * 1 + 3 * 2 * 2 * 2 * 1 + 3 * 2 * 2 * 2 * 1 + 5 * 2 * 2 * 2 * 1),
    ("M5", 2): 2 * (5 * 2 * (1 * 1 + 2 * 1 + 1 * 1)),
    ("M6", 1): 2 * (3 * 1 + 5 * 2),
    ("M6", 2): 2 * (5 * 1),
    ("M9", 3): 2 * 3,
}


def test_t_cx374_validation_groups_by_rule_match_hand_counts(round_1_manifest) -> None:
    validation = [g for g in round_1_manifest.source_groups if g.side == "validation"]
    counts = Counter((g.family, _rule(g, ROUND_1)) for g in validation)
    assert dict(counts) == _ROUND_1_EXPECTED


def test_t_cx374_rule_1_includes_held_out_f0_with_fixed_subsets() -> None:
    groups = enumerate_source_groups(MINI)
    for family in ("M1", "M2", "M3", "M4", "M5", "M6"):
        rule1_f0 = [
            g
            for g in groups
            if g.side == "validation"
            and g.family == family
            and _held_out_dims(g, MINI)[0] == {"f0"}
        ]
        assert rule1_f0, family


def _mini_with_phases() -> CharacterizationConstants:
    return MINI.model_copy(update={"calibration_start_phases_rad": (0.0, 1.0)})


def test_t_cx374_change_pairs_cover_three_bit_depths_at_phase_zero() -> None:
    c = _mini_with_phases()
    manifest = build_manifest(c)
    groups = {g.group_key: g for g in manifest.source_groups}
    change = [p for p in _descriptions(manifest, c) if p.kind in ("onset_change", "aggravation_change")]
    assert change
    bits_by_cell: dict[tuple, set[int]] = {}
    for p in change:
        assert p.old_side.encoding.bits == p.new_side.encoding.bits
        assert p.old_side.encoding.rounding == p.new_side.encoding.rounding == "round"
        assert groups[p.source_group_key].start_phase_rad == 0.0
        assert p.old_side.effective.phase_rad == p.new_side.effective.phase_rad == 0.0
        cell = (p.source_group_key, p.kind, p.perturbation_detail, p.range_length_s)
        bits_by_cell.setdefault(cell, set()).add(p.old_side.encoding.bits)
    assert all(bits == {16, 24, 32} for bits in bits_by_cell.values())
    m3_phase0 = [
        g for g in manifest.source_groups if g.family == "M3" and g.start_phase_rad == 0.0
    ]
    m3_other = [g for g in manifest.source_groups if g.family == "M3" and g.start_phase_rad != 0.0]
    assert m3_other
    aggr = [p for p in change if p.kind == "aggravation_change"]
    expected = sum(
        len(c.calibration_range_lengths_s if g.side == "calibration" else c.validation_range_lengths_s)
        for g in m3_phase0
    ) * len(c.aggravation_relative_peaks) * 3
    assert len(aggr) == expected


def test_t_cx374_formula_counts_match_enumerated_pairs() -> None:
    c = _mini_with_phases()
    manifest = build_manifest(c)
    described = _descriptions(manifest, c)
    enumerated = Counter(p.side for p in described)
    assert dict(enumerated) == manifest.planned_pair_counts.by_side
    per = Counter((p.side, p.family, p.perturbation_code) for p in described)
    planned = {
        (side, fam, code): n
        for side, fams in manifest.planned_pair_counts.by_side_family_perturbation.items()
        for fam, codes in fams.items()
        for code, n in codes.items()
    }
    assert dict(per) == planned


def test_t_cx374_m9_calibration_layouts_swap_left_and_right() -> None:
    families = []
    for layout in ROUND_1.m9_calibration_layouts:
        left, right = _layout_channel_params(
            M9ChannelLayout.model_validate(layout.model_dump()), f0_hz=100.0, sample_rate_hz=48_000, phase_rad=0.0
        )
        families.append((left.family, right.family))
    assert families == [("M1", "M3"), ("M3", "M1")]


def test_t_cx374_blind_pairs_change_material_and_clip_new_side() -> None:
    described = _descriptions(build_manifest(MINI))
    single = [p for p in described if p.perturbation_code == "BLIND_SINGLE"]
    sub = [p for p in described if p.perturbation_code == "BLIND_SUB"]
    assert single and sub
    f0, level, pre_peak = MINI.blind_single_sample
    for p in single:
        old, new = p.old_side.effective, p.new_side.effective
        assert old != new
        assert old.family == "M1" and old.amplitude == MINI.blind_single_sample_old_amplitude
        assert old.f0_hz == new.f0_hz == f0
        assert new.family == "M3" and new.level == level
        assert new.level / new.depth == pytest.approx(pre_peak)
        wave = synthesize_mono(new, duration_s=MINI.file_duration_s)
        assert float(np.max(np.abs(wave))) == pytest.approx(level, abs=1e-12)
    levels = sorted({p.old_side.effective.level for p in sub})
    assert levels == sorted(MINI.blind_sublevel_levels)
    old_depth, new_depth = MINI.blind_sublevel_depths
    for p in sub:
        old, new = p.old_side.effective, p.new_side.effective
        assert old != new
        assert old.family == new.family == "M4"
        assert old.level == new.level
        assert (old.depth, new.depth) == (old_depth, new_depth)
