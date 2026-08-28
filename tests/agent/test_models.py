"""Checkpoint D — Agent models (T064–T067)."""

import json

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors


def _signal_meta() -> SignalMeta:
    return SignalMeta(
        signal_id="sig_test",
        source_type="generated",
        sample_rate_hz=48_000,
        channels=1,
        num_samples=96_000,
        duration_s=2.0,
        original_dtype="float32",
    )


def _planner_context(**overrides: object) -> PlannerContext:
    base = {
        "run_id": "run_001",
        "user_request": "Why distorted?",
        "signal_meta": _signal_meta(),
        "task_assessment": None,
        "observations": (),
        "evidence": (),
        "tool_history": (),
        "available_tools": get_tool_descriptors(),
        "remaining_tool_calls": 8,
        "remaining_planner_retries": 2,
        "no_progress_count": 0,
    }
    base.update(overrides)
    return PlannerContext(**base)  # type: ignore[arg-type]


def test_t064_valid_tool_invocations_parse() -> None:
    adapter = TypeAdapter(AgentDecision)
    clipping = adapter.validate_python(
        {
            "decision_type": "call_tool",
            "task_assessment": {
                "task_type": "distortion_analysis",
                "objective": "inspect clipping",
            },
            "call": {
                "tool_name": "detect_clipping",
                "args": {"full_scale_threshold": 0.99},
            },
            "purpose": "check clipping",
        }
    )
    assert isinstance(clipping, CallToolDecision)
    assert clipping.call.tool_name == "detect_clipping"

    spectrum = adapter.validate_python(
        {
            "decision_type": "call_tool",
            "call": {
                "tool_name": "analyze_spectrum",
                "args": {"window": "hann", "max_peaks": 5},
            },
            "purpose": "inspect spectrum",
        }
    )
    assert spectrum.call.tool_name == "analyze_spectrum"

    fundamental = adapter.validate_python(
        {
            "decision_type": "call_tool",
            "call": {
                "tool_name": "estimate_fundamental",
                "args": {"fmin_hz": 50.0, "fmax_hz": 1000.0},
            },
            "purpose": "estimate f0",
        }
    )
    assert fundamental.call.tool_name == "estimate_fundamental"

    harmonic = adapter.validate_python(
        {
            "decision_type": "call_tool",
            "call": {
                "tool_name": "analyze_harmonic_distortion",
                "args": {"max_harmonic_order": 5},
            },
            "purpose": "measure thd",
        }
    )
    assert harmonic.call.tool_name == "analyze_harmonic_distortion"


@pytest.mark.parametrize(
    ("payload", "tool_name"),
    [
        (
            {
                "decision_type": "call_tool",
                "call": {"tool_name": "unknown_tool", "args": {}},
                "purpose": "bad",
            },
            "unknown_tool",
        ),
        (
            {
                "decision_type": "call_tool",
                "call": {
                    "tool_name": "detect_clipping",
                    "args": {"full_scale_threshold": -1.0},
                },
                "purpose": "bad threshold",
            },
            "detect_clipping",
        ),
    ],
)
def test_t064_invalid_tool_name_or_args_fail(payload: dict, tool_name: str) -> None:
    adapter = TypeAdapter(AgentDecision)
    with pytest.raises(ValidationError):
        adapter.validate_python(payload)


def test_t065_planner_context_serialization_has_no_waveform_or_fft() -> None:
    context = _planner_context()
    serialized = context.model_dump_json()
    assert "ndarray" not in serialized
    assert "frequencies_hz" not in serialized
    assert "magnitude_db" not in serialized
    parsed = json.loads(serialized)
    assert parsed["signal_meta"]["signal_id"] == "sig_test"
    assert parsed["observations"] == []


def test_t066_runtime_rejects_initial_decision_without_task_assessment() -> None:
    from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
    from signal_diag.agent.runtime import DistortionDiagnosisRuntime
    from signal_diag.signal import InMemorySignalRepository
    from signal_diag.tools.service import SignalToolService

    repo = InMemorySignalRepository()
    # Will be populated by caller in runtime tests; here we only need validation path
    decision = CallToolDecision(
        call=DetectClippingCall(args=ClippingInput()),
        purpose="check clipping",
    )
    step = ScriptedStep(expected_observation_count=0, decision=decision)
    runtime = DistortionDiagnosisRuntime(
        repository=repo,
        tool_service=SignalToolService(repo),
        planner=ScriptedPlanner([step]),
        limits=__import__(
            "signal_diag.agent.policies", fromlist=["AgentLimits"]
        ).AgentLimits(max_planner_retries=0),
    )

    async def _run() -> None:
        from signal_diag.signal import build_signal_record

        samples = np.zeros((48000, 1), dtype=np.float32)
        record = build_signal_record(
            samples,
            sample_rate_hz=48_000,
            source_type="generated",
            signal_id="sig_t066",
        )
        repo.put(record)
        result = await runtime.run(
            signal_id="sig_t066",
            user_request="distortion?",
        )
        assert result.termination_reason == "max_planner_retries"
        assert result.status == "error"

    import asyncio

    asyncio.run(_run())


def test_t067_finish_semantics_require_evidence_or_limitation() -> None:
    assessment = TaskAssessment(
        task_type="distortion_analysis",
        objective="diagnose",
    )
    supported = FinishDecision(
        task_assessment=assessment,
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_1",
                fault_type="clipping",
                statement="clipping detected",
                evidence_refs=(),
            ),
        ),
        confidence_label="high",
    )
    with pytest.raises(DiagnosisValidationError):
        validate_finish_decision(
            supported,
            known_evidence_ids=frozenset({"ev_x"}),
            task_assessment=assessment,
        )

    no_fault = FinishDecision(
        task_assessment=assessment,
        outcome="no_supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_2",
                fault_type="no_supported_fault",
                statement="no fault",
                evidence_refs=(),
            ),
        ),
        confidence_label="medium",
    )
    with pytest.raises(DiagnosisValidationError):
        validate_finish_decision(
            no_fault,
            known_evidence_ids=frozenset(),
            task_assessment=assessment,
        )

    inconclusive = FinishDecision(
        task_assessment=assessment,
        outcome="inconclusive",
        claims=(),
        confidence_label="low",
        limitations=(),
    )
    with pytest.raises(DiagnosisValidationError):
        validate_finish_decision(
            inconclusive,
            known_evidence_ids=frozenset(),
            task_assessment=assessment,
        )

    validate_finish_decision(
        FinishDecision(
            task_assessment=assessment,
            outcome="inconclusive",
            claims=(),
            confidence_label="low",
            limitations=("insufficient evidence",),
        ),
        known_evidence_ids=frozenset(),
        task_assessment=assessment,
    )
