"""Read-only v9.7 rule-closure shadow replay over preserved Observation Evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from signal_diag.agent.rule_closure import (
    build_rule_closure_request,
    required_rule_profile,
)
from signal_diag.evaluation.models import (
    EvaluationEvent,
    ObservationEvent,
    PlannerDecisionEvent,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import RuleEvaluationBatch, RuleProfileLoader

_EVENT_ADAPTER: TypeAdapter[list[EvaluationEvent]] = TypeAdapter(list[EvaluationEvent])

_PAIRED_CONTEXTUAL_PASS_RULES = frozenset(
    {
        "rule_contextual_analysis_valid",
        "rule_contextual_f0_compatible",
        "rule_reference_clipping_ratio_acceptable",
        "rule_reference_flat_top_absent",
        "rule_even_harmonic_growth_acceptable",
    }
)
_NOMINAL_CONTEXTUAL_PASS_RULES = frozenset(
    {
        "rule_contextual_analysis_valid",
        "rule_contextual_f0_compatible",
        "rule_nominal_thd_acceptable",
    }
)
_CLIPPING_PASS_RULES = frozenset(
    {
        "rule_clipping_ratio_acceptable",
        "rule_flat_top_absent",
    }
)


def build_replay_row(
    case_id: str,
    mode: str,
    event: ObservationEvent,
    batch: RuleEvaluationBatch,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "mode": mode,
        "observation_id": event.observation.observation_id,
        "call_id": event.observation.call_id,
        "tool_name": event.observation.tool_name,
        "profile_id": batch.profile_id,
        "evidence_refs": list(event.observation.evidence_refs),
        "batch_id": batch.batch_id,
        "evaluations": [
            {
                "rule_id": evaluation.rule_id,
                "judgment": evaluation.judgment,
                "evidence_refs": list(evaluation.evidence_refs),
            }
            for evaluation in batch.evaluations
        ],
    }


def _rule_judgments(row: dict[str, object]) -> dict[str, str]:
    judgments: dict[str, str] = {}
    for item in row["evaluations"]:  # type: ignore[assignment]
        assert isinstance(item, dict)
        judgments[str(item["rule_id"])] = str(item["judgment"])
    return judgments


def _all_pass(judgments: dict[str, str], required: frozenset[str]) -> bool:
    return all(judgments.get(rule_id) == "pass" for rule_id in required)


def build_replay_report(
    rows: list[dict[str, object]],
    trace_hashes: dict[str, str],
) -> dict[str, object]:
    by_case: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_case.setdefault(str(row["case_id"]), []).append(row)

    contextual_positive_fail: list[str] = []
    contextual_complete_pass: list[str] = []
    for case_id, case_rows in sorted(by_case.items()):
        judgments: dict[str, str] = {}
        modes = {str(row["mode"]) for row in case_rows}
        profiles = {str(row["profile_id"]) for row in case_rows}
        for row in case_rows:
            judgments.update(_rule_judgments(row))
        mode = next(iter(modes)) if len(modes) == 1 else None
        if mode is None:
            for row in case_rows:
                if row["profile_id"] == "profile_s1_contextual_comparison":
                    mode = str(row["mode"])
                    break
        if mode == "paired_reference" and (
            judgments.get("rule_even_harmonic_growth_acceptable") == "fail"
        ):
            contextual_positive_fail.append(case_id)
        elif mode == "nominal_single_tone" and (
            judgments.get("rule_nominal_thd_acceptable") == "fail"
        ):
            contextual_positive_fail.append(case_id)
        required: frozenset[str] | None = None
        if mode == "paired_reference":
            required = _PAIRED_CONTEXTUAL_PASS_RULES | _CLIPPING_PASS_RULES
        elif mode == "nominal_single_tone":
            required = _NOMINAL_CONTEXTUAL_PASS_RULES | _CLIPPING_PASS_RULES
        if required is not None and _all_pass(judgments, required):
            if "profile_s1_contextual_comparison" in profiles:
                contextual_complete_pass.append(case_id)

    return {
        "source_case_count": len(trace_hashes),
        "replayed_observation_count": len(rows),
        "label_independent_mapping": True,
        "trace_sha256": trace_hashes,
        "rows": rows,
        "contextual_positive_fail_case_ids": contextual_positive_fail,
        "contextual_complete_pass_case_ids": contextual_complete_pass,
    }


def _load_events(raw: bytes) -> list[EvaluationEvent]:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or "events" not in payload:
        raise ValueError("trace.json must contain an events array")
    return _EVENT_ADAPTER.validate_python(payload["events"])


def replay_rule_closure(
    run_dir: Path,
    *,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    trace_hashes: dict[str, str] = {}
    case_dirs = sorted(
        path for path in (run_dir / "cases").iterdir() if path.is_dir()
    )
    for case_dir in case_dirs:
        trace_path = case_dir / "trace.json"
        raw = trace_path.read_bytes()
        trace_hashes[case_dir.name] = hashlib.sha256(raw).hexdigest()
        events = _load_events(raw)
        planner_contexts = {
            event.record.decision_index: event.record.context
            for event in events
            if isinstance(event, PlannerDecisionEvent)
        }
        for event in events:
            if not isinstance(event, ObservationEvent):
                continue
            context = planner_contexts[event.caused_by_decision_index].stimulus_context
            if context is None:
                raise ValueError("contextual replay requires StimulusContext")
            profile_id = required_rule_profile(
                causal_policy_version="v9_7_deterministic_rule_closure",
                stimulus_context=context,
                tool_name=event.observation.tool_name,
            )
            if profile_id is None or event.observation.status == "error":
                continue
            request = build_rule_closure_request(
                profile_id=profile_id,
                observation=event.observation,
            )
            if request is None:
                continue
            if (
                tuple(item.evidence_id for item in event.evidence)
                != request.evidence_refs
            ):
                raise ValueError("Observation Evidence suffix mismatch")
            batch = rule_engine.evaluate_profile(
                profile_loader.load(profile_id),
                event.evidence,
                evidence_filter=frozenset(request.evidence_refs),
            )
            if batch.profile_id != profile_id:
                raise ValueError("replayed batch profile mismatch")
            for evaluation in batch.evaluations:
                for ref in evaluation.evidence_refs:
                    if ref not in request.evidence_refs:
                        raise ValueError("replayed evaluation Evidence out of scope")
            rows.append(
                build_replay_row(case_dir.name, context.mode, event, batch)
            )
    return build_replay_report(rows, trace_hashes)


def write_shadow_replay_report(
    *,
    run_dir: Path,
    destination: Path,
    rule_engine: RuleEngine,
    profile_loader: RuleProfileLoader,
) -> dict[str, Any]:
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    before = {
        path.name: hashlib.sha256((path / "trace.json").read_bytes()).hexdigest()
        for path in sorted((run_dir / "cases").iterdir())
        if path.is_dir()
    }
    report = replay_rule_closure(
        run_dir,
        rule_engine=rule_engine,
        profile_loader=profile_loader,
    )
    after = {
        path.name: hashlib.sha256((path / "trace.json").read_bytes()).hexdigest()
        for path in sorted((run_dir / "cases").iterdir())
        if path.is_dir()
    }
    if before != after:
        raise RuntimeError("v9.6 trace files mutated during shadow replay")
    (destination / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
