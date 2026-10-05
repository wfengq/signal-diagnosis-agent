"""T-CX373: deterministic manifest hashing and perturbation/seed rules."""

from __future__ import annotations

import pytest

from signal_diag.evaluation.full_scale_characterization.constants import (
    ROUND_1,
    constants_digest,
    make_round_1_constants,
)
from signal_diag.evaluation.full_scale_characterization.manifest import (
    build_manifest,
    manifest_sha256,
)
from signal_diag.evaluation.full_scale_characterization.pairs import (
    COMBO_CODES,
    SENSITIVITY_CODES,
    TOLERANCE_CODES,
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

ROUND_1_WALL_BUDGET_S = 120.0


def test_round_1_manifest_hash_is_stable(round_1_manifest) -> None:
    """Hash is deterministic; wall budget is enforced on the session cold build."""
    first = round_1_manifest
    second = build_manifest(ROUND_1)
    assert manifest_sha256(first) == manifest_sha256(second)
    assert first.pairs_list_sha256 == second.pairs_list_sha256


def test_round_1_build_within_wall_budget(round_1_build_elapsed_s: float) -> None:
    assert round_1_build_elapsed_s < ROUND_1_WALL_BUDGET_S


def test_constants_change_changes_manifest_hash(round_1_manifest) -> None:
    base = round_1_manifest
    tweaked_constants = make_round_1_constants().model_copy(
        update={"m1_calibration_amplitudes": (0.05, 0.5, 0.91)}
    )
    tweaked = build_manifest(tweaked_constants)
    assert constants_digest(tweaked_constants) != base.constants_digest
    assert manifest_sha256(tweaked) != manifest_sha256(base)


def test_round_1_planned_counts_only(round_1_manifest) -> None:
    manifest = round_1_manifest
    assert manifest.planned_pair_counts.by_side["calibration"] > 0
    assert manifest.planned_pair_counts.by_side["validation"] > 0
    assert sum(manifest.planned_pair_counts.by_side.values()) > 0
    assert manifest.pairs_list_sha256
    assert manifest.pairs == ()
    assert manifest.pair_templates.tolerance_codes


def test_mini_sensitivity_pairs_single_perturbation() -> None:
    manifest = build_manifest(MINI)
    for pair in _descriptions(manifest):
        if pair.perturbation_code in SENSITIVITY_CODES:
            assert not pair.is_combo
            assert pair.perturbation_code in {"P1", "P3", "P5", "P6", "P8"}
        if pair.is_combo:
            assert pair.side == "validation"
            assert pair.perturbation_code in COMBO_CODES


def test_mini_tolerance_codes_only_listed() -> None:
    manifest = build_manifest(MINI)
    for pair in _descriptions(manifest):
        if pair.perturbation_code in TOLERANCE_CODES:
            assert pair.perturbation_code in TOLERANCE_CODES
        if (
            pair.perturbation_code.startswith("P")
            and pair.perturbation_code[1:2].isdigit()
            and pair.perturbation_code not in SENSITIVITY_CODES | TOLERANCE_CODES | {"P8"}
            and not pair.perturbation_code.startswith("COMBO")
        ):
            pytest.fail(f"unexpected perturbation code {pair.perturbation_code}")


def test_seed_sets_do_not_overlap() -> None:
    manifest = build_manifest(MINI)
    cal_seeds = set(MINI.calibration_seeds)
    val_seeds = set(MINI.validation_seeds)
    assert cal_seeds.isdisjoint(val_seeds)
    for pair in _descriptions(manifest):
        if pair.seed is not None:
            allowed = cal_seeds if pair.side == "calibration" else val_seeds
            assert pair.seed in allowed


def test_calibration_has_no_combo_or_blind() -> None:
    manifest = build_manifest(MINI)
    for pair in _descriptions(manifest):
        if pair.side == "calibration":
            assert pair.perturbation_code not in COMBO_CODES
            assert not pair.is_blind
