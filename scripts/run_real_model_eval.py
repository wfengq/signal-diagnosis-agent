#!/usr/bin/env python3
"""Manual R001-R006 real-model evaluation protocol (TEST_PLAN section 13).

Runs RealLLMPlanner on S1-CLIP-SUBFS, S1-HARM, S1-CLEAN, and S1-NOISE.
Results are written as structured JSON traces without waveform arrays.
This script is outside required CI and performs network calls when credentials
are present.
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

from signal_diag.agent.models import PlannerOutputError
from signal_diag.agent.planner import (
    DEFAULT_DEEPSEEK_MODEL,
    PROMPT_VERSION,
    RealLLMPlanner,
    _missing_credentials_message,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.signal import (
    InMemorySignalRepository,
    SyntheticCase,
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools import SignalToolService

FORBIDDEN_TRACE_KEYS = frozenset({"frequencies_hz", "magnitude_db"})


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


def _assert_trace_is_safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_TRACE_KEYS:
                raise RuntimeError(
                    f"trace must not expose full FFT arrays ({key!r})"
                )
            _assert_trace_is_safe(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_trace_is_safe(item)


def _require_credentials() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print(_missing_credentials_message(), file=sys.stderr)
        sys.exit(1)


async def _run_case(eval_case: EvalCase, planner: RealLLMPlanner) -> dict[str, object]:
    synthetic = eval_case.build()
    repository = InMemorySignalRepository()
    repository.put(synthetic.record)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
    )
    started = time.perf_counter()
    result = await runtime.run(
        signal_id=synthetic.record.meta.signal_id,
        user_request=eval_case.user_request,
    )
    elapsed_s = time.perf_counter() - started
    trace = result.model_dump(mode="json")
    _assert_trace_is_safe(trace)
    serialized = json.dumps(trace)
    if "ndarray" in serialized:
        raise RuntimeError("trace must not contain ndarray payloads")
    first_tool = result.tool_history[0].tool_name if result.tool_history else None
    return {
        "case_id": eval_case.case_id,
        "ground_truth": eval_case.ground_truth,
        "model_id": planner.model_id or DEFAULT_DEEPSEEK_MODEL,
        "prompt_version": PROMPT_VERSION,
        "elapsed_s": round(elapsed_s, 3),
        "planner_calls": "see runtime trace observations + retries in errors",
        "tool_call_count": result.diagnosis.tool_call_count if result.diagnosis else len(result.tool_history),
        "r001_first_tool": first_tool,
        "r002_observation_driven_replanning": "review tool_history sequence in trace",
        "r003_unnecessary_calls": "compare tool_history to evidence added per step",
        "r004_stopping_timing": result.termination_reason,
        "r005_final_diagnosis_quality": {
            "status": result.status,
            "outcome": result.diagnosis.outcome if result.diagnosis else None,
            "claims": [claim.model_dump(mode="json") for claim in result.diagnosis.claims]
            if result.diagnosis
            else [],
        },
        "r006_execution": {
            "tool_calls": len(result.tool_history),
            "latency_s": round(elapsed_s, 3),
            "model_id": planner.model_id or DEFAULT_DEEPSEEK_MODEL,
            "prompt_version": PROMPT_VERSION,
        },
        "trace": trace,
    }


async def _run_all(output_dir: Path) -> list[dict[str, object]]:
    planner = RealLLMPlanner(provider="deepseek")
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
                "protocol": "R001-R006",
                "model_id": planner.model_id or DEFAULT_DEEPSEEK_MODEL,
                "prompt_version": PROMPT_VERSION,
                "cases": [item["case_id"] for item in summaries],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run manual RealLLMPlanner evaluation for R001-R006 (outside CI)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("real_model_eval_output"),
        help="Directory for structured JSON traces (default: real_model_eval_output)",
    )
    args = parser.parse_args(argv)

    _require_credentials()
    try:
        asyncio.run(_run_all(args.output_dir))
    except PlannerOutputError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(
        "Real-model evaluation complete. Score R001-R006 from the JSON traces.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
