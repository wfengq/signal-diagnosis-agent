#!/usr/bin/env python3
"""Build the packaged Phase 4.3.1 official evaluation presentation summary.

Reads the immutable official bundle only. Does not rescore or rewrite source files.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from signal_diag.app.models import AcceptedEvaluationSummary
from signal_diag.evaluation.models import AggregateMetrics, TargetBands

SOURCE = Path(
    "docs/evaluations/phase4_3_1/official/"
    "bench_official_s1_v12_planner8_1_gate5"
)
DESTINATION = Path(
    "src/signal_diag/evaluation/assets/phase4_3_1_official_summary.json"
)
DATA_FILES = (
    "benchmark_manifest.json",
    "case_summary.csv",
    "metrics.json",
    "report.md",
    "runs.jsonl",
)
EXPECTED_CHECKSUMS = {
    "benchmark_manifest.json": (
        "355fc75eab5d4580606fb3eb31a71566cc4b2a8303d412aa309df5b3c9ae71a7"
    ),
    "case_summary.csv": (
        "3699061f726cf8de1b8d6eff9bcf3bd8487431d64f23944dbf0c95ce87bcaeae"
    ),
    "metrics.json": (
        "e60aa63de6f030bf88fd7154cd0f7b72fd7bf36589ad769a234ee02fd6e956d0"
    ),
    "report.md": "8f2f47e34731254ae45987445076e041f8675da17f56cc0463530c412ec1b4f0",
    "runs.jsonl": "cff5a41ea8ed6f7838cc72e25b678d7b11eb97976e27a039e80d877d781ac35d",
}
SOURCE_BUNDLE_RELATIVE_PATH = (
    "docs/evaluations/phase4_3_1/official/bench_official_s1_v12_planner8_1_gate5"
)


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(_canonical_bytes(path)).hexdigest()


def _json_dumps(value: object) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _count_agent_scored_runs(runs_text: str) -> tuple[int, int, int]:
    agent_slots = 0
    behavioral_failures = 0
    outcome_errors = 0
    for line in runs_text.splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") != "scored_run":
            continue
        score = record["score"]
        if score.get("execution_path") != "agent":
            continue
        agent_slots += 1
        if score.get("failure_codes"):
            behavioral_failures += 1
        if score.get("outcome_correct") is False:
            outcome_errors += 1
    return agent_slots, behavioral_failures, outcome_errors


def build_accepted_evaluation_summary(
    source: Path = SOURCE,
    destination: Path = DESTINATION,
) -> Path:
    src = _resolve(source)
    dest = _resolve(destination)
    checksums: dict[str, str] = {}
    for name in DATA_FILES:
        digest = _sha256(src / name)
        expected = EXPECTED_CHECKSUMS[name]
        if digest != expected:
            raise ValueError(f"official bundle checksum mismatch: {name}")
        checksums[name] = digest

    manifest = json.loads(_canonical_bytes(src / "benchmark_manifest.json"))
    metrics = json.loads(_canonical_bytes(src / "metrics.json"))
    report_md = _canonical_bytes(src / "report.md").decode("utf-8")
    runs_text = _canonical_bytes(src / "runs.jsonl").decode("utf-8")
    config = manifest["config"]
    if "benchmark_status: completed" not in report_md:
        raise ValueError("official report.md is missing completed status")
    if "target_status: meets_target" not in report_md:
        raise ValueError("official report.md is missing meets_target status")

    agent_slots, behavioral_failures, outcome_errors = _count_agent_scored_runs(
        runs_text
    )
    if (agent_slots, behavioral_failures, outcome_errors) != (80, 2, 1):
        raise ValueError(
            "unexpected Agent scored_run counts: "
            f"{agent_slots} slots, {behavioral_failures} behavioral, "
            f"{outcome_errors} outcome errors"
        )
    summary = AcceptedEvaluationSummary(
        source_bundle_relative_path=SOURCE_BUNDLE_RELATIVE_PATH,
        source_checksums_sha256=checksums,
        benchmark_id=config["benchmark_id"],
        dataset_id=config["dataset_id"],
        dataset_version=config["dataset_version"],
        provider=config["provider"],
        model=config["model"],
        prompt_version=config["prompt_version"],
        prompt_sha256=config["prompt_sha256"],
        rule_profile_id=config["rule_profile_id"],
        rule_profile_version=config["rule_profile_version"],
        scoring_version=config["sdk_versions"]["signal_diag.scoring"],
        benchmark_status=metrics["benchmark_status"],
        target_status=metrics["target_status"],
        agent_slot_count=80,
        behavioral_failure_slot_count=2,
        outcome_error_slot_count=1,
        targets=TargetBands.model_validate(metrics["targets"]),
        agent_metrics=AggregateMetrics.model_validate(metrics["agent_metrics"]),
        baseline_metrics=AggregateMetrics.model_validate(metrics["baseline_metrics"]),
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_json_dumps(summary.model_dump(mode="json")), encoding="utf-8")
    return dest


def main() -> None:
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else DESTINATION
    build_accepted_evaluation_summary(destination=destination)


if __name__ == "__main__":
    main()
