"""T-CX374: A.15 near-reproduction scan over every calibration side; per-channel parameter leakage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.evaluation.full_scale_characterization.__main__ import main
from signal_diag.evaluation.full_scale_characterization.constants import M9ChannelLayout
from signal_diag.evaluation.full_scale_characterization.groups import (
    enumerate_source_groups,
)
from signal_diag.evaluation.full_scale_characterization.leakage import (
    ManifestLeakageAbort,
    count_param_leakage,
)
from signal_diag.evaluation.full_scale_characterization.manifest import build_manifest
from tests.evaluation.full_scale_characterization.mini_manifest import MINI
from tests.evaluation.full_scale_characterization.test_t_cx380_end_to_end import E2E


def _excluded_codes(manifest) -> dict[str, int]:
    calibration = {p.pair_id for p in manifest.pairs}
    out: dict[str, int] = {}
    for entry in manifest.excluded_near_duplicates:
        assert entry.pair_id not in calibration
        assert entry.max_code_delta <= 1
        out[entry.pair_id] = entry.max_code_delta
    return out


def test_t_cx374_a15_mini_excludes_known_p5_hit() -> None:
    manifest = build_manifest(MINI)
    assert len(manifest.excluded_near_duplicates) > 0
    _excluded_codes(manifest)
    counts = manifest.planned_pair_counts.by_side_family_perturbation["calibration"]["M3"]
    assert counts["P5"] < 2 * len(MINI.p5_calibration_gains) * len(MINI.calibration_range_lengths_s)


def test_t_cx374_a15_scan_reaches_p3_sides() -> None:
    # A held-out level 1e-8 above a calibration level, present only at phase 2.0:
    # the calibration base (phase 0) has no same-phase bucket, its P3 (+2.0 rad) side does.
    c = MINI.model_copy(
        update={
            "validation_fixed_start_phases_rad": (2.0,),
            "m3_validation_levels_heldout": (0.99500001,),
            "p3_calibration_deltas_rad": (2.0,),
        }
    )
    manifest = build_manifest(c)
    excluded_ids = {e.pair_id for e in manifest.excluded_near_duplicates}
    p3_ids = {
        p.pair_id for p in manifest.pairs if p.perturbation_code == "P3" and p.family == "M3"
    }
    assert excluded_ids
    assert not (p3_ids & excluded_ids)  # excluded pairs are removed from the manifest
    planned = manifest.planned_pair_counts.by_side_family_perturbation["calibration"]["M3"]
    full = build_manifest(MINI.model_copy(update={"p3_calibration_deltas_rad": (2.0,)}))
    assert planned["P3"] < full.planned_pair_counts.by_side_family_perturbation["calibration"]["M3"]["P3"]


def test_t_cx374_a15_scan_reaches_change_pairs() -> None:
    # Held-out depth next to the aggravated depth 0.99 / (1 + 1e-4) (not equal to it).
    c = MINI.model_copy(update={"m3_validation_depths_heldout": (0.98990102,)})
    manifest = build_manifest(c)
    aggr_planned = manifest.planned_pair_counts.by_side_family_perturbation["calibration"]["M3"]["AGGR"]
    base_planned = build_manifest(MINI).planned_pair_counts.by_side_family_perturbation["calibration"]["M3"]["AGGR"]
    assert aggr_planned < base_planned


def test_t_cx374_a15_base_material_hit_aborts() -> None:
    c = MINI.model_copy(update={"m3_validation_levels_heldout": (0.99500001,)})
    with pytest.raises(ManifestLeakageAbort, match="base"):
        build_manifest(c)


def _m9_leaky():
    layout = M9ChannelLayout(
        left_family="M1", left_amplitude=0.5, right_family="M3", right_level=0.991, right_depth=0.99
    )
    return MINI.model_copy(update={"m9_calibration_layouts": (layout,)})


def test_t_cx374_param_leakage_is_checked_per_channel_including_m9() -> None:
    c = _m9_leaky()
    hits = count_param_leakage(enumerate_source_groups(c), c)
    assert hits and all("M9" in h for h in hits)
    assert count_param_leakage(enumerate_source_groups(MINI), MINI) == []
    with pytest.raises(ManifestLeakageAbort):
        build_manifest(c)


def test_t_cx374_dry_run_prints_param_leakage_hits(tmp_path: Path, capsys) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps(E2E.model_dump(mode="json")), encoding="utf-8")
    assert main(["manifest", "--constants-json", str(path), "--dry-run"]) == 0
    assert "param_leakage_hits=0" in capsys.readouterr().out


# ROUND_1 exclusion count after the scan covers every sensitivity and change side
# (was 336 when only P5 was scanned).
ROUND_1_EXCLUDED_NEAR_DUPLICATES = 384


def test_t_cx374_round_1_exclusion_count_is_pinned(round_1_manifest) -> None:
    assert len(round_1_manifest.excluded_near_duplicates) == ROUND_1_EXCLUDED_NEAR_DUPLICATES
