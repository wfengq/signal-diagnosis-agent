"""Deterministic full-manifest evaluation harness and official real-model runner.

Private runner helpers. CONTRACTS §49 does not export a public runner function.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from signal_diag.agent.models import (
    AgentDecision,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    PlannerContext,
    RetrieveKnowledgeDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import (
    RealLLMPlanner,
    ScriptedPlanner,
    ScriptedStep,
    _Phase4V4RealLLMPlanner,
)
from signal_diag.agent.prompts import _S1_PROMPT_V4
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.baseline import FixedPipelineBaseline
from signal_diag.evaluation.dataset import (
    _condition_matches,
    _materialize_case,
    load_dataset_manifest,
    validate_dataset,
)
from signal_diag.evaluation.models import (
    AttemptErrorCode,
    AttemptRecord,
    AttemptStatus,
    BenchmarkConfig,
    BenchmarkReport,
    ConfigValue,
    DatasetManifest,
    EvaluationCase,
    EvaluationTrace,
    ProviderUsage,
    TargetBands,
)
from signal_diag.evaluation.recording import (
    RecordingPlanner,
    assemble_evaluation_trace,
)
from signal_diag.evaluation.reporting import write_benchmark_bundle
from signal_diag.evaluation.scoring import aggregate_benchmark, score_evaluation_trace
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.repository import InMemorySignalRepository, SignalRepository
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.service import SignalToolService

_OFFICIAL_PROFILE_ID = "profile_s1_distortion"
_OFFICIAL_PROFILE_VERSION = "1.0.0-demo"
_OFFICIAL_DATASET_ID = "s1-distortion-synthetic"
_OFFICIAL_DATASET_VERSION = "1.0.0"
_OFFICIAL_PROVIDER = "deepseek"
_OFFICIAL_MODEL = "deepseek-v4-flash"
_OFFICIAL_PROMPT_VERSION = "v0.2-s1-planner-4"
_OFFICIAL_REPETITIONS = 5
_RETRYABLE_ERROR_CODES: frozenset[AttemptErrorCode] = frozenset(
    {"timeout", "rate_limited", "provider_5xx"}
)
_CONFIG_ERROR_CODES: frozenset[AttemptErrorCode] = frozenset(
    {
        "missing_credentials",
        "missing_dependency",
        "authentication",
        "invalid_configuration",
    }
)
_HARMONIC_ONLY_CASES = frozenset({"case_dev_harmonic_01"})
_HARMONIC_THEN_CLIPPING_CLEAN = "case_held_clean_02"
_SCRIPTED_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)


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


class _PreflightFailure(Exception):
    def __init__(self, code: AttemptErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@runtime_checkable
class _ChatCompletions(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


@runtime_checkable
class _ChatResource(Protocol):
    @property
    def completions(self) -> _ChatCompletions: ...


@runtime_checkable
class _ProviderClient(Protocol):
    @property
    def chat(self) -> _ChatResource: ...


class _UsageCapturingCompletions:
    def __init__(self, owner: _UsageCapturingClient, inner: Any) -> None:
        self._owner = owner
        self._inner = inner

    async def create(self, **kwargs: Any) -> Any:
        try:
            response = await self._inner.create(**kwargs)
        except Exception:
            self._owner._captured = None
            raise
        self._owner._captured = _provider_usage_from_response(response)
        return response


class _UsageCapturingChat:
    def __init__(self, owner: _UsageCapturingClient, inner_chat: Any) -> None:
        self.completions = _UsageCapturingCompletions(owner, inner_chat.completions)


class _UsageCapturingClient:
    def __init__(self, inner: _ProviderClient) -> None:
        self._inner = inner
        self._captured: ProviderUsage | None = None
        self.chat = _UsageCapturingChat(self, inner.chat)

    @property
    def captured_provider_usage(self) -> ProviderUsage | None:
        return self._captured


def _provider_usage_from_response(response: object) -> ProviderUsage | None:
    raw = getattr(response, "usage", None)
    if raw is None:
        return None
    if isinstance(raw, ProviderUsage):
        return raw
    payload = {
        "input_tokens": _usage_field(raw, "input_tokens", "prompt_tokens"),
        "output_tokens": _usage_field(raw, "output_tokens", "completion_tokens"),
        "total_tokens": _usage_field(raw, "total_tokens"),
        "cost_usd": _usage_field(raw, "cost_usd"),
    }
    if all(value is None for value in payload.values()):
        return None
    try:
        return ProviderUsage.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        return None


def _usage_field(raw: object, *names: str) -> int | float | None:
    for name in names:
        value = getattr(raw, name, None)
        if value is None and isinstance(raw, Mapping):
            value = raw.get(name)
        if value is not None:
            return value  # type: ignore[no-any-return]
    return None


def _official_prompt_sha256() -> str:
    return hashlib.sha256(_S1_PROMPT_V4.system_prompt.encode("utf-8")).hexdigest()


def _official_model_parameters() -> dict[str, ConfigValue]:
    return {
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def _official_sdk_versions() -> dict[str, str]:
    try:
        import openai
    except ImportError:
        return {}
    version = getattr(openai, "__version__", None)
    if not isinstance(version, str) or not version:
        return {}
    return {"openai": version}


def _official_benchmark_config(
    *,
    benchmark_id: str,
    started_at_utc: datetime,
) -> BenchmarkConfig:
    if _S1_PROMPT_V4.version != _OFFICIAL_PROMPT_VERSION:
        raise _PreflightFailure(
            "invalid_configuration",
            f"prompt version must be {_OFFICIAL_PROMPT_VERSION!r}",
        )
    return BenchmarkConfig(
        benchmark_id=benchmark_id,
        dataset_id=_OFFICIAL_DATASET_ID,
        dataset_version=_OFFICIAL_DATASET_VERSION,
        rule_profile_id=_OFFICIAL_PROFILE_ID,
        rule_profile_version=_OFFICIAL_PROFILE_VERSION,
        provider=_OFFICIAL_PROVIDER,
        model=_OFFICIAL_MODEL,
        prompt_version=_OFFICIAL_PROMPT_VERSION,
        prompt_sha256=_official_prompt_sha256(),
        model_parameters=_official_model_parameters(),
        sdk_versions=_official_sdk_versions(),
        repetitions=_OFFICIAL_REPETITIONS,
        max_infrastructure_retries=2,
        max_concurrency=1,
        started_at_utc=started_at_utc,
    )


def _scripted_benchmark_config(
    manifest: DatasetManifest,
    *,
    benchmark_id: str,
    started_at_utc: datetime,
) -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id=benchmark_id,
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        rule_profile_id=manifest.rule_profile_id,
        rule_profile_version=manifest.rule_profile_version,
        provider=None,
        model=None,
        prompt_version=None,
        prompt_sha256=None,
        model_parameters={},
        sdk_versions={},
        repetitions=1,
        started_at_utc=started_at_utc,
    )


def _held_out_slot_schedule(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
) -> tuple[tuple[str, int], ...]:
    return tuple(
        (case.case_id, run_slot)
        for run_slot in range(1, config.repetitions + 1)
        for case in manifest.cases
        if case.split == "held_out"
    )


def _baseline_slot_schedule(
    manifest: DatasetManifest,
) -> tuple[tuple[str, int], ...]:
    return tuple((case.case_id, 1) for case in manifest.cases)


def _classify_transport_error(
    error: BaseException,
) -> tuple[AttemptStatus, AttemptErrorCode]:
    marked = getattr(error, "_signal_diag_attempt_error_code", None)
    if marked in _RETRYABLE_ERROR_CODES or marked == "provider_other":
        return "infrastructure_error", marked
    if marked in _CONFIG_ERROR_CODES:
        return "configuration_error", marked
    if marked in {"trace_assembly", "scoring", "reporting"}:
        return "evaluator_error", marked
    status_code = getattr(error, "status_code", None)
    name = type(error).__name__.lower()
    if isinstance(error, TimeoutError) or "timeout" in name:
        return "infrastructure_error", "timeout"
    if status_code == 429 or "ratelimit" in name:
        return "infrastructure_error", "rate_limited"
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return "infrastructure_error", "provider_5xx"
    if status_code in {401, 403} or "auth" in name:
        return "configuration_error", "authentication"
    module = type(error).__module__ or ""
    if getattr(error, "_signal_diag_provider_error", False) or module == "openai" or module.startswith("openai."):
        return "infrastructure_error", "provider_other"
    return "evaluator_error", "trace_assembly"


def _import_openai() -> object:
    import openai

    return openai


def _live_provider_client() -> object:
    from signal_diag.agent.planner import (
        _create_async_openai_client,
        _resolve_deepseek_config,
    )

    api_key, base_url, _model = _resolve_deepseek_config(
        api_key=None,
        base_url=None,
        model=None,
    )
    return _create_async_openai_client(api_key=api_key, base_url=base_url)


def _preflight_official(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
    *,
    client_factory: Callable[[], object] | None = None,
    import_openai: Callable[[], object] | None = None,
) -> None:
    if _S1_PROMPT_V4.version != _OFFICIAL_PROMPT_VERSION:
        raise _PreflightFailure(
            "invalid_configuration",
            f"prompt version must be {_OFFICIAL_PROMPT_VERSION!r}",
        )
    expected_hash = _official_prompt_sha256()
    if config.prompt_sha256 != expected_hash:
        raise _PreflightFailure(
            "invalid_configuration",
            "prompt SHA-256 does not match the frozen product planner prompt",
        )
    if config.prompt_version != _OFFICIAL_PROMPT_VERSION:
        raise _PreflightFailure(
            "invalid_configuration",
            f"prompt version must be {_OFFICIAL_PROMPT_VERSION!r}",
        )
    if config.provider != _OFFICIAL_PROVIDER or config.model != _OFFICIAL_MODEL:
        raise _PreflightFailure(
            "invalid_configuration",
            "official runner pins provider deepseek and model deepseek-v4-flash",
        )
    if config.max_concurrency != 1:
        raise _PreflightFailure(
            "invalid_configuration",
            "official execution requires max_concurrency=1",
        )
    _require_valid_dataset(manifest)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise _PreflightFailure(
            "missing_credentials",
            "set DEEPSEEK_API_KEY before running the official real-model benchmark",
        )
    if client_factory is None:
        try:
            (import_openai or _import_openai)()
        except ImportError as error:
            raise _PreflightFailure(
                "missing_dependency",
                "RealLLMPlanner requires the optional openai dependency",
            ) from error


def _configuration_attempts(
    slots: tuple[tuple[str, int], ...],
    code: AttemptErrorCode,
    message: str,
    when: datetime,
) -> tuple[AttemptRecord, ...]:
    return tuple(
        AttemptRecord(
            execution_path="agent",
            case_id=case_id,
            run_slot=run_slot,
            attempt_index=1,
            status="configuration_error",
            error_code=code,
            error_message=message,
            started_at_utc=when,
            finished_at_utc=when,
        )
        for case_id, run_slot in slots
    )


def _error_status_code(error: BaseException) -> int | None:
    for attribute in ("status_code", "status"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def _restricted_error_message(error: BaseException) -> str:
    error_type = type(error).__name__
    status = _error_status_code(error)
    if status is None:
        return error_type
    return f"{error_type} status={status}"


def _attempt_record(
    *,
    execution_path: str,
    case_id: str,
    run_slot: int,
    attempt_index: int,
    status: AttemptStatus,
    started: datetime,
    finished: datetime,
    error_code: AttemptErrorCode | None = None,
    error_message: str | None = None,
) -> AttemptRecord:
    return AttemptRecord(
        execution_path=execution_path,  # type: ignore[arg-type]
        case_id=case_id,
        run_slot=run_slot,
        attempt_index=attempt_index,
        status=status,
        error_code=error_code,
        error_message=error_message,
        started_at_utc=started,
        finished_at_utc=finished,
    )


def _build_official_planner(inner_client: object) -> RealLLMPlanner:
    capture_client = _UsageCapturingClient(inner_client)  # type: ignore[arg-type]
    return _Phase4V4RealLLMPlanner(provider="deepseek", client=capture_client)


def _assemble_applied_agent_trace(
    case: EvaluationCase,
    records: tuple[Any, ...],
    result: Any,
    config: BenchmarkConfig,
    run_slot: int,
) -> EvaluationTrace:
    try:
        return assemble_evaluation_trace(
            case,
            records,
            result,
            config,
            run_slot=run_slot,
            execution_path="agent",
        )
    except ValueError as error:
        error._signal_diag_attempt_error_code = "trace_assembly"  # type: ignore[attr-defined]
        raise


async def _execute_agent_slot(
    case: EvaluationCase,
    config: BenchmarkConfig,
    run_slot: int,
    inner_client: object,
) -> EvaluationTrace:
    repository = InMemorySignalRepository()
    record = _materialize_case(case, repository)
    tool_service, rule_engine, profile_loader, knowledge_index = _official_dependencies(
        repository
    )
    planner = _build_official_planner(inner_client)
    recording = RecordingPlanner(planner)
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
    return _assemble_applied_agent_trace(
        case,
        recording.records,
        result,
        config,
        run_slot,
    )


async def _run_agent_slot_with_retries(
    case: EvaluationCase,
    config: BenchmarkConfig,
    run_slot: int,
    *,
    client_factory: Callable[[], object],
    classify_error: Callable[[BaseException], tuple[AttemptStatus, AttemptErrorCode]],
    now: Callable[[], datetime],
) -> tuple[EvaluationTrace | None, tuple[AttemptRecord, ...]]:
    max_attempts = 1 + config.max_infrastructure_retries
    attempts: list[AttemptRecord] = []
    for attempt_index in range(1, max_attempts + 1):
        started = now()
        try:
            trace = await _execute_agent_slot(
                case,
                config,
                run_slot,
                client_factory(),
            )
        except Exception as error:  # noqa: BLE001 - classify any provider/transport failure
            finished = max(now(), started)
            status, code = classify_error(error)
            attempts.append(
                _attempt_record(
                    execution_path="agent",
                    case_id=case.case_id,
                    run_slot=run_slot,
                    attempt_index=attempt_index,
                    status=status,
                    error_code=code,
                    error_message=_restricted_error_message(error),
                    started=started,
                    finished=finished,
                )
            )
            if code in _RETRYABLE_ERROR_CODES and attempt_index < max_attempts:
                continue
            return None, tuple(attempts)
        finished = now()
        finished = max(finished, started)
        attempts.append(
            _attempt_record(
                execution_path="agent",
                case_id=case.case_id,
                run_slot=run_slot,
                attempt_index=attempt_index,
                status="behavior_result",
                started=started,
                finished=finished,
            )
        )
        return trace, tuple(attempts)
    return None, tuple(attempts)


async def _execute_baseline_slot(
    case: EvaluationCase,
    config: BenchmarkConfig,
    run_slot: int,
) -> EvaluationTrace:
    repository = InMemorySignalRepository()
    record = _materialize_case(case, repository)
    tool_service, rule_engine, profile_loader, _index = _official_dependencies(
        repository
    )
    baseline = FixedPipelineBaseline(
        repository=repository,
        tool_service=tool_service,
        rule_engine=rule_engine,
        profile_loader=profile_loader,
    )
    result = await baseline.run(
        signal_id=record.meta.signal_id,
        user_request=case.user_request,
    )
    return assemble_evaluation_trace(
        case,
        (),
        result,
        config,
        run_slot=run_slot,
        execution_path="fixed_pipeline",
    )


def _tool_step(
    tool_name: str,
    *,
    observation_count: int,
    first: bool = False,
) -> ScriptedStep:
    if tool_name == "detect_clipping":
        call: DetectClippingCall | AnalyzeHarmonicDistortionCall = DetectClippingCall(
            args=ClippingInput()
        )
    elif tool_name == "analyze_harmonic_distortion":
        call = AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput())
    else:
        raise ValueError(f"unsupported scripted tool: {tool_name}")
    return ScriptedStep(
        expected_observation_count=observation_count,
        decision=CallToolDecision(
            task_assessment=_SCRIPTED_ASSESSMENT if first else None,
            call=call,
            purpose=f"collect {tool_name} evidence",
        ),
    )


def _scripted_tool_route(case: EvaluationCase) -> tuple[str, ...]:
    if case.category == "clipping":
        return ("detect_clipping",)
    if case.category == "invalid_noise":
        return ("analyze_harmonic_distortion",)
    if case.category == "harmonic":
        if case.case_id in _HARMONIC_ONLY_CASES:
            return ("analyze_harmonic_distortion",)
        return ("detect_clipping", "analyze_harmonic_distortion")
    if case.category == "clean" and case.case_id == _HARMONIC_THEN_CLIPPING_CLEAN:
        return ("analyze_harmonic_distortion", "detect_clipping")
    return ("detect_clipping", "analyze_harmonic_distortion")


def _finish_template(case: EvaluationCase) -> FinishDecision:
    if case.category == "invalid_noise":
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_inconclusive",
                    fault_type="inconclusive",
                    statement="Harmonic analysis is not applicable on this signal.",
                ),
            ),
            confidence_label="low",
            limitations=(
                "harmonic analysis is not applicable; no THD value was fabricated",
            ),
        )
    claims: tuple[DiagnosisClaim, ...]
    if case.category == "clean":
        claims = (
            DiagnosisClaim(
                claim_id="claim_clean",
                fault_type="no_supported_fault",
                statement="Configured clipping and THD limits pass on this signal.",
            ),
        )
        outcome = "no_supported_fault"
    elif case.category == "clipping":
        claims = (
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping evidence supports a clipping diagnosis.",
            ),
        )
        outcome = "supported_fault"
    elif case.category == "harmonic":
        claims = (
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Harmonic evidence supports a harmonic-distortion diagnosis.",
            ),
        )
        outcome = "supported_fault"
    else:
        claims = (
            DiagnosisClaim(
                claim_id="claim_clip",
                fault_type="clipping",
                statement="Clipping evidence supports a clipping diagnosis.",
            ),
            DiagnosisClaim(
                claim_id="claim_harm",
                fault_type="harmonic_distortion",
                statement="Harmonic evidence supports a harmonic-distortion diagnosis.",
            ),
        )
        outcome = "supported_fault"
    return FinishDecision(
        outcome=outcome,  # type: ignore[arg-type]
        claims=claims,
        confidence_label="high",
    )


def _scripted_steps_for_case(case: EvaluationCase) -> tuple[ScriptedStep, ...]:
    tools = _scripted_tool_route(case)
    steps: list[ScriptedStep] = [
        _tool_step(tool_name, observation_count=index, first=index == 0)
        for index, tool_name in enumerate(tools)
    ]
    observations = len(tools)
    if case.category != "invalid_noise":
        steps.append(
            ScriptedStep(
                expected_observation_count=observations,
                decision=EvaluateRulesDecision(
                    profile_id=_OFFICIAL_PROFILE_ID,
                    evidence_refs=(),
                    purpose="apply configured S1 demonstration limits",
                ),
            )
        )
    if case.knowledge_policy == "required":
        steps.append(
            ScriptedStep(
                expected_observation_count=observations,
                decision=RetrieveKnowledgeDecision(
                    query_text=" ".join(case.knowledge_tags) or "inconclusive analysis",
                    tags=case.knowledge_tags,
                    purpose="retrieve required knowledge for the current diagnosis",
                ),
            )
        )
    steps.append(
        ScriptedStep(
            expected_observation_count=observations,
            decision=_finish_template(case),
        )
    )
    return tuple(steps)


async def _run_official_benchmark(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
    output_dir: Path,
    *,
    client_factory: Callable[[], object] | None = None,
    classify_error: Callable[[BaseException], tuple[AttemptStatus, AttemptErrorCode]]
    | None = None,
    import_openai: Callable[[], object] | None = None,
    now: Callable[[], datetime] | None = None,
) -> BenchmarkReport:
    dest = output_dir / config.benchmark_id
    if dest.exists():
        raise FileExistsError(dest)
    clock = now or (lambda: datetime.now(UTC))
    classifier = classify_error or _classify_transport_error
    cases = {case.case_id: case for case in manifest.cases}
    agent_slots = _held_out_slot_schedule(manifest, config)
    try:
        _preflight_official(
            manifest,
            config,
            client_factory=client_factory,
            import_openai=import_openai,
        )
    except _PreflightFailure as error:
        preflight_attempts = _configuration_attempts(
            agent_slots,
            error.code,
            error.message,
            clock(),
        )
        report = aggregate_benchmark(
            manifest,
            (),
            (),
            preflight_attempts,
            config,
            TargetBands(),
            harness_status="pending",
        )
        write_benchmark_bundle(report, output_dir)
        return report

    factory = client_factory or _live_provider_client
    traces: list[EvaluationTrace] = []
    scores = []
    recorded_attempts: list[AttemptRecord] = []
    for case_id, run_slot in agent_slots:
        trace, slot_attempts = await _run_agent_slot_with_retries(
            cases[case_id],
            config,
            run_slot,
            client_factory=factory,
            classify_error=classifier,
            now=clock,
        )
        recorded_attempts.extend(slot_attempts)
        if trace is None:
            continue
        try:
            score = score_evaluation_trace(cases[case_id], trace)
        except (ValueError, ValidationError, TypeError) as error:
            finished = clock()
            recorded_attempts.append(
                _attempt_record(
                    execution_path="agent",
                    case_id=case_id,
                    run_slot=run_slot,
                    attempt_index=len(slot_attempts) + 1,
                    status="evaluator_error",
                    error_code="scoring",
                    error_message=_restricted_error_message(error),
                    started=finished,
                    finished=finished,
                )
            )
            continue
        traces.append(trace)
        scores.append(score)

    for case_id, run_slot in _baseline_slot_schedule(manifest):
        started = clock()
        try:
            trace = await _execute_baseline_slot(cases[case_id], config, run_slot)
            score = score_evaluation_trace(cases[case_id], trace)
        except Exception as error:  # noqa: BLE001 - baseline evaluator failures stay incomplete
            finished = clock()
            recorded_attempts.append(
                _attempt_record(
                    execution_path="fixed_pipeline",
                    case_id=case_id,
                    run_slot=run_slot,
                    attempt_index=1,
                    status="evaluator_error",
                    error_code="trace_assembly",
                    error_message=_restricted_error_message(error),
                    started=started,
                    finished=finished,
                )
            )
            continue
        finished = clock()
        traces.append(trace)
        scores.append(score)
        recorded_attempts.append(
            _attempt_record(
                execution_path="fixed_pipeline",
                case_id=case_id,
                run_slot=run_slot,
                attempt_index=1,
                status="behavior_result",
                started=started,
                finished=finished,
            )
        )

    report = aggregate_benchmark(
        manifest,
        tuple(traces),
        tuple(scores),
        tuple(recorded_attempts),
        config,
        TargetBands(),
        harness_status="pending",
    )
    write_benchmark_bundle(report, output_dir)
    return report


async def _run_deterministic_benchmark(
    manifest: DatasetManifest,
    config: BenchmarkConfig,
    output_dir: Path,
    *,
    _clock: Callable[[], float] | None = None,
    now: Callable[[], datetime] | None = None,
) -> BenchmarkReport:
    dest = output_dir / config.benchmark_id
    if dest.exists():
        raise FileExistsError(dest)
    clock = now or (lambda: datetime.now(UTC))
    scripts = {
        case.case_id: _scripted_steps_for_case(case) for case in manifest.cases
    }
    agent_traces = await _run_deterministic_harness(
        manifest,
        scripts,
        config,
        _clock=_clock,
    )
    cases = {case.case_id: case for case in manifest.cases}
    traces: list[EvaluationTrace] = list(agent_traces)
    scores = [score_evaluation_trace(cases[trace.case_id], trace) for trace in agent_traces]
    attempts: list[AttemptRecord] = []
    started = clock()
    for trace in agent_traces:
        attempts.append(
            _attempt_record(
                execution_path="agent",
                case_id=trace.case_id,
                run_slot=trace.run_slot,
                attempt_index=1,
                status="behavior_result",
                started=started,
                finished=clock(),
            )
        )
    for case_id, run_slot in _baseline_slot_schedule(manifest):
        slot_started = clock()
        trace = await _execute_baseline_slot(cases[case_id], config, run_slot)
        traces.append(trace)
        scores.append(score_evaluation_trace(cases[case_id], trace))
        attempts.append(
            _attempt_record(
                execution_path="fixed_pipeline",
                case_id=case_id,
                run_slot=run_slot,
                attempt_index=1,
                status="behavior_result",
                started=slot_started,
                finished=clock(),
            )
        )
    report = aggregate_benchmark(
        manifest,
        tuple(traces),
        tuple(scores),
        tuple(attempts),
        config,
        TargetBands(),
        harness_status="pending",
    )
    write_benchmark_bundle(report, output_dir)
    return report


def _load_official_manifest() -> DatasetManifest:
    return load_dataset_manifest(_official_manifest_path())
