"""T-CX105: contextual diagnosis report projection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualDiagnosisReport,
)
from signal_diag.app.contextual_reporting import (
    build_contextual_diagnosis_report,
    render_contextual_report_html,
    render_contextual_report_json,
)
from signal_diag.app.errors import TraceIntegrityError
from signal_diag.app.models import (
    PlannerIdentity,
    SourceSummary,
    TraceEventView,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext
from signal_diag.tools.evidence import Evidence

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 9, 4, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 9, 4, 12, 2, tzinfo=UTC)
GENERATED = datetime(2026, 9, 4, 12, 3, tzinfo=UTC)
RUN_ID = "run_" + "d" * 32


def _source(name: str) -> SourceSummary:
    return SourceSummary(
        source_kind="wav",
        display_name=name,
        sample_rate_hz=8_000,
        channels=1,
        num_frames=8_000,
        duration_s=1.0,
        bits_per_sample=16,
    )


def _preview() -> WaveformPreview:
    return WaveformPreview(
        sample_rate_hz=8_000,
        original_num_samples=1,
        points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.25),),
    )


def _planner() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="v0.3-s1-planner-9.5",
        phase4_certified_default=True,
    )


def _context() -> StimulusContext:
    return StimulusContext(
        mode="paired_reference",
        test_signal_id="sig_test",
        reference_signal_id="sig_ref",
        assertion_source="user_supplied",
    )


def _evidence(evidence_id: str = "ev_context_valid_001") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id="call_analyze_contextual_distortion_000000",
        metric="context_valid",
        value=False,
        channel="mixdown",
    )


def _result(*, evidence_id: str = "ev_context_valid_001") -> AgentRunResult:
    evidence = (_evidence(evidence_id),)
    claim = DiagnosisClaim(
        claim_id="claim_ctx_001",
        fault_type="inconclusive",
        statement="Reference comparison is invalid; clipping path remains.",
        evidence_refs=(evidence_id,),
        rule_refs=(),
        knowledge_refs=(),
    )
    diagnosis = StructuredDiagnosis(
        run_id="run_agent",
        task_type="distortion_analysis",
        outcome="inconclusive",
        claims=(claim,),
        confidence_label="low",
        limitations=("comparison_invalid",),
        termination_reason="planner_finished",
        tool_call_count=1,
    )
    return AgentRunResult(
        run_id="run_agent",
        status="success",
        diagnosis=diagnosis,
        observations=(),
        evidence=evidence,
        tool_history=(),
        termination_reason="planner_finished",
    )


def _completed(**overrides: object) -> ContextualAppRunSnapshot:
    payload: dict[str, object] = {
        "run_id": RUN_ID,
        "status": "completed",
        "created_at": NOW,
        "started_at": STARTED,
        "finished_at": FINISHED,
        "user_request": "Why does this signal sound distorted?",
        "analyzed_channel": "mixdown",
        "test_source": _source("test.wav"),
        "reference_source": _source("ref.wav"),
        "stimulus_context": _context(),
        "effective_capabilities": EffectiveCapabilities(
            clipping=True,
            paired_harmonic_attribution=False,
        ),
        "test_preview": _preview(),
        "planner_identity": _planner(),
        "trace_events": (
            TraceEventView(
                event_index=0,
                kind="observation",
                action_name="analyze_contextual_distortion",
                status="success",
                purpose="qualify",
                reference_ids=("ev_context_valid_001",),
            ),
        ),
        "result": _result(),
    }
    payload.update(overrides)
    return ContextualAppRunSnapshot.model_validate(payload)


def test_t_cx105_report_discloses_context_and_same_run_refs() -> None:
    report = build_contextual_diagnosis_report(
        _completed(),
        generated_at=GENERATED,
    )
    assert isinstance(report, ContextualDiagnosisReport)
    assert report.schema_version == "1.0.0"
    assert report.test_source.display_name == "test.wav"
    assert report.reference_source is not None
    assert report.reference_source.display_name == "ref.wav"
    assert report.stimulus_context.mode == "paired_reference"
    assert report.effective_capabilities.paired_harmonic_attribution is False
    assert report.effective_capabilities.clipping is True

    html = render_contextual_report_html(report)
    assert "paired_reference" in html
    assert "user_supplied" in html
    assert "test.wav" in html
    assert "ref.wav" in html
    assert "paired_harmonic_attribution" in html
    assert "clipping" in html
    assert "Measured" in html or "measured" in html
    assert "Declared" in html or "declared" in html or "StimulusContext" in html

    payload = render_contextual_report_json(report)
    assert '"schema_version":"1.0.0"' in payload
    assert "sig_ref" in payload

    broken = _completed(result=_result(evidence_id="ev_context_valid_001"))
    assert broken.result is not None
    assert broken.result.diagnosis is not None
    claim = broken.result.diagnosis.claims[0].model_copy(
        update={"evidence_refs": ("ev_missing_999",)}
    )
    diagnosis = broken.result.diagnosis.model_copy(update={"claims": (claim,)})
    result = broken.result.model_copy(update={"diagnosis": diagnosis})
    broken = broken.model_copy(update={"result": result})
    with pytest.raises(TraceIntegrityError):
        build_contextual_diagnosis_report(broken, generated_at=GENERATED)
