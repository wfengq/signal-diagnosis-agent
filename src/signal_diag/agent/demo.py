"""Development CLI for distortion diagnosis traces (scripted or real LLM)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from signal_diag.signal import InMemorySignalRepository, generate_clipped_sine
from signal_diag.tools import ClippingInput, SignalToolService

from .models import (
    AgentDecision,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    FinishDecision,
    PlannerContext,
    PlannerOutputError,
    TaskAssessment,
)
from .planner import RealLLMPlanner, ScriptedPlanner, _missing_credentials_message
from .runtime import DistortionDiagnosisRuntime


class _DemoFinishPlanner(ScriptedPlanner):
    """Run one clipping Tool, then finish using the observed evidence ID."""

    async def decide(self, context: PlannerContext) -> AgentDecision:
        if len(context.observations) == 0:
            return CallToolDecision(
                task_assessment=TaskAssessment(
                    task_type="distortion_analysis",
                    objective="inspect clipping on demo signal",
                ),
                call=DetectClippingCall(args=ClippingInput()),
                purpose="check for clipping evidence",
            )
        evidence_id = next(
            item.evidence_id
            for item in context.evidence
            if item.metric == "clipping_detected"
        )
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_demo_clip",
                    fault_type="clipping",
                    statement="demo signal shows clipping evidence",
                    evidence_refs=(evidence_id,),
                ),
            ),
            confidence_label="medium",
        )


def _build_planner(name: str) -> ScriptedPlanner | RealLLMPlanner:
    if name == "scripted":
        return _DemoFinishPlanner([])
    if name == "real":
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise PlannerOutputError(_missing_credentials_message())
        return RealLLMPlanner(provider="deepseek")
    raise ValueError(f"unsupported planner: {name}")


async def _run_demo(planner: ScriptedPlanner | RealLLMPlanner) -> dict[str, object]:
    case = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=1.0,
        amplitude=1.2,
        clip_level=1.0,
    )
    repository = InMemorySignalRepository()
    repository.put(case.record)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
    )
    result = await runtime.run(
        signal_id=case.record.meta.signal_id,
        user_request="Diagnose distortion on demo clipped sine.",
    )
    payload = result.model_dump(mode="json")
    serialized = json.dumps(payload)
    if "ndarray" in serialized:
        raise RuntimeError("demo output must not contain ndarray payloads")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a distortion diagnosis demo trace.",
    )
    parser.add_argument(
        "--planner",
        choices=("scripted", "real"),
        default="scripted",
        help="Planner backend (default: scripted for CI-safe deterministic runs)",
    )
    args = parser.parse_args(argv)
    try:
        planner = _build_planner(args.planner)
    except PlannerOutputError as error:
        print(str(error), file=sys.stderr)
        return 1
    try:
        payload = asyncio.run(_run_demo(planner))
    except PlannerOutputError as error:
        print(str(error), file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
