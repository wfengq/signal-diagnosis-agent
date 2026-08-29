"""Checkpoint M/N — append-only report bundle (T173–T174, report/artifact T181)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.evaluation import aggregate_benchmark, write_benchmark_bundle
from signal_diag.evaluation.models import (
    AttemptRecord,
    BaselineDiagnosis,
    BaselineRunResult,
    BenchmarkConfig,
    BenchmarkReport,
    EvaluationTrace,
    ProviderUsage,
    RateMetric,
    RunScore,
    ScoredRunArtifact,
    TargetBands,
    UnscoredSlotArtifact,
)
from tests.evaluation.conftest import make_dataset_manifest, make_evaluation_case

SECRET_FIXTURE = "sk-leaked-credential"
CSV_HEADER = (
    "execution_path,case_id,split,category,run_slot,causal_exact_set_correct,"
    "outcome_correct,evidence_grounding_rate,unsupported_claim_rate,"
    "first_tool_correct,observation_driven_replan_rate,"
    "unnecessary_tool_action_rate,timely_stop,applicable_rule_usage_rate,"
    "required_knowledge_usage_rate,unnecessary_knowledge_retrieval_rate,"
    "knowledge_citation_utilization_rate,tool_actions,planner_calls,"
    "end_to_end_latency_ms,input_tokens,output_tokens,total_tokens,cost_usd,"
    "completion_reason,failure_codes"
)
REQUIRED_FILES = (
    "benchmark_manifest.json",
    "runs.jsonl",
    "metrics.json",
    "case_summary.csv",
    "report.md",
    "checksums.sha256",
)
DATA_FILES = REQUIRED_FILES[:-1]
MARKDOWN_SECTIONS = (
    "Configuration",
    "Dataset",
    "Acceptance Status",
    "Agent Metrics",
    "Baseline Metrics",
    "Per-Case Variation",
    "Failures",
    "Limitations",
)
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "password",
        "secret",
        "credentials",
        "access_token",
    }
)
_PROMPT_SHA256 = "ab" * 32
_STARTED = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def _config(**overrides: Any) -> BenchmarkConfig:
    payload: dict[str, Any] = {
        "benchmark_id": "bench_task9_bundle",
        "dataset_id": "s1-distortion-synthetic",
        "dataset_version": "1.0.0",
        "rule_profile_id": "profile_s1_distortion",
        "rule_profile_version": "1.0.0-demo",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "prompt_version": "v0.2-s1-planner-4",
        "prompt_sha256": _PROMPT_SHA256,
        "model_parameters": {
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        },
        "sdk_versions": {"openai": "1.0.0"},
        "repetitions": 2,
        "max_infrastructure_retries": 2,
        "max_concurrency": 1,
        "started_at_utc": datetime(2026, 8, 29, 10, 0, tzinfo=UTC),
    }
    payload.update(overrides)
    return BenchmarkConfig(**payload)


def _agent_result(*, run_id: str, outcome: str) -> AgentRunResult:
    fault = "clipping" if outcome == "supported_fault" else "no_supported_fault"
    return AgentRunResult(
        run_id=run_id,
        status="success",
        diagnosis=StructuredDiagnosis(
            run_id=run_id,
            task_type="distortion_analysis",
            outcome=outcome,  # type: ignore[arg-type]
            claims=(
                DiagnosisClaim(
                    claim_id=f"claim_{run_id}",
                    fault_type=fault,  # type: ignore[arg-type]
                    statement=f"{fault} claim",
                ),
            ),
            confidence_label="high",
            limitations=(),
            termination_reason="planner_finished",
            tool_call_count=1,
        ),
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="planner_finished",
    )


def _baseline_result(*, run_id: str, outcome: str) -> BaselineRunResult:
    fault = "clipping" if outcome == "supported_fault" else "no_supported_fault"
    return BaselineRunResult(
        run_id=run_id,
        status="success",
        diagnosis=BaselineDiagnosis(
            run_id=run_id,
            outcome=outcome,  # type: ignore[arg-type]
            claims=(
                DiagnosisClaim(
                    claim_id=f"claim_{run_id}",
                    fault_type=fault,  # type: ignore[arg-type]
                    statement=f"{fault} claim",
                ),
            ),
            confidence_label="medium",
            tool_call_count=2,
            rule_evaluation_batches=(),
        ),
        observations=(),
        evidence=(),
        tool_history=(),
        completion_reason="baseline_completed",
        rule_evaluation_batches=(),
    )


def _trace(
    *,
    case_id: str,
    run_slot: int,
    execution_path: str,
    config: BenchmarkConfig,
    result: AgentRunResult | BaselineRunResult,
    provider_usage: ProviderUsage | None = None,
) -> EvaluationTrace:
    return EvaluationTrace(
        trace_id=f"trace_{execution_path}_{case_id}_{run_slot:02d}",
        case_id=case_id,
        run_slot=run_slot,
        execution_path=execution_path,  # type: ignore[arg-type]
        config=config,
        events=(),
        result=result,
        provider_usage=provider_usage,
    )


def _score(
    trace: EvaluationTrace,
    *,
    expected_faults: tuple[str, ...] = (),
    predicted_faults: tuple[str, ...] = (),
    acceptable_outcomes: tuple[str, ...] = ("supported_fault",),
    predicted_outcome: str = "supported_fault",
    causal_exact_set_correct: bool = True,
    outcome_correct: bool = True,
    grounded_claims: int = 1,
    scored_claims: int = 1,
    unsupported_fault_claims: int = 0,
    predicted_fault_claims: int = 1,
        first_tool_correct: bool | None = True,
        timely_stop: bool | None = True,
        tool_actions: int = 2,
        planner_calls: int = 3,
        appropriate_replans: int = 0,
        replan_opportunities: int = 0,
        unnecessary_tool_actions: int = 0,
        correct_rule_actions: int = 0,
        rule_action_opportunities: int = 0,
        required_knowledge_actions: int = 0,
        required_knowledge_opportunities: int = 0,
        unnecessary_knowledge_actions: int = 0,
        knowledge_actions: int = 0,
        cited_knowledge_actions: int = 0,
        failure_codes: tuple[str, ...] = (),
        completion_reason: str = "planner_finished",
        provider_usage: ProviderUsage | None = None,
    ) -> RunScore:
        return RunScore(
            trace_id=trace.trace_id,
            case_id=trace.case_id,
            run_slot=trace.run_slot,
            execution_path=trace.execution_path,
            expected_faults=expected_faults,  # type: ignore[arg-type]
            predicted_faults=predicted_faults,  # type: ignore[arg-type]
            acceptable_outcomes=acceptable_outcomes,  # type: ignore[arg-type]
            predicted_outcome=predicted_outcome,  # type: ignore[arg-type]
            causal_exact_set_correct=causal_exact_set_correct,
            outcome_correct=outcome_correct,
            grounded_claims=grounded_claims,
            scored_claims=scored_claims,
            unsupported_fault_claims=unsupported_fault_claims,
            predicted_fault_claims=predicted_fault_claims,
            first_tool_correct=first_tool_correct,
            appropriate_replans=appropriate_replans,
            replan_opportunities=replan_opportunities,
            unnecessary_tool_actions=unnecessary_tool_actions,
            tool_actions=tool_actions,
            timely_stop=timely_stop,
            correct_rule_actions=correct_rule_actions,
            rule_action_opportunities=rule_action_opportunities,
            required_knowledge_actions=required_knowledge_actions,
            required_knowledge_opportunities=required_knowledge_opportunities,
            unnecessary_knowledge_actions=unnecessary_knowledge_actions,
            knowledge_actions=knowledge_actions,
            cited_knowledge_actions=cited_knowledge_actions,
            planner_calls=planner_calls,
            provider_usage=provider_usage,
            completion_reason=completion_reason,  # type: ignore[arg-type]
            failure_codes=failure_codes,
        )


def _attempt(
    *,
    execution_path: str,
    case_id: str,
    run_slot: int,
    latency_ms: float = 12.0,
    attempt_index: int = 1,
    status: str = "behavior_result",
    error_code: str | None = None,
    error_message: str | None = None,
) -> AttemptRecord:
    return AttemptRecord(
        execution_path=execution_path,  # type: ignore[arg-type]
        case_id=case_id,
        run_slot=run_slot,
        attempt_index=attempt_index,
        status=status,  # type: ignore[arg-type]
        error_code=error_code,  # type: ignore[arg-type]
        error_message=error_message,
        started_at_utc=_STARTED,
        finished_at_utc=_STARTED + timedelta(milliseconds=latency_ms),
    )


def _make_report() -> BenchmarkReport:
    config = _config()
    clip = make_evaluation_case("clipping", case_id="case_held_clip_01", split="held_out")
    clean = make_evaluation_case("clean", case_id="case_held_clean_01", split="held_out")
    usage = ProviderUsage(
        input_tokens=11,
        output_tokens=5,
        total_tokens=16,
        cost_usd=0.002,
    )
    clip_t1 = _trace(
        case_id=clip.case_id,
        run_slot=1,
        execution_path="agent",
        config=config,
        result=_agent_result(run_id="run_clip_01", outcome="supported_fault"),
        provider_usage=usage,
    )
    clip_t2 = _trace(
        case_id=clip.case_id,
        run_slot=2,
        execution_path="agent",
        config=config,
        result=_agent_result(run_id="run_clip_02", outcome="supported_fault"),
    )
    clean_t1 = _trace(
        case_id=clean.case_id,
        run_slot=1,
        execution_path="agent",
        config=config,
        result=_agent_result(run_id="run_clean_01", outcome="no_supported_fault"),
    )
    clip_b1 = _trace(
        case_id=clip.case_id,
        run_slot=1,
        execution_path="fixed_pipeline",
        config=config,
        result=_baseline_result(run_id="baseline_clip_01", outcome="supported_fault"),
    )
    clean_b1 = _trace(
        case_id=clean.case_id,
        run_slot=1,
        execution_path="fixed_pipeline",
        config=config,
        result=_baseline_result(
            run_id="baseline_clean_01", outcome="no_supported_fault"
        ),
    )
    traces = (clip_t1, clip_t2, clean_t1, clip_b1, clean_b1)
    scores = (
        _score(
            clip_t1,
            expected_faults=("clipping",),
            predicted_faults=("clipping",),
            provider_usage=usage,
        ),
        _score(
            clip_t2,
            expected_faults=("clipping",),
            predicted_faults=("clipping", "harmonic_distortion"),
            causal_exact_set_correct=False,
            unsupported_fault_claims=1,
            predicted_fault_claims=2,
            first_tool_correct=False,
            failure_codes=("unsupported_fault_claim", "exact_set_mismatch"),
        ),
        _score(
            clean_t1,
            expected_faults=(),
            predicted_faults=(),
            acceptable_outcomes=("no_supported_fault",),
            predicted_outcome="no_supported_fault",
            predicted_fault_claims=0,
        ),
        _score(
            clip_b1,
            expected_faults=("clipping",),
            predicted_faults=("clipping",),
            first_tool_correct=None,
            timely_stop=None,
            planner_calls=0,
            completion_reason="baseline_completed",
        ),
        _score(
            clean_b1,
            expected_faults=(),
            predicted_faults=(),
            acceptable_outcomes=("no_supported_fault",),
            predicted_outcome="no_supported_fault",
            predicted_fault_claims=0,
            first_tool_correct=None,
            timely_stop=None,
            planner_calls=0,
            completion_reason="baseline_completed",
        ),
    )
    attempts = (
        _attempt(execution_path="agent", case_id=clip.case_id, run_slot=1),
        _attempt(execution_path="agent", case_id=clip.case_id, run_slot=2),
        _attempt(execution_path="agent", case_id=clean.case_id, run_slot=1),
        _attempt(
            execution_path="agent",
            case_id=clean.case_id,
            run_slot=2,
            status="infrastructure_error",
            error_code="timeout",
            error_message=f"provider timeout api_key={SECRET_FIXTURE}",
        ),
        _attempt(execution_path="fixed_pipeline", case_id=clip.case_id, run_slot=1),
        _attempt(execution_path="fixed_pipeline", case_id=clean.case_id, run_slot=1),
    )
    return aggregate_benchmark(
        make_dataset_manifest(cases=(clip, clean)),
        traces,
        scores,
        attempts,
        config,
        TargetBands(),
        harness_status="accepted",
    )


def _bundle_dir(tmp_path: Path, report: BenchmarkReport) -> Path:
    return tmp_path / report.config.benchmark_id


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _parse_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _finite_numbers(value: Any) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        assert math.isfinite(value)
        return
    if isinstance(value, dict):
        for item in value.values():
            _finite_numbers(item)
        return
    if isinstance(value, list):
        for item in value:
            _finite_numbers(item)


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


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _csv_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_bytes().decode("utf-8")
    assert text.endswith("\n")
    reader = csv.DictReader(io.StringIO(text), lineterminator="\n")
    return list(reader)


def test_t173_report_representation_agreement(tmp_path: Path) -> None:
    report = _make_report()
    paths = write_benchmark_bundle(report, tmp_path)
    dest = _bundle_dir(tmp_path, report)
    names = tuple(path.name for path in paths)
    assert names == REQUIRED_FILES
    assert tuple(sorted(child.name for child in dest.iterdir())) == tuple(
        sorted(REQUIRED_FILES)
    )

    for path in paths:
        raw = path.read_bytes()
        raw.decode("utf-8")
        assert b"\r" not in raw
        assert raw.endswith(b"\n")

    manifest = _parse_json(dest / "benchmark_manifest.json")
    metrics = _parse_json(dest / "metrics.json")
    artifacts = _parse_jsonl(dest / "runs.jsonl")
    _finite_numbers(manifest)
    _finite_numbers(metrics)
    for artifact in artifacts:
        _finite_numbers(artifact)

    csv_text = _read_text(dest / "case_summary.csv")
    header_line = csv_text.split("\n", 1)[0]
    assert header_line == CSV_HEADER
    rows = _csv_rows(dest / "case_summary.csv")
    assert len(rows) == len(report.scores)

    scored = [item for item in artifacts if item["record_type"] == "scored_run"]
    unscored = [item for item in artifacts if item["record_type"] == "unscored_slot"]
    assert len(scored) == len(report.scores)
    assert len(unscored) == 1
    assert len(artifacts) == len(scored) + len(unscored)
    assert unscored[0]["case_id"] == "case_held_clean_01"
    assert unscored[0]["run_slot"] == 2
    assert unscored[0]["execution_path"] == "agent"
    ScoredRunArtifact.model_validate(scored[0])
    UnscoredSlotArtifact.model_validate(unscored[0])

    assert metrics["harness_status"] == report.harness_status
    assert metrics["benchmark_status"] == report.benchmark_status
    assert metrics["target_status"] == report.target_status
    assert metrics["agent_metrics"]["run_count"] == report.agent_metrics.run_count
    assert metrics["baseline_metrics"]["run_count"] == report.baseline_metrics.run_count
    assert metrics["agent_metrics"]["causal_macro_f1"] == pytest.approx(
        report.agent_metrics.causal_macro_f1
    )
    assert manifest["config_fingerprint_sha256"] == report.config_fingerprint_sha256
    assert manifest["config"]["benchmark_id"] == report.config.benchmark_id
    assert len(manifest["manifest"]["cases"]) == len(report.manifest.cases)

    markdown = _read_text(dest / "report.md")
    for section in MARKDOWN_SECTIONS:
        assert re.search(rf"^## {re.escape(section)}\s*$", markdown, re.MULTILINE)

    clip_rows = [row for row in rows if row["case_id"] == "case_held_clip_01"]
    agent_clip_slots = {
        int(row["run_slot"])
        for row in clip_rows
        if row["execution_path"] == "agent"
    }
    assert agent_clip_slots == {1, 2}
    failed_rows = [row for row in rows if row["failure_codes"]]
    assert any("exact_set_mismatch" in row["failure_codes"] for row in failed_rows)
    assert "exact_set_mismatch" in markdown
    assert "case_held_clip_01" in markdown
    assert "run_slot" in markdown or "slot" in markdown.lower() or "2" in markdown

    by_key = {(score.execution_path, score.case_id, score.run_slot): score for score in report.scores}
    cases = {case.case_id: case for case in report.manifest.cases}
    for row in rows:
        score = by_key[(row["execution_path"], row["case_id"], int(row["run_slot"]))]
        case = cases[score.case_id]
        assert row["split"] == case.split
        assert row["category"] == case.category
        assert row["causal_exact_set_correct"].lower() == str(score.causal_exact_set_correct).lower()
        assert row["outcome_correct"].lower() == str(score.outcome_correct).lower()
        assert float(row["evidence_grounding_rate"]) == pytest.approx(
            _rate(score.grounded_claims, score.scored_claims)
        )
        assert float(row["unsupported_claim_rate"]) == pytest.approx(
            _rate(score.unsupported_fault_claims, score.predicted_fault_claims)
        )
        assert float(row["observation_driven_replan_rate"]) == pytest.approx(
            _rate(score.appropriate_replans, score.replan_opportunities)
        )
        assert row["failure_codes"] == ";".join(score.failure_codes)
        assert row["completion_reason"] == score.completion_reason
        assert int(row["tool_actions"]) == score.tool_actions
        assert int(row["planner_calls"]) == score.planner_calls

    assert report.agent_metrics is not None
    assert report.baseline_metrics is not None
    assert str(report.agent_metrics.run_count) in markdown
    assert str(report.baseline_metrics.run_count) in markdown
    assert report.harness_status in markdown
    assert report.benchmark_status in markdown
    assert report.target_status in markdown


def test_t174_immutable_report_bundle_and_checksums(tmp_path: Path) -> None:
    report = _make_report()
    paths = write_benchmark_bundle(report, tmp_path)
    dest = _bundle_dir(tmp_path, report)
    checksum_path = dest / "checksums.sha256"
    assert checksum_path in paths
    checksum_text = _read_text(checksum_path)
    checksum_lines = [line for line in checksum_text.split("\n") if line]
    assert len(checksum_lines) == 5
    hashed: dict[str, str] = {}
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        hashed[name] = digest
    assert set(hashed) == set(DATA_FILES)
    assert "checksums.sha256" not in hashed
    ordered_names = tuple(name for name, _digest in ((line.split("  ", 1)[1], line) for line in checksum_lines))
    assert ordered_names == tuple(sorted(DATA_FILES))
    for name, digest in hashed.items():
        payload = (dest / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest

    markdown = _read_text(dest / "report.md")
    assert "unsupported_fault_claim" in markdown or "exact_set_mismatch" in markdown
    csv_text = _read_text(dest / "case_summary.csv")
    assert "exact_set_mismatch" in csv_text
    assert csv_text.count("case_held_clip_01") >= 2

    with pytest.raises(FileExistsError):
        write_benchmark_bundle(report, tmp_path)


def test_t181_report_artifact_safety(tmp_path: Path) -> None:
    report = _make_report()
    write_benchmark_bundle(report, tmp_path)
    dest = _bundle_dir(tmp_path, report)
    combined = b"".join(path.read_bytes() for path in dest.iterdir()).decode("utf-8")
    assert SECRET_FIXTURE not in combined
    assert '"raw_response"' not in combined
    assert '"waveform"' not in combined
    assert "numpy." not in combined
    assert "ndarray" not in combined
    assert "float64" not in combined

    for name in ("benchmark_manifest.json", "metrics.json"):
        payload = _parse_json(dest / name)
        for text in _walk_strings(payload):
            assert "\\" not in text
            assert SECRET_FIXTURE not in text
    for artifact in _parse_jsonl(dest / "runs.jsonl"):
        for text in _walk_strings(artifact):
            assert "\\" not in text
            assert SECRET_FIXTURE not in text
            assert "raw_response" not in text
        assert "waveform" not in json.dumps(artifact)

    markdown = _read_text(dest / "report.md")
    csv_text = _read_text(dest / "case_summary.csv")
    assert "\\" not in markdown
    assert "\\" not in csv_text
    assert SECRET_FIXTURE not in markdown
    assert SECRET_FIXTURE not in csv_text

    field_names = set(BenchmarkReport.model_fields)
    field_names.update(BenchmarkConfig.model_fields)
    field_names.update(RateMetric.model_fields)
    assert field_names.isdisjoint(FORBIDDEN_FIELD_NAMES)
    dumped = json.dumps(report.config.model_dump(mode="json"), sort_keys=True)
    assert "api_key" not in dumped
