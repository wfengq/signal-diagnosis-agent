"""Checkpoint L — pure per-run scoring (T155, T157–T165)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from signal_diag.agent.models import (
    AgentRunResult,
    AnalyzeHarmonicDistortionCall,
    AnalyzeSpectrumCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    Observation,
    PlannerContext,
    RetrieveKnowledgeDecision,
    StructuredDiagnosis,
    TaskAssessment,
    ToolHistoryEntry,
)
from signal_diag.agent.policies import normalize_tool_arguments
from signal_diag.evaluation import score_evaluation_trace
from signal_diag.evaluation.models import (
    BaselineDiagnosis,
    BaselineRunResult,
    BenchmarkConfig,
    EvaluationCase,
    EvaluationTrace,
    KnowledgeRetrievalEvent,
    ObservationEvent,
    PlannerDecisionEvent,
    PlannerDecisionRecord,
    ProviderUsage,
    RuleEvaluationEvent,
)
from signal_diag.knowledge.models import (
    KnowledgeChunk,
    KnowledgeMatch,
    KnowledgeRetrievalResult,
)
from signal_diag.rules.models import RuleEvaluation, RuleEvaluationBatch
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.contracts import (
    ClippingInput,
    HarmonicDistortionInput,
    SpectrumInput,
)
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.registry import get_tool_descriptors
from tests.evaluation.conftest import (
    make_condition,
    make_evaluation_case,
    make_sufficient_set,
)

FAILURE_EXACT_SET = "exact_set_mismatch"
FAILURE_OUTCOME = "outcome_mismatch"
FAILURE_UNGROUNDED = "ungrounded_claim"
FAILURE_UNSUPPORTED = "unsupported_fault_claim"
FAILURE_FIRST_TOOL = "first_tool_incorrect"
FAILURE_INAPPROPRIATE_REPLAN = "inappropriate_replan"
FAILURE_UNNECESSARY_TOOL = "unnecessary_tool"
FAILURE_LATE_TOOL = "late_tool_after_sufficiency"
FAILURE_PREMATURE_RULE = "premature_rule"
FAILURE_REDUNDANT_RULE = "redundant_rule"
FAILURE_OMITTED_RULE = "omitted_rule"
FAILURE_REQUIRED_KNOWLEDGE_OMITTED = "required_knowledge_omitted"
FAILURE_UNNECESSARY_KNOWLEDGE = "unnecessary_knowledge"
FAILURE_IRRELEVANT_TAGS = "irrelevant_knowledge_tags"
FAILURE_UNCITED_KNOWLEDGE = "uncited_knowledge"

_ASSESSMENT = TaskAssessment(task_type="distortion_analysis", objective="diagnose")


def _config() -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id="bench_task6",
        dataset_id="s1-distortion-synthetic",
        dataset_version="1.0.0",
        rule_profile_id="profile_s1_distortion",
        rule_profile_version="1.0.0-demo",
        started_at_utc=datetime(2026, 8, 29, 10, 0, tzinfo=UTC),
    )


def _context() -> PlannerContext:
    return PlannerContext(
        run_id="run_scoring",
        user_request="Diagnose this signal.",
        signal_meta=SignalMeta(
            signal_id="sig_scoring",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        task_assessment=_ASSESSMENT,
        observations=(),
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
    )


def _tool_call(tool_name: str) -> CallToolDecision:
    if tool_name == "detect_clipping":
        call: Any = DetectClippingCall(args=ClippingInput())
    elif tool_name == "analyze_harmonic_distortion":
        call = AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput())
    elif tool_name == "analyze_spectrum":
        call = AnalyzeSpectrumCall(args=SpectrumInput())
    else:
        raise ValueError(tool_name)
    return CallToolDecision(
        task_assessment=_ASSESSMENT,
        call=call,
        purpose=f"call {tool_name}",
    )


def _evidence(
    *,
    evidence_id: str,
    call_id: str,
    tool_name: str,
    metric: str,
    value: object,
    unit: str | None = None,
    validity: str = "valid",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=tool_name,  # type: ignore[arg-type]
        call_id=call_id,
        metric=metric,
        value=value,  # type: ignore[arg-type]
        unit=unit,
        validity=validity,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _observation(
    *,
    observation_id: str,
    call_id: str,
    tool_name: str,
    evidence_ids: tuple[str, ...],
    status: str = "success",
    decision: CallToolDecision | None = None,
) -> Observation:
    call = decision.call if decision is not None else _tool_call(tool_name).call
    return Observation(
        observation_id=observation_id,
        call_id=call_id,
        tool_name=tool_name,  # type: ignore[arg-type]
        normalized_arguments=normalize_tool_arguments(call),
        purpose=f"call {tool_name}",
        status=status,  # type: ignore[arg-type]
        evidence_refs=evidence_ids,
        error_message="tool failed" if status == "error" else None,
    )


def _rule_batch(batch_id: str, evaluation_id: str, evidence_refs: tuple[str, ...]) -> RuleEvaluationBatch:
    return RuleEvaluationBatch(
        batch_id=batch_id,
        profile_id="profile_s1_distortion",
        profile_version="1.0.0-demo",
        evaluations=(
            RuleEvaluation(
                evaluation_id=evaluation_id,
                rule_id="rule_clipping_ratio_acceptable",
                judgment="pass",
                observed_value=0.0,
                comparator="lte",
                threshold=0.01,
                profile_id="profile_s1_distortion",
                profile_version="1.0.0-demo",
                evidence_refs=evidence_refs or ("ev_placeholder",),
            ),
        ),
    )


def _retrieval(
    *,
    retrieval_id: str,
    tags: tuple[str, ...],
) -> KnowledgeRetrievalResult:
    chunk = KnowledgeChunk(
        chunk_id="chunk_scoring_000",
        document_id="doc_scoring",
        title="Scoring notes",
        excerpt="Relevant excerpt.",
        tags=tags,
    )
    return KnowledgeRetrievalResult(
        retrieval_id=retrieval_id,
        query_text=" ".join(tags) or "notes",
        query_tags=tags,
        matches=(
            KnowledgeMatch(
                document_id="doc_scoring",
                chunk_id="chunk_scoring_000",
                matched_tags=tags,
            ),
        )
        if tags
        else (),
        chunks=(chunk,) if tags else (),
    )


def _claim(
    *,
    claim_id: str,
    fault_type: str,
    evidence_refs: tuple[str, ...] = (),
    rule_refs: tuple[str, ...] = (),
    knowledge_refs: tuple[str, ...] = (),
) -> DiagnosisClaim:
    return DiagnosisClaim(
        claim_id=claim_id,
        fault_type=fault_type,  # type: ignore[arg-type]
        statement=f"{fault_type} claim",
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
        knowledge_refs=knowledge_refs,
    )


def _decision_record(
    index: int,
    context: PlannerContext,
    decision: Any,
) -> PlannerDecisionRecord:
    return PlannerDecisionRecord(
        record_id=f"decision_{index:06d}",
        decision_index=index,
        context=context,
        status="decision",
        decision=decision,
        latency_ms=1.0,
    )


def _clean_case() -> EvaluationCase:
    condition = make_condition(
        condition_id="cond_clean_clip",
        tool_name="detect_clipping",
        metric="clipping_detected",
        comparator="eq",
        expected_value=False,
        supports_claims=("no_supported_fault",),
    )
    harmonic = make_condition(
        condition_id="cond_clean_thd",
        tool_name="analyze_harmonic_distortion",
        metric="thd_percent",
        comparator="lte",
        expected_value=5.0,
        unit="%",
        supports_claims=("no_supported_fault",),
    )
    return make_evaluation_case(
        "clean",
        case_id="case_score_clean_01",
        acceptable_first_tools=("detect_clipping", "analyze_harmonic_distortion"),
        observable_conditions=(condition, harmonic),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_clean",
                condition_refs=("cond_clean_clip", "cond_clean_thd"),
                supported_claims=("no_supported_fault",),
                acceptable_outcomes=("no_supported_fault",),
            ),
        ),
    )


def _clipping_case() -> EvaluationCase:
    condition = make_condition(
        condition_id="cond_clip",
        tool_name="detect_clipping",
        metric="clipping_detected",
        comparator="eq",
        expected_value=True,
        supports_claims=("clipping",),
    )
    return make_evaluation_case(
        "clipping",
        case_id="case_score_clip_01",
        acceptable_first_tools=("detect_clipping",),
        observable_conditions=(condition,),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_clip",
                condition_refs=("cond_clip",),
                supported_claims=("clipping",),
                acceptable_outcomes=("supported_fault",),
            ),
        ),
    )


def _harmonic_case() -> EvaluationCase:
    clipping_absent = make_condition(
        condition_id="cond_harm_clip_absent",
        tool_name="detect_clipping",
        metric="clipping_detected",
        comparator="eq",
        expected_value=False,
        supports_claims=(),
    )
    valid = make_condition(
        condition_id="cond_harm_valid",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        comparator="eq",
        expected_value=True,
        supports_claims=("harmonic_distortion",),
    )
    thd = make_condition(
        condition_id="cond_harm_thd",
        tool_name="analyze_harmonic_distortion",
        metric="thd_percent",
        comparator="gt",
        expected_value=5.0,
        unit="%",
        supports_claims=("harmonic_distortion",),
    )
    return make_evaluation_case(
        "harmonic",
        case_id="case_score_harm_01",
        acceptable_first_tools=("detect_clipping", "analyze_harmonic_distortion"),
        observable_conditions=(clipping_absent, valid, thd),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_harm_direct",
                condition_refs=("cond_harm_valid", "cond_harm_thd"),
                supported_claims=("harmonic_distortion",),
                acceptable_outcomes=("supported_fault",),
            ),
            make_sufficient_set(
                evidence_set_id="evset_harm_via_clip",
                condition_refs=(
                    "cond_harm_clip_absent",
                    "cond_harm_valid",
                    "cond_harm_thd",
                ),
                supported_claims=("harmonic_distortion",),
                acceptable_outcomes=("supported_fault",),
            ),
        ),
    )


def _combined_case() -> EvaluationCase:
    clipping = make_condition(
        condition_id="cond_comb_clip",
        tool_name="detect_clipping",
        metric="clipping_detected",
        comparator="eq",
        expected_value=True,
        supports_claims=("clipping",),
    )
    thd = make_condition(
        condition_id="cond_comb_thd",
        tool_name="analyze_harmonic_distortion",
        metric="thd_percent",
        comparator="gt",
        expected_value=5.0,
        unit="%",
        supports_claims=("harmonic_distortion",),
    )
    return make_evaluation_case(
        "combined",
        case_id="case_score_comb_01",
        acceptable_first_tools=("detect_clipping", "analyze_harmonic_distortion"),
        observable_conditions=(clipping, thd),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_comb",
                condition_refs=("cond_comb_clip", "cond_comb_thd"),
                supported_claims=("clipping", "harmonic_distortion"),
                acceptable_outcomes=("supported_fault",),
            ),
        ),
    )


def _noise_case() -> EvaluationCase:
    condition = make_condition(
        condition_id="cond_noise",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        validity="not_applicable",
        comparator="eq",
        expected_value=False,
        supports_claims=("inconclusive",),
    )
    return make_evaluation_case(
        "invalid_noise",
        case_id="case_score_noise_01",
        acceptable_first_tools=("analyze_harmonic_distortion",),
        observable_conditions=(condition,),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_noise",
                condition_refs=("cond_noise",),
                supported_claims=("inconclusive",),
                acceptable_outcomes=("inconclusive",),
            ),
        ),
    )


def _agent_trace(
    case: EvaluationCase,
    steps: tuple[dict[str, Any], ...],
    *,
    claims: tuple[DiagnosisClaim, ...],
    outcome: str,
    diagnosis: StructuredDiagnosis | None | object = ...,
    termination_reason: str = "planner_finished",
    status: str = "success",
    provider_usage: ProviderUsage | None = None,
) -> EvaluationTrace:
    context = _context()
    events: list[Any] = []
    observations: list[Observation] = []
    evidence: list[Evidence] = []
    batches: list[RuleEvaluationBatch] = []
    retrievals: list[KnowledgeRetrievalResult] = []
    history: list[ToolHistoryEntry] = []
    event_index = 0
    decision_index = 0
    finish_decision: FinishDecision | None = None

    for step in steps:
        kind = step["kind"]
        if kind == "tool":
            decision = _tool_call(step["tool_name"])
            record = _decision_record(decision_index, context, decision)
            events.append(
                PlannerDecisionEvent(event_index=event_index, record=record)
            )
            event_index += 1
            call_id = step.get("call_id", f"call_{decision_index:03d}")
            items = tuple(step["evidence"])
            obs = _observation(
                observation_id=step.get("observation_id", f"obs_{decision_index:03d}"),
                call_id=call_id,
                tool_name=step["tool_name"],
                evidence_ids=tuple(item.evidence_id for item in items),
                status=step.get("status", "success"),
                decision=decision,
            )
            events.append(
                ObservationEvent(
                    event_index=event_index,
                    caused_by_decision_index=decision_index,
                    observation=obs,
                    evidence=items,
                )
            )
            event_index += 1
            observations.append(obs)
            evidence.extend(items)
            history.append(
                ToolHistoryEntry(
                    call_id=call_id,
                    tool_name=step["tool_name"],  # type: ignore[arg-type]
                    normalized_arguments=obs.normalized_arguments,
                    purpose=obs.purpose,
                    status=obs.status,
                )
            )
            context = context.model_copy(
                update={
                    "observations": tuple(observations),
                    "evidence": tuple(evidence),
                    "tool_history": tuple(history),
                }
            )
            decision_index += 1
        elif kind == "rules":
            batch: RuleEvaluationBatch = step["batch"]
            decision = EvaluateRulesDecision(
                task_assessment=_ASSESSMENT,
                profile_id="profile_s1_distortion",
                evidence_refs=tuple(item.evidence_id for item in evidence),
                purpose="apply official profile",
            )
            record = _decision_record(decision_index, context, decision)
            events.append(
                PlannerDecisionEvent(event_index=event_index, record=record)
            )
            event_index += 1
            events.append(
                RuleEvaluationEvent(
                    event_index=event_index,
                    caused_by_decision_index=decision_index,
                    batch=batch,
                )
            )
            event_index += 1
            batches.append(batch)
            context = context.model_copy(
                update={"rule_evaluation_batches": tuple(batches)}
            )
            decision_index += 1
        elif kind == "knowledge":
            retrieval: KnowledgeRetrievalResult = step["retrieval"]
            decision = RetrieveKnowledgeDecision(
                task_assessment=_ASSESSMENT,
                query_text=retrieval.query_text or "notes",
                tags=retrieval.query_tags,
                purpose="retrieve notes",
            )
            record = _decision_record(decision_index, context, decision)
            events.append(
                PlannerDecisionEvent(event_index=event_index, record=record)
            )
            event_index += 1
            events.append(
                KnowledgeRetrievalEvent(
                    event_index=event_index,
                    caused_by_decision_index=decision_index,
                    retrieval=retrieval,
                )
            )
            event_index += 1
            retrievals.append(retrieval)
            context = context.model_copy(
                update={"knowledge_retrievals": tuple(retrievals)}
            )
            decision_index += 1
        elif kind == "finish":
            finish_decision = FinishDecision(
                task_assessment=_ASSESSMENT,
                outcome=outcome,  # type: ignore[arg-type]
                claims=claims,
                confidence_label="high",
            )
            record = _decision_record(decision_index, context, finish_decision)
            events.append(
                PlannerDecisionEvent(event_index=event_index, record=record)
            )
            event_index += 1
            decision_index += 1
        else:
            raise ValueError(kind)

    resolved_diagnosis: StructuredDiagnosis | None
    if diagnosis is ...:
        resolved_diagnosis = StructuredDiagnosis(
            run_id="run_scoring",
            task_type="distortion_analysis",
            outcome=outcome,  # type: ignore[arg-type]
            claims=claims,
            confidence_label="high",
            limitations=("invalid harmonic analysis",) if outcome == "inconclusive" else (),
            termination_reason=termination_reason,  # type: ignore[arg-type]
            tool_call_count=len(observations),
            rule_evaluation_batches=tuple(batches),
            knowledge_retrievals=tuple(retrievals),
        )
    else:
        resolved_diagnosis = diagnosis  # type: ignore[assignment]

    result = AgentRunResult(
        run_id="run_scoring",
        status=status,  # type: ignore[arg-type]
        diagnosis=resolved_diagnosis,
        observations=tuple(observations),
        evidence=tuple(evidence),
        tool_history=tuple(history),
        termination_reason=termination_reason,  # type: ignore[arg-type]
        rule_evaluation_batches=tuple(batches),
        knowledge_retrievals=tuple(retrievals),
    )
    return EvaluationTrace(
        trace_id=f"trace_agent_{case.case_id}_01",
        case_id=case.case_id,
        run_slot=1,
        execution_path="agent",
        config=_config(),
        events=tuple(events),
        result=result,
        provider_usage=provider_usage,
    )


def _baseline_trace(
    case: EvaluationCase,
    *,
    observations: tuple[Observation, ...],
    evidence: tuple[Evidence, ...],
    batches: tuple[RuleEvaluationBatch, ...],
    claims: tuple[DiagnosisClaim, ...],
    outcome: str,
) -> EvaluationTrace:
    diagnosis = BaselineDiagnosis(
        run_id="baseline_scoring",
        outcome=outcome,  # type: ignore[arg-type]
        claims=claims,
        confidence_label="medium",
        tool_call_count=len(observations),
        rule_evaluation_batches=batches,
    )
    result = BaselineRunResult(
        run_id="baseline_scoring",
        status="success",
        diagnosis=diagnosis,
        observations=observations,
        evidence=evidence,
        tool_history=tuple(
            ToolHistoryEntry(
                call_id=item.call_id,
                tool_name=item.tool_name,
                normalized_arguments=item.normalized_arguments,
                purpose=item.purpose,
                status=item.status,
            )
            for item in observations
        ),
        completion_reason="baseline_completed",
        rule_evaluation_batches=batches,
    )
    events: list[Any] = []
    event_index = 0
    evidence_by_id = {item.evidence_id: item for item in evidence}
    for ordinal, observation in enumerate(observations):
        attached = tuple(evidence_by_id[ref] for ref in observation.evidence_refs)
        events.append(
            ObservationEvent(
                event_index=event_index,
                caused_by_decision_index=ordinal,
                observation=observation,
                evidence=attached,
            )
        )
        event_index += 1
    for batch in batches:
        events.append(
            RuleEvaluationEvent(
                event_index=event_index,
                caused_by_decision_index=2,
                batch=batch,
            )
        )
        event_index += 1
    return EvaluationTrace(
        trace_id=f"trace_fixed_pipeline_{case.case_id}_01",
        case_id=case.case_id,
        run_slot=1,
        execution_path="fixed_pipeline",
        config=_config(),
        events=tuple(events),
        result=result,
        provider_usage=None,
    )


def _clip_ev(evidence_id: str, call_id: str, *, detected: bool) -> Evidence:
    return _evidence(
        evidence_id=evidence_id,
        call_id=call_id,
        tool_name="detect_clipping",
        metric="clipping_detected",
        value=detected,
    )


def _thd_ev(
    evidence_id: str,
    call_id: str,
    *,
    value: float,
    comparator_pass_gt: bool = True,
) -> Evidence:
    del comparator_pass_gt
    return _evidence(
        evidence_id=evidence_id,
        call_id=call_id,
        tool_name="analyze_harmonic_distortion",
        metric="thd_percent",
        value=value,
        unit="%",
    )


def _harm_valid_ev(evidence_id: str, call_id: str, *, valid: bool = True) -> Evidence:
    return _evidence(
        evidence_id=evidence_id,
        call_id=call_id,
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        value=valid,
    )


def _legal_clipping_trace(
    case: EvaluationCase | None = None,
    *,
    claims: tuple[DiagnosisClaim, ...] | None = None,
    outcome: str = "supported_fault",
) -> tuple[EvaluationCase, EvaluationTrace]:
    case = case or _clipping_case()
    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    batch = _rule_batch("rulebatch_clip", "ruleval_clip", ("ev_clip",))
    if claims is None:
        claims = (
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        )
    trace = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=claims,
        outcome=outcome,
    )
    return case, trace


def _legal_clean_trace() -> tuple[EvaluationCase, EvaluationTrace]:
    case = _clean_case()
    clip = _clip_ev("ev_clean_clip", "call_000", detected=False)
    thd = _thd_ev("ev_clean_thd", "call_001", value=1.0)
    batch = _rule_batch(
        "rulebatch_clean", "ruleval_clean", ("ev_clean_clip", "ev_clean_thd")
    )
    claims = (
        _claim(
            claim_id="claim_clean",
            fault_type="no_supported_fault",
            evidence_refs=("ev_clean_clip", "ev_clean_thd"),
            rule_refs=("ruleval_clean",),
        ),
    )
    trace = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (clip,)},
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (thd,),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=claims,
        outcome="no_supported_fault",
    )
    return case, trace


def _legal_harmonic_trace(*, first: str = "analyze_harmonic_distortion") -> tuple[EvaluationCase, EvaluationTrace]:
    case = _harmonic_case()
    valid = _harm_valid_ev("ev_harm_valid", "call_000", valid=True)
    thd = _thd_ev("ev_harm_thd", "call_000", value=8.0)
    batch = _rule_batch(
        "rulebatch_harm", "ruleval_harm", ("ev_harm_valid", "ev_harm_thd")
    )
    claims = (
        _claim(
            claim_id="claim_harm",
            fault_type="harmonic_distortion",
            evidence_refs=("ev_harm_valid", "ev_harm_thd"),
            rule_refs=("ruleval_harm",),
        ),
    )
    trace = _agent_trace(
        case,
        (
            {
                "kind": "tool",
                "tool_name": first,
                "evidence": (valid, thd),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=claims,
        outcome="supported_fault",
    )
    return case, trace


def _legal_combined_trace() -> tuple[EvaluationCase, EvaluationTrace]:
    case = _combined_case()
    clip = _clip_ev("ev_comb_clip", "call_000", detected=True)
    thd = _thd_ev("ev_comb_thd", "call_001", value=9.0)
    batch = _rule_batch(
        "rulebatch_comb", "ruleval_comb", ("ev_comb_clip", "ev_comb_thd")
    )
    claims = (
        _claim(
            claim_id="claim_comb_clip",
            fault_type="clipping",
            evidence_refs=("ev_comb_clip",),
            rule_refs=("ruleval_comb",),
        ),
        _claim(
            claim_id="claim_comb_harm",
            fault_type="harmonic_distortion",
            evidence_refs=("ev_comb_thd",),
            rule_refs=("ruleval_comb",),
        ),
    )
    trace = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (clip,)},
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (thd,),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=claims,
        outcome="supported_fault",
    )
    return case, trace


def _legal_noise_trace(
    *,
    retrieve: bool = True,
    cite: bool = True,
    tags: tuple[str, ...] | None = None,
) -> tuple[EvaluationCase, EvaluationTrace]:
    case = _noise_case()
    evidence = _evidence(
        evidence_id="ev_noise",
        call_id="call_000",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        value=False,
        validity="not_applicable",
    )
    batch = _rule_batch("rulebatch_noise", "ruleval_noise", ("ev_noise",))
    retrieval = _retrieval(
        retrieval_id="know_noise",
        tags=case.knowledge_tags if tags is None else tags,
    )
    claims = (
        _claim(
            claim_id="claim_noise",
            fault_type="inconclusive",
            evidence_refs=("ev_noise",),
            rule_refs=("ruleval_noise",),
            knowledge_refs=("know_noise",) if retrieve and cite else (),
        ),
    )
    steps: list[dict[str, Any]] = [
        {
            "kind": "tool",
            "tool_name": "analyze_harmonic_distortion",
            "evidence": (evidence,),
        },
        {"kind": "rules", "batch": batch},
    ]
    if retrieve:
        steps.append({"kind": "knowledge", "retrieval": retrieval})
    steps.append({"kind": "finish"})
    trace = _agent_trace(
        case,
        tuple(steps),
        claims=claims,
        outcome="inconclusive",
    )
    return case, trace


def test_score_evaluation_trace_is_package_public_export() -> None:
    from signal_diag.evaluation.scoring import score_evaluation_trace as module_fn

    assert score_evaluation_trace is module_fn


def test_t155_causal_exact_set_scoring() -> None:
    clean_case, clean_trace = _legal_clean_trace()
    clean = score_evaluation_trace(clean_case, clean_trace)
    assert clean.expected_faults == ()
    assert clean.predicted_faults == ()
    assert clean.causal_exact_set_correct is True

    clip_case, clip_trace = _legal_clipping_trace()
    clip = score_evaluation_trace(clip_case, clip_trace)
    assert clip.expected_faults == ("clipping",)
    assert clip.predicted_faults == ("clipping",)
    assert clip.causal_exact_set_correct is True

    harm_case, harm_trace = _legal_harmonic_trace()
    harm = score_evaluation_trace(harm_case, harm_trace)
    assert harm.expected_faults == ("harmonic_distortion",)
    assert harm.predicted_faults == ("harmonic_distortion",)
    assert harm.causal_exact_set_correct is True

    comb_case, comb_trace = _legal_combined_trace()
    comb = score_evaluation_trace(comb_case, comb_trace)
    assert comb.expected_faults == ("clipping", "harmonic_distortion")
    assert comb.predicted_faults == ("clipping", "harmonic_distortion")
    assert comb.causal_exact_set_correct is True

    noise_case, noise_trace = _legal_noise_trace()
    noise = score_evaluation_trace(noise_case, noise_trace)
    assert noise.expected_faults == ()
    assert noise.predicted_faults == ()
    assert noise.causal_exact_set_correct is True

    duplicate_claims = (
        _claim(
            claim_id="claim_clip_a",
            fault_type="clipping",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_clip",),
        ),
        _claim(
            claim_id="claim_clip_b",
            fault_type="clipping",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_clip",),
        ),
    )
    dup_case, dup_trace = _legal_clipping_trace(claims=duplicate_claims)
    dup = score_evaluation_trace(dup_case, dup_trace)
    assert dup.predicted_faults == ("clipping",)
    assert dup.causal_exact_set_correct is True
    assert dup.predicted_fault_claims == 2

    missing_case, missing_trace = _legal_combined_trace()
    missing_claims = (
        _claim(
            claim_id="claim_only_clip",
            fault_type="clipping",
            evidence_refs=("ev_comb_clip",),
            rule_refs=("ruleval_comb",),
        ),
    )
    missing_trace = _agent_trace(
        missing_case,
        (
            {
                "kind": "tool",
                "tool_name": "detect_clipping",
                "evidence": (_clip_ev("ev_comb_clip", "call_000", detected=True),),
            },
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (_thd_ev("ev_comb_thd", "call_001", value=9.0),),
            },
            {
                "kind": "rules",
                "batch": _rule_batch(
                    "rulebatch_comb", "ruleval_comb", ("ev_comb_clip", "ev_comb_thd")
                ),
            },
            {"kind": "finish"},
        ),
        claims=missing_claims,
        outcome="supported_fault",
    )
    missing = score_evaluation_trace(missing_case, missing_trace)
    assert missing.predicted_faults == ("clipping",)
    assert missing.causal_exact_set_correct is False
    assert FAILURE_EXACT_SET in missing.failure_codes

    baseline_case = _combined_case()
    clip = _clip_ev("ev_base_clip", "call_base_0", detected=True)
    thd = _thd_ev("ev_base_thd", "call_base_1", value=9.0)
    obs0 = _observation(
        observation_id="obs_base_0",
        call_id="call_base_0",
        tool_name="detect_clipping",
        evidence_ids=("ev_base_clip",),
    )
    obs1 = _observation(
        observation_id="obs_base_1",
        call_id="call_base_1",
        tool_name="analyze_harmonic_distortion",
        evidence_ids=("ev_base_thd",),
    )
    batch = _rule_batch("rulebatch_base", "ruleval_base", ("ev_base_clip", "ev_base_thd"))
    baseline_trace = _baseline_trace(
        baseline_case,
        observations=(obs0, obs1),
        evidence=(clip, thd),
        batches=(batch,),
        claims=(
            _claim(
                claim_id="claim_base_clip",
                fault_type="clipping",
                evidence_refs=("ev_base_clip",),
                rule_refs=("ruleval_base",),
            ),
            _claim(
                claim_id="claim_base_harm",
                fault_type="harmonic_distortion",
                evidence_refs=("ev_base_thd",),
                rule_refs=("ruleval_base",),
            ),
        ),
        outcome="supported_fault",
    )
    baseline = score_evaluation_trace(baseline_case, baseline_trace)
    assert baseline.execution_path == "fixed_pipeline"
    assert baseline.causal_exact_set_correct is True
    assert baseline.first_tool_correct is None
    assert baseline.planner_calls == 0
    assert baseline.completion_reason == "baseline_completed"


def test_t157_outcome_scoring() -> None:
    clean_case, clean_trace = _legal_clean_trace()
    clean = score_evaluation_trace(clean_case, clean_trace)
    assert clean.predicted_outcome == "no_supported_fault"
    assert clean.outcome_correct is True

    noise_case, noise_trace = _legal_noise_trace()
    noise = score_evaluation_trace(noise_case, noise_trace)
    assert noise.predicted_outcome == "inconclusive"
    assert noise.outcome_correct is True

    wrong_case, _ = _legal_clean_trace()
    clip = _clip_ev("ev_clean_clip", "call_000", detected=False)
    thd = _thd_ev("ev_clean_thd", "call_001", value=1.0)
    batch = _rule_batch(
        "rulebatch_clean", "ruleval_clean", ("ev_clean_clip", "ev_clean_thd")
    )
    wrong_trace = _agent_trace(
        wrong_case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (clip,)},
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (thd,),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_wrong",
                fault_type="clipping",
                evidence_refs=("ev_clean_clip",),
                rule_refs=("ruleval_clean",),
            ),
        ),
        outcome="supported_fault",
    )
    wrong = score_evaluation_trace(wrong_case, wrong_trace)
    assert wrong.predicted_outcome == "supported_fault"
    assert wrong.outcome_correct is False
    assert FAILURE_OUTCOME in wrong.failure_codes

    disallowed_noise, _ = _legal_noise_trace()
    evidence = _evidence(
        evidence_id="ev_noise",
        call_id="call_000",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        value=False,
        validity="not_applicable",
    )
    batch = _rule_batch("rulebatch_noise", "ruleval_noise", ("ev_noise",))
    retrieval = _retrieval(retrieval_id="know_noise", tags=disallowed_noise.knowledge_tags)
    disallowed_trace = _agent_trace(
        disallowed_noise,
        (
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (evidence,),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "knowledge", "retrieval": retrieval},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_cleanish",
                fault_type="no_supported_fault",
                evidence_refs=("ev_noise",),
                rule_refs=("ruleval_noise",),
                knowledge_refs=("know_noise",),
            ),
        ),
        outcome="no_supported_fault",
    )
    disallowed = score_evaluation_trace(disallowed_noise, disallowed_trace)
    assert disallowed.predicted_outcome == "no_supported_fault"
    assert disallowed.outcome_correct is False

    absent_case = _clipping_case()
    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    absent_trace = _agent_trace(
        absent_case,
        ({"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},),
        claims=(),
        outcome="supported_fault",
        diagnosis=None,
        termination_reason="runtime_error",
        status="error",
    )
    absent = score_evaluation_trace(absent_case, absent_trace)
    assert absent.predicted_outcome is None
    assert absent.predicted_faults == ()
    assert absent.outcome_correct is False
    assert FAILURE_OUTCOME in absent.failure_codes
    assert absent.end_to_end_latency_ms is None
    assert absent.provider_usage is None


def test_t158_semantic_grounding() -> None:
    case, grounded_trace = _legal_clipping_trace()
    grounded = score_evaluation_trace(case, grounded_trace)
    assert grounded.scored_claims == 1
    assert grounded.grounded_claims == 1
    assert FAILURE_UNGROUNDED not in grounded.failure_codes

    unrelated_claims = (
        _claim(
            claim_id="claim_harm_on_clip",
            fault_type="harmonic_distortion",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_clip",),
        ),
    )
    _, unrelated_trace = _legal_clipping_trace(claims=unrelated_claims)
    unrelated = score_evaluation_trace(case, unrelated_trace)
    assert unrelated.scored_claims == 1
    assert unrelated.grounded_claims == 0
    assert FAILURE_UNGROUNDED in unrelated.failure_codes

    dangling_claims = (
        _claim(
            claim_id="claim_missing_ref",
            fault_type="clipping",
            evidence_refs=("ev_missing",),
            rule_refs=("ruleval_clip",),
        ),
    )
    _, dangling_trace = _legal_clipping_trace(claims=dangling_claims)
    dangling = score_evaluation_trace(case, dangling_trace)
    assert dangling.grounded_claims == 0
    assert FAILURE_UNGROUNDED in dangling.failure_codes

    empty_claims = (
        _claim(claim_id="claim_empty", fault_type="clipping"),
    )
    _, empty_trace = _legal_clipping_trace(claims=empty_claims)
    empty = score_evaluation_trace(case, empty_trace)
    assert empty.grounded_claims == 0

    name_only_case = _harmonic_case()
    thd_only = _thd_ev("ev_name_thd", "call_000", value=8.0)
    valid = _harm_valid_ev("ev_name_valid", "call_000", valid=True)
    batch = _rule_batch(
        "rulebatch_name", "ruleval_name", ("ev_name_thd", "ev_name_valid")
    )
    name_trace = _agent_trace(
        name_only_case,
        (
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (valid, thd_only),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_name",
                fault_type="harmonic_distortion",
                evidence_refs=("ev_name_thd",),
                rule_refs=("ruleval_name",),
            ),
        ),
        outcome="supported_fault",
    )
    by_name = score_evaluation_trace(name_only_case, name_trace)
    assert by_name.grounded_claims == 1

    unsupported_metric_case = make_evaluation_case(
        "clipping",
        case_id="case_score_clip_metric",
        acceptable_first_tools=("detect_clipping",),
        observable_conditions=(
            make_condition(
                condition_id="cond_ratio_only",
                tool_name="detect_clipping",
                metric="clipping_ratio",
                comparator="gt",
                expected_value=0.01,
                unit="ratio",
                supports_claims=(),
            ),
            make_condition(
                condition_id="cond_detected",
                tool_name="detect_clipping",
                metric="clipping_detected",
                comparator="eq",
                expected_value=True,
                supports_claims=("clipping",),
            ),
        ),
        sufficient_evidence_sets=(
            make_sufficient_set(
                evidence_set_id="evset_metric",
                condition_refs=("cond_detected",),
                supported_claims=("clipping",),
                acceptable_outcomes=("supported_fault",),
            ),
        ),
    )
    ratio_ev = _evidence(
        evidence_id="ev_ratio",
        call_id="call_000",
        tool_name="detect_clipping",
        metric="clipping_ratio",
        value=0.2,
        unit="ratio",
    )
    detected_ev = _clip_ev("ev_detected", "call_000", detected=True)
    metric_batch = _rule_batch("rulebatch_metric", "ruleval_metric", ("ev_detected",))
    metric_trace = _agent_trace(
        unsupported_metric_case,
        (
            {
                "kind": "tool",
                "tool_name": "detect_clipping",
                "evidence": (ratio_ev, detected_ev),
            },
            {"kind": "rules", "batch": metric_batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_metric",
                fault_type="clipping",
                evidence_refs=("ev_ratio",),
                rule_refs=("ruleval_metric",),
            ),
        ),
        outcome="supported_fault",
    )
    metric_score = score_evaluation_trace(unsupported_metric_case, metric_trace)
    assert metric_score.grounded_claims == 0
    assert FAILURE_UNGROUNDED in metric_score.failure_codes


def test_t159_unsupported_claim_scoring() -> None:
    case, clean_trace = _legal_clean_trace()
    clean = score_evaluation_trace(case, clean_trace)
    assert clean.predicted_fault_claims == 0
    assert clean.unsupported_fault_claims == 0

    clip_case, clip_trace = _legal_clipping_trace()
    clip = score_evaluation_trace(clip_case, clip_trace)
    assert clip.predicted_fault_claims == 1
    assert clip.unsupported_fault_claims == 0

    extra_claims = (
        _claim(
            claim_id="claim_cleanish",
            fault_type="no_supported_fault",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_clip",),
        ),
        _claim(
            claim_id="claim_extra_a",
            fault_type="harmonic_distortion",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_clip",),
        ),
        _claim(
            claim_id="claim_extra_b",
            fault_type="harmonic_distortion",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_clip",),
        ),
    )
    _, extra_trace = _legal_clipping_trace(claims=extra_claims)
    extra = score_evaluation_trace(clip_case, extra_trace)
    assert extra.predicted_faults == ("harmonic_distortion",)
    assert extra.predicted_fault_claims == 2
    assert extra.unsupported_fault_claims == 2
    assert extra.causal_exact_set_correct is False
    assert FAILURE_UNSUPPORTED in extra.failure_codes

    noise_case, noise_trace = _legal_noise_trace()
    noise = score_evaluation_trace(noise_case, noise_trace)
    assert noise.predicted_fault_claims == 0
    assert noise.unsupported_fault_claims == 0


def test_t160_first_tool_scoring() -> None:
    harm_case, harmonic_first = _legal_harmonic_trace(
        first="analyze_harmonic_distortion"
    )
    alt = score_evaluation_trace(harm_case, harmonic_first)
    assert alt.first_tool_correct is True

    clip_first_case, clip_first_trace = _legal_harmonic_trace(first="detect_clipping")
    # Harmonic evidence on a clipping tool does not satisfy harmonic conditions;
    # first tool is still an acceptable alternative.
    clip_first = score_evaluation_trace(clip_first_case, clip_first_trace)
    assert "detect_clipping" in clip_first_case.acceptable_first_tools
    assert clip_first.first_tool_correct is True

    case, good = _legal_clipping_trace()
    assert score_evaluation_trace(case, good).first_tool_correct is True

    spectrum_ev = _evidence(
        evidence_id="ev_spec",
        call_id="call_000",
        tool_name="analyze_spectrum",
        metric="peak_frequency_hz",
        value=200.0,
        unit="Hz",
    )
    batch = _rule_batch("rulebatch_spec", "ruleval_spec", ("ev_spec",))
    wrong_trace = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "analyze_spectrum", "evidence": (spectrum_ev,)},
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_spec",
                fault_type="clipping",
                evidence_refs=("ev_spec",),
                rule_refs=("ruleval_spec",),
            ),
        ),
        outcome="supported_fault",
    )
    wrong = score_evaluation_trace(case, wrong_trace)
    assert wrong.first_tool_correct is False
    assert FAILURE_FIRST_TOOL in wrong.failure_codes

    finish_only = _agent_trace(
        case,
        ({"kind": "finish"},),
        claims=(),
        outcome="supported_fault",
        diagnosis=None,
        termination_reason="runtime_error",
        status="error",
    )
    none_tool = score_evaluation_trace(case, finish_only)
    assert none_tool.first_tool_correct is False

    baseline_case = _combined_case()
    clip = _clip_ev("ev_base_clip", "call_base_0", detected=True)
    thd = _thd_ev("ev_base_thd", "call_base_1", value=9.0)
    obs0 = _observation(
        observation_id="obs_base_0",
        call_id="call_base_0",
        tool_name="detect_clipping",
        evidence_ids=("ev_base_clip",),
    )
    obs1 = _observation(
        observation_id="obs_base_1",
        call_id="call_base_1",
        tool_name="analyze_harmonic_distortion",
        evidence_ids=("ev_base_thd",),
    )
    batch = _rule_batch("rulebatch_base", "ruleval_base", ("ev_base_clip", "ev_base_thd"))
    baseline_trace = _baseline_trace(
        baseline_case,
        observations=(obs0, obs1),
        evidence=(clip, thd),
        batches=(batch,),
        claims=(
            _claim(
                claim_id="claim_base_clip",
                fault_type="clipping",
                evidence_refs=("ev_base_clip",),
                rule_refs=("ruleval_base",),
            ),
            _claim(
                claim_id="claim_base_harm",
                fault_type="harmonic_distortion",
                evidence_refs=("ev_base_thd",),
                rule_refs=("ruleval_base",),
            ),
        ),
        outcome="supported_fault",
    )
    assert score_evaluation_trace(baseline_case, baseline_trace).first_tool_correct is None


def test_t161_observable_replanning_scoring() -> None:
    case, trace = _legal_combined_trace()
    score = score_evaluation_trace(case, trace)
    assert score.replan_opportunities == 3
    assert score.appropriate_replans == 3
    assert FAILURE_INAPPROPRIATE_REPLAN not in score.failure_codes

    clip = _clip_ev("ev_comb_clip", "call_000", detected=True)
    thd = _thd_ev("ev_comb_thd", "call_001", value=9.0)
    batch = _rule_batch(
        "rulebatch_comb", "ruleval_comb", ("ev_comb_clip", "ev_comb_thd")
    )
    stalled = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (clip,)},
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (clip,)},
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (thd,),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_comb_clip",
                fault_type="clipping",
                evidence_refs=("ev_comb_clip",),
                rule_refs=("ruleval_comb",),
            ),
            _claim(
                claim_id="claim_comb_harm",
                fault_type="harmonic_distortion",
                evidence_refs=("ev_comb_thd",),
                rule_refs=("ruleval_comb",),
            ),
        ),
        outcome="supported_fault",
    )
    stalled_score = score_evaluation_trace(case, stalled)
    assert stalled_score.replan_opportunities == 4
    assert stalled_score.appropriate_replans == 3
    assert FAILURE_INAPPROPRIATE_REPLAN in stalled_score.failure_codes


def test_t162_unnecessary_tool_scoring() -> None:
    case, good = _legal_clipping_trace()
    good_score = score_evaluation_trace(case, good)
    assert good_score.tool_actions == 1
    assert good_score.unnecessary_tool_actions == 0

    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    spectrum = _evidence(
        evidence_id="ev_spec",
        call_id="call_001",
        tool_name="analyze_spectrum",
        metric="peak_frequency_hz",
        value=200.0,
        unit="Hz",
    )
    batch = _rule_batch("rulebatch_clip", "ruleval_clip", ("ev_clip",))
    extra = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "tool", "tool_name": "analyze_spectrum", "evidence": (spectrum,)},
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    extra_score = score_evaluation_trace(case, extra)
    assert extra_score.tool_actions == 2
    assert extra_score.unnecessary_tool_actions == 1
    assert FAILURE_UNNECESSARY_TOOL in extra_score.failure_codes

    failed = _evidence(
        evidence_id="ev_fail",
        call_id="call_000",
        tool_name="detect_clipping",
        metric="clipping_detected",
        value=True,
    )
    recovered = _clip_ev("ev_clip", "call_001", detected=True)
    recovery_batch = _rule_batch("rulebatch_rec", "ruleval_rec", ("ev_clip",))
    recovery = _agent_trace(
        case,
        (
            {
                "kind": "tool",
                "tool_name": "detect_clipping",
                "evidence": (failed,),
                "status": "error",
            },
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (recovered,)},
            {"kind": "rules", "batch": recovery_batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_rec",),
            ),
        ),
        outcome="supported_fault",
    )
    recovery_score = score_evaluation_trace(case, recovery)
    assert recovery_score.tool_actions == 2
    assert recovery_score.unnecessary_tool_actions == 0
    assert recovery_score.appropriate_replans == recovery_score.replan_opportunities

    recovery_claims = (
        _claim(
            claim_id="claim_clip",
            fault_type="clipping",
            evidence_refs=("ev_clip",),
            rule_refs=("ruleval_rec",),
        ),
    )
    for failed_status in ("error", "invalid"):
        empty_fail = _agent_trace(
            case,
            (
                {
                    "kind": "tool",
                    "tool_name": "detect_clipping",
                    "evidence": (),
                    "status": failed_status,
                },
                {
                    "kind": "tool",
                    "tool_name": "detect_clipping",
                    "evidence": (recovered,),
                },
                {"kind": "rules", "batch": recovery_batch},
                {"kind": "finish"},
            ),
            claims=recovery_claims,
            outcome="supported_fault",
        )
        empty_score = score_evaluation_trace(case, empty_fail)
        assert empty_score.tool_actions == 2
        assert empty_score.unnecessary_tool_actions == 0
        assert empty_score.replan_opportunities >= 1
        assert empty_score.appropriate_replans == empty_score.replan_opportunities
        assert FAILURE_UNNECESSARY_TOOL not in empty_score.failure_codes
        assert FAILURE_INAPPROPRIATE_REPLAN not in empty_score.failure_codes

    noise_case = _noise_case()
    clip = _clip_ev("ev_noise_clip", "call_base_0", detected=False)
    noise_ev = _evidence(
        evidence_id="ev_noise_valid",
        call_id="call_base_1",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        value=False,
        validity="not_applicable",
    )
    obs_clip = _observation(
        observation_id="obs_base_0",
        call_id="call_base_0",
        tool_name="detect_clipping",
        evidence_ids=("ev_noise_clip",),
    )
    obs_noise = _observation(
        observation_id="obs_base_1",
        call_id="call_base_1",
        tool_name="analyze_harmonic_distortion",
        evidence_ids=("ev_noise_valid",),
    )
    noise_batch = _rule_batch(
        "rulebatch_base_noise", "ruleval_base_noise", ("ev_noise_valid",)
    )
    noise_baseline = _baseline_trace(
        noise_case,
        observations=(obs_clip, obs_noise),
        evidence=(clip, noise_ev),
        batches=(noise_batch,),
        claims=(
            _claim(
                claim_id="claim_base_noise",
                fault_type="inconclusive",
                evidence_refs=("ev_noise_valid",),
                rule_refs=("ruleval_base_noise",),
            ),
        ),
        outcome="inconclusive",
    )
    noise_baseline_score = score_evaluation_trace(noise_case, noise_baseline)
    assert noise_baseline_score.tool_actions == 2
    assert noise_baseline_score.unnecessary_tool_actions == 1
    assert FAILURE_UNNECESSARY_TOOL in noise_baseline_score.failure_codes


def test_t163_timely_stopping_scoring() -> None:
    case, good = _legal_clipping_trace()
    assert score_evaluation_trace(case, good).timely_stop is True

    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    extra_ev = _evidence(
        evidence_id="ev_spec",
        call_id="call_001",
        tool_name="analyze_spectrum",
        metric="peak_frequency_hz",
        value=200.0,
        unit="Hz",
    )
    batch = _rule_batch("rulebatch_clip", "ruleval_clip", ("ev_clip",))
    late = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "tool", "tool_name": "analyze_spectrum", "evidence": (extra_ev,)},
            {"kind": "rules", "batch": batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    late_score = score_evaluation_trace(case, late)
    assert late_score.timely_stop is False
    assert FAILURE_LATE_TOOL in late_score.failure_codes

    knowledge = _retrieval(retrieval_id="know_clip", tags=("clipping",))
    after_sufficient = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": batch},
            {"kind": "knowledge", "retrieval": knowledge},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
                knowledge_refs=("know_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    allowed = score_evaluation_trace(case, after_sufficient)
    assert allowed.timely_stop is True
    assert FAILURE_LATE_TOOL not in allowed.failure_codes


def test_t164_applicable_rule_scoring() -> None:
    case, good = _legal_clipping_trace()
    good_score = score_evaluation_trace(case, good)
    assert good_score.rule_action_opportunities == 1
    assert good_score.correct_rule_actions == 1

    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    premature_batch = _rule_batch("rulebatch_pre", "ruleval_pre", ("ev_placeholder",))
    later_batch = _rule_batch("rulebatch_clip", "ruleval_clip", ("ev_clip",))
    premature = _agent_trace(
        case,
        (
            {"kind": "rules", "batch": premature_batch},
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": later_batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    premature_score = score_evaluation_trace(case, premature)
    assert premature_score.correct_rule_actions == 1
    assert premature_score.rule_action_opportunities == 2
    assert FAILURE_PREMATURE_RULE in premature_score.failure_codes

    redundant = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": later_batch},
            {"kind": "rules", "batch": later_batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    redundant_score = score_evaluation_trace(case, redundant)
    assert redundant_score.correct_rule_actions == 1
    assert redundant_score.rule_action_opportunities == 2
    assert FAILURE_REDUNDANT_RULE in redundant_score.failure_codes

    omitted = _agent_trace(
        case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    omitted_score = score_evaluation_trace(case, omitted)
    assert omitted_score.correct_rule_actions == 0
    assert omitted_score.rule_action_opportunities == 1
    assert FAILURE_OMITTED_RULE in omitted_score.failure_codes


def test_t165_knowledge_selectivity_scoring() -> None:
    required_case, required_trace = _legal_noise_trace()
    required = score_evaluation_trace(required_case, required_trace)
    assert required.required_knowledge_opportunities == 1
    assert required.required_knowledge_actions == 1
    assert required.knowledge_actions == 1
    assert required.unnecessary_knowledge_actions == 0
    assert required.cited_knowledge_actions == 1

    omitted_case, omitted_trace = _legal_noise_trace(retrieve=False, cite=False)
    omitted = score_evaluation_trace(omitted_case, omitted_trace)
    assert omitted.required_knowledge_opportunities == 1
    assert omitted.required_knowledge_actions == 0
    assert FAILURE_REQUIRED_KNOWLEDGE_OMITTED in omitted.failure_codes

    irrelevant_case, irrelevant_trace = _legal_noise_trace(tags=("unrelated-topic",))
    irrelevant = score_evaluation_trace(irrelevant_case, irrelevant_trace)
    assert irrelevant.required_knowledge_actions == 0
    assert irrelevant.unnecessary_knowledge_actions == 1
    assert FAILURE_IRRELEVANT_TAGS in irrelevant.failure_codes
    assert FAILURE_UNNECESSARY_KNOWLEDGE in irrelevant.failure_codes

    uncited_case, uncited_trace = _legal_noise_trace(cite=False)
    uncited = score_evaluation_trace(uncited_case, uncited_trace)
    assert uncited.knowledge_actions == 1
    assert uncited.cited_knowledge_actions == 0
    assert FAILURE_UNCITED_KNOWLEDGE in uncited.failure_codes

    clean_case, clean_trace = _legal_clean_trace()
    not_needed = score_evaluation_trace(clean_case, clean_trace)
    assert not_needed.required_knowledge_opportunities == 0
    assert not_needed.knowledge_actions == 0
    assert not_needed.unnecessary_knowledge_actions == 0

    clip = _clip_ev("ev_clean_clip", "call_000", detected=False)
    thd = _thd_ev("ev_clean_thd", "call_001", value=1.0)
    batch = _rule_batch(
        "rulebatch_clean", "ruleval_clean", ("ev_clean_clip", "ev_clean_thd")
    )
    retrieval = _retrieval(retrieval_id="know_clean", tags=("clipping",))
    not_needed_trace = _agent_trace(
        clean_case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (clip,)},
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (thd,),
            },
            {"kind": "rules", "batch": batch},
            {"kind": "knowledge", "retrieval": retrieval},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clean",
                fault_type="no_supported_fault",
                evidence_refs=("ev_clean_clip", "ev_clean_thd"),
                rule_refs=("ruleval_clean",),
                knowledge_refs=("know_clean",),
            ),
        ),
        outcome="no_supported_fault",
    )
    penalized = score_evaluation_trace(clean_case, not_needed_trace)
    assert penalized.knowledge_actions == 1
    assert penalized.unnecessary_knowledge_actions == 1
    assert FAILURE_UNNECESSARY_KNOWLEDGE in penalized.failure_codes

    clip_case, optional_good = _legal_clipping_trace()
    optional = score_evaluation_trace(clip_case, optional_good)
    assert optional.required_knowledge_opportunities == 0
    assert optional.knowledge_actions == 0
    assert optional.unnecessary_knowledge_actions == 0

    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    opt_batch = _rule_batch("rulebatch_clip", "ruleval_clip", ("ev_clip",))
    opt_retrieval = _retrieval(retrieval_id="know_clip", tags=("clipping",))
    optional_cited = _agent_trace(
        clip_case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": opt_batch},
            {"kind": "knowledge", "retrieval": opt_retrieval},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
                knowledge_refs=("know_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    optional_score = score_evaluation_trace(clip_case, optional_cited)
    assert optional_score.knowledge_actions == 1
    assert optional_score.unnecessary_knowledge_actions == 0
    assert optional_score.cited_knowledge_actions == 1

    usage = ProviderUsage(input_tokens=10, output_tokens=4, total_tokens=14)
    used_trace = _agent_trace(
        clip_case,
        (
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": opt_batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        ),
        outcome="supported_fault",
        provider_usage=usage,
    )
    used = score_evaluation_trace(clip_case, used_trace)
    assert used.provider_usage == usage
    assert used.end_to_end_latency_ms is None
