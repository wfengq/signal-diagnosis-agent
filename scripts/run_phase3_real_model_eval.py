#!/usr/bin/env python3
"""Manual Phase 3 real-model evaluation (outside required CI).

Composes RealLLMPlanner with real repository/Tools, RuleEngine, an explicitly
mapped YamlRuleProfileLoader, and KnowledgeIndex. Never falls back to
ScriptedPlanner.

S1 demonstration thresholds in profile_s1_distortion 1.0.0-demo are not
industry standards.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
else:
    sys.path.remove(str(_SRC))
    sys.path.insert(0, str(_SRC))

from signal_diag.agent.models import AgentRunResult, PlannerOutputError
from signal_diag.agent.planner import (
    DEFAULT_DEEPSEEK_MODEL,
    PROMPT_VERSION,
    RealLLMPlanner,
    _missing_credentials_message,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import (
    InMemorySignalRepository,
    SignalRepository,
    SyntheticCase,
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools import SignalToolService

FORBIDDEN_TRACE_KEYS = frozenset({"frequencies_hz", "magnitude_db"})
S1_PROFILE_ID = "profile_s1_distortion"
PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    ground_truth: str
    build: Callable[[], SyntheticCase]
    user_request: str


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        case_id="S1-CLIP-SUBFS",
        ground_truth="clipping (sub-full-scale flat top)",
        build=lambda: generate_clipped_sine(
            frequency_hz=200.0,
            sample_rate_hz=48_000,
            duration_s=2.0,
            amplitude=0.9,
            clip_level=0.5,
        ),
        user_request="Why does this signal sound distorted?",
    ),
    EvalCase(
        case_id="S1-HARM",
        ground_truth="harmonic distortion",
        build=lambda: generate_harmonic_sine(
            fundamental_hz=200.0,
            harmonic_ratios={2: 0.10, 3: 0.05},
            sample_rate_hz=48_000,
            duration_s=2.0,
            fundamental_amplitude=0.5,
        ),
        user_request="Why does this signal sound distorted?",
    ),
    EvalCase(
        case_id="S1-CLEAN",
        ground_truth="no supported fault",
        build=lambda: generate_sine(
            frequency_hz=200.0,
            sample_rate_hz=48_000,
            duration_s=2.0,
            amplitude=0.5,
        ),
        user_request="Why does this signal sound distorted?",
    ),
    EvalCase(
        case_id="S1-NOISE",
        ground_truth="inconclusive (noise-only input)",
        build=lambda: generate_white_noise(
            sample_rate_hz=48_000,
            duration_s=2.0,
            rms=0.1,
            seed=1234,
        ),
        user_request="Why does this signal sound distorted?",
    ),
)


def assert_trace_is_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_TRACE_KEYS:
                raise RuntimeError(
                    f"trace must not expose full FFT arrays ({key!r})"
                )
            assert_trace_is_safe(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_trace_is_safe(item)


def build_planner() -> RealLLMPlanner:
    return RealLLMPlanner(provider="deepseek")


def build_phase3_runtime(
    *,
    repository: SignalRepository,
    planner: RealLLMPlanner,
) -> DistortionDiagnosisRuntime:
    return DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {S1_PROFILE_ID: PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run manual RealLLMPlanner Phase 3 evaluation with injected "
            "RuleEngine, explicitly mapped YamlRuleProfileLoader, and "
            "KnowledgeIndex (outside CI). Demonstration thresholds are not "
            "industry standards."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("real_model_eval_output/phase3"),
        help=(
            "Directory for structured JSON traces "
            "(default: real_model_eval_output/phase3)"
        ),
    )
    return parser


def _action_sequence(result: AgentRunResult) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = [
        {
            "kind": "tool",
            "name": entry.tool_name,
            "call_id": entry.call_id,
        }
        for entry in result.tool_history
    ]
    actions.extend(
        {
            "kind": "evaluate_rules",
            "profile_id": batch.profile_id,
            "batch_id": batch.batch_id,
        }
        for batch in result.rule_evaluation_batches
    )
    actions.extend(
        {
            "kind": "retrieve_knowledge",
            "retrieval_id": item.retrieval_id,
            "query_text": item.query_text,
        }
        for item in result.knowledge_retrievals
    )
    return actions


def _diagnosis_refs(result: AgentRunResult) -> dict[str, object]:
    if result.diagnosis is None:
        return {
            "outcome": None,
            "evidence_refs": [],
            "rule_refs": [],
            "knowledge_refs": [],
        }
    evidence_refs: list[str] = []
    rule_refs: list[str] = []
    knowledge_refs: list[str] = []
    for claim in result.diagnosis.claims:
        evidence_refs.extend(claim.evidence_refs)
        rule_refs.extend(claim.rule_refs)
        knowledge_refs.extend(claim.knowledge_refs)
    return {
        "outcome": result.diagnosis.outcome,
        "evidence_refs": evidence_refs,
        "rule_refs": rule_refs,
        "knowledge_refs": knowledge_refs,
    }


def summarize_case(
    *,
    case_id: str,
    ground_truth: str,
    planner: RealLLMPlanner,
    elapsed_s: float,
    result: AgentRunResult,
    provider_usage: object,
) -> dict[str, object]:
    trace = result.model_dump(mode="json")
    assert_trace_is_safe(trace)
    serialized = json.dumps(trace)
    if "ndarray" in serialized:
        raise RuntimeError("trace must not contain ndarray payloads")
    return {
        "case_id": case_id,
        "ground_truth": ground_truth,
        "model_id": planner.model_id or DEFAULT_DEEPSEEK_MODEL,
        "prompt_version": PROMPT_VERSION,
        "elapsed_s": round(elapsed_s, 3),
        "action_sequence": _action_sequence(result),
        "rule_evaluation_count": len(result.rule_evaluation_batches),
        "knowledge_retrieval_count": len(result.knowledge_retrievals),
        "diagnosis_refs": _diagnosis_refs(result),
        "provider_usage": provider_usage,
        "status": result.status,
        "termination_reason": result.termination_reason,
        "trace": trace,
        "threshold_disclaimer": (
            "profile_s1_distortion 1.0.0-demo thresholds are demonstration-only, "
            "not industry standards."
        ),
    }


async def _run_case(
    eval_case: EvalCase,
    planner: RealLLMPlanner,
) -> dict[str, object]:
    synthetic = eval_case.build()
    repository = InMemorySignalRepository()
    repository.put(synthetic.record)
    runtime = build_phase3_runtime(repository=repository, planner=planner)
    started = time.perf_counter()
    result = await runtime.run(
        signal_id=synthetic.record.meta.signal_id,
        user_request=eval_case.user_request,
    )
    elapsed_s = time.perf_counter() - started
    return summarize_case(
        case_id=eval_case.case_id,
        ground_truth=eval_case.ground_truth,
        planner=planner,
        elapsed_s=elapsed_s,
        result=result,
        provider_usage=None,
    )


async def _run_all(output_dir: Path) -> list[dict[str, object]]:
    planner = build_planner()
    summaries: list[dict[str, object]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for eval_case in EVAL_CASES:
        print(f"Running {eval_case.case_id}...", file=sys.stderr)
        summary = await _run_case(eval_case, planner)
        summaries.append(summary)
        case_path = output_dir / f"{eval_case.case_id.lower()}.json"
        case_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"  wrote {case_path}", file=sys.stderr)
    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "protocol": "phase3-real-model",
                "model_id": planner.model_id or DEFAULT_DEEPSEEK_MODEL,
                "prompt_version": PROMPT_VERSION,
                "cases": [item["case_id"] for item in summaries],
                "threshold_disclaimer": (
                    "profile_s1_distortion 1.0.0-demo thresholds are "
                    "demonstration-only, not industry standards."
                ),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print(_missing_credentials_message(), file=sys.stderr)
        return 1
    try:
        asyncio.run(_run_all(args.output_dir))
    except PlannerOutputError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(
        "Phase 3 real-model evaluation complete. Score selection, "
        "observation-driven rule/retrieval decisions, unnecessary actions, "
        "stopping, grounding, and limitations from the JSON traces.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
