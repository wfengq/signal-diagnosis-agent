"""T-CX139: contextual seal and verify."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.evaluation.contextual.manifest import build_slot_plan
from signal_diag.evaluation.contextual.models import (
    CONTEXTUAL_SCORING_ID,
    CONTEXTUAL_SCORING_VERSION,
    ContextualManifest,
)
from signal_diag.evaluation.contextual.sealing import (
    seal_contextual_bundle,
    verify_contextual_bundle,
)


def test_t_cx139_seal_and_verify_roundtrip(
    validation_manifest: ContextualManifest,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "seal"
    slots = [
        {
            "case_id": slot.case_id,
            "test_sha": slot.contextual.test_wav_sha256,
        }
        for slot in build_slot_plan(validation_manifest)
    ]
    seal_contextual_bundle(
        destination=destination,
        manifest=validation_manifest,
        wav_checksums={
            case.case_id: case.test_wav_sha256 for case in validation_manifest.cases
        },
        source_decisions={"reviewer": "single_reviewer_provenance_audit"},
        product_code_sha256="d" * 64,
        prompt_sha256="e" * 64,
        profile_s1_sha256="f" * 64,
        profile_contextual_sha256="a" * 64,
        scoring_identity=f"{CONTEXTUAL_SCORING_ID}:{CONTEXTUAL_SCORING_VERSION}",
        slot_plan=slots,
        execution_counters={"arms": 3, "cases": 20},
    )
    verify_contextual_bundle(destination)


def test_t_cx139b_verify_rejects_tamper(
    validation_manifest: ContextualManifest,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "seal2"
    seal_contextual_bundle(
        destination=destination,
        manifest=validation_manifest,
        wav_checksums={"x": "b" * 64},
        source_decisions={},
        product_code_sha256="d" * 64,
        prompt_sha256="e" * 64,
        profile_s1_sha256="f" * 64,
        profile_contextual_sha256="a" * 64,
        scoring_identity="id",
        slot_plan=[],
        execution_counters={"arms": 3},
    )
    (destination / "manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_contextual_bundle(destination)


def test_t_cx206_replacement_seal_binds_evaluation_harness(
    validation_manifest: ContextualManifest,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "seal3"
    seal_contextual_bundle(
        destination=destination,
        manifest=validation_manifest,
        wav_checksums={"x": "b" * 64},
        source_decisions={},
        product_code_sha256="d" * 64,
        evaluation_harness_sha256="c" * 64,
        prompt_sha256="e" * 64,
        profile_s1_sha256="f" * 64,
        profile_contextual_sha256="a" * 64,
        scoring_identity="id",
        slot_plan=[],
        execution_counters={"executed_arms": 0},
    )
    meta = json.loads((destination / "seal_meta.json").read_text(encoding="utf-8"))
    assert meta["evaluation_harness_sha256"] == "c" * 64
    verify_contextual_bundle(destination)


def test_t_cx207_active_replacement_seal_preserves_study_inputs() -> None:
    study = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "evaluations"
        / "v0_3"
        / "contextual"
        / "validation"
        / "study_v0_3_contextual_validation_1"
    )
    historical = study / "validation_seal"
    active = study / "validation_seal_v2"
    verify_contextual_bundle(historical)
    verify_contextual_bundle(active)
    for name in (
        "manifest.json",
        "wav_checksums.json",
        "source_decisions.json",
        "slot_plan.json",
    ):
        assert (historical / name).read_bytes() == (active / name).read_bytes()
    supersession = json.loads(
        (study / "VALIDATION_SEAL_SUPERSESSION.json").read_text(encoding="utf-8")
    )
    assert supersession["original_seal"]["executed_arms"] == 0
    assert supersession["replacement_seal"]["executed_arms"] == 0
    assert supersession["replacement_seal"]["status"] == "active_model_not_run"
