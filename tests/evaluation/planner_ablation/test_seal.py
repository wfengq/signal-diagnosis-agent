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
        "decision_protocol": {"n_unit": "scorable_slots"},
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
