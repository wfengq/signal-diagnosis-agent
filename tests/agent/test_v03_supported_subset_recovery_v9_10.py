"""T-CX238: v9.10 validation-only clipping subset recovery guidance."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    DiagnosisValidationError,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.models import SignalMeta, SignalRecord
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.contracts import ClippingInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

REPO = Path(__file__).resolve().parents[2]
PROFILE_S1 = REPO / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
PROFILE_CX_V910 = (
    REPO / "src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10_v1.yaml"
)

ASSESSMENT = TaskAssessment(task_type="distortion_analysis", objective="S1")
CONTEXT = StimulusContext(
    mode="single_signal",
    test_signal_id="sig_test",
    assertion_source="evaluation_manifest",
)


def _evidence(evidence_id: str, metric: str, value: object) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool="analyze_contextual_distortion",
        call_id="call_contextual_000001",
        metric=metric,
        value=value,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _rule(evaluation_id: str, rule_id: str, judgment: str) -> RuleEvaluation:
    return RuleEvaluation(
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        judgment=judgment,  # type: ignore[arg-type]
        observed_value=None,
        comparator="eq",
        threshold=True,
        profile_id="profile_s1_contextual_comparison_v9_10",
        profile_version="1.0.0",
        evidence_refs=("ev_clip",),
    )


def test_t_cx238_preserves_supported_clipping_subset_and_gives_recovery_guidance() -> None:
    evidence = (
        _evidence("ev_clip", "test_clipping_mechanism", True),
    )
    rules = (
        _rule("ruleval_clip", "rule_test_clipping_ratio_acceptable", "fail"),
    )
    clipping = DiagnosisClaim(
        claim_id="claim_clipping",
        fault_type="clipping",
        statement="Clipping is supported.",
        evidence_refs=("ev_clip",),
        rule_refs=("ruleval_clip",),
    )
    harmonic = DiagnosisClaim(
        claim_id="claim_harmonic",
        fault_type="harmonic_distortion",
        statement="Harmonic distortion is supported.",
        evidence_refs=("ev_clip",),
        rule_refs=(),
    )
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(clipping, harmonic),
        confidence_label="medium",
        task_assessment=ASSESSMENT,
    )
    before = decision.model_dump_json()
    with pytest.raises(DiagnosisValidationError, match="independently supported") as caught:
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip"}),
            known_rule_evaluation_ids=frozenset({"ruleval_clip"}),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=CONTEXT,
            causal_policy_version="v9_10_contextual_clipping_recovery",
        )
    message = str(caught.value)
    assert "preserve the clipping claim" in message
    assert "same-run references" in message
    assert "remove the unsupported harmonic_distortion sibling" in message
    assert decision.model_dump_json() == before


def test_t_cx238_v99_keeps_generic_harmonic_rejection() -> None:
    evidence = (_evidence("ev_clip", "clipping_mechanism", True),)
    rules = (_rule("ruleval_clip", "rule_clipping_ratio_acceptable", "fail"),)
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clipping",
                fault_type="clipping",
                statement="Clipping is supported.",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
            DiagnosisClaim(
                claim_id="claim_harmonic",
                fault_type="harmonic_distortion",
                statement="Harmonic distortion is supported.",
                evidence_refs=("ev_clip",),
            ),
        ),
        confidence_label="medium",
        task_assessment=ASSESSMENT,
    )
    with pytest.raises(DiagnosisValidationError) as caught:
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip"}),
            known_rule_evaluation_ids=frozenset({"ruleval_clip"}),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=CONTEXT,
            causal_policy_version="v9_9_paired_reference_recovery",
        )
    assert "independently supported" not in str(caught.value)


def test_t_cx238_v910_recovery_accepts_coherent_legacy_clipping_family() -> None:
    evidence = (_evidence("ev_clip", "clipping_mechanism", True),)
    rules = (_rule("ruleval_clip", "rule_clipping_ratio_acceptable", "fail"),)
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clipping",
                fault_type="clipping",
                statement="Clipping is supported.",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
            DiagnosisClaim(
                claim_id="claim_harmonic",
                fault_type="harmonic_distortion",
                statement="Harmonic distortion is unsupported.",
                evidence_refs=("ev_clip",),
            ),
        ),
        confidence_label="medium",
        task_assessment=ASSESSMENT,
    )
    with pytest.raises(DiagnosisValidationError, match="independently supported"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip"}),
            known_rule_evaluation_ids=frozenset({"ruleval_clip"}),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=CONTEXT,
            causal_policy_version="v9_10_contextual_clipping_recovery",
        )


@pytest.mark.parametrize(
    "context",
    (
        StimulusContext(
            mode="paired_reference",
            test_signal_id="sig_test",
            reference_signal_id="sig_reference",
            assertion_source="evaluation_manifest",
        ),
        StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            assertion_source="evaluation_manifest",
        ),
    ),
)
def test_t_cx238_v910_subset_guidance_is_single_signal_only(
    context: StimulusContext,
) -> None:
    evidence = (_evidence("ev_clip", "test_clipping_mechanism", True),)
    rules = (
        _rule("ruleval_clip", "rule_test_clipping_ratio_acceptable", "fail"),
    )
    decision = FinishDecision(
        outcome="supported_fault",
        claims=(
            DiagnosisClaim(
                claim_id="claim_clipping",
                fault_type="clipping",
                statement="Clipping is supported.",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
            DiagnosisClaim(
                claim_id="claim_harmonic",
                fault_type="harmonic_distortion",
                statement="Harmonic distortion is unsupported.",
                evidence_refs=("ev_clip",),
            ),
        ),
        confidence_label="medium",
        task_assessment=ASSESSMENT,
    )
    with pytest.raises(DiagnosisValidationError) as caught:
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset({"ev_clip"}),
            known_rule_evaluation_ids=frozenset({"ruleval_clip"}),
            task_assessment=ASSESSMENT,
            evidence=evidence,
            rule_evaluations=rules,
            stimulus_context=context,
            causal_policy_version="v9_10_contextual_clipping_recovery",
        )
    assert "independently supported" not in str(caught.value)


@pytest.mark.asyncio
async def test_t_cx238_runtime_retries_without_mutating_supported_subset() -> None:
    repository = InMemorySignalRepository()
    sample_rate_hz = 48_000
    time = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    waveform = np.clip(2.5 * np.sin(2.0 * np.pi * 440.0 * time), -0.99, 0.99)
    samples = waveform.astype(np.float32)[:, None]
    signal_id = "sig_v910_subset_runtime"
    samples.setflags(write=False)
    repository.put(
        SignalRecord(
            meta=SignalMeta(
                signal_id=signal_id,
                sample_rate_hz=sample_rate_hz,
                num_samples=samples.shape[0],
                channels=1,
                duration_s=1.0,
                source_type="generated",
                original_dtype="float32",
            ),
            samples=samples,
        )
    )
    proposed_finishes: list[FinishDecision] = []

    class RecoveryPlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            if not context.observations:
                return CallToolDecision(
                    task_assessment=ASSESSMENT,
                    call=DetectClippingCall(args=ClippingInput()),
                    purpose="obtain deterministic clipping evidence",
                )
            mechanism = next(
                item
                for item in context.evidence
                if item.metric == "clipping_mechanism" and item.value is True
            )
            substantial = next(
                item
                for batch in context.rule_evaluation_batches
                for item in batch.evaluations
                if item.rule_id
                in {"rule_clipping_ratio_acceptable", "rule_flat_top_absent"}
                and item.judgment == "fail"
            )
            clipping = DiagnosisClaim(
                claim_id="claim_clipping",
                fault_type="clipping",
                statement="Clipping is supported.",
                evidence_refs=(mechanism.evidence_id,),
                rule_refs=(substantial.evaluation_id,),
            )
            claims = (clipping,)
            if not context.recoverable_errors:
                claims = (
                    clipping,
                    DiagnosisClaim(
                        claim_id="claim_harmonic",
                        fault_type="harmonic_distortion",
                        statement="Unsupported harmonic sibling.",
                        evidence_refs=(mechanism.evidence_id,),
                    ),
                )
            decision = FinishDecision(
                outcome="supported_fault",
                claims=claims,
                confidence_label="medium",
                task_assessment=ASSESSMENT,
            )
            proposed_finishes.append(decision)
            return decision

    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=RecoveryPlanner(),  # type: ignore[arg-type]
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": PROFILE_S1,
                "profile_s1_contextual_comparison_v9_10": PROFILE_CX_V910,
            }
        ),
        causal_policy_version="v9_10_contextual_clipping_recovery",
        limits=AgentLimits(max_planner_retries=2),
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why distorted?",
        stimulus_context=StimulusContext(
            mode="single_signal",
            test_signal_id=signal_id,
            assertion_source="evaluation_manifest",
        ),
    )

    assert result.status == "success"
    assert result.diagnosis is not None
    assert tuple(claim.fault_type for claim in result.diagnosis.claims) == ("clipping",)
    assert len(proposed_finishes) == 2
    assert len(proposed_finishes[0].claims) == 2
    assert proposed_finishes[1].claims == (proposed_finishes[0].claims[0],)
    assert any("independently supported" in error for error in result.errors)
