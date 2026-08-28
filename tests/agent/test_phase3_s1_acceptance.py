"""Phase 3 S1 scripted acceptance with rules and knowledge (T121–T124)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    AgentRunResult,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    HarmonicDistortionInput,
    PlannerContext,
    RetrieveKnowledgeDecision,
    TaskAssessment,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation, RuleJudgment
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"

FinishBuilder = Callable[[PlannerContext], FinishDecision]


class Phase3S1RoutePlanner:
    """Deterministic route with real rule and knowledge runtime actions."""

    def __init__(
        self,
        steps: list[AgentDecision],
        finish_builder: FinishBuilder,
    ) -> None:
        self._steps = steps
        self._finish_builder = finish_builder
        self._index = 0

    async def decide(self, context: PlannerContext) -> AgentDecision:
        if self._index < len(self._steps):
            decision = self._steps[self._index]
            if (
                self._index == 0
                and getattr(decision, "task_assessment", None) is None
            ):
                decision = decision.model_copy(
                    update={
                        "task_assessment": TaskAssessment(
                            task_type="distortion_analysis",
                            objective="determine why the signal sounds distorted",
                            hypotheses=("clipping", "harmonic_distortion"),
                        )
                    }
                )
            self._index += 1
            return decision
        return self._finish_builder(context)


def _assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine why the signal sounds distorted",
        hypotheses=("clipping", "harmonic_distortion"),
    )


def _evidence_by_metric(context: PlannerContext, metric: str) -> str:
    for item in context.evidence:
        if item.metric == metric:
            return item.evidence_id
    raise AssertionError(f"missing evidence metric: {metric}")


def _evaluation(
    context: PlannerContext,
    rule_id: str,
    *,
    judgment: RuleJudgment | None = None,
) -> RuleEvaluation:
    for batch in context.rule_evaluation_batches:
        for item in batch.evaluations:
            if item.rule_id == rule_id and (
                judgment is None or item.judgment == judgment
            ):
                return item
    raise AssertionError(f"missing rule evaluation: {rule_id}")


def _latest_knowledge_id(context: PlannerContext) -> str:
    if not context.knowledge_retrievals:
        raise AssertionError("missing knowledge retrieval")
    return context.knowledge_retrievals[-1].retrieval_id


def assert_phase3_trace_is_grounded(result: AgentRunResult) -> None:
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        evaluation.evaluation_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    assert result.diagnosis is not None
    for claim in result.diagnosis.claims:
        assert set(claim.evidence_refs) <= evidence_ids
        assert set(claim.rule_refs) <= rule_ids
        assert set(claim.knowledge_refs) <= knowledge_ids


def _evaluate_rules_decision() -> EvaluateRulesDecision:
    return EvaluateRulesDecision(
        profile_id="profile_s1_distortion",
        evidence_refs=(),
        purpose="apply configured S1 demonstration limits",
    )


async def _run_phase3(
    repository: InMemorySignalRepository,
    signal_id: str,
    planner: Phase3S1RoutePlanner,
) -> AgentRunResult:
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    return await runtime.run(
        signal_id=signal_id,
        user_request="Why does this signal sound distorted?",
    )


@pytest.mark.asyncio
async def test_t121_s1_clean_rules_branch(
    repository: InMemorySignalRepository,
    sine_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, sine_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="no_supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clean",
                    fault_type="no_supported_fault",
                    statement="Configured clipping and THD limits pass on clean evidence.",
                    evidence_refs=(
                        _evidence_by_metric(context, "clipping_detected"),
                        _evidence_by_metric(context, "thd_percent"),
                    ),
                    rule_refs=(
                        _evaluation(
                            context, "rule_clipping_detected_absent", judgment="pass"
                        ).evaluation_id,
                        _evaluation(
                            context, "rule_thd_acceptable", judgment="pass"
                        ).evaluation_id,
                    ),
                ),
            ),
            confidence_label="high",
        )

    planner = Phase3S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="collect harmonic evidence",
            ),
            _evaluate_rules_decision(),
        ],
        finish,
    )
    result = await _run_phase3(repository, signal_id, planner)
    assert_phase3_trace_is_grounded(result)
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "no_supported_fault"
    judgments = {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert judgments["rule_clipping_detected_absent"] == "pass"
    assert judgments["rule_clipping_ratio_acceptable"] == "pass"
    assert judgments["rule_flat_top_absent"] == "pass"
    assert judgments["rule_harmonic_analysis_valid"] == "pass"
    assert judgments["rule_thd_acceptable"] == "pass"
    assert result.knowledge_retrievals == ()


@pytest.mark.asyncio
async def test_t122_s1_clip_rules_branch(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip",
                    fault_type="clipping",
                    statement="Configured clipping limits fail on sub-full-scale clipping.",
                    evidence_refs=(
                        _evidence_by_metric(context, "flat_top_detected"),
                        _evidence_by_metric(context, "clipping_ratio"),
                    ),
                    rule_refs=(
                        _evaluation(
                            context, "rule_flat_top_absent", judgment="fail"
                        ).evaluation_id,
                    ),
                ),
            ),
            confidence_label="high",
        )

    planner = Phase3S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            ),
            _evaluate_rules_decision(),
        ],
        finish,
    )
    result = await _run_phase3(repository, signal_id, planner)
    assert_phase3_trace_is_grounded(result)
    judgments = {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert judgments["rule_clipping_detected_absent"] == "fail"
    assert judgments["rule_clipping_ratio_acceptable"] == "fail"
    assert judgments["rule_flat_top_absent"] == "fail"
    assert judgments["rule_harmonic_analysis_valid"] == "not_applicable"
    assert judgments["rule_thd_acceptable"] == "not_applicable"
    harmonic_evals = [
        evaluation
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
        if evaluation.rule_id.startswith("rule_harmonic")
        or evaluation.rule_id == "rule_thd_acceptable"
    ]
    assert all(item.evidence_refs == () for item in harmonic_evals)


@pytest.mark.asyncio
async def test_t123_s1_harm_rules_branch(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_harm",
                    fault_type="harmonic_distortion",
                    statement="Configured THD limit fails on harmonic distortion evidence.",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="high",
        )

    planner = Phase3S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="collect harmonic evidence",
            ),
            _evaluate_rules_decision(),
        ],
        finish,
    )
    result = await _run_phase3(repository, signal_id, planner)
    assert_phase3_trace_is_grounded(result)
    judgments = {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert judgments["rule_clipping_detected_absent"] == "pass"
    assert judgments["rule_clipping_ratio_acceptable"] == "pass"
    assert judgments["rule_flat_top_absent"] == "pass"
    assert judgments["rule_harmonic_analysis_valid"] == "pass"
    assert judgments["rule_thd_acceptable"] == "fail"
    thd_eval = next(
        evaluation
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
        if evaluation.rule_id == "rule_thd_acceptable"
    )
    assert thd_eval.observed_value == pytest.approx(11.18, rel=0.01, abs=0.1)


@pytest.mark.asyncio
async def test_t124_s1_combined_rules_and_knowledge(
    repository: InMemorySignalRepository,
    combined_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, combined_case)

    def finish(context: PlannerContext) -> FinishDecision:
        knowledge_id = _latest_knowledge_id(context)
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip",
                    fault_type="clipping",
                    statement="Configured clipping limits fail on combined distortion.",
                    evidence_refs=(_evidence_by_metric(context, "clipping_ratio"),),
                    rule_refs=(
                        _evaluation(
                            context, "rule_clipping_ratio_acceptable", judgment="fail"
                        ).evaluation_id,
                    ),
                    knowledge_refs=(knowledge_id,),
                ),
                DiagnosisClaim(
                    claim_id="claim_harm",
                    fault_type="harmonic_distortion",
                    statement="Configured THD limit fails on combined distortion.",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                    rule_refs=(
                        _evaluation(
                            context, "rule_thd_acceptable", judgment="fail"
                        ).evaluation_id,
                    ),
                    knowledge_refs=(knowledge_id,),
                ),
            ),
            confidence_label="high",
        )

    planner = Phase3S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="collect harmonic evidence",
            ),
            _evaluate_rules_decision(),
            RetrieveKnowledgeDecision(
                query_text="clipping harmonic distortion",
                tags=("clipping", "harmonic-distortion"),
                purpose="explain combined clipping and THD findings",
            ),
        ],
        finish,
    )
    result = await _run_phase3(repository, signal_id, planner)
    assert_phase3_trace_is_grounded(result)
    assert len(result.knowledge_retrievals) == 1
    assert len(result.diagnosis.claims) == 2  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_t124_s1_noise_rules_and_knowledge_inconclusive(
    repository: InMemorySignalRepository,
    noise_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, noise_case)

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="inconclusive",
            claims=(),
            confidence_label="low",
            limitations=(
                (
                    "Harmonic analysis is not applicable on noise-only input; "
                    "no numeric THD or F0 claim is supported."
                ),
            ),
            task_assessment=_assessment(),
        )

    planner = Phase3S1RoutePlanner(
        [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="attempt harmonic evidence on noise",
            ),
            _evaluate_rules_decision(),
            RetrieveKnowledgeDecision(
                query_text="inconclusive harmonic analysis",
                tags=("inconclusive",),
                purpose="explain invalid harmonic analysis",
            ),
        ],
        finish,
    )
    result = await _run_phase3(repository, signal_id, planner)
    assert_phase3_trace_is_grounded(result)
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    judgments = {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert judgments["rule_harmonic_analysis_valid"] == "not_applicable"
    assert judgments["rule_thd_acceptable"] == "not_applicable"
    for claim in result.diagnosis.claims:
        for ref in claim.evidence_refs:
            evidence = next(item for item in result.evidence if item.evidence_id == ref)
            if evidence.metric in {"thd_percent", "f0_hz"}:
                pytest.fail("noise case must not create numeric THD/F0 claims")
