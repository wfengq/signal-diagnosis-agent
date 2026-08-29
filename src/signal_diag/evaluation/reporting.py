"""Append-only official evaluation report bundle writer."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any

from signal_diag.evaluation.models import (
    AggregateMetrics,
    AttemptRecord,
    BenchmarkReport,
    RateMetric,
    RunScore,
    ScoredRunArtifact,
    UnscoredSlotArtifact,
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
_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key\s*[=:]\s*)\S+"
    r"|(?:authorization\s*[=:]\s*)\S+"
    r"|(?:bearer\s+)\S+"
    r"|\bsk-[A-Za-z0-9]+\b"
)
_PROVIDER_PAYLOAD_MARKERS = (
    '"choices"',
    '"provider_response"',
    '"raw_response"',
    '"response_body"',
    '"raw_body"',
    '"raw_provider_response"',
)
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "samples",
        "waveform",
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "password",
        "secret",
        "credentials",
        "access_token",
        "raw_response",
        "provider_response",
        "response_body",
        "raw_body",
        "raw_provider_response",
    }
)
_SLOT_KEY = tuple[str, str, int]


def write_benchmark_bundle(
    report: BenchmarkReport,
    output_dir: Path,
) -> tuple[Path, ...]:
    dest = output_dir / report.config.benchmark_id
    dest.mkdir(parents=True, exist_ok=False)
    artifacts = _run_artifacts(report)
    contents = {
        "benchmark_manifest.json": _json_line(_manifest_payload(report)).encode("utf-8"),
        "runs.jsonl": _runs_jsonl(artifacts),
        "metrics.json": _json_line(_metrics_payload(report)).encode("utf-8"),
        "case_summary.csv": _case_summary_csv(report).encode("utf-8"),
        "report.md": _report_markdown(report).encode("utf-8"),
    }
    for name in DATA_FILES:
        (dest / name).write_bytes(contents[name])
    checksum_lines = [
        f"{hashlib.sha256(contents[name]).hexdigest()}  {name}\n"
        for name in sorted(DATA_FILES)
    ]
    (dest / "checksums.sha256").write_bytes("".join(checksum_lines).encode("utf-8"))
    return tuple(dest / name for name in REQUIRED_FILES)


def _json_line(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _dump(value: object) -> object:
    return _reject_unsafe(_sanitize(value))


def _manifest_payload(report: BenchmarkReport) -> object:
    return _dump(
        {
            "config": report.config.model_dump(mode="json"),
            "config_fingerprint_sha256": report.config_fingerprint_sha256,
            "manifest": report.manifest.model_dump(mode="json"),
        }
    )


def _metrics_payload(report: BenchmarkReport) -> object:
    return _dump(
        {
            "harness_status": report.harness_status,
            "benchmark_status": report.benchmark_status,
            "target_status": report.target_status,
            "targets": report.targets.model_dump(mode="json"),
            "agent_metrics": _optional_model(report.agent_metrics),
            "baseline_metrics": _optional_model(report.baseline_metrics),
            "warnings": list(report.warnings),
        }
    )


def _optional_model(value: AggregateMetrics | None) -> object:
    if value is None:
        return None
    return value.model_dump(mode="json")


def _runs_jsonl(artifacts: tuple[ScoredRunArtifact | UnscoredSlotArtifact, ...]) -> bytes:
    if not artifacts:
        return b"\n"
    return "".join(
        _json_line(_dump(item.model_dump(mode="json"))) for item in artifacts
    ).encode("utf-8")


def _run_artifacts(
    report: BenchmarkReport,
) -> tuple[ScoredRunArtifact | UnscoredSlotArtifact, ...]:
    attempts_by_key: dict[_SLOT_KEY, list[AttemptRecord]] = {}
    for attempt in report.attempts:
        attempts_by_key.setdefault(_slot_key(attempt), []).append(attempt)
    traces = {_slot_key(trace): trace for trace in report.traces}
    artifacts: list[ScoredRunArtifact | UnscoredSlotArtifact] = []
    scored_keys: set[_SLOT_KEY] = set()
    for score in report.scores:
        key = _slot_key(score)
        scored_keys.add(key)
        artifacts.append(
            ScoredRunArtifact(
                trace=traces[key],
                score=score,
                attempts=tuple(attempts_by_key.get(key, ())),
            )
        )
    for key in sorted(k for k in attempts_by_key if k not in scored_keys):
        artifacts.append(
            UnscoredSlotArtifact(
                execution_path=key[0],  # type: ignore[arg-type]
                case_id=key[1],
                run_slot=key[2],
                attempts=tuple(attempts_by_key[key]),
            )
        )
    return tuple(artifacts)


def _slot_key(item: AttemptRecord | RunScore | Any) -> _SLOT_KEY:
    return (item.execution_path, item.case_id, item.run_slot)


def _case_summary_csv(report: BenchmarkReport) -> str:
    cases = {case.case_id: case for case in report.manifest.cases}
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER.split(","))
    for score in report.scores:
        case = cases[score.case_id]
        usage = score.provider_usage
        writer.writerow(
            [
                score.execution_path,
                score.case_id,
                case.split,
                case.category,
                score.run_slot,
                _csv_bool(score.causal_exact_set_correct),
                _csv_bool(score.outcome_correct),
                _csv_rate(score.grounded_claims, score.scored_claims),
                _csv_rate(score.unsupported_fault_claims, score.predicted_fault_claims),
                _csv_bool(score.first_tool_correct),
                _csv_rate(score.appropriate_replans, score.replan_opportunities),
                _csv_rate(score.unnecessary_tool_actions, score.tool_actions),
                _csv_bool(score.timely_stop),
                _csv_rate(score.correct_rule_actions, score.rule_action_opportunities),
                _csv_rate(
                    score.required_knowledge_actions,
                    score.required_knowledge_opportunities,
                ),
                _csv_rate(score.unnecessary_knowledge_actions, score.knowledge_actions),
                _csv_rate(score.cited_knowledge_actions, score.knowledge_actions),
                score.tool_actions,
                score.planner_calls,
                _csv_number(score.end_to_end_latency_ms),
                _csv_number(None if usage is None else usage.input_tokens),
                _csv_number(None if usage is None else usage.output_tokens),
                _csv_number(None if usage is None else usage.total_tokens),
                _csv_number(None if usage is None else usage.cost_usd),
                score.completion_reason,
                ";".join(score.failure_codes),
            ]
        )
    return _sanitize_text(buffer.getvalue())


def _csv_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _csv_number(value: float | None) -> str:
    if value is None:
        return ""
    return json.dumps(value, allow_nan=False)


def _csv_rate(numerator: int, denominator: int) -> str:
    return json.dumps(
        0.0 if denominator == 0 else numerator / denominator,
        allow_nan=False,
    )


def _report_markdown(report: BenchmarkReport) -> str:
    config = report.config
    lines = ["# Evaluation Report", ""]
    sections: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "Configuration",
            (
                f"- benchmark_id: {config.benchmark_id}",
                f"- config_fingerprint_sha256: {report.config_fingerprint_sha256}",
                f"- provider: {config.provider}",
                f"- model: {config.model}",
                f"- prompt_version: {config.prompt_version}",
                f"- repetitions: {config.repetitions}",
                f"- max_concurrency: {config.max_concurrency}",
            ),
        ),
        (
            "Dataset",
            (
                f"- dataset_id: {report.manifest.dataset_id}",
                f"- version: {report.manifest.version}",
                f"- case_count: {len(report.manifest.cases)}",
            ),
        ),
        (
            "Acceptance Status",
            (
                f"- harness_status: {report.harness_status}",
                f"- benchmark_status: {report.benchmark_status}",
                f"- target_status: {report.target_status}",
            ),
        ),
        ("Agent Metrics", _metrics_lines(report.agent_metrics)),
        ("Baseline Metrics", _metrics_lines(report.baseline_metrics)),
        ("Per-Case Variation", _variation_lines(report)),
        ("Failures", _failure_lines(report)),
        (
            "Limitations",
            (
                "V0.2 demonstration targets are not industry standards or SLAs.",
                "Demo rule thresholds are not product pass criteria.",
                "Official bundles are append-only and retain failures and run variation.",
            ),
        ),
    )
    for title, body in sections:
        lines.append(f"## {title}")
        lines.extend(body)
        lines.append("")
    return _sanitize_text("\n".join(lines).rstrip("\n") + "\n")


def _metrics_lines(metrics: AggregateMetrics | None) -> tuple[str, ...]:
    if metrics is None:
        return ("none",)
    return (
        f"- run_count: {metrics.run_count}",
        f"- causal_macro_f1: {metrics.causal_macro_f1}",
        f"- causal_exact_set_accuracy: {_rate_text(metrics.causal_exact_set_accuracy)}",
        f"- outcome_accuracy: {_rate_text(metrics.outcome_accuracy)}",
        f"- evidence_grounding_rate: {_rate_text(metrics.evidence_grounding_rate)}",
        f"- unsupported_claim_rate: {_rate_text(metrics.unsupported_claim_rate)}",
    )


def _rate_text(metric: RateMetric) -> str:
    return json.dumps(metric.value, allow_nan=False)


def _variation_lines(report: BenchmarkReport) -> tuple[str, ...]:
    lines: list[str] = []
    grouped: dict[str, list[RunScore]] = {}
    for score in report.scores:
        grouped.setdefault(score.case_id, []).append(score)
    for case_id, scores in grouped.items():
        lines.append(f"### {case_id}")
        for score in scores:
            lines.append(
                f"- {score.execution_path} run_slot {score.run_slot}: "
                f"outcome_correct={_csv_bool(score.outcome_correct)} "
                f"failure_codes={';'.join(score.failure_codes)}"
            )
    if not lines:
        return ("none",)
    return tuple(lines)


def _failure_lines(report: BenchmarkReport) -> tuple[str, ...]:
    lines: list[str] = [
        (
            f"- {score.execution_path} {score.case_id} run_slot {score.run_slot}: "
            f"{';'.join(score.failure_codes)}"
        )
        for score in report.scores
        if score.failure_codes
    ]
    scored_keys = {_slot_key(score) for score in report.scores}
    for artifact in _run_artifacts(report):
        if not isinstance(artifact, UnscoredSlotArtifact):
            continue
        labels: list[str] = []
        for attempt in artifact.attempts:
            if attempt.status == "behavior_result":
                continue
            if attempt.error_code:
                labels.append(attempt.error_code)
            labels.append(attempt.status)
        unique = tuple(dict.fromkeys(labels))
        text = ";".join(unique) if unique else "unscored"
        lines.append(
            f"- {artifact.execution_path} {artifact.case_id} run_slot {artifact.run_slot}: "
            f"{text}"
        )
    for attempt in report.attempts:
        if attempt.status == "behavior_result":
            continue
        if _slot_key(attempt) not in scored_keys:
            continue
        code = attempt.error_code or attempt.status
        lines.append(
            f"- {attempt.execution_path} {attempt.case_id} run_slot {attempt.run_slot}: "
            f"{attempt.status}/{code}"
        )
    if not lines:
        return ("none",)
    return tuple(lines)


def _sanitize(value: object) -> object:
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    return value


def _sanitize_text(text: str) -> str:
    redacted = _SECRET_PATTERN.sub("[redacted]", text).replace("\\", "/")
    lowered = redacted.lower()
    if "{" in redacted and any(
        marker in lowered for marker in _PROVIDER_PAYLOAD_MARKERS
    ):
        return "[redacted-provider-payload]"
    return redacted


def _reject_unsafe(value: object) -> object:
    module = getattr(type(value), "__module__", "")
    if module.startswith("numpy"):
        raise ValueError("numpy values cannot be serialized into a report bundle")
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_PAYLOAD_KEYS:
                raise ValueError(f"forbidden report field: {key}")
            _reject_unsafe(item)
        return value
    if isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe(item)
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if "{" in value and any(
            marker in lowered for marker in _PROVIDER_PAYLOAD_MARKERS
        ):
            raise ValueError("raw provider response cannot be serialized")
        return value
    return value
