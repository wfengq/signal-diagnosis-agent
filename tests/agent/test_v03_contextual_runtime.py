"""T-CX056–T-CX075: mode-aware contextual causal finish gates."""

from __future__ import annotations

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    TaskAssessment,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="diagnose S1 distortion",
)


def _ctx_single(signal_id: str = "sig_test") -> StimulusContext:
    return StimulusContext(
        mode="single_signal",
        test_signal_id=signal_id,
        assertion_source="user_supplied",
    )


def _ctx_paired(
    test_id: str = "sig_test",
    ref_id: str = "sig_ref",
) -> StimulusContext:
    return StimulusContext(
        mode="paired_reference",
        test_signal_id=test_id,
        reference_signal_id=ref_id,
        assertion_source="user_supplied",
    )


def _ctx_nominal(signal_id: str = "sig_test") -> StimulusContext:
    return StimulusContext(
        mode="nominal_single_tone",
        test_signal_id=signal_id,
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
        assertion_source="user_supplied",
    )


def _ev(
    evidence_id: str,
    metric: str,
    value: object,
    *,
    source_tool: str = "analyze_contextual_distortion",
    unit: str | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=source_tool,  # type: ignore[arg-type]
        call_id="call_analyze_contextual_distortion_000000",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        unit=unit,
        channel="mixdown",
    )


def _rule(
    evaluation_id: str,
    rule_id: str,
    judgment: str,
    *,
    profile_id: str = "profile_s1_contextual_comparison",
) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id=profile_id,
        profile_version="1.0.0-dev.1",
        evidence_refs=(),
    )


def _paired_growth_fail_pack() -> tuple[tuple[Evidence, ...], tuple[RuleEvaluation, ...]]:
    evidence = (
        _ev("ev_series", "test_series_kind", "even_order_present"),
        _ev("ev_growth", "even_harmonic_growth_percent", 2.5, unit="%"),
    )
    rules = (
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_ref_ratio", "rule_reference_clipping_ratio_acceptable", "pass"),
        _rule("ruleval_ref_flat", "rule_reference_flat_top_absent", "pass"),
        _rule("ruleval_growth", "rule_even_harmonic_growth_acceptable", "fail"),
    )
    return evidence, rules


def _harmonic_finish(
    *,
    evidence_refs: tuple[str, ...],
    rule_refs: tuple[str, ...],
) -> FinishDecision:
    return FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Paired harmonic growth supports distortion.",
                evidence_refs=evidence_refs,
                rule_refs=rule_refs,
            ),
        ),
        confidence_label="medium",
        limitations=(),
    )


def test_t_cx056_default_policy_remains_v9_4_legacy() -> None:
    runtime = DistortionDiagnosisRuntime(
        repository=InMemorySignalRepository(),
        tool_service=SignalToolService(InMemorySignalRepository()),
        planner=object(),  # type: ignore[arg-type]
    )
    assert runtime._causal_policy_version == "v9_4_legacy"


def test_t_cx064_single_signal_rejects_causal_harmonic_claim() -> None:
    evidence = (_ev("ev_series", "series_kind", "even_order_present", source_tool="analyze_harmonic_distortion"),)
    decision = _harmonic_finish(evidence_refs=("ev_series",), rule_refs=())
    with pytest.raises(DiagnosisValidationError, match="contextual support"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_series"}),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=(),
            stimulus_context=_ctx_single(),
            causal_policy_version="v9_5_contextual",
        )


def test_t_cx065_paired_harmonic_success() -> None:
    evidence, rules = _paired_growth_fail_pack()
    decision = _harmonic_finish(
        evidence_refs=("ev_series", "ev_growth"),
        rule_refs=tuple(item.evaluation_id for item in rules),
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_ctx_paired(),
        causal_policy_version="v9_5_contextual",
    )


def test_t_cx066_paired_absolute_thd_alone_rejected() -> None:
    evidence = (
        _ev("ev_thd", "test_thd_percent", 12.0, unit="%"),
        _ev("ev_series", "test_series_kind", "even_order_present"),
    )
    rules = (
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_ref_ratio", "rule_reference_clipping_ratio_acceptable", "pass"),
        _rule("ruleval_ref_flat", "rule_reference_flat_top_absent", "pass"),
        _rule("ruleval_nominal", "rule_nominal_thd_acceptable", "fail"),
    )
    decision = _harmonic_finish(
        evidence_refs=("ev_thd", "ev_series"),
        rule_refs=tuple(item.evaluation_id for item in rules),
    )
    with pytest.raises(DiagnosisValidationError, match="harmonic growth"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(item.evidence_id for item in evidence),
            known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_ctx_paired(),
            causal_policy_version="v9_5_contextual",
        )


def test_t_cx067_paired_claim_requires_growth_rule_fail() -> None:
    evidence, rules = _paired_growth_fail_pack()
    rules_without_growth = rules[:-1]
    decision = _harmonic_finish(
        evidence_refs=("ev_series", "ev_growth"),
        rule_refs=tuple(item.evaluation_id for item in rules_without_growth),
    )
    with pytest.raises(DiagnosisValidationError, match="harmonic growth"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(item.evidence_id for item in evidence),
            known_rule_evaluation_ids=frozenset(
                item.evaluation_id for item in rules_without_growth
            ),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules_without_growth,
            stimulus_context=_ctx_paired(),
            causal_policy_version="v9_5_contextual",
        )


def test_t_cx068_nominal_conditional_success() -> None:
    evidence = (
        _ev("ev_series", "test_series_kind", "even_order_present"),
        _ev("ev_thd", "test_thd_percent", 8.0, unit="%"),
    )
    rules = (
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_thd", "rule_nominal_thd_acceptable", "fail"),
    )
    decision = _harmonic_finish(
        evidence_refs=("ev_series", "ev_thd"),
        rule_refs=tuple(item.evaluation_id for item in rules),
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(item.evidence_id for item in evidence),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_ctx_nominal(),
        causal_policy_version="v9_5_contextual",
    )


def test_t_cx069_nominal_without_even_order_rejected() -> None:
    evidence = (_ev("ev_thd", "test_thd_percent", 8.0, unit="%"),)
    rules = (
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_thd", "rule_nominal_thd_acceptable", "fail"),
    )
    decision = _harmonic_finish(
        evidence_refs=("ev_thd",),
        rule_refs=tuple(item.evaluation_id for item in rules),
    )
    with pytest.raises(DiagnosisValidationError, match="test_series_kind"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_thd"}),
            known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=_ctx_nominal(),
            causal_policy_version="v9_5_contextual",
        )


def test_t_cx070_clipping_gate_unchanged_under_v95() -> None:
    evidence = (
        _ev(
            "ev_mech",
            "clipping_mechanism",
            True,
            source_tool="detect_clipping",
        ),
    )
    rules = (
        _rule(
            "ruleval_ratio",
            "rule_clipping_ratio_acceptable",
            "fail",
            profile_id="profile_s1_distortion",
        ),
    )
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping mechanism with substantial rule FAIL.",
                evidence_refs=("ev_mech",),
                rule_refs=("ruleval_ratio",),
            ),
        ),
        confidence_label="high",
        limitations=(),
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset({"ev_mech"}),
        known_rule_evaluation_ids=frozenset({"ruleval_ratio"}),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_ctx_single(),
        causal_policy_version="v9_5_contextual",
    )


def test_t_cx071_clipping_mechanism_alone_not_enough() -> None:
    evidence = (
        _ev(
            "ev_mech",
            "clipping_mechanism",
            True,
            source_tool="detect_clipping",
        ),
    )
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Mechanism without substantial FAIL.",
                evidence_refs=("ev_mech",),
            ),
        ),
        confidence_label="medium",
        limitations=(),
    )
    with pytest.raises(DiagnosisValidationError, match="substantial"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_mech"}),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=(),
            stimulus_context=_ctx_paired(),
            causal_policy_version="v9_5_contextual",
        )


def test_t_cx072_no_supported_fault_paired_requires_growth_pass() -> None:
    evidence = (
        _ev(
            "ev_mech",
            "clipping_mechanism",
            False,
            source_tool="detect_clipping",
        ),
    )
    rules = (
        _rule(
            "ruleval_ratio",
            "rule_clipping_ratio_acceptable",
            "pass",
            profile_id="profile_s1_distortion",
        ),
        _rule(
            "ruleval_flat",
            "rule_flat_top_absent",
            "pass",
            profile_id="profile_s1_distortion",
        ),
        _rule("ruleval_valid", "rule_contextual_analysis_valid", "pass"),
        _rule("ruleval_f0", "rule_contextual_f0_compatible", "pass"),
        _rule("ruleval_ref_ratio", "rule_reference_clipping_ratio_acceptable", "pass"),
        _rule("ruleval_ref_flat", "rule_reference_flat_top_absent", "pass"),
        _rule("ruleval_growth", "rule_even_harmonic_growth_acceptable", "pass"),
    )
    decision = FinishDecision(
        outcome="no_supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clean",
                fault_type="no_supported_fault",
                statement="Paired comparison finds no supported fault.",
                evidence_refs=("ev_mech",),
                rule_refs=tuple(item.evaluation_id for item in rules),
            ),
        ),
        confidence_label="medium",
        limitations=(),
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset({"ev_mech"}),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rules),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=rules,
        stimulus_context=_ctx_paired(),
        causal_policy_version="v9_5_contextual",
    )


def test_t_cx073_inconclusive_requires_same_run_refs() -> None:
    decision = FinishDecision(
        outcome="inconclusive",
        claims=(
            DiagnosisClaim(
                claim_id="claim_open",
                fault_type="inconclusive",
                statement="Unresolved without citations.",
            ),
        ),
        confidence_label="low",
        limitations=("need reference",),
    )
    with pytest.raises(DiagnosisValidationError, match="same-run"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(),
            task_assessment=ASSESSMENT,
            stimulus_context=_ctx_single(),
            causal_policy_version="v9_5_contextual",
        )


def test_t_cx074_v94_legacy_still_accepts_even_order_series_kind() -> None:
    evidence = (
        _ev(
            "ev_series",
            "series_kind",
            "even_order_present",
            source_tool="analyze_harmonic_distortion",
        ),
    )
    decision = _harmonic_finish(evidence_refs=("ev_series",), rule_refs=())
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset({"ev_series"}),
        task_assessment=ASSESSMENT,
        evidence=evidence,
        rule_evaluations=(),
        causal_policy_version="v9_4_legacy",
    )


@pytest.mark.asyncio
async def test_t_cx075_runtime_rejects_mismatched_test_signal_id() -> None:
    repository = InMemorySignalRepository()
    case = generate_sine(
        sample_rate_hz=48_000,
        duration_s=0.5,
        frequency_hz=440.0,
        amplitude=0.5,
    )
    repository.put(case.record)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=object(),  # type: ignore[arg-type]
        causal_policy_version="v9_5_contextual",
    )
    result = await runtime.run(
        signal_id=case.record.meta.signal_id,
        user_request="diagnose",
        stimulus_context=_ctx_single("sig_other"),
    )
    assert result.status == "error"
    assert result.termination_reason == "runtime_error"
    assert any("test_signal_id" in message for message in result.errors)
