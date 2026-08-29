"""Deterministic full-manifest evaluation harness.

Private runner helpers. CONTRACTS §49 does not export a public runner function.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib.resources import files
from pathlib import Path

from signal_diag.agent.models import (
    AgentDecision,
    DiagnosisClaim,
    FinishDecision,
    PlannerContext,
)
from signal_diag.agent.planner import ScriptedPlanner, ScriptedStep
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.dataset import (
    _condition_matches,
    _materialize_case,
    validate_dataset,
)
from signal_diag.evaluation.models import (
    BenchmarkConfig,
    DatasetManifest,
    EvaluationCase,
    EvaluationTrace,
)
from signal_diag.evaluation.recording import RecordingPlanner, assemble_evaluation_trace
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.repository import InMemorySignalRepository, SignalRepository
from signal_diag.tools.service import SignalToolService

_OFFICIAL_PROFILE_ID = "profile_s1_distortion"


def _package_path(*parts: str) -> Path:
    current = files("signal_diag")
    for part in parts:
        current = current.joinpath(part)
    return Path(str(current))


def _official_manifest_path() -> Path:
    return _package_path("evaluation", "manifests", "s1_distortion_v1.yaml")


def _official_profile_path() -> Path:
    return _package_path("rules", "profiles", "s1_distortion_v1.yaml")


def _official_corpus_path() -> Path:
    return _package_path("knowledge", "corpus")


def _official_profile_loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader({_OFFICIAL_PROFILE_ID: _official_profile_path()})


def _official_knowledge_index() -> KnowledgeIndex:
    return KnowledgeIndex(_official_corpus_path())


def _official_dependencies(
    repository: SignalRepository,
) -> tuple[SignalToolService, RuleEngine, YamlRuleProfileLoader, KnowledgeIndex]:
    return (
        SignalToolService(repository),
        RuleEngine(),
        _official_profile_loader(),
        _official_knowledge_index(),
    )


class _ContextBoundScriptedPlanner:
    """Delegate to ScriptedPlanner, then bind finish refs from live context."""

    def __init__(self, planner: ScriptedPlanner, case: EvaluationCase) -> None:
        self._planner = planner
        self._case = case

    async def decide(self, context: PlannerContext) -> AgentDecision:
        decision = await self._planner.decide(context)
        if isinstance(decision, FinishDecision):
            return _bind_finish(decision, context, self._case)
        return decision


def _evidence_refs_for_claim(
    context: PlannerContext,
    case: EvaluationCase,
    fault_type: str,
) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for condition in case.observable_conditions:
        if fault_type not in condition.supports_claims:
            continue
        for item in context.evidence:
            if item.evidence_id in seen:
                continue
            if _condition_matches(condition, item):
                refs.append(item.evidence_id)
                seen.add(item.evidence_id)
                break
    return tuple(refs)


def _all_rule_ids(context: PlannerContext) -> tuple[str, ...]:
    return tuple(
        item.evaluation_id
        for batch in context.rule_evaluation_batches
        for item in batch.evaluations
    )


def _all_knowledge_ids(context: PlannerContext) -> tuple[str, ...]:
    return tuple(item.retrieval_id for item in context.knowledge_retrievals)


def _bind_claim(
    claim: DiagnosisClaim,
    context: PlannerContext,
    case: EvaluationCase,
) -> DiagnosisClaim:
    return claim.model_copy(
        update={
            "evidence_refs": _evidence_refs_for_claim(
                context, case, claim.fault_type
            ),
            "rule_refs": _all_rule_ids(context),
            "knowledge_refs": _all_knowledge_ids(context),
        }
    )


def _bind_finish(
    decision: FinishDecision,
    context: PlannerContext,
    case: EvaluationCase,
) -> FinishDecision:
    return decision.model_copy(
        update={
            "claims": tuple(
                _bind_claim(claim, context, case) for claim in decision.claims
            )
        }
    )


def _require_valid_dataset(manifest: DatasetManifest) -> None:
    repository = InMemorySignalRepository()
    tool_service, rule_engine, profile_loader, _index = _official_dependencies(
        repository
    )
    report = validate_dataset(
        manifest,
        repository,
        tool_service,
        rule_engine,
        profile_loader,
    )
    if not report.valid:
        raise ValueError("dataset is not valid; harness cannot start")


async def _run_deterministic_harness(
    manifest: DatasetManifest,
    scripted_steps: Mapping[str, tuple[ScriptedStep, ...]],
    config: BenchmarkConfig,
    *,
    _clock: Callable[[], float] | None = None,
) -> tuple[EvaluationTrace, ...]:
    _require_valid_dataset(manifest)
    traces: list[EvaluationTrace] = []
    for case in manifest.cases:
        repository = InMemorySignalRepository()
        record = _materialize_case(case, repository)
        tool_service, rule_engine, profile_loader, knowledge_index = (
            _official_dependencies(repository)
        )
        recording = RecordingPlanner(
            _ContextBoundScriptedPlanner(
                ScriptedPlanner(scripted_steps[case.case_id]),
                case,
            ),
            _clock=_clock,
        )
        runtime = DistortionDiagnosisRuntime(
            repository=repository,
            tool_service=tool_service,
            planner=recording,
            rule_engine=rule_engine,
            rule_profile_loader=profile_loader,
            knowledge_index=knowledge_index,
        )
        result = await runtime.run(
            signal_id=record.meta.signal_id,
            user_request=case.user_request,
        )
        traces.append(
            assemble_evaluation_trace(
                case,
                recording.records,
                result,
                config,
                run_slot=1,
                execution_path="agent",
            )
        )
    return tuple(traces)
