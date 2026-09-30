"""T-CX280: offline planner-ablation sealing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.evaluation.planner_ablation.identity import PLANNER_ABLATION_STUDY_ID
from signal_diag.evaluation.planner_ablation.sealing import (
    seal_planner_ablation_bundle,
    verify_planner_ablation_bundle,
)


def test_t_cx280_seal_and_verify_round_trip(tmp_path: Path) -> None:
    destination = tmp_path / "seal_bundle"
    seal_planner_ablation_bundle(
        destination=destination,
        study_id=PLANNER_ABLATION_STUDY_ID,
        scoring_identity="signal_diag.planner_ablation_scoring",
        denominator_derivation="completion_slots",
        manifest={"study_id": PLANNER_ABLATION_STUDY_ID, "slots": 48},
    )
    verify_planner_ablation_bundle(destination)


def test_t_cx280_seal_rejects_foreign_study(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="foreign study"):
        seal_planner_ablation_bundle(
            destination=tmp_path / "bad",
            study_id="study_foreign",
            scoring_identity="signal_diag.planner_ablation_scoring",
            denominator_derivation="completion_slots",
            manifest={},
        )
