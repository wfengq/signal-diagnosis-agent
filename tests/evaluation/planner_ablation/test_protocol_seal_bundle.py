"""Wave 3: committed protocol seal verifies and binds study input."""

from __future__ import annotations

import json
from pathlib import Path

from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
)
from signal_diag.evaluation.planner_ablation.sealing import (
    verify_planner_ablation_bundle,
)
from signal_diag.evaluation.planner_ablation.study_score import (
    study_input_from_verified_manifest,
)

_SEAL = (
    Path(__file__).resolve().parents[3]
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1/protocol_seal"
)


def test_protocol_seal_verifies_and_binds_verified_study_input() -> None:
    assert _SEAL.is_dir()
    verify_planner_ablation_bundle(_SEAL)
    manifest = json.loads((_SEAL / "manifest.json").read_text(encoding="utf-8"))
    study = study_input_from_verified_manifest(manifest)
    assert study.protocol.study_id == PLANNER_ABLATION_STUDY_ID
    assert study.protocol.scoring_identity == PLANNER_ABLATION_SCORING_IDENTITY
    assert study.protocol.n_unit == "scorable_slots"
    assert study.protocol.non_inferiority_max_gap == 0.025
    assert study.protocol.material_improvement_ratio == 0.20
    assert study.protocol.advantage_endpoint == "quality"
    assert len(study.schedule) == 20
    assert len(study.oracle) == 20
    assert len({(key.case_id, key.mode) for key in study.schedule}) == 20
    assert manifest["scorable_slot_count"] == 40
    assert manifest["case_count"] == 10
    assert manifest["arm_order"] == ["product_agent", "fixed_pipeline"]
    assert len(manifest["input_identity"]) == 64
    assert len(manifest["code_identity"]) == 64
