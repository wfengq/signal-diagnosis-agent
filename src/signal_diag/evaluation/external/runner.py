"""Identical-WAV Agent and fixed-pipeline execution for external validation."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from signal_diag.agent.models import AgentRunResult
from signal_diag.agent.planner import (
    PlannerModel,
    RealLLMPlanner,
    ScriptedPlanner,
    _Phase4V8_1RealLLMPlanner,
)
from signal_diag.agent.prompts import _S1_PROMPT_V8_1
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.baseline import FixedPipelineBaseline
from signal_diag.evaluation.external.manifest import (
    canonical_json_bytes,
    load_external_manifest,
    manifest_sha256,
)
from signal_diag.evaluation.external.models import (
    ExternalAttemptRecord,
    ExternalCase,
    ExternalDatasetManifest,
    ExternalMaterializedSignal,
    ExternalRunnerReport,
    FinalSeal,
)
from signal_diag.evaluation.models import (
    AttemptErrorCode,
    AttemptStatus,
    BenchmarkConfig,
    ConfigValue,
    EvaluationTrace,
    ExecutionPath,
)
from signal_diag.evaluation.recording import (
    RecordingPlanner,
    assemble_evaluation_trace,
)
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.signal.models import SignalRecord
from signal_diag.signal.wav import InvalidWavError, load_wav_bytes
from signal_diag.tools.service import SignalToolService

_NEUTRAL_USER_REQUEST = (
    "Why does this signal sound distorted? Check only the supported S1 causes and "
    "state clearly when the evidence is insufficient or the analysis is not "
    "applicable."
)
_EXTERNAL_BENCHMARK_ID = "bench_ext_wav_final_1"
_OFFICIAL_PROFILE_ID = "profile_s1_distortion"
_OFFICIAL_PROFILE_VERSION = "1.0.0-demo"
_OFFICIAL_PROVIDER = "deepseek"
_OFFICIAL_MODEL = "deepseek-v4-flash"
_RETRYABLE_ERROR_CODES = frozenset({"timeout", "rate_limited", "provider_5xx"})
_CONFIG_ERROR_CODES = frozenset(
    {
        "authentication",
        "missing_credentials",
        "missing_dependency",
        "invalid_configuration",
    }
)


@runtime_checkable
class ExternalPlannerFactory(Protocol):
    def __call__(self, client: object) -> PlannerModel: ...


@dataclass(frozen=True)
class _TraceCaseShell:
    case_id: str


class ExternalRunnerError(Exception):
    """Base class for external runner preflight and slot errors."""


class ExternalAuthorizationError(PermissionError):
    """Raised when real-model execution is not explicitly authorized."""


class ExternalPreflightError(ExternalRunnerError):
    def __init__(self, code: AttemptErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _package_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[2].joinpath(*parts)


def _official_profile_path() -> Path:
    return _package_path("rules", "profiles", "s1_distortion_v1.yaml")


def _official_corpus_path() -> Path:
    return _package_path("knowledge", "corpus")


def _official_profile_loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader({_OFFICIAL_PROFILE_ID: _official_profile_path()})


def _official_knowledge_index() -> KnowledgeIndex:
    return KnowledgeIndex(_official_corpus_path())


def _official_dependencies(
    repository: InMemorySignalRepository,
) -> tuple[SignalToolService, RuleEngine, YamlRuleProfileLoader, KnowledgeIndex]:
    return (
        SignalToolService(repository),
        RuleEngine(),
        _official_profile_loader(),
        _official_knowledge_index(),
    )


def _external_prompt_sha256() -> str:
    return hashlib.sha256(_S1_PROMPT_V8_1.system_prompt.encode("utf-8")).hexdigest()


def _external_model_parameters() -> dict[str, ConfigValue]:
    return {
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def _baseline_config(
    manifest: ExternalDatasetManifest,
    *,
    started_at_utc: datetime,
) -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id=_EXTERNAL_BENCHMARK_ID,
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        rule_profile_id=manifest.rule_profile_id,
        rule_profile_version=manifest.rule_profile_version,
        repetitions=1,
        max_infrastructure_retries=0,
        max_concurrency=1,
        started_at_utc=started_at_utc,
    )


def _agent_config(
    manifest: ExternalDatasetManifest,
    *,
    started_at_utc: datetime,
) -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id=_EXTERNAL_BENCHMARK_ID,
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        rule_profile_id=manifest.rule_profile_id,
        rule_profile_version=manifest.rule_profile_version,
        provider=_OFFICIAL_PROVIDER,
        model=_OFFICIAL_MODEL,
        prompt_version=_S1_PROMPT_V8_1.version,
        prompt_sha256=_external_prompt_sha256(),
        model_parameters=_external_model_parameters(),
        sdk_versions={},
        repetitions=1,
        max_infrastructure_retries=0,
        max_concurrency=1,
        started_at_utc=started_at_utc,
    )


def _opaque_external_signal_id(case: ExternalCase) -> str:
    raw = f"v0.2-external-wav-validity-1\0{case.case_id}\0{case.wav_sha256}".encode()
    return f"sig_ext_{hashlib.sha256(raw).hexdigest()[:16]}"


def _trace_case_id(case: ExternalCase) -> str:
    return f"case_ext_{case.case_id}"


def _analysis_filename(case: ExternalCase) -> str:
    return f"extwav_{case.split}_{case.case_id}.wav"


def _load_sealed_study(seal: Path) -> tuple[FinalSeal, ExternalDatasetManifest]:
    seal_dir = seal.resolve()
    if not seal_dir.is_dir():
        raise FileNotFoundError(f"sealed study directory not found: {seal_dir}")
    manifest_path = seal_dir / "study_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("sealed study missing study_manifest.json")
    manifest = load_external_manifest(manifest_path)
    manifest_bytes = canonical_json_bytes(manifest)
    if manifest_bytes != manifest_path.read_bytes():
        raise ValueError("study_manifest.json is not canonical")
    checksum_path = seal_dir / "seal.sha256"
    if not checksum_path.is_file():
        raise FileNotFoundError("sealed study missing seal.sha256")
    expected_manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    checksum_lines = checksum_path.read_text(encoding="utf-8").splitlines()
    manifest_record = next(
        (
            line
            for line in checksum_lines
            if line.endswith("  study_manifest.json")
        ),
        None,
    )
    if manifest_record is None:
        raise ValueError("seal.sha256 missing study_manifest.json record")
    recorded_digest = manifest_record.split("  ", maxsplit=1)[0]
    if recorded_digest != expected_manifest_digest:
        raise ValueError("sealed manifest digest mismatch")
    seal_id = hashlib.sha256(checksum_path.read_bytes()).hexdigest()
    final_cases = tuple(
        case for case in manifest.cases if case.split == "final_external_test"
    )
    scoreable_count = sum(
        1
        for case in final_cases
        if case.confidence in {"strong_ground_truth", "reference_supported"}
    )
    sealed_at_utc = datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=UTC)
    metadata = FinalSeal(
        seal_id=seal_id,
        study_id=manifest.study_id,
        manifest_sha256=manifest_sha256(manifest),
        sealed_at_utc=sealed_at_utc,
        case_count=len(final_cases),
        scoreable_case_count=scoreable_count,
    )
    return metadata, manifest


def _final_cases(manifest: ExternalDatasetManifest) -> tuple[ExternalCase, ...]:
    cases = tuple(
        case for case in manifest.cases if case.split == "final_external_test"
    )
    if not cases:
        raise ValueError("sealed manifest has no final_external_test cases")
    return cases


def _preflight_assets(
    cases: tuple[ExternalCase, ...],
    asset_root: Path,
) -> None:
    repository = InMemorySignalRepository()
    for case in cases:
        _materialize_external_signal(case, asset_root, repository)


def _attempt_record_path(
    output: Path,
    *,
    execution_path: ExecutionPath,
    case_id: str,
) -> Path:
    return output / "attempts" / execution_path / f"{case_id}.json"


def _assert_slot_available(path: Path) -> None:
    pending = path.with_suffix(".pending.json")
    if path.exists() or pending.exists():
        raise FileExistsError(f"attempt slot already consumed: {path.stem}")


def _write_pending_attempt(path: Path, attempt: ExternalAttemptRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending.json")
    _assert_slot_available(path)
    pending.write_text(
        json.dumps(attempt.model_dump(mode="json"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _finalize_attempt(path: Path, attempt: ExternalAttemptRecord) -> None:
    pending = path.with_suffix(".pending.json")
    payload = json.dumps(attempt.model_dump(mode="json"), sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    if pending.exists():
        pending.unlink()


def _load_existing_attempt(path: Path) -> ExternalAttemptRecord | None:
    if not path.is_file():
        return None
    return ExternalAttemptRecord.model_validate_json(path.read_text(encoding="utf-8"))


def _materialize_external_signal(
    case: ExternalCase,
    asset_root: Path,
    repository: InMemorySignalRepository,
) -> ExternalMaterializedSignal:
    wav_path = asset_root / case.analysis_wav_path
    if not wav_path.is_file():
        raise FileNotFoundError(f"analysis WAV not found: {wav_path.as_posix()}")
    payload = wav_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != case.wav_sha256:
        raise ValueError(
            f"wav_sha256 mismatch for {case.case_id}: expected {case.wav_sha256}, got {digest}"
        )
    filename = _analysis_filename(case)
    try:
        loaded = load_wav_bytes(payload, filename=filename)
    except InvalidWavError as error:
        raise ValueError(f"analysis WAV failed loader validation: {error}") from error
    record = loaded.record
    if record.meta.sample_rate_hz != case.wav_sample_rate_hz:
        raise ValueError("wav sample rate does not match manifest")
    if record.meta.channels != case.wav_channels:
        raise ValueError("wav channel count does not match manifest")
    if record.meta.num_samples != case.wav_frames:
        raise ValueError("wav frame count does not match manifest")
    signal_id = _opaque_external_signal_id(case)
    updated = SignalRecord(
        meta=record.meta.model_copy(
            update={
                "signal_id": signal_id,
                "filename": filename,
            }
        ),
        samples=record.samples,
    )
    repository.put(updated)
    return ExternalMaterializedSignal(
        case_id=case.case_id,
        signal_id=signal_id,
        trace_case_id=_trace_case_id(case),
        filename=filename,
        wav_sha256=digest,
    )


def _preflight_shared(
    seal: Path,
    asset_root: Path,
    output: Path,
) -> tuple[FinalSeal, ExternalDatasetManifest, tuple[ExternalCase, ...]]:
    metadata, manifest = _load_sealed_study(seal)
    asset_root = asset_root.resolve()
    if not asset_root.is_dir():
        raise FileNotFoundError(f"asset_root not found: {asset_root}")
    output.resolve()
    cases = _final_cases(manifest)
    _preflight_assets(cases, asset_root)
    return metadata, manifest, cases


def _preflight_agent(
    *,
    authorized: bool,
    client_factory: Callable[[], object] | None,
    import_openai: Callable[[], object] | None,
) -> None:
    if not authorized:
        raise ExternalAuthorizationError(
            "external agent execution requires explicit authorization"
        )
    if _S1_PROMPT_V8_1.version != "v0.2-s1-planner-8.1":
        raise ExternalPreflightError(
            "invalid_configuration",
            "prompt version must be 'v0.2-s1-planner-8.1'",
        )
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise ExternalPreflightError(
            "missing_credentials",
            "set DEEPSEEK_API_KEY before running the external agent campaign",
        )
    if client_factory is None:
        try:
            (import_openai or _import_openai)()
        except ImportError as error:
            raise ExternalPreflightError(
                "missing_dependency",
                "RealLLMPlanner requires the optional openai dependency",
            ) from error


def _import_openai() -> object:
    import openai

    return openai


def _default_client_factory() -> object:
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


def _build_production_planner(client: object) -> RealLLMPlanner:
    return _Phase4V8_1RealLLMPlanner(  # type: ignore[arg-type]
        provider=_OFFICIAL_PROVIDER,
        client=client,
    )


def _reject_scripted_planner(planner: PlannerModel) -> PlannerModel:
    if isinstance(planner, ScriptedPlanner):
        raise ExternalPreflightError(
            "invalid_configuration",
            "ScriptedPlanner is not permitted for external agent execution",
        )
    return planner


def _attempt_record(
    *,
    execution_path: ExecutionPath,
    case_id: str,
    run_slot: int,
    attempt_index: int,
    status: AttemptStatus,
    started: datetime,
    finished: datetime,
    error_code: AttemptErrorCode | None = None,
    error_message: str | None = None,
) -> ExternalAttemptRecord:
    return ExternalAttemptRecord(
        execution_path=execution_path,
        case_id=case_id,
        run_slot=run_slot,
        attempt_index=attempt_index,
        status=status,
        error_code=error_code,
        error_message=error_message,
        started_at_utc=started,
        finished_at_utc=finished,
    )


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
    if (
        getattr(error, "_signal_diag_provider_error", False)
        or module == "openai"
        or module.startswith("openai.")
    ):
        return "infrastructure_error", "provider_other"
    return "evaluator_error", "trace_assembly"


def _restricted_error_message(error: BaseException) -> str:
    error_type = type(error).__name__
    status = getattr(error, "status_code", None)
    if status is None:
        return error_type
    return f"{error_type} status={status}"


def _assemble_external_trace(
    case: ExternalCase,
    records: tuple[object, ...],
    result: AgentRunResult | object,
    config: BenchmarkConfig,
    *,
    run_slot: int,
    execution_path: ExecutionPath,
) -> EvaluationTrace:
    shell = _TraceCaseShell(case_id=_trace_case_id(case))
    return assemble_evaluation_trace(
        shell,  # type: ignore[arg-type]
        records,  # type: ignore[arg-type]
        result,  # type: ignore[arg-type]
        config,
        run_slot=run_slot,
        execution_path=execution_path,
    )


async def _execute_baseline_slot(
    case: ExternalCase,
    asset_root: Path,
    config: BenchmarkConfig,
    run_slot: int,
) -> tuple[EvaluationTrace, ExternalMaterializedSignal]:
    repository = InMemorySignalRepository()
    materialized = _materialize_external_signal(case, asset_root, repository)
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
        signal_id=materialized.signal_id,
        user_request=_NEUTRAL_USER_REQUEST,
    )
    trace = _assemble_external_trace(
        case,
        (),
        result,
        config,
        run_slot=run_slot,
        execution_path="fixed_pipeline",
    )
    return trace, materialized


async def _execute_agent_slot(
    case: ExternalCase,
    asset_root: Path,
    config: BenchmarkConfig,
    run_slot: int,
    planner: PlannerModel,
) -> tuple[EvaluationTrace, ExternalMaterializedSignal]:
    repository = InMemorySignalRepository()
    materialized = _materialize_external_signal(case, asset_root, repository)
    tool_service, rule_engine, profile_loader, knowledge_index = _official_dependencies(
        repository
    )
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
        signal_id=materialized.signal_id,
        user_request=_NEUTRAL_USER_REQUEST,
    )
    trace = _assemble_external_trace(
        case,
        recording.records,
        result,
        config,
        run_slot=run_slot,
        execution_path="agent",
    )
    return trace, materialized


async def run_external_baseline(
    seal: Path,
    asset_root: Path,
    output: Path,
    *,
    started_at_utc: datetime | None = None,
) -> ExternalRunnerReport:
    started = started_at_utc or datetime.now(tz=UTC)
    metadata, manifest, cases = _preflight_shared(seal, asset_root, output)
    config = _baseline_config(manifest, started_at_utc=started)
    attempts: list[ExternalAttemptRecord] = []
    traces: list[EvaluationTrace] = []
    materialized: list[ExternalMaterializedSignal] = []
    for run_slot, case in enumerate(cases, start=1):
        attempt_path = _attempt_record_path(
            output,
            execution_path="fixed_pipeline",
            case_id=case.case_id,
        )
        existing = _load_existing_attempt(attempt_path)
        if existing is not None:
            raise FileExistsError(f"attempt slot already consumed: {case.case_id}")
        started_slot = datetime.now(tz=UTC)
        pending = _attempt_record(
            execution_path="fixed_pipeline",
            case_id=case.case_id,
            run_slot=run_slot,
            attempt_index=1,
            status="behavior_result",
            started=started_slot,
            finished=started_slot,
        )
        _write_pending_attempt(attempt_path, pending)
        try:
            trace, signal = await _execute_baseline_slot(
                case,
                asset_root,
                config,
                run_slot,
            )
        except Exception as error:  # noqa: BLE001
            finished = datetime.now(tz=UTC)
            status, code = _classify_transport_error(error)
            final_attempt = _attempt_record(
                execution_path="fixed_pipeline",
                case_id=case.case_id,
                run_slot=run_slot,
                attempt_index=1,
                status=status,
                error_code=code,
                error_message=_restricted_error_message(error),
                started=started_slot,
                finished=finished,
            )
            _finalize_attempt(attempt_path, final_attempt)
            attempts.append(final_attempt)
            continue
        finished = datetime.now(tz=UTC)
        final_attempt = pending.model_copy(update={"finished_at_utc": finished})
        _finalize_attempt(attempt_path, final_attempt)
        attempts.append(final_attempt)
        traces.append(trace)
        materialized.append(signal)
    return ExternalRunnerReport(
        execution_path="fixed_pipeline",
        seal_id=metadata.seal_id,
        manifest_sha256=metadata.manifest_sha256,
        config=config,
        attempts=tuple(attempts),
        traces=tuple(traces),
        materialized=tuple(materialized),
    )


async def run_external_agent(
    seal: Path,
    asset_root: Path,
    output: Path,
    *,
    planner_factory: ExternalPlannerFactory | None = None,
    authorized: bool = False,
    client_factory: Callable[[], object] | None = None,
    import_openai: Callable[[], object] | None = None,
    started_at_utc: datetime | None = None,
) -> ExternalRunnerReport:
    metadata, manifest, cases = _preflight_shared(seal, asset_root, output)
    _preflight_agent(
        authorized=authorized,
        client_factory=client_factory,
        import_openai=import_openai,
    )
    started = started_at_utc or datetime.now(tz=UTC)
    config = _agent_config(manifest, started_at_utc=started)
    factory = planner_factory or _build_production_planner
    attempts: list[ExternalAttemptRecord] = []
    traces: list[EvaluationTrace] = []
    materialized: list[ExternalMaterializedSignal] = []
    for run_slot, case in enumerate(cases, start=1):
        attempt_path = _attempt_record_path(
            output,
            execution_path="agent",
            case_id=case.case_id,
        )
        existing = _load_existing_attempt(attempt_path)
        if existing is not None:
            raise FileExistsError(f"attempt slot already consumed: {case.case_id}")
        started_slot = datetime.now(tz=UTC)
        pending = _attempt_record(
            execution_path="agent",
            case_id=case.case_id,
            run_slot=run_slot,
            attempt_index=1,
            status="behavior_result",
            started=started_slot,
            finished=started_slot,
        )
        _write_pending_attempt(attempt_path, pending)
        client = (client_factory or _default_client_factory)()
        planner = _reject_scripted_planner(factory(client))
        try:
            trace, signal = await _execute_agent_slot(
                case,
                asset_root,
                config,
                run_slot,
                planner,
            )
        except Exception as error:  # noqa: BLE001
            finished = datetime.now(tz=UTC)
            status, code = _classify_transport_error(error)
            final_attempt = _attempt_record(
                execution_path="agent",
                case_id=case.case_id,
                run_slot=run_slot,
                attempt_index=1,
                status=status,
                error_code=code,
                error_message=_restricted_error_message(error),
                started=started_slot,
                finished=finished,
            )
            _finalize_attempt(attempt_path, final_attempt)
            attempts.append(final_attempt)
            continue
        finished = datetime.now(tz=UTC)
        final_attempt = pending.model_copy(update={"finished_at_utc": finished})
        _finalize_attempt(attempt_path, final_attempt)
        attempts.append(final_attempt)
        traces.append(trace)
        materialized.append(signal)
    return ExternalRunnerReport(
        execution_path="agent",
        seal_id=metadata.seal_id,
        manifest_sha256=metadata.manifest_sha256,
        config=config,
        attempts=tuple(attempts),
        traces=tuple(traces),
        materialized=tuple(materialized),
    )
