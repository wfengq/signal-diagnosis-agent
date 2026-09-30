"""T-CX280: offline planner-ablation sealing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.evaluation.planner_ablation.identity import PLANNER_ABLATION_STUDY_ID
from signal_diag.evaluation.planner_ablation.sealing import (
    seal_planner_ablation_bundle,
    verify_planner_ablation_bundle,
)


def _manifest() -> dict[str, object]:
    return {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": "signal_diag.planner_ablation_scoring",
        "denominator_derivation": "completion_slots",
        "decision_protocol": {
            "study_id": PLANNER_ABLATION_STUDY_ID,
            "scoring_identity": "signal_diag.planner_ablation_scoring",
            "non_inferiority_max_gap": 0.05,
            "material_improvement_ratio": 0.20,
            "n_unit": "scorable_slots",
            "advantage_endpoint": "quality",
        },
        "population_identity": "wave2_test_population_v1",
        "oracle_identity": "wave2_test_oracle_v1",
        "input_identity": "wave2_test_input_v1",
        "code_identity": "wave2_test_code_v1",
        "slots": 48,
    }


def test_t_cx280_seal_and_verify_round_trip(tmp_path: Path) -> None:
    destination = tmp_path / "seal_bundle"
    seal_planner_ablation_bundle(
        destination=destination,
        study_id=PLANNER_ABLATION_STUDY_ID,
        scoring_identity="signal_diag.planner_ablation_scoring",
        denominator_derivation="completion_slots",
        manifest=_manifest(),
    )
    verify_planner_ablation_bundle(destination)


def test_t_cx280_seal_rejects_foreign_study(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="foreign study"):
        seal_planner_ablation_bundle(
            destination=tmp_path / "bad",
            study_id="study_foreign",
            scoring_identity="signal_diag.planner_ablation_scoring",
            denominator_derivation="completion_slots",
            manifest=_manifest(),
        )


def test_t_cx280_verify_rejects_empty_checksum_index(tmp_path: Path) -> None:
    destination = tmp_path / "empty_index"
    destination.mkdir()
    (destination / "seal.sha256").write_text("", encoding="utf-8")
    (destination / "seal_meta.json").write_text(
        '{"study_id":"study_s1_planner_ablation_dev_1",'
        '"scoring_identity":"signal_diag.planner_ablation_scoring",'
        '"denominator_derivation":"completion_slots"}\n',
        encoding="utf-8",
    )
    (destination / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        verify_planner_ablation_bundle(destination)


def test_t_cx280_seal_rejects_null_decision_protocol(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["decision_protocol"] = None
    with pytest.raises(ValueError, match="decision_protocol"):
        seal_planner_ablation_bundle(
            destination=tmp_path / "null_protocol",
            study_id=PLANNER_ABLATION_STUDY_ID,
            scoring_identity="signal_diag.planner_ablation_scoring",
            denominator_derivation="completion_slots",
            manifest=manifest,
        )


def test_t_cx280_seal_rejects_protocol_identity_mismatch(tmp_path: Path) -> None:
    manifest = _manifest()
    protocol = dict(manifest["decision_protocol"])  # type: ignore[arg-type]
    protocol["study_id"] = "study_foreign"
    manifest["decision_protocol"] = protocol
    with pytest.raises(ValueError, match="study_id mismatch"):
        seal_planner_ablation_bundle(
            destination=tmp_path / "bad_protocol",
            study_id=PLANNER_ABLATION_STUDY_ID,
            scoring_identity="signal_diag.planner_ablation_scoring",
            denominator_derivation="completion_slots",
            manifest=manifest,
        )


def test_t_cx280_verify_rejects_duplicate_checksum_lines(tmp_path: Path) -> None:
    destination = tmp_path / "dup"
    seal_planner_ablation_bundle(
        destination=destination,
        study_id=PLANNER_ABLATION_STUDY_ID,
        scoring_identity="signal_diag.planner_ablation_scoring",
        denominator_derivation="completion_slots",
        manifest=_manifest(),
    )
    seal_path = destination / "seal.sha256"
    seal_path.write_text(seal_path.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        verify_planner_ablation_bundle(destination)
