"""Append-only external WAV validity study bundle writer."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from io import StringIO
from pathlib import Path

from signal_diag.evaluation.external.manifest import canonical_json_bytes
from signal_diag.evaluation.external.models import (
    ExternalAttemptRecord,
    ExternalRunScore,
    ExternalScoredRunArtifact,
    ExternalStudyReport,
    ExternalUnscoredSlotArtifact,
)

REQUIRED_FILES = (
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
DATA_FILES = REQUIRED_FILES[:-1]
_STRATA_HEADER = (
    "dimension",
    "value",
    "metric_name",
    "numerator",
    "denominator",
    "exclusions",
    "rate_value",
)
_SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key\s*[=:]\s*)\S+"
    r"|(?:authorization\s*[=:]\s*)\S+"
    r"|(?:bearer\s+)\S+"
    r"|\bsk-[A-Za-z0-9]+\b"
)
_LOCAL_PATH_PATTERN = re.compile(
    r"(?i)(?:[A-Za-z]:\\|/Users/|/home/)[^\s\"']+"
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


def write_external_bundle(
    report: ExternalStudyReport,
    destination: Path,
) -> tuple[Path, ...]:
    if destination.exists():
        raise FileExistsError("destination already exists")
    destination.mkdir(parents=True, exist_ok=False)
    artifacts = _run_artifacts(report)
    contents = {
        "study_manifest.json": canonical_json_bytes(report.manifest),
        "provenance.jsonl": _provenance_jsonl(report),
        "reference_summaries.jsonl": _reference_summaries_jsonl(report),
        "review_agreement.json": _json_line(
            _dump(report.review_agreement.model_dump(mode="json"))
        ).encode("utf-8"),
        "attempts.jsonl": _attempts_jsonl(report.attempts),
        "runs.jsonl": _runs_jsonl(artifacts),
        "metrics.json": _json_line(_metrics_payload(report)).encode("utf-8"),
        "strata.csv": _strata_csv(report).encode("utf-8"),
        "report.md": _report_markdown(report).encode("utf-8"),
        "protected_assets.json": _json_line(
            _dump(report.protected_assets.model_dump(mode="json"))
        ).encode("utf-8"),
    }
    for name in DATA_FILES:
        (destination / name).write_bytes(contents[name])
    checksum_lines = [
        f"{hashlib.sha256(contents[name]).hexdigest()}  {name}\n"
        for name in sorted(DATA_FILES)
    ]
    (destination / "checksums.sha256").write_bytes("".join(checksum_lines).encode("utf-8"))
    return tuple(destination / name for name in REQUIRED_FILES)


def verify_external_bundle(bundle: Path) -> None:
    if not bundle.is_dir():
        raise FileNotFoundError(f"bundle directory not found: {bundle}")
    present = {path.name for path in bundle.iterdir() if path.is_file()}
    missing = [name for name in REQUIRED_FILES if name not in present]
    if missing:
        raise ValueError(f"missing bundle file: {missing[0]}")
    extra = sorted(name for name in present if name not in REQUIRED_FILES)
    if extra:
        raise ValueError(f"unexpected bundle file: {extra[0]}")
    if any(name.endswith(".wav") for name in present):
        raise ValueError("bundle must not contain original third-party audio")
    checksum_path = bundle / "checksums.sha256"
    checksum_text = checksum_path.read_text(encoding="utf-8")
    if "\r" in checksum_text:
        raise ValueError("checksums.sha256 must use LF line endings")
    lines = [line for line in checksum_text.split("\n") if line]
    if len(lines) != len(DATA_FILES):
        raise ValueError("checksum count mismatch")
    ordered_names: list[str] = []
    for line in lines:
        digest, name = line.split("  ", 1)
        if len(digest) != 64 or not all(ch in "0123456789abcdef" for ch in digest):
            raise ValueError(f"invalid checksum digest for {name}")
        ordered_names.append(name)
        payload = (bundle / name).read_bytes()
        if b"\r" in payload:
            raise ValueError(f"{name} must use LF line endings")
        if not payload.endswith(b"\n"):
            raise ValueError(f"{name} must end with a newline")
        payload.decode("utf-8")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError(f"checksum mismatch for {name}")
        _verify_redacted_file(name, payload)
    if ordered_names != sorted(DATA_FILES):
        raise ValueError("checksum lines must be sorted by filename")
    if "checksums.sha256" in ordered_names:
        raise ValueError("checksums.sha256 must not hash itself")


def _verify_redacted_file(name: str, payload: bytes) -> None:
    text = payload.decode("utf-8")
    if _SECRET_PATTERN.search(text):
        raise ValueError(f"secret material found in {name}")
    if _LOCAL_PATH_PATTERN.search(text):
        raise ValueError(f"local path found in {name}")
    if name.endswith((".json", ".jsonl")) and '"choices"' in text and '"message"' in text:
        raise ValueError(f"provider payload found in {name}")


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


def _provenance_jsonl(report: ExternalStudyReport) -> bytes:
    if not report.provenance:
        return b"\n"
    lines: list[str] = []
    for record in report.provenance:
        payload = record.model_dump(mode="json")
        payload.pop("original_filename_evaluator_only", None)
        lines.append(_json_line(_dump(payload)))
    return "".join(lines).encode("utf-8")


def _reference_summaries_jsonl(report: ExternalStudyReport) -> bytes:
    if not report.reference_summaries:
        return b"\n"
    return "".join(
        _json_line(
            _dump(
                {
                    "case_id": case_id,
                    "summary": summary.model_dump(mode="json"),
                }
            )
        )
        for case_id, summary in sorted(report.reference_summaries.items())
    ).encode("utf-8")


def _attempts_jsonl(attempts: tuple[ExternalAttemptRecord, ...]) -> bytes:
    if not attempts:
        return b"\n"
    return "".join(
        _json_line(_dump(attempt.model_dump(mode="json"))) for attempt in attempts
    ).encode("utf-8")


def _runs_jsonl(
    artifacts: tuple[ExternalScoredRunArtifact | ExternalUnscoredSlotArtifact, ...],
) -> bytes:
    if not artifacts:
        return b"\n"
    return "".join(
        _json_line(_dump(artifact.model_dump(mode="json"))) for artifact in artifacts
    ).encode("utf-8")


def _metrics_payload(report: ExternalStudyReport) -> object:
    aggregate = report.aggregate.model_dump(mode="json")
    return _dump(
        {
            "study_id": report.study_id,
            "dataset_id": report.dataset_id,
            "dataset_version": report.dataset_version,
            "seal_id": report.seal_id,
            "manifest_sha256": report.manifest_sha256,
            "harness_status": report.harness_status,
            "target_status": report.target_status,
            "external_scoring_id": report.aggregate.external_scoring_id,
            "external_scoring_version": report.aggregate.external_scoring_version,
            "aggregate": aggregate,
        }
    )


def _strata_csv(report: ExternalStudyReport) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_STRATA_HEADER)
    for stratum in (*report.aggregate.strata, *report.aggregate.master_cluster_summaries):
        for metric in stratum.metrics:
            writer.writerow(
                [
                    stratum.dimension,
                    stratum.value,
                    metric.metric_name,
                    metric.numerator,
                    metric.denominator,
                    metric.exclusions,
                    "" if metric.value is None else json.dumps(metric.value, allow_nan=False),
                ]
            )
    return _sanitize_text(buffer.getvalue())


def _report_markdown(report: ExternalStudyReport) -> str:
    aggregate = report.aggregate
    lines = ["# External WAV Validity Study Report", ""]
    sections: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "Study",
            (
                f"- study_id: {report.study_id}",
                f"- dataset_id: {report.dataset_id}",
                f"- dataset_version: {report.dataset_version}",
                f"- seal_id: {report.seal_id}",
                f"- manifest_sha256: {report.manifest_sha256}",
                f"- case_count: {len(report.manifest.cases)}",
                f"- external_scoring_id: {report.aggregate.external_scoring_id}",
                f"- external_scoring_version: {report.aggregate.external_scoring_version}",
            ),
        ),
        (
            "Acceptance Status",
            (
                f"- harness_status: {report.harness_status}",
                f"- target_status: {report.target_status}",
            ),
        ),
        (
            "Aggregate Metrics",
            _aggregate_metric_lines(aggregate),
        ),
        (
            "Stratification",
            _strata_lines(aggregate),
        ),
        (
            "Review Agreement",
            (
                f"- raw_outcome_agreement: {report.review_agreement.raw_outcome_agreement}",
                f"- causal_set_agreement: {report.review_agreement.causal_set_agreement}",
                f"- outcome_cohen_kappa: {report.review_agreement.outcome_cohen_kappa}",
                f"- confidence_quadratic_kappa: {report.review_agreement.confidence_quadratic_kappa}",
            ),
        ),
        (
            "Agent versus Fixed Pipeline",
            _execution_path_lines(report),
        ),
        (
            "Failures and Unscored Slots",
            _failure_lines(report),
        ),
        (
            "Licensing and Limitations",
            (
                (
                    "Public real-capture, controlled paired distortions, and licensed "
                    "out-of-domain audio only."
                ),
                "V0.2 demonstration targets are not industry standards or SLAs.",
                "Original third-party audio is excluded from append-only bundles.",
                "No official benchmark or production-readiness claim is implied.",
            ),
        ),
    )
    for title, body in sections:
        lines.append(f"## {title}")
        lines.extend(body)
        lines.append("")
    return _sanitize_text("\n".join(lines).rstrip("\n") + "\n")


def _aggregate_metric_lines(aggregate: object) -> tuple[str, ...]:
    from signal_diag.evaluation.external.models import ExternalAggregate
    from signal_diag.evaluation.models import RateMetric

    if not isinstance(aggregate, ExternalAggregate):
        raise TypeError("expected ExternalAggregate")
    lines: list[str] = []
    for name in (
        "outcome_accuracy",
        "causal_exact_set_accuracy",
        "evidence_grounding",
        "unsupported_same_run_claim_rate",
        "unnecessary_tool_action_rate",
        "inconclusive_appropriateness",
        "positive_causal_claims_on_unscored",
        "scoreable_coverage",
    ):
        metric = getattr(aggregate, name)
        if metric is None:
            lines.append(f"- {name}: none")
            continue
        if isinstance(metric, RateMetric):
            lines.append(
                f"- {name}: {metric.numerator}/{metric.denominator} "
                f"(value={metric.value})"
            )
        else:
            lines.append(f"- {name}: {metric}")
    if aggregate.causal_macro_f1 is not None:
        lines.append(f"- causal_macro_f1: {aggregate.causal_macro_f1}")
    return tuple(lines) or ("none",)


def _strata_lines(aggregate: object) -> tuple[str, ...]:
    from signal_diag.evaluation.external.models import ExternalAggregate

    if not isinstance(aggregate, ExternalAggregate):
        raise TypeError("expected ExternalAggregate")
    lines = [
        f"- {stratum.dimension}={stratum.value}: "
        + ", ".join(
            f"{metric.metric_name} {metric.numerator}/{metric.denominator}"
            for metric in stratum.metrics
        )
        for stratum in aggregate.strata
    ]
    return tuple(lines) or ("none",)


def _execution_path_lines(report: ExternalStudyReport) -> tuple[str, ...]:
    agent_scores = [score for score in report.scores if score.execution_path == "agent"]
    baseline_scores = [
        score for score in report.scores if score.execution_path == "fixed_pipeline"
    ]
    return (
        f"- agent scored runs: {len(agent_scores)}",
        f"- fixed_pipeline scored runs: {len(baseline_scores)}",
        f"- total attempts retained: {len(report.attempts)}",
    )


def _failure_lines(report: ExternalStudyReport) -> tuple[str, ...]:
    lines: list[str] = []
    scored_keys = {_slot_key(score) for score in report.scores}
    for attempt in report.attempts:
        key = _slot_key(attempt)
        if attempt.status == "behavior_result" and key in scored_keys:
            continue
        code = attempt.error_code or attempt.status
        lines.append(
            f"- {attempt.execution_path} {attempt.case_id} run_slot {attempt.run_slot}: "
            f"{attempt.status}/{code}"
        )
    if not lines:
        return ("none",)
    return tuple(lines)


def _run_artifacts(
    report: ExternalStudyReport,
) -> tuple[ExternalScoredRunArtifact | ExternalUnscoredSlotArtifact, ...]:
    attempts_by_key: dict[_SLOT_KEY, list[ExternalAttemptRecord]] = {}
    for attempt in report.attempts:
        attempts_by_key.setdefault(_slot_key(attempt), []).append(attempt)
    artifacts: list[ExternalScoredRunArtifact | ExternalUnscoredSlotArtifact] = []
    scored_keys: set[_SLOT_KEY] = set()
    for score in report.scores:
        key = _slot_key(score)
        scored_keys.add(key)
        artifacts.append(
            ExternalScoredRunArtifact(
                score=score,
                attempts=tuple(attempts_by_key.get(key, ())),
            )
        )
    for key in sorted(k for k in attempts_by_key if k not in scored_keys):
        artifacts.append(
            ExternalUnscoredSlotArtifact(
                execution_path=key[0],  # type: ignore[arg-type]
                case_id=key[1],
                run_slot=key[2],
                attempts=tuple(attempts_by_key[key]),
            )
        )
    return tuple(artifacts)


def _slot_key(item: ExternalAttemptRecord | ExternalRunScore) -> _SLOT_KEY:
    run_slot = getattr(item, "run_slot", 1)
    return (item.execution_path, item.case_id, run_slot)


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
    redacted = _SECRET_PATTERN.sub("[redacted]", text)
    redacted = _LOCAL_PATH_PATTERN.sub("[redacted-local-path]", redacted)
    redacted = redacted.replace("\\", "/")
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
