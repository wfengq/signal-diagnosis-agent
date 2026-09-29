"""T-CX264 / T-CX265: deterministic context_guidance builder."""

from __future__ import annotations

from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.app.context_guidance import build_context_guidance
from signal_diag.tools.evidence import Evidence


def _evidence(
    *,
    metric: str,
    value: object,
    evidence_id: str = "ev_guide_001",
    tool: str = "analyze_harmonic_distortion",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=tool,  # type: ignore[arg-type]
        call_id="call_analyze_harmonic_distortion_000000",
        metric=metric,
        value=value,
        channel="mixdown",
        validity="valid",
    )


def _result(
    *,
    outcome: str,
    evidence: tuple[Evidence, ...],
    fault_type: str = "inconclusive",
) -> AgentRunResult:
    claim = DiagnosisClaim(
        claim_id="claim_guide_001",
        fault_type=fault_type,  # type: ignore[arg-type]
        statement="fixture",
        evidence_refs=tuple(item.evidence_id for item in evidence) or (),
        rule_refs=(),
        knowledge_refs=(),
    )
    diagnosis = StructuredDiagnosis(
        run_id="run_guide",
        task_type="distortion_analysis",
        outcome=outcome,  # type: ignore[arg-type]
        claims=(claim,),
        confidence_label="low",
        limitations=(),
        termination_reason="planner_finished",
        tool_call_count=1,
    )
    return AgentRunResult(
        run_id="run_guide",
        status="success" if outcome != "inconclusive" else "inconclusive",
        diagnosis=diagnosis,
        observations=(),
        evidence=evidence,
        tool_history=(),
        termination_reason="planner_finished",
    )


def test_t_cx264_harmonic_inconclusive_emits_guidance() -> None:
    result = _result(
        outcome="inconclusive",
        evidence=(_evidence(metric="thd_percent", value=12.65),),
    )
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert guidance.unlockable_modes == (
        "paired_reference",
        "nominal_single_tone",
    )
    assert "reference_wav" in guidance.required_inputs["paired_reference"]
    lowered = guidance.summary.lower()
    assert "可能是" not in guidance.summary
    assert "likely" not in lowered
    assert "insufficient" in lowered or "not enough" in lowered


def test_t_cx265_supported_fault_and_other_modes_skip_guidance() -> None:
    clipping = _result(
        outcome="supported_fault",
        evidence=(
            _evidence(
                metric="flat_top_detected",
                value=True,
                tool="detect_clipping",
            ),
        ),
        fault_type="clipping",
    )
    assert build_context_guidance(mode="single_signal", result=clipping) is None

    clean = _result(
        outcome="no_supported_fault",
        evidence=(_evidence(metric="thd_percent", value=0.1),),
        fault_type="no_supported_fault",
    )
    assert build_context_guidance(mode="single_signal", result=clean) is None

    paired = _result(
        outcome="inconclusive",
        evidence=(_evidence(metric="thd_percent", value=12.0),),
    )
    assert build_context_guidance(mode="paired_reference", result=paired) is None
