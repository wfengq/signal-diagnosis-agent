"""T-CX264 / T-CX265 / T-CX319–T-CX322: context_guidance builder."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.app.context_guidance import (
    ContextGuidance,
    ObservedFact,
    build_context_guidance,
)
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualDiagnosisReport,
)
from signal_diag.app.contextual_reporting import build_contextual_diagnosis_report
from signal_diag.app.errors import TraceIntegrityError
from signal_diag.app.models import (
    PlannerIdentity,
    SourceSummary,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.evaluation.planner_ablation.models import StudyObservedFactView
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext
from signal_diag.signal.models import TimeRange
from signal_diag.tools.evidence import Evidence

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
STARTED = datetime(2026, 9, 4, 12, 1, tzinfo=UTC)
FINISHED = datetime(2026, 9, 4, 12, 2, tzinfo=UTC)
GENERATED = datetime(2026, 9, 4, 12, 3, tzinfo=UTC)
RUN_ID = "run_" + "a" * 32


def _evidence(
    *,
    metric: str,
    value: object,
    evidence_id: str = "ev_guide_001",
    tool: str = "analyze_harmonic_distortion",
    unit: str | None = "%",
    validity: str = "valid",
    channel: str = "mixdown",
    time_range: TimeRange | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=tool,  # type: ignore[arg-type]
        call_id="call_analyze_harmonic_distortion_000000",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        unit=unit,
        channel=channel,  # type: ignore[arg-type]
        validity=validity,  # type: ignore[arg-type]
        time_range=time_range,
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


def _source(name: str = "test.wav") -> SourceSummary:
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


def _single_signal_context() -> StimulusContext:
    return StimulusContext(
        mode="single_signal",
        test_signal_id="sig_test",
        assertion_source="user_supplied",
    )


def _single_signal_snapshot(
    *,
    result: AgentRunResult,
    context_guidance: ContextGuidance,
) -> ContextualAppRunSnapshot:
    return ContextualAppRunSnapshot.model_validate(
        {
            "run_id": RUN_ID,
            "status": "completed",
            "created_at": NOW,
            "started_at": STARTED,
            "finished_at": FINISHED,
            "user_request": "Why does this signal sound distorted?",
            "analyzed_channel": "mixdown",
            "test_source": _source("alone.wav"),
            "reference_source": None,
            "stimulus_context": _single_signal_context(),
            "effective_capabilities": EffectiveCapabilities(
                clipping=True,
                absolute_harmonic_description=True,
                nominal_harmonic_attribution=False,
                paired_harmonic_attribution=False,
            ),
            "test_preview": _preview(),
            "planner_identity": _planner(),
            "result": result,
            "context_guidance": context_guidance,
        }
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


def test_t_cx319_qualifying_thd_emits_field_faithful_facts() -> None:
    tr = TimeRange(start_s=0.0, end_s=1.0)
    ev = _evidence(
        metric="thd_percent",
        value=12.65,
        evidence_id="ev_analyze_harmonic_distortion_x_002",
        unit="%",
        time_range=tr,
        channel="mixdown",
    )
    result = _result(outcome="inconclusive", evidence=(ev,))
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert len(guidance.observed_facts) == 1
    fact = guidance.observed_facts[0]
    assert fact.evidence_id == ev.evidence_id
    assert fact.source_tool == ev.source_tool
    assert fact.call_id == ev.call_id
    assert fact.metric == ev.metric
    assert fact.value == ev.value
    assert fact.unit == ev.unit
    assert fact.validity == "valid"
    assert fact.channel == ev.channel
    assert fact.time_range == ev.time_range
    assert "可能是" not in guidance.summary
    assert "likely" not in guidance.summary.lower()


def test_t_cx320_harmonic_reason_with_empty_display_facts() -> None:
    ev = _evidence(
        metric="even_order_present",
        value=True,
        unit=None,
        evidence_id="ev_guide_eop",
    )
    result = _result(outcome="inconclusive", evidence=(ev,))
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert guidance.observed_facts == ()


def test_t_cx321_display_exclusions_keep_harmonic_reason() -> None:
    nan_ev = _evidence(metric="thd_percent", value=float("nan"), evidence_id="ev_nan")
    inf_ev = _evidence(metric="thd_percent", value=float("inf"), evidence_id="ev_inf")
    int_ev = _evidence(metric="thd_percent", value=12, evidence_id="ev_int")
    bool_ev = _evidence(
        metric="thd_percent", value=True, unit="%", evidence_id="ev_bool"
    )
    str_ev = _evidence(
        metric="thd_percent", value="12.65", unit="%", evidence_id="ev_str"
    )
    wrong_tool = _evidence(
        metric="thd_percent",
        value=9.0,
        tool="detect_clipping",
        evidence_id="ev_wrong_tool",
    )
    na = _evidence(
        metric="thd_percent",
        value="not_applicable",
        validity="not_applicable",
        evidence_id="ev_na",
    )
    result = _result(
        outcome="inconclusive",
        evidence=(nan_ev, inf_ev, int_ev, bool_ev, str_ev, wrong_tool, na),
    )
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert guidance.reason_codes == ("harmonic_attribution_requires_context",)
    assert guidance.observed_facts == ()

    clean = _result(outcome="inconclusive", evidence=())
    g_insufficient = build_context_guidance(mode="single_signal", result=clean)
    assert g_insufficient is not None
    assert g_insufficient.reason_codes == ("insufficient_evidence_for_supported_fault",)
    assert g_insufficient.observed_facts == ()


def test_t_cx322_compat_old_payload_and_report_round_trip() -> None:
    old = ContextGuidance.model_validate(
        {
            "reason_codes": ("insufficient_evidence_for_supported_fault",),
            "unlockable_modes": ("paired_reference", "nominal_single_tone"),
            "required_inputs": {
                "paired_reference": ("reference_wav",),
                "nominal_single_tone": (
                    "nominal_fundamental_hz",
                    "stimulus_kind=single_tone",
                ),
            },
            "summary": "fixture summary without observed_facts key",
        }
    )
    assert old.observed_facts == ()

    tr = TimeRange(start_s=0.0, end_s=1.0)
    ev = _evidence(
        metric="thd_percent",
        value=12.65,
        evidence_id="ev_rt_001",
        time_range=tr,
    )
    guidance = build_context_guidance(
        mode="single_signal",
        result=_result(outcome="inconclusive", evidence=(ev,)),
    )
    assert guidance is not None
    snapshot = _single_signal_snapshot(
        result=_result(outcome="inconclusive", evidence=(ev,)),
        context_guidance=guidance,
    )
    payload = snapshot.model_dump(mode="json")
    restored = ContextualAppRunSnapshot.model_validate(payload)
    assert restored.context_guidance is not None
    fact = restored.context_guidance.observed_facts[0]
    assert fact.metric == "thd_percent"
    assert isinstance(fact.value, float) and fact.value == 12.65
    assert fact.unit == "%"
    assert fact.time_range == tr
    assert fact.channel == "mixdown"

    report = build_contextual_diagnosis_report(restored, generated_at=GENERATED)
    report2 = ContextualDiagnosisReport.model_validate(report.model_dump(mode="json"))
    assert report2.context_guidance is not None
    assert report2.context_guidance.observed_facts[0].evidence_id == "ev_rt_001"


def test_observed_facts_dedupe_keeps_smaller_evidence_id() -> None:
    tr = TimeRange(start_s=0.0, end_s=1.0)
    ev_lo = _evidence(
        metric="thd_percent",
        value=12.65,
        evidence_id="ev_a_lo",
        time_range=tr,
    )
    ev_hi = _evidence(
        metric="thd_percent",
        value=99.0,
        evidence_id="ev_z_hi",
        time_range=tr,
    )
    result = _result(outcome="inconclusive", evidence=(ev_hi, ev_lo))
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert len(guidance.observed_facts) == 1
    assert guidance.observed_facts[0].evidence_id == "ev_a_lo"
    assert guidance.observed_facts[0].value == 12.65


def _qualifying_fact(**overrides: object) -> ObservedFact:
    payload: dict[str, object] = {
        "evidence_id": "ev_rt_001",
        "source_tool": "analyze_harmonic_distortion",
        "call_id": "call_analyze_harmonic_distortion_000000",
        "metric": "thd_percent",
        "value": 12.65,
        "unit": "%",
        "validity": "valid",
        "time_range": TimeRange(start_s=0.0, end_s=1.0),
        "channel": "mixdown",
    }
    payload.update(overrides)
    return ObservedFact.model_validate(payload)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_observed_fact_model_rejects_non_finite_float(bad: float) -> None:
    with pytest.raises(ValidationError):
        _qualifying_fact(value=bad)
    with pytest.raises(ValidationError):
        StudyObservedFactView.model_validate(
            {
                "evidence_id": "ev_rt_001",
                "source_tool": "analyze_harmonic_distortion",
                "call_id": "call_analyze_harmonic_distortion_000000",
                "metric": "thd_percent",
                "value": bad,
                "unit": "%",
                "channel": "mixdown",
            }
        )


@pytest.mark.parametrize(
    "tamper",
    [
        {"evidence_id": "ev_missing_999"},
        {"value": 99.0},
        {"channel": "left"},
    ],
)
def test_report_rejects_observed_facts_inconsistent_with_evidence(
    tamper: dict[str, object],
) -> None:
    tr = TimeRange(start_s=0.0, end_s=1.0)
    ev = _evidence(
        metric="thd_percent",
        value=12.65,
        evidence_id="ev_rt_001",
        time_range=tr,
    )
    result = _result(outcome="inconclusive", evidence=(ev,))
    guidance = build_context_guidance(mode="single_signal", result=result)
    assert guidance is not None
    assert len(guidance.observed_facts) == 1
    tampered = guidance.observed_facts[0].model_copy(update=tamper)
    broken_guidance = guidance.model_copy(update={"observed_facts": (tampered,)})
    snapshot = _single_signal_snapshot(result=result, context_guidance=broken_guidance)
    with pytest.raises(TraceIntegrityError):
        build_contextual_diagnosis_report(snapshot, generated_at=GENERATED)

    good_report = build_contextual_diagnosis_report(
        _single_signal_snapshot(result=result, context_guidance=guidance),
        generated_at=GENERATED,
    )
    payload = good_report.model_dump(mode="json")
    assert payload["context_guidance"] is not None
    fact_payload = dict(payload["context_guidance"]["observed_facts"][0])
    fact_payload.update(tamper)
    payload["context_guidance"]["observed_facts"] = [fact_payload]
    with pytest.raises(ValidationError):
        ContextualDiagnosisReport.model_validate(payload)
