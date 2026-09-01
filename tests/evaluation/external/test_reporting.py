"""Checkpoint K — append-only external bundle reporting (EV-T047)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from signal_diag.evaluation.external.manifest import (
    canonical_json_bytes,
    manifest_sha256,
)
from signal_diag.evaluation.external.models import (
    SINGLE_REVIEWER_DISCLOSURE,
    ExternalAttemptRecord,
    ExternalProtectedAssetsAudit,
    ExternalProvenanceRecord,
    ExternalScoredRunArtifact,
    ExternalStudyReport,
    ExternalUnscoredSlotArtifact,
    ReferenceSummary,
    ReviewAgreement,
)
from signal_diag.evaluation.external.reporting import (
    verify_external_bundle,
    write_external_bundle,
)
from signal_diag.evaluation.external.scoring import (
    EXTERNAL_SCORING_ID,
    EXTERNAL_SCORING_VERSION,
    aggregate_external_scores,
    score_external_trace,
)
from tests.evaluation.conftest import (
    make_condition,
    make_evaluation_case,
    make_sufficient_set,
)
from tests.evaluation.external.conftest import (
    make_external_case,
    make_external_manifest,
)
from tests.evaluation.test_scoring import (
    _agent_trace,
    _claim,
    _evidence,
)

_UNKNOWN_CASE = make_external_case(
    case_id="1111111111111111",
    confidence="unknown",
    external_class="ambiguous",
    source_group="C",
    parent_master_id=None,
    transform=None,
)

SECRET_FIXTURE = "sk-leaked-credential"
_LOCAL_PATH = r"C:\Users\secret\private\external_wav\upstream.wav"
_REQUIRED_FILES = (
    "study_manifest.json",
    "provenance.jsonl",
    "reference_summaries.jsonl",
    "review_agreement.json",
    "attempts.jsonl",
    "runs.jsonl",
    "metrics.json",
    "strata.csv",
    "report.md",
    "protected_assets.json",
    "checksums.sha256",
)
_DATA_FILES = _REQUIRED_FILES[:-1]
_MARKDOWN_SECTIONS = (
    "Study",
    "Acceptance Status",
    "Aggregate Metrics",
    "Stratification",
    "Review Agreement",
    "Agent versus Fixed Pipeline",
    "Failures and Unscored Slots",
    "Licensing and Limitations",
)
_STARTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _trace_with_clipping_claim() -> object:
    condition = make_condition(
        condition_id="cond_primary",
        tool_name="detect_clipping",
        metric="clipping_ratio",
        comparator="gt",
        expected_value=0.01,
        supports_claims=("clipping",),
    )
    evaluation_case = make_evaluation_case(
        "clipping",
        case_id="case_external_trace",
        observable_conditions=(condition,),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_primary",
                condition_refs=("cond_primary",),
                supported_claims=("clipping",),
                acceptable_outcomes=("supported_fault",),
            ),
        ),
        causal_faults=("clipping",),
        acceptable_outcomes=("supported_fault",),
    )
    evidence = _evidence(
        evidence_id="ev_clip",
        call_id="call_000",
        tool_name="detect_clipping",
        metric="clipping_ratio",
        value=0.05,
    )
    return _agent_trace(
        evaluation_case,
        (
            {
                "kind": "tool",
                "tool_name": "detect_clipping",
                "evidence": (evidence,),
            },
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
            ),
        ),
        outcome="supported_fault",
    )


def _reference_summary() -> ReferenceSummary:
    return ReferenceSummary(
        input_sha256="a" * 64,
        applicable=True,
        clipping_ratio=0.05,
        flat_top_detected=True,
        f0_hz=440.0,
        thd_percent=2.5,
        order_2_relative_amplitude=0.1,
    )


def _attempt(
    *,
    execution_path: str,
    case_id: str,
    run_slot: int = 1,
    status: str = "behavior_result",
    error_code: str | None = None,
    error_message: str | None = None,
) -> ExternalAttemptRecord:
    return ExternalAttemptRecord(
        execution_path=execution_path,  # type: ignore[arg-type]
        case_id=case_id,
        run_slot=run_slot,
        attempt_index=1,
        status=status,  # type: ignore[arg-type]
        error_code=error_code,  # type: ignore[arg-type]
        error_message=error_message,
        started_at_utc=_STARTED,
        finished_at_utc=_STARTED + timedelta(milliseconds=12),
    )


def _make_external_study_report() -> ExternalStudyReport:
    strong = make_external_case(
        case_id="2222222222222222",
        confidence="strong_ground_truth",
        external_class="clipping",
        source_group="B",
        causal_faults=("clipping",),
        acceptable_outcomes=("supported_fault",),
    )
    unknown = make_external_case(
        case_id="1111111111111111",
        confidence="unknown",
        external_class="ambiguous",
        source_group="C",
        parent_master_id=None,
        transform=None,
    )
    manifest = make_external_manifest(cases=(strong, unknown))
    trace = _trace_with_clipping_claim()
    scores = (
        score_external_trace(strong, trace),  # type: ignore[arg-type]
        score_external_trace(unknown, trace),  # type: ignore[arg-type]
    )
    attempts = (
        _attempt(execution_path="agent", case_id=strong.case_id),
        _attempt(
            execution_path="agent",
            case_id=unknown.case_id,
            status="infrastructure_error",
            error_code="timeout",
            error_message=f"provider timeout api_key={SECRET_FIXTURE} path={_LOCAL_PATH}",
        ),
        _attempt(execution_path="fixed_pipeline", case_id=strong.case_id),
        _attempt(execution_path="fixed_pipeline", case_id=unknown.case_id),
    )
    aggregate = aggregate_external_scores((strong, unknown), scores, ())
    summaries = {
        strong.case_id: _reference_summary(),
        unknown.case_id: _reference_summary(),
    }
    provenance = (
        ExternalProvenanceRecord(
            case_id=strong.case_id,
            provenance_ref=strong.provenance_ref,
            source_recording_key=strong.source_recording_key,
            capture_configuration_key=strong.capture_configuration_key,
            original_sha256="b" * 64,
            derived_sha256=strong.wav_sha256,
            original_filename_evaluator_only="upstream_master.wav",
            redistribution_permitted=False,
        ),
        ExternalProvenanceRecord(
            case_id=unknown.case_id,
            provenance_ref=unknown.provenance_ref,
            source_recording_key=unknown.source_recording_key,
            capture_configuration_key=unknown.capture_configuration_key,
            original_sha256="c" * 64,
            derived_sha256=unknown.wav_sha256,
            redistribution_permitted=True,
        ),
    )
    return ExternalStudyReport(
        study_id=manifest.study_id,
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        seal_id="seal_" + "d" * 64,
        harness_status="external_validation_completed",
        target_status="meets_target",
        manifest=manifest,
        manifest_sha256=manifest_sha256(manifest),
        provenance=provenance,
        reference_summaries=summaries,
        review_agreement=ReviewAgreement(
            raw_outcome_agreement=0.90,
            causal_set_agreement=0.85,
            outcome_cohen_kappa=0.75,
            confidence_quadratic_kappa=0.72,
        ),
        attempts=attempts,
        scores=scores,
        traces=(),
        aggregate=aggregate,
        protected_assets=ExternalProtectedAssetsAudit(
            checksum_file="docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256",
            checksum_file_sha256="e" * 64,
        ),
    )


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _parse_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_jsonl(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8")
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines() if line]


def _walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item))
    return found


def _csv_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_bytes().decode("utf-8")
    assert text.endswith("\n")
    reader = csv.DictReader(io.StringIO(text), lineterminator="\n")
    return list(reader)


def test_ev_t047_required_files_and_checksums(tmp_path: Path) -> None:
    report = _make_external_study_report()
    paths = write_external_bundle(report, tmp_path / "bundle")
    dest = tmp_path / "bundle"
    names = tuple(path.name for path in paths)
    assert names == _REQUIRED_FILES
    assert tuple(sorted(child.name for child in dest.iterdir())) == tuple(
        sorted(_REQUIRED_FILES)
    )
    assert not any(path.suffix == ".wav" for path in dest.iterdir())

    for path in paths:
        raw = path.read_bytes()
        raw.decode("utf-8")
        assert b"\r" not in raw
        assert raw.endswith(b"\n")

    checksum_text = _read_text(dest / "checksums.sha256")
    checksum_lines = [line for line in checksum_text.split("\n") if line]
    assert len(checksum_lines) == len(_DATA_FILES)
    hashed: dict[str, str] = {}
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        hashed[name] = digest
    assert set(hashed) == set(_DATA_FILES)
    assert "checksums.sha256" not in hashed
    ordered_names = tuple(line.split("  ", 1)[1] for line in checksum_lines)
    assert ordered_names == tuple(sorted(_DATA_FILES))
    for name, digest in hashed.items():
        payload = (dest / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest

    manifest_bytes = canonical_json_bytes(report.manifest)
    assert (dest / "study_manifest.json").read_bytes() == manifest_bytes
    verify_external_bundle(dest)


def test_ev_t047_retains_failed_and_unscored_attempts(tmp_path: Path) -> None:
    report = _make_external_study_report()
    write_external_bundle(report, tmp_path / "bundle")
    dest = tmp_path / "bundle"
    attempts = _parse_jsonl(dest / "attempts.jsonl")
    runs = _parse_jsonl(dest / "runs.jsonl")
    assert len(attempts) == len(report.attempts)
    failed = [item for item in attempts if item["status"] != "behavior_result"]
    assert len(failed) == 1
    assert failed[0]["case_id"] == _UNKNOWN_CASE.case_id
    scored = [item for item in runs if item["record_type"] == "scored_run"]
    assert len(scored) == len(report.scores)
    ExternalScoredRunArtifact.model_validate(scored[0])
    unscored = [item for item in runs if item["record_type"] == "unscored_slot"]
    assert unscored
    assert any(item["status"] != "behavior_result" for item in attempts)


def test_ev_t047_unscored_slot_artifact_is_retained(tmp_path: Path) -> None:
    report = _make_external_study_report()
    failed_attempt = report.attempts[1]
    poisoned = report.model_copy(
        update={
            "scores": (report.scores[0],),
            "attempts": tuple(
                attempt for attempt in report.attempts if attempt.execution_path == "agent"
            ),
        }
    )
    write_external_bundle(poisoned, tmp_path / "bundle")
    runs = _parse_jsonl(tmp_path / "bundle" / "runs.jsonl")
    unscored = [item for item in runs if item["record_type"] == "unscored_slot"]
    assert len(unscored) == 1
    ExternalUnscoredSlotArtifact.model_validate(unscored[0])
    assert unscored[0]["case_id"] == failed_attempt.case_id


def test_ev_t047_destination_exists_is_rejected(tmp_path: Path) -> None:
    report = _make_external_study_report()
    dest = tmp_path / "bundle"
    write_external_bundle(report, dest)
    with pytest.raises(FileExistsError, match="destination already exists"):
        write_external_bundle(report, dest)


def test_ev_t047_redacts_secrets_and_local_paths(tmp_path: Path) -> None:
    report = _make_external_study_report()
    write_external_bundle(report, tmp_path / "bundle")
    dest = tmp_path / "bundle"
    combined = b"".join(path.read_bytes() for path in dest.iterdir()).decode("utf-8")
    assert SECRET_FIXTURE not in combined
    assert _LOCAL_PATH not in combined
    assert "upstream_master.wav" not in combined
    assert "Users" not in combined
    for name in _DATA_FILES:
        if name.endswith((".md", ".csv")):
            continue
        payload = (
            _read_text(dest / name)
            if name.endswith(".md")
            else _parse_json(dest / name)
            if name.endswith(".json")
            else _parse_jsonl(dest / name)
        )
        for text in _walk_strings(payload):
            assert SECRET_FIXTURE not in text
            assert _LOCAL_PATH not in text
            assert "\\" not in text


def test_ev_t047_report_markdown_sections_and_metrics(tmp_path: Path) -> None:
    report = _make_external_study_report()
    write_external_bundle(report, tmp_path / "bundle")
    markdown = _read_text(tmp_path / "bundle" / "report.md")
    for section in _MARKDOWN_SECTIONS:
        assert re.search(rf"^## {re.escape(section)}\s*$", markdown, re.MULTILINE)
    assert report.harness_status in markdown
    assert report.target_status in markdown
    assert EXTERNAL_SCORING_ID in markdown
    assert str(report.review_agreement.raw_outcome_agreement) in markdown
    metrics = _parse_json(tmp_path / "bundle" / "metrics.json")
    assert metrics["external_scoring_id"] == EXTERNAL_SCORING_ID
    assert metrics["external_scoring_version"] == EXTERNAL_SCORING_VERSION
    assert metrics["harness_status"] == report.harness_status
    assert metrics["target_status"] == report.target_status
    rows = _csv_rows(tmp_path / "bundle" / "strata.csv")
    assert rows
    assert {"dimension", "value", "metric_name", "numerator", "denominator"}.issubset(
        rows[0].keys()
    )


def test_ev_t039c_report_discloses_single_reviewer_limitation(tmp_path: Path) -> None:
    report = _make_external_study_report().model_copy(
        update={
            "review_agreement": ReviewAgreement(
                review_mode="single_reviewer_provenance_audit",
                evaluation_status="not_evaluated",
                disclosure=SINGLE_REVIEWER_DISCLOSURE,
            ),
        }
    )
    write_external_bundle(report, tmp_path / "bundle")
    markdown = _read_text(tmp_path / "bundle" / "report.md")
    assert "single reviewer" in markdown.lower()
    assert "not evaluated" in markdown.lower()
    assert SINGLE_REVIEWER_DISCLOSURE in markdown
