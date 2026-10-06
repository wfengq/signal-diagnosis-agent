"""T-CX382–T-CX386: D044 round_1 approved full-scale method floor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from signal_diag.rules.full_scale_check import (
    PRODUCT_APPROVED_FULL_SCALE_FLOORS,
    FullScaleMethodFloor,
    evaluate_full_scale_check,
    full_scale_floor_digest,
    load_approved_full_scale_floor_yaml,
)
from tests.rules.full_scale_fixtures import eligible

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOR_YAML = (
    REPO_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_full_scale_floor_round_1.yaml"
)
FREEZE_RECORD = (
    REPO_ROOT
    / "docs"
    / "evaluations"
    / "v0_3"
    / "full_scale_characterization"
    / "round_1"
    / "freeze_record.json"
)
VALIDATION_REPORT_MD = FREEZE_RECORD.with_name("validation_report.md")


def test_t_cx383_floor_yaml_loads_and_digest_self_checks() -> None:
    floor, provenance = load_approved_full_scale_floor_yaml(FLOOR_YAML)
    assert full_scale_floor_digest(floor) == floor.digest
    assert provenance["freeze_record_digest"] == (
        "447751cee16da908ec179ab8966b3342ef273fc2a71028fb1ba01d07e585af06"
    )
    payload = yaml.safe_load(FLOOR_YAML.read_text(encoding="utf-8"))
    payload["floor"]["digest"] = "0" * 64
    tampered = FLOOR_YAML.with_name("s1_full_scale_floor_round_1.tampered.yaml")
    try:
        tampered.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="digest"):
            load_approved_full_scale_floor_yaml(tampered)
    finally:
        tampered.unlink(missing_ok=True)


def test_t_cx384_yaml_matches_freeze_record_full_precision() -> None:
    floor, provenance = load_approved_full_scale_floor_yaml(FLOOR_YAML)
    freeze = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))
    stage1 = freeze["stage1"]
    assert provenance["freeze_record_digest"] == freeze["digest"]
    assert provenance["manifest_sha256"] == stage1["manifest_sha256"]
    validation_md = VALIDATION_REPORT_MD.read_text(encoding="utf-8")
    assert provenance["validation_conclusion"] in validation_md
    assert floor.facts_version == "v0.3-full-scale-facts-1"
    assert floor.full_scale_threshold == 0.99
    assert floor.min_consecutive_samples == 2
    assert floor.min_samples_per_period == stage1["domain"]["n_min"] == 5.5125
    assert floor.min_periods_in_range == float(stage1["domain"]["p_min"]) == 1.0
    assert floor.zone_below_threshold == stage1["zone_params"]["zone_below"] == 0.0
    assert (
        floor.zone_above_threshold
        == stage1["zone_params"]["zone_above"]
        == 0.002004394531250009
    )
    assert floor.zone_min_counted_samples == stage1["zone_params"]["min_counted"]
    assert floor.count_floor_samples == int(freeze["floor_params"]["value"]) == 1280
    assert floor.count_floor_ratio is None
    assert freeze["floor_form"] == "F2"
    assert stage1["zone_form"] == "K2"


def test_t_cx382_approved_zone_above_at_least_one_16bit_step() -> None:
    floor, _ = load_approved_full_scale_floor_yaml(FLOOR_YAML)
    assert floor.zone_above_threshold >= 2.0**-15


def test_t_cx386_product_registry_equals_loaded_yaml_floor() -> None:
    floor, _ = load_approved_full_scale_floor_yaml(FLOOR_YAML)
    assert PRODUCT_APPROVED_FULL_SCALE_FLOORS == (floor,)
    assert isinstance(PRODUCT_APPROVED_FULL_SCALE_FLOORS[0], FullScaleMethodFloor)


def test_t_cx385_builder_wires_floor_approved_product_floor() -> None:
    from signal_diag.app.regression import build_regression_service

    service = build_regression_service()
    assert service._full_scale_floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]


def _evaluate_product_floor(anchor, repeats):
    return evaluate_full_scale_check(
        check_id="chk_t_cx385",
        anchor=anchor,
        repeats=repeats,
        floor=PRODUCT_APPROVED_FULL_SCALE_FLOORS[0],
        supersedes=None,
    )


def test_t_cx385_no_to_yes_large_onset_regression_detected() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(20000, 1.0))
    record = _evaluate_product_floor(anchor, repeats)
    assert record.status == "regression_detected"
    assert record.floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]
    assert record.unmet_conditions == ()
    assert record.unevaluated_conditions == ()


def test_t_cx385_yes_to_yes_increase_below_floor_no_regression() -> None:
    anchor, repeats = eligible(baseline=(20000, 1.0), candidate=(20500, 1.0))
    record = _evaluate_product_floor(anchor, repeats)
    assert record.status == "no_regression_detected"
    assert record.floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]
    assert record.unmet_conditions == ()
    assert record.unevaluated_conditions == ()


def test_t_cx385_yes_to_yes_increase_above_floor_regression_detected() -> None:
    anchor, repeats = eligible(baseline=(20000, 1.0), candidate=(22000, 1.0))
    record = _evaluate_product_floor(anchor, repeats)
    assert record.status == "regression_detected"
    assert record.floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]
    assert record.unmet_conditions == ()
    assert record.unevaluated_conditions == ()


def test_t_cx385_critical_zone_both_sides_descriptive_only() -> None:
    anchor, repeats = eligible(baseline=(20000, 0.991), candidate=(22000, 0.991))
    record = _evaluate_product_floor(anchor, repeats)
    assert record.status == "descriptive_only"
    assert record.floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]
    assert "critical_zone:baseline" in record.unmet_conditions
    assert "critical_zone:candidate" in record.unmet_conditions
    assert record.unevaluated_conditions == ()


def test_t_cx385_count_floor_boundary_strict_greater_than_no_regression() -> None:
    anchor, repeats = eligible(baseline=(20000, 1.0), candidate=(21280, 1.0))
    record = _evaluate_product_floor(anchor, repeats)
    assert record.status == "no_regression_detected"
    assert record.floor == PRODUCT_APPROVED_FULL_SCALE_FLOORS[0]
    assert record.unmet_conditions == ()
    assert record.unevaluated_conditions == ()
