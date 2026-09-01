"""Checkpoint G/H sealing extensions (EV-T035)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from signal_diag.evaluation.external.manifest import (
    canonical_json_bytes,
    manifest_sha256,
)
from signal_diag.evaluation.external.models import (
    FinalSealInputs,
    ReferenceSummary,
    ReviewRecord,
    ReviewRound,
    ReviewTargets,
)
from signal_diag.evaluation.external.sealing import seal_final_external_test
from tests.evaluation.external.test_validation import (
    build_valid_manifest,
    materialize_manifest_assets,
)

ROUND1_START = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _reference_summary() -> ReferenceSummary:
    return ReferenceSummary(
        input_sha256="a" * 64,
        applicable=True,
        clipping_ratio=0.02,
        flat_top_detected=False,
        f0_hz=220.0,
        thd_percent=1.5,
        order_2_relative_amplitude=0.1,
    )


def _review_record(
    *,
    case_id: str,
    round_number: int,
    outcome: str,
    causal_faults: tuple[str, ...],
    confidence: str,
    reviewed_at: datetime,
) -> ReviewRecord:
    return ReviewRecord(
        review_alias=f"alias_{case_id}",
        case_id=case_id,
        round_number=round_number,  # type: ignore[arg-type]
        outcome=outcome,  # type: ignore[arg-type]
        causal_faults=causal_faults,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        applicability="applicable",
        reason_codes=(),
        reviewed_at_utc=reviewed_at,
    )


def _review_rounds(manifest) -> tuple[ReviewRound, ReviewRound]:
    round1_records: list[ReviewRecord] = []
    round2_records: list[ReviewRecord] = []
    summaries: dict[str, ReferenceSummary] = {}
    for index, case in enumerate(manifest.cases):
        outcome = (
            case.acceptable_outcomes[0] if case.acceptable_outcomes else "inconclusive"
        )
        round1_records.append(
            _review_record(
                case_id=case.case_id,
                round_number=1,
                outcome=outcome,
                causal_faults=case.causal_faults,
                confidence=case.confidence,
                reviewed_at=ROUND1_START + timedelta(hours=index),
            )
        )
        round2_records.append(
            _review_record(
                case_id=case.case_id,
                round_number=2,
                outcome=outcome,
                causal_faults=case.causal_faults,
                confidence=case.confidence,
                reviewed_at=ROUND1_START + timedelta(days=14, hours=index),
            )
        )
        summaries[case.case_id] = _reference_summary()
    return (
        ReviewRound(
            round_number=1,
            records=tuple(round1_records),
            reference_summaries=summaries,
        ),
        ReviewRound(round_number=2, records=tuple(round2_records)),
    )


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def sealed_inputs(repo_root: Path, tmp_path: Path) -> FinalSealInputs:
    manifest = build_valid_manifest()
    asset_root = tmp_path / "assets_root"
    manifest = materialize_manifest_assets(manifest, asset_root)
    round1, round2 = _review_rounds(manifest)
    return FinalSealInputs(
        manifest=manifest,
        asset_root=asset_root,
        repo_root=repo_root,
        checksum_file=repo_root
        / "docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256",
        round1=round1,
        round2=round2,
        review_targets=ReviewTargets(),
        sealed_at_utc=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
    )


def test_ev_t035_final_seal_is_write_once(
    sealed_inputs: FinalSealInputs,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "final_seal"
    seal = seal_final_external_test(sealed_inputs, destination)
    assert seal.case_count == 52
    assert seal.scoreable_case_count == 24
    assert destination.is_dir()
    assert (destination / "study_manifest.json").is_file()
    assert (destination / "scoreability_mask.json").is_file()
    assert (destination / "reference_summaries.jsonl").is_file()
    assert (destination / "review_agreement.json").is_file()
    assert (destination / "protected_assets.json").is_file()
    assert (destination / "seal.sha256").is_file()

    with pytest.raises(FileExistsError, match="destination already exists"):
        seal_final_external_test(sealed_inputs, destination)


def test_ev_t035_existing_run_output_blocks_sealing(
    sealed_inputs: FinalSealInputs,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "final_seal"
    destination.mkdir()
    (destination / "attempts.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="existing run output"):
        seal_final_external_test(sealed_inputs, destination)


def test_seal_requires_final_preflight_validity(
    sealed_inputs: FinalSealInputs,
    tmp_path: Path,
) -> None:
    leaked_case = sealed_inputs.manifest.cases[0].model_copy(
        update={"split": "validation"},
    )
    bad_manifest = sealed_inputs.manifest.model_copy(
        update={"cases": (leaked_case,) + sealed_inputs.manifest.cases[1:]},
    )
    bad_inputs = sealed_inputs.model_copy(update={"manifest": bad_manifest})
    destination = tmp_path / "bad_seal"
    with pytest.raises(ValueError, match="final preflight"):
        seal_final_external_test(bad_inputs, destination)


def test_seal_single_reviewer_mode_without_round2(
    sealed_inputs: FinalSealInputs,
    tmp_path: Path,
) -> None:
    single_inputs = sealed_inputs.model_copy(
        update={
            "review_mode": "single_reviewer_provenance_audit",
            "round2": None,
        }
    )
    destination = tmp_path / "single_reviewer_seal"
    seal = seal_final_external_test(single_inputs, destination)
    assert seal.case_count == 52
    agreement = json.loads(
        (destination / "review_agreement.json").read_text(encoding="utf-8")
    )
    assert agreement["evaluation_status"] == "not_evaluated"
    assert agreement["review_mode"] == "single_reviewer_provenance_audit"
    assert agreement["raw_outcome_agreement"] is None


def test_seal_writes_canonical_manifest_and_checksum(
    sealed_inputs: FinalSealInputs,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "final_seal"
    seal = seal_final_external_test(sealed_inputs, destination)
    manifest_bytes = (destination / "study_manifest.json").read_bytes()
    assert manifest_bytes == canonical_json_bytes(sealed_inputs.manifest)
    assert seal.manifest_sha256 == manifest_sha256(sealed_inputs.manifest)

    checksum_lines = (
        (destination / "seal.sha256").read_text(encoding="utf-8").splitlines()
    )
    assert checksum_lines
    for line in checksum_lines:
        digest, rel_path = line.split("  ", maxsplit=1)
        assert len(digest) == 64
        assert (destination / rel_path).is_file()

    agreement = json.loads(
        (destination / "review_agreement.json").read_text(encoding="utf-8")
    )
    assert agreement["raw_outcome_agreement"] == 1.0
