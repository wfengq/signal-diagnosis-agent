"""OQ-014 Option C: single_signal flat-top clipping supported_fault (T-CX263)."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal import SyntheticCase
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

REPO = Path(__file__).resolve().parents[2]
PROFILE_S1 = REPO / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"

ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic distortion"),
)

V911 = "v9_11_mode_aware_no_fault_recovery"


def _evaluation(context: PlannerContext, rule_id: str) -> str:
    for batch in context.rule_evaluation_batches:
        for item in batch.evaluations:
            if item.rule_id == rule_id:
                return item.evaluation_id
    raise AssertionError(f"missing rule evaluation: {rule_id}")


def _evidence_by_metric(context: PlannerContext, metric: str) -> str:
    for item in context.evidence:
        if item.metric == metric:
            return item.evidence_id
    raise AssertionError(f"missing evidence metric: {metric}")


class _FlatTopFinishPlanner:
    """detect_clipping only; v9.11 automatic rule closure supplies rule FAILs."""

    async def decide(self, context: PlannerContext) -> AgentDecision:
        if not context.observations:
            return CallToolDecision(
                task_assessment=ASSESSMENT,
                call=DetectClippingCall(args=ClippingInput()),
                purpose="detect sub-full-scale flat-top clipping",
            )
        flat_top = _evidence_by_metric(context, "flat_top_detected")
        rule_fail = _evaluation(context, "rule_flat_top_absent")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip_flat_top",
                    fault_type="clipping",
                    statement="sub-full-scale flat-top clipping",
                    evidence_refs=(flat_top,),
                    rule_refs=(rule_fail,),
                ),
            ),
            confidence_label="high",
            task_assessment=ASSESSMENT,
        )


@pytest.mark.asyncio
async def test_t_cx263_single_signal_flat_top_clipping_supported_fault(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=_FlatTopFinishPlanner(),  # type: ignore[arg-type]
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_S1}
        ),
        causal_policy_version=V911,
    )
    result = await runtime.run(
        signal_id=signal_id,
        user_request="Why does this signal sound distorted?",
        stimulus_context=StimulusContext(
            mode="single_signal",
            test_signal_id=signal_id,
            assertion_source="evaluation_manifest",
        ),
    )

    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    clipping = next(
        claim for claim in result.diagnosis.claims if claim.fault_type == "clipping"
    )
    evidence_metrics = {
        item.metric
        for item in result.evidence
        if item.evidence_id in clipping.evidence_refs
    }
    assert "flat_top_detected" in evidence_metrics
    rule_ids = {
        evaluation.rule_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
        if evaluation.evaluation_id in clipping.rule_refs
    }
    assert "rule_flat_top_absent" in rule_ids
