"""Phase 3 runtime integration tests (T117, T120)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from signal_diag.agent.models import (
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    EvaluateRulesDecision,
    FinishDecision,
    RetrieveKnowledgeDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluationBatch, RuleProfile, RuleProfileLoader
from signal_diag.signal import SyntheticCase
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.evidence import Evidence
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


def _assessment() -> TaskAssessment:
    return TaskAssessment(
        task_type="distortion_analysis",
        objective="determine distortion cause",
    )


@dataclass
class CountingRuleEngine:
    calls: int = 0
    raise_on_call: bool = False
    _delegate: RuleEngine = field(default_factory=RuleEngine)

    def evaluate_profile(
        self,
        profile: RuleProfile,
        evidence: Sequence[Evidence],
        *,
        evidence_filter: frozenset[str] | None = None,
    ) -> RuleEvaluationBatch:
        self.calls += 1
        if self.raise_on_call:
            raise RuntimeError("rule engine failure")
        return self._delegate.evaluate_profile(
            profile,
            evidence,
            evidence_filter=evidence_filter,
        )


class ExplodingLoader:
    def load(self, profile_id: str) -> RuleProfile:
        raise RuntimeError("loader failure")


def rule_first_planner() -> ScriptedPlanner:
    return ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=EvaluateRulesDecision(
                    task_assessment=_assessment(),
                    profile_id="profile_s1_distortion",
                    evidence_refs=(),
                    purpose="evaluate configured limits",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=FinishDecision(
                    outcome="inconclusive",
                    claims=(),
                    confidence_label="low",
                    limitations=("stop after rules",),
                ),
            ),
        ]
    )


def build_runtime(
    *,
    planner: ScriptedPlanner,
    rule_engine: CountingRuleEngine | None = None,
    rule_profile_loader: RuleProfileLoader | None = None,
    limits: AgentLimits | None = None,
    repository: InMemorySignalRepository | None = None,
    clipped_case: SyntheticCase | None = None,
) -> tuple[DistortionDiagnosisRuntime, str]:
    repo = repository or InMemorySignalRepository()
    signal_id = "sig_runtime"
    if clipped_case is not None:
        signal_id = store_synthetic_case(repo, clipped_case)
    runtime = DistortionDiagnosisRuntime(
        repository=repo,
        tool_service=SignalToolService(repo),
        planner=planner,
        limits=limits or AgentLimits(),
        rule_engine=rule_engine,
        rule_profile_loader=rule_profile_loader,
    )
    return runtime, signal_id


@pytest.fixture
def runtime_parts(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> dict[str, object]:
    signal_id = store_synthetic_case(repository, clipped_case)
    return {
        "repository": repository,
        "signal_id": signal_id,
        "loader": YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
    }


@pytest.mark.asyncio
async def test_t117_zero_rule_budget_terminates_before_execution(
    runtime_parts: dict[str, object],
) -> None:
    engine = CountingRuleEngine()
    runtime, _signal_id = build_runtime(
        planner=rule_first_planner(),
        rule_engine=engine,
        rule_profile_loader=runtime_parts["loader"],  # type: ignore[arg-type]
        limits=AgentLimits(max_rule_evaluations=0),
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "max_rule_evaluations"
    assert engine.calls == 0


@pytest.mark.asyncio
async def test_t117_rule_counter_increments_before_dependency_exception(
    runtime_parts: dict[str, object],
) -> None:
    engine = CountingRuleEngine(raise_on_call=True)
    runtime, _ = build_runtime(
        planner=rule_first_planner(),
        rule_engine=engine,
        rule_profile_loader=runtime_parts["loader"],  # type: ignore[arg-type]
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert engine.calls == 1
    assert result.termination_reason == "runtime_error"


@pytest.mark.asyncio
async def test_t117_successful_rule_action_propagates_batch(
    runtime_parts: dict[str, object],
) -> None:
    engine = CountingRuleEngine()
    runtime, _ = build_runtime(
        planner=rule_first_planner(),
        rule_engine=engine,
        rule_profile_loader=runtime_parts["loader"],  # type: ignore[arg-type]
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert engine.calls == 1
    assert len(result.rule_evaluation_batches) == 1
    assert result.rule_evaluation_batches[0].profile_id == "profile_s1_distortion"


@pytest.mark.asyncio
async def test_t117_duplicate_rule_request_is_no_progress_without_budget_use(
    runtime_parts: dict[str, object],
) -> None:
    engine = CountingRuleEngine()
    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=EvaluateRulesDecision(
                    task_assessment=_assessment(),
                    profile_id="profile_s1_distortion",
                    evidence_refs=(),
                    purpose="first evaluation",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=EvaluateRulesDecision(
                    profile_id="profile_s1_distortion",
                    evidence_refs=(),
                    purpose="duplicate evaluation",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=FinishDecision(
                    outcome="inconclusive",
                    claims=(),
                    confidence_label="low",
                    limitations=("done",),
                ),
            ),
        ]
    )
    runtime, _ = build_runtime(
        planner=planner,
        rule_engine=engine,
        rule_profile_loader=runtime_parts["loader"],  # type: ignore[arg-type]
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert engine.calls == 1
    assert len(result.rule_evaluation_batches) == 1
    assert result.termination_reason == "planner_finished"


@pytest.mark.asyncio
async def test_t117_rule_budget_exhausts_after_successful_evaluation(
    runtime_parts: dict[str, object],
) -> None:
    engine = CountingRuleEngine()
    evidence_id = "ev_detect_clipping_detect_clipping_000000_000"
    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=CallToolDecision(
                    task_assessment=_assessment(),
                    call=DetectClippingCall(args=ClippingInput()),
                    purpose="collect clipping evidence",
                ),
            ),
            ScriptedStep(
                expected_observation_count=1,
                required_evidence_metrics=("clipping_detected",),
                decision=EvaluateRulesDecision(
                    profile_id="profile_s1_distortion",
                    evidence_refs=(),
                    purpose="first evaluation",
                ),
            ),
            ScriptedStep(
                expected_observation_count=1,
                decision=EvaluateRulesDecision(
                    profile_id="profile_s1_distortion",
                    evidence_refs=(evidence_id,),
                    purpose="distinct filter evaluation",
                ),
            ),
        ]
    )
    runtime, _ = build_runtime(
        planner=planner,
        rule_engine=engine,
        rule_profile_loader=runtime_parts["loader"],  # type: ignore[arg-type]
        limits=AgentLimits(max_rule_evaluations=1),
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "max_rule_evaluations"
    assert engine.calls == 1
    assert len(result.rule_evaluation_batches) == 1


@pytest.mark.asyncio
async def test_t120_missing_rule_dependencies_return_runtime_error(
    runtime_parts: dict[str, object],
) -> None:
    runtime, _ = build_runtime(
        planner=rule_first_planner(),
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "runtime_error"


@pytest.mark.asyncio
async def test_t120_loader_exception_terminates_runtime_error(
    runtime_parts: dict[str, object],
) -> None:
    runtime, _ = build_runtime(
        planner=rule_first_planner(),
        rule_engine=CountingRuleEngine(),
        rule_profile_loader=ExplodingLoader(),
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "runtime_error"


@pytest.mark.asyncio
async def test_phase2_constructor_remains_compatible(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=ScriptedPlanner(
            [
                ScriptedStep(
                    expected_observation_count=0,
                    decision=CallToolDecision(
                        task_assessment=_assessment(),
                        call=DetectClippingCall(args=ClippingInput()),
                        purpose="check clipping",
                    ),
                ),
                ScriptedStep(
                    expected_observation_count=1,
                    decision=FinishDecision(
                        outcome="inconclusive",
                        claims=(),
                        confidence_label="low",
                        limitations=("phase2 path",),
                    ),
                ),
            ]
        ),
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert result.termination_reason == "planner_finished"
    assert result.rule_evaluation_batches == ()


@pytest.mark.asyncio
async def test_rule_action_with_tool_evidence_filter(
    repository: InMemorySignalRepository,
    clipped_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)
    loader = YamlRuleProfileLoader({"profile_s1_distortion": PROFILE_PATH})
    engine = CountingRuleEngine()
    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=CallToolDecision(
                    task_assessment=_assessment(),
                    call=DetectClippingCall(args=ClippingInput()),
                    purpose="collect clipping evidence",
                ),
            ),
            ScriptedStep(
                expected_observation_count=1,
                required_evidence_metrics=("clipping_ratio",),
                decision=EvaluateRulesDecision(
                    profile_id="profile_s1_distortion",
                    evidence_refs=(),
                    purpose="evaluate clipping evidence",
                ),
            ),
            ScriptedStep(
                expected_observation_count=1,
                decision=FinishDecision(
                    outcome="inconclusive",
                    claims=(),
                    confidence_label="low",
                    limitations=("done",),
                ),
            ),
        ]
    )
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
        rule_engine=engine,
        rule_profile_loader=loader,
    )
    result = await runtime.run(signal_id=signal_id, user_request="Why distorted?")
    assert engine.calls == 1
    assert result.rule_evaluation_batches


@dataclass
class CountingKnowledgeIndex:
    calls: int = 0
    raise_on_call: bool = False
    _delegate: KnowledgeIndex = field(
        default_factory=lambda: KnowledgeIndex(CORPUS_PATH)
    )

    def retrieve(
        self,
        *,
        query_text: str,
        tags: Sequence[str] = (),
        max_results: int = 5,
    ):
        self.calls += 1
        if self.raise_on_call:
            raise RuntimeError("knowledge index failure")
        return self._delegate.retrieve(
            query_text=query_text,
            tags=tags,
            max_results=max_results,
        )


def knowledge_first_planner() -> ScriptedPlanner:
    return ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=RetrieveKnowledgeDecision(
                    task_assessment=_assessment(),
                    query_text="clipping",
                    tags=("clipping",),
                    purpose="explain clipping evidence",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=FinishDecision(
                    outcome="inconclusive",
                    claims=(),
                    confidence_label="low",
                    limitations=("stop after knowledge",),
                ),
            ),
        ]
    )


@pytest.mark.asyncio
async def test_t118_zero_knowledge_budget_terminates_before_execution(
    runtime_parts: dict[str, object],
) -> None:
    index = CountingKnowledgeIndex()
    runtime = DistortionDiagnosisRuntime(
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
        tool_service=SignalToolService(runtime_parts["repository"]),  # type: ignore[arg-type]
        planner=knowledge_first_planner(),
        limits=AgentLimits(max_knowledge_retrievals=0),
        knowledge_index=index,
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "max_knowledge_retrievals"
    assert index.calls == 0


@pytest.mark.asyncio
async def test_t118_knowledge_counter_increments_before_dependency_exception(
    runtime_parts: dict[str, object],
) -> None:
    index = CountingKnowledgeIndex(raise_on_call=True)
    runtime = DistortionDiagnosisRuntime(
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
        tool_service=SignalToolService(runtime_parts["repository"]),  # type: ignore[arg-type]
        planner=knowledge_first_planner(),
        knowledge_index=index,
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert index.calls == 1
    assert result.termination_reason == "runtime_error"


@pytest.mark.asyncio
async def test_t118_successful_knowledge_action_propagates_retrieval(
    runtime_parts: dict[str, object],
) -> None:
    index = CountingKnowledgeIndex()
    runtime = DistortionDiagnosisRuntime(
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
        tool_service=SignalToolService(runtime_parts["repository"]),  # type: ignore[arg-type]
        planner=knowledge_first_planner(),
        knowledge_index=index,
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert index.calls == 1
    assert len(result.knowledge_retrievals) == 1
    assert result.knowledge_retrievals[0].query_text == "clipping"


@pytest.mark.asyncio
async def test_t118_duplicate_knowledge_request_is_no_progress_without_budget_use(
    runtime_parts: dict[str, object],
) -> None:
    index = CountingKnowledgeIndex()
    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=RetrieveKnowledgeDecision(
                    task_assessment=_assessment(),
                    query_text="clipping",
                    tags=("clipping",),
                    purpose="first retrieval",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=RetrieveKnowledgeDecision(
                    query_text="clipping",
                    tags=(" clipping ",),
                    purpose="duplicate retrieval",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=FinishDecision(
                    outcome="inconclusive",
                    claims=(),
                    confidence_label="low",
                    limitations=("done",),
                ),
            ),
        ]
    )
    runtime = DistortionDiagnosisRuntime(
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
        tool_service=SignalToolService(runtime_parts["repository"]),  # type: ignore[arg-type]
        planner=planner,
        knowledge_index=index,
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert index.calls == 1
    assert len(result.knowledge_retrievals) == 1
    assert result.termination_reason == "planner_finished"


@pytest.mark.asyncio
async def test_t118_knowledge_budget_exhausts_after_successful_retrieval(
    runtime_parts: dict[str, object],
) -> None:
    index = CountingKnowledgeIndex()
    planner = ScriptedPlanner(
        [
            ScriptedStep(
                expected_observation_count=0,
                decision=RetrieveKnowledgeDecision(
                    task_assessment=_assessment(),
                    query_text="clipping",
                    tags=("clipping",),
                    purpose="first retrieval",
                ),
            ),
            ScriptedStep(
                expected_observation_count=0,
                decision=RetrieveKnowledgeDecision(
                    query_text="harmonic",
                    tags=("harmonic",),
                    purpose="distinct retrieval",
                ),
            ),
        ]
    )
    runtime = DistortionDiagnosisRuntime(
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
        tool_service=SignalToolService(runtime_parts["repository"]),  # type: ignore[arg-type]
        planner=planner,
        limits=AgentLimits(max_knowledge_retrievals=1),
        knowledge_index=index,
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "max_knowledge_retrievals"
    assert index.calls == 1
    assert len(result.knowledge_retrievals) == 1


@pytest.mark.asyncio
async def test_t120_missing_knowledge_index_returns_runtime_error(
    runtime_parts: dict[str, object],
) -> None:
    runtime = DistortionDiagnosisRuntime(
        repository=runtime_parts["repository"],  # type: ignore[arg-type]
        tool_service=SignalToolService(runtime_parts["repository"]),  # type: ignore[arg-type]
        planner=knowledge_first_planner(),
    )
    result = await runtime.run(
        signal_id=str(runtime_parts["signal_id"]),
        user_request="Why distorted?",
    )
    assert result.termination_reason == "runtime_error"
