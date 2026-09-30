"""T-CX279, T-CX283–T-CX285: report parity and scoring labels."""

from __future__ import annotations

import pytest

from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.app.context_guidance import build_context_guidance
from signal_diag.evaluation.models import BaselineDiagnosis, BaselineRunResult
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
)
from signal_diag.evaluation.planner_ablation.labels import guidance_attribution_label
from signal_diag.evaluation.planner_ablation.report_fields import (
    derive_context_guidance_from_agent_result,
    derive_context_guidance_from_baseline,
    guidance_parity_equal,
)
from signal_diag.evaluation.planner_ablation.scoring import (
    ScoringPopulationError,
    claim_population_denominator,
    diagnosis_completion_rate,
    reject_offline_context_labels_on_execution_inputs,
    score_guidance_fields,
    terminal_reach_rate,
    upgrade_success_denominators,
)
from signal_diag.tools.evidence import Evidence


def _scored_slot(**fields: object) -> dict[str, object]:
    base = {
        "arm": "product_agent",
        "execution_identity": "product_campaign",
        "planner_class": "RealLLMPlanner",
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
    }
    base.update(fields)
    return base


def _agent_inconclusive_with_harmonic() -> AgentRunResult:
    evidence = (
        Evidence(
            evidence_id="ev_thd",
            call_id="call_1",
            source_tool="analyze_harmonic_distortion",
            metric="thd_percent",
            value=12.0,
            validity="valid",
            channel="mixdown",
        ),
    )
    diagnosis = StructuredDiagnosis(
        run_id="run_test",
        task_type="distortion_analysis",
        outcome="inconclusive",
        claims=(),
        confidence_label="low",
        limitations=(),
        termination_reason="planner_finished",
        tool_call_count=1,
    )
    return AgentRunResult(
        run_id="run_test",
        status="success",
        diagnosis=diagnosis,
        observations=(),
        evidence=evidence,
        tool_history=(),
        termination_reason="planner_finished",
        rule_evaluation_batches=(),
    )


def test_t_cx279_guidance_emission_parity_both_arms() -> None:
    agent_result = _agent_inconclusive_with_harmonic()
    product_guidance = build_context_guidance(mode="single_signal", result=agent_result)
    study_guidance = derive_context_guidance_from_agent_result(
        mode="single_signal", result=agent_result
    )
    assert product_guidance is not None and study_guidance is not None
    assert guidance_parity_equal(
        study_guidance,
        study_guidance.__class__(
            reason_codes=product_guidance.reason_codes,
            unlockable_modes=product_guidance.unlockable_modes,
            required_inputs={
                key: tuple(value) for key, value in product_guidance.required_inputs.items()
            },
            summary=product_guidance.summary,
        ),
    )
    baseline = BaselineRunResult(
        run_id="baseline_abcd1234",
        status="inconclusive",
        diagnosis=BaselineDiagnosis(
            run_id="baseline_abcd1234",
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_inc",
                    fault_type="inconclusive",
                    statement="insufficient",
                    evidence_refs=("ev_thd",),
                    rule_refs=(),
                ),
            ),
            confidence_label="low",
            tool_call_count=2,
            rule_evaluation_batches=(),
        ),
        observations=(),
        evidence=agent_result.evidence,
        tool_history=(),
        completion_reason="insufficient_evidence",
        rule_evaluation_batches=(),
    )
    baseline_guidance = derive_context_guidance_from_baseline(
        mode="single_signal", baseline=baseline
    )
    assert baseline_guidance is not None
    assert baseline_guidance.reason_codes == study_guidance.reason_codes
    assert guidance_parity_equal(baseline_guidance, study_guidance)


def test_t_cx279_guidance_omitted_when_not_inconclusive() -> None:
    result = _agent_inconclusive_with_harmonic()
    diagnosed = result.model_copy(
        update={
            "diagnosis": result.diagnosis.model_copy(
                update={"outcome": "no_supported_fault"}
            )
        }
    )
    assert derive_context_guidance_from_agent_result(mode="single_signal", result=diagnosed) is None
    baseline = BaselineRunResult(
        run_id="baseline_done",
        status="success",
        diagnosis=BaselineDiagnosis(
            run_id="baseline_done",
            outcome="no_supported_fault",
            claims=(),
            confidence_label="medium",
            tool_call_count=1,
            rule_evaluation_batches=(),
        ),
        observations=(),
        evidence=result.evidence,
        tool_history=(),
        completion_reason="baseline_completed",
        rule_evaluation_batches=(),
    )
    assert (
        derive_context_guidance_from_baseline(mode="single_signal", baseline=baseline) is None
    )


def test_t_cx279_guidance_never_planner_skill() -> None:
    scored = score_guidance_fields(None)
    assert scored["guidance_attribution"] == guidance_attribution_label()
    assert scored["guidance_attribution"] != "planner_skill"


def test_t_cx284_rejects_offline_labels_on_execution_inputs() -> None:
    with pytest.raises(ValueError, match="context_valid"):
        reject_offline_context_labels_on_execution_inputs(
            {"case_id": "c1", "context_valid": True}
        )


def test_t_cx283_terminal_reach_and_diagnosis_completion_diverge() -> None:
    slots = (
        _scored_slot(terminal_reached=True, completed_diagnosis=False),
        _scored_slot(terminal_reached=True, completed_diagnosis=True),
        _scored_slot(terminal_reached=False, completed_diagnosis=False),
    )
    terminal = terminal_reach_rate(slots)
    completion = diagnosis_completion_rate(slots)
    assert terminal.denominator == 3
    assert terminal.numerator == 2
    assert completion.denominator == 3
    assert completion.numerator == 1


def test_t_cx283_claim_population_counts_grounded_claims_only() -> None:
    evidence = (
        Evidence(
            evidence_id="ev_1",
            call_id="call_1",
            source_tool="detect_clipping",
            metric="clipping_ratio",
            value=0.02,
            validity="valid",
            channel="mixdown",
        ),
    )
    slots = (
        _scored_slot(
            completed_diagnosis=True,
            evidence=evidence,
            rule_evaluation_batches=(),
            claims=(
                {
                    "claim_id": "c1",
                    "evidence_refs": ("ev_1",),
                    "rule_refs": (),
                },
                {
                    "claim_id": "c2",
                    "evidence_refs": ("ev_missing",),
                    "rule_refs": (),
                },
            ),
        ),
        _scored_slot(completed_diagnosis=False, claims=({"claim_id": "c3"},)),
    )
    population = claim_population_denominator(slots)
    assert population.numerator == 1
    assert population.denominator == 2
    assert population.value == 0.5


def test_t_cx283_zero_claim_population_is_not_evaluable() -> None:
    with pytest.raises(ScoringPopulationError, match="not evaluable"):
        claim_population_denominator(
            (
                _scored_slot(completed_diagnosis=True, claims=()),
                _scored_slot(completed_diagnosis=False, claims=({"claim_id": "ignored"},)),
            )
        )


def test_t_cx283_claim_population_ignores_incomplete_diagnosis_slots() -> None:
    population = claim_population_denominator(
        (
            _scored_slot(
                completed_diagnosis=True,
                evidence=(),
                claims=(
                    {"claim_id": "c1", "evidence_refs": (), "rule_refs": ()},
                    {"claim_id": "c2", "evidence_refs": (), "rule_refs": ()},
                ),
            ),
            _scored_slot(
                completed_diagnosis=False,
                claims=({"claim_id": "c3", "evidence_refs": ("ev_x",), "rule_refs": ()},),
            ),
        )
    )
    assert population.numerator == 0
    assert population.denominator == 2


def test_t_cx285_upgrade_success_reports_both_denominators() -> None:
    full, conditional = upgrade_success_denominators(
        pre_fixed_population=12,
        conditional_successes=3,
        conditional_population=6,
    )
    assert full.denominator == 12
    assert conditional.denominator == 6
