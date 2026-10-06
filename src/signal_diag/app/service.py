"""Shared diagnosis application service."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, runtime_checkable

from signal_diag.agent.diagnosis import CausalPolicyVersion
from signal_diag.agent.intake import (
    ContextDraft,
    IntakeCallLimits,
    IntakeCredentialsError,
    IntakePlanner,
    IntakeRequest,
    RealLLMIntakePlanner,
    build_openai_intake_client,
)
from signal_diag.agent.planner import PlannerModel
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.app.contextual_models import (
    ContextualAppRunSnapshot,
    ContextualRunSubmission,
)
from signal_diag.app.contextual_runs import (
    BoundedContextualRunExecutor,
    ContextualRunExecutionResult,
    ContextualRunWorkItem,
    InMemoryContextualRunStore,
)
from signal_diag.app.errors import (
    ApplicationError,
    InvalidRequestError,
    PlannerNotConfiguredError,
)
from signal_diag.app.models import (
    AppErrorDetail,
    AppRunSnapshot,
    ChannelMode,
    DemoPresetDescriptor,
    DemoPresetId,
    PlannerIdentity,
    RunSubmission,
    SourceSummary,
)
from signal_diag.app.presets import (
    build_demo_preset,
    list_demo_presets,
    render_demo_preset_wav,
)
from signal_diag.app.preview import build_waveform_preview
from signal_diag.app.reporting import project_agent_events
from signal_diag.app.runs import (
    BoundedRunExecutor,
    InMemoryRunStore,
    RunExecutionResult,
    RunWorkItem,
)
from signal_diag.evaluation.recording import RecordingPlanner, assemble_agent_events
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.models import RuleProfileLoader
from signal_diag.signal import (
    InvalidWavError,
    SignalLimitExceededError,
    SignalRecord,
    SignalRepository,
    UnsupportedChannelError,
    UnsupportedWavError,
    build_signal_record,
    extract_segment,
    load_wav_bytes,
)
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.guarded_service import GuardedSignalToolService

_MAX_USER_REQUEST_CHARS = 2_000
_DEFAULT_WAV_DISPLAY_NAME = "input.wav"


@runtime_checkable
class PlannerFactory(Protocol):
    def __call__(self) -> PlannerModel:
        ...


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    repository: SignalRepository
    planner_factory: PlannerFactory
    planner_identity: PlannerIdentity
    planner_configured: bool
    rule_engine: RuleEngine
    rule_profile_loader: RuleProfileLoader
    knowledge_index: KnowledgeIndex
    causal_policy_version: CausalPolicyVersion = "v9_4_legacy"
    intake_planner_factory: Callable[[], IntakePlanner] | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _planner_not_configured_detail() -> AppErrorDetail:
    return AppErrorDetail(
        code="planner_not_configured",
        message=(
            "RealLLMPlanner is not configured: set DEEPSEEK_API_KEY before "
            "submitting a diagnosis. The application does not fall back to "
            "ScriptedPlanner."
        ),
    )


def _invalid_request(message: str) -> InvalidRequestError:
    return InvalidRequestError(AppErrorDetail(code="invalid_request", message=message))


def product_intake_planner(
    *,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> IntakePlanner:
    """Product intake planner. Missing credentials raise; no scripted stand-in."""
    if not api_key or not model:
        raise IntakeCredentialsError(
            "RealLLMIntakePlanner is not configured: set DEEPSEEK_API_KEY. "
            "The application does not fall back to a scripted intake stand-in."
        )
    client = build_openai_intake_client(api_key=api_key, base_url=base_url)
    return RealLLMIntakePlanner(
        client=client,
        model=model,
        limits=IntakeCallLimits(max_output_tokens=800, timeout_s=60.0),
    )


def intake_planner_from_diagnosis_planner(diagnosis: PlannerModel) -> IntakePlanner:
    """Reuse the product diagnosis planner's closed-over credentials."""
    api_key = getattr(diagnosis, "_api_key", None)
    base_url = getattr(diagnosis, "_base_url", None)
    model = getattr(diagnosis, "model_id", None)
    return product_intake_planner(
        api_key=api_key if isinstance(api_key, str) else None,
        base_url=base_url if isinstance(base_url, str) else None,
        model=model if isinstance(model, str) else None,
    )


def _normalize_question(user_request: str) -> str:
    question = user_request.strip()
    if not question:
        raise _invalid_request("user_request must be a non-empty question")
    if len(question) > _MAX_USER_REQUEST_CHARS:
        raise _invalid_request("user_request must be at most 2000 characters")
    return question


def _as_source_channels(count: int) -> Literal[1, 2]:
    if count == 1:
        return 1
    if count == 2:
        return 2
    raise _invalid_request(f"unsupported channel count: {count}")


def _new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


def _queued_capabilities(
    mode: Literal["single_signal", "nominal_single_tone", "paired_reference"],
) -> EffectiveCapabilities:
    if mode == "nominal_single_tone":
        return EffectiveCapabilities(nominal_harmonic_attribution=True)
    if mode == "paired_reference":
        return EffectiveCapabilities(paired_harmonic_attribution=True)
    return EffectiveCapabilities()


def _context_valid_value(evidence: tuple[Evidence, ...]) -> bool | None:
    for item in evidence:
        if item.metric == "context_valid":
            return bool(item.value)
    return None


def _terminal_capabilities(
    *,
    mode: Literal["single_signal", "nominal_single_tone", "paired_reference"],
    queued: EffectiveCapabilities,
    evidence: tuple[Evidence, ...],
) -> EffectiveCapabilities:
    context_valid = _context_valid_value(evidence)
    if mode == "paired_reference":
        paired = bool(queued.paired_harmonic_attribution and context_valid is True)
        return EffectiveCapabilities(
            clipping=True,
            absolute_harmonic_description=True,
            nominal_harmonic_attribution=queued.nominal_harmonic_attribution,
            paired_harmonic_attribution=paired,
        )
    if mode == "nominal_single_tone":
        nominal = bool(
            queued.nominal_harmonic_attribution and context_valid is not False
        )
        return EffectiveCapabilities(
            clipping=True,
            absolute_harmonic_description=True,
            nominal_harmonic_attribution=nominal,
            paired_harmonic_attribution=False,
        )
    return EffectiveCapabilities(
        clipping=True,
        absolute_harmonic_description=True,
        nominal_harmonic_attribution=False,
        paired_harmonic_attribution=False,
    )


class DiagnosisApplicationService:
    def __init__(
        self,
        dependencies: ApplicationDependencies,
        *,
        clock: Callable[[], datetime] | None = None,
        store: InMemoryRunStore | None = None,
        executor: BoundedRunExecutor | None = None,
        contextual_store: InMemoryContextualRunStore | None = None,
        contextual_executor: BoundedContextualRunExecutor | None = None,
    ) -> None:
        self._dependencies = dependencies
        self._clock = clock or _utc_now
        self._store = store or InMemoryRunStore(cleanup=self._cleanup_owned_signals)
        self._executor = executor or BoundedRunExecutor(self._store, clock=self._clock)
        self._contextual_store = contextual_store or InMemoryContextualRunStore(
            cleanup=self._cleanup_owned_signals
        )
        self._contextual_executor = contextual_executor or BoundedContextualRunExecutor(
            self._contextual_store,
            clock=self._clock,
        )

    async def submit_wav(
        self,
        data: bytes,
        *,
        filename: str | None,
        user_request: str,
        channel: ChannelMode = "mixdown",
    ) -> RunSubmission:
        return await self._submit(
            user_request=user_request,
            channel=channel,
            source_builder=lambda: self._load_wav_source(data, filename=filename),
        )

    async def submit_synthetic(
        self,
        preset_id: DemoPresetId,
        *,
        user_request: str,
        channel: ChannelMode = "mixdown",
    ) -> RunSubmission:
        return await self._submit(
            user_request=user_request,
            channel=channel,
            source_builder=lambda: self._load_synthetic_source(preset_id),
        )

    def list_presets(self) -> tuple[DemoPresetDescriptor, ...]:
        return list_demo_presets()

    def render_preset_wav(self, preset_id: DemoPresetId) -> bytes:
        return render_demo_preset_wav(preset_id)

    def get_run(self, run_id: str) -> AppRunSnapshot:
        return self._store.get(run_id)

    async def wait_for_terminal(
        self,
        run_id: str,
        *,
        timeout_s: float | None = None,
    ) -> AppRunSnapshot:
        waiter = self._store.wait_for_terminal(run_id)
        if timeout_s is None:
            return await waiter
        return await asyncio.wait_for(waiter, timeout=timeout_s)

    async def draft_intake_payload(self, payload: object) -> ContextDraft:
        if not isinstance(payload, dict):
            raise _invalid_request("malformed intake request")
        try:
            request = IntakeRequest.model_validate(payload)
        except (ValueError, TypeError) as error:
            raise _invalid_request("malformed intake request") from error
        return await self.draft_intake(request)

    async def draft_intake(self, request: IntakeRequest) -> ContextDraft:
        if not self._dependencies.planner_configured:
            raise PlannerNotConfiguredError(_planner_not_configured_detail())
        factory = self._dependencies.intake_planner_factory
        try:
            if factory is None:
                planner = intake_planner_from_diagnosis_planner(
                    self._dependencies.planner_factory()
                )
            else:
                planner = factory()
        except IntakeCredentialsError as error:
            raise PlannerNotConfiguredError(_planner_not_configured_detail()) from error
        return await planner.propose(request)

    async def submit_contextual_wav(
        self,
        test_data: bytes,
        *,
        test_filename: str | None,
        mode: Literal["single_signal", "nominal_single_tone", "paired_reference"],
        reference_data: bytes | None,
        reference_filename: str | None,
        nominal_fundamental_hz: float | None,
        stimulus_kind: Literal["single_tone"] | None,
        user_request: str,
        channel: ChannelMode = "mixdown",
        context_origin: Literal["intake_confirmed"] | None = None,
    ) -> ContextualRunSubmission:
        if not self._dependencies.planner_configured:
            raise PlannerNotConfiguredError(_planner_not_configured_detail())
        question = _normalize_question(user_request)
        if mode == "single_signal":
            if reference_data is not None or reference_filename is not None:
                raise _invalid_request("single_signal rejects a reference WAV")
            if stimulus_kind is not None or nominal_fundamental_hz is not None:
                raise _invalid_request(
                    "single_signal rejects nominal stimulus fields"
                )
        elif mode == "nominal_single_tone":
            if reference_data is not None or reference_filename is not None:
                raise _invalid_request(
                    "nominal_single_tone rejects a reference WAV"
                )
            if stimulus_kind != "single_tone":
                raise _invalid_request(
                    "nominal_single_tone requires stimulus_kind=single_tone"
                )
            if nominal_fundamental_hz is None:
                raise _invalid_request(
                    "nominal_single_tone requires nominal_fundamental_hz"
                )
        else:
            if reference_data is None:
                raise _invalid_request("paired_reference requires a reference WAV")
            if stimulus_kind == "single_tone" and nominal_fundamental_hz is None:
                raise _invalid_request(
                    "paired_reference with stimulus_kind=single_tone requires "
                    "nominal_fundamental_hz"
                )

        test_source_record, test_source_summary = self._load_wav_source(
            test_data, filename=test_filename
        )
        reference_source_record: SignalRecord | None = None
        reference_source_summary: SourceSummary | None = None
        if mode == "paired_reference":
            assert reference_data is not None
            reference_source_record, reference_source_summary = self._load_wav_source(
                reference_data, filename=reference_filename
            )

        try:
            test_selected = extract_segment(test_source_record, channel=channel)
        except UnsupportedChannelError as error:
            raise _invalid_request(str(error)) from error
        test_analysis_record = build_signal_record(
            test_selected,
            sample_rate_hz=test_source_record.meta.sample_rate_hz,
            source_type=test_source_record.meta.source_type,
            filename=test_source_record.meta.filename,
        )
        test_preview = build_waveform_preview(
            test_selected,
            sample_rate_hz=test_analysis_record.meta.sample_rate_hz,
        )

        reference_analysis_record: SignalRecord | None = None
        if reference_source_record is not None:
            try:
                reference_selected = extract_segment(
                    reference_source_record, channel=channel
                )
            except UnsupportedChannelError as error:
                raise _invalid_request(str(error)) from error
            reference_analysis_record = build_signal_record(
                reference_selected,
                sample_rate_hz=reference_source_record.meta.sample_rate_hz,
                source_type=reference_source_record.meta.source_type,
                filename=reference_source_record.meta.filename,
            )

        test_analysis_id = test_analysis_record.meta.signal_id
        reference_analysis_id = (
            reference_analysis_record.meta.signal_id
            if reference_analysis_record is not None
            else None
        )
        stimulus_context = StimulusContext(
            mode=mode,
            test_signal_id=test_analysis_id,
            reference_signal_id=reference_analysis_id,
            nominal_fundamental_hz=nominal_fundamental_hz,
            stimulus_kind=stimulus_kind,
            assertion_source="user_supplied",
        )
        queued_caps = _queued_capabilities(mode)
        run_id = _new_run_id()
        snapshot = ContextualAppRunSnapshot(
            run_id=run_id,
            status="queued",
            created_at=self._clock(),
            user_request=question,
            analyzed_channel=channel,
            test_source=test_source_summary,
            reference_source=reference_source_summary,
            stimulus_context=stimulus_context,
            effective_capabilities=queued_caps,
            test_preview=test_preview,
            planner_identity=self._dependencies.planner_identity,
            context_origin=context_origin,
        )

        async def execute() -> ContextualRunExecutionResult:
            inner = self._dependencies.planner_factory()
            recorder = RecordingPlanner(inner)
            runtime = DistortionDiagnosisRuntime(
                repository=self._dependencies.repository,
                tool_service=GuardedSignalToolService(self._dependencies.repository),
                planner=recorder,
                rule_engine=self._dependencies.rule_engine,
                rule_profile_loader=self._dependencies.rule_profile_loader,
                knowledge_index=self._dependencies.knowledge_index,
                causal_policy_version=self._dependencies.causal_policy_version,
            )
            result = await runtime.run(
                signal_id=test_analysis_id,
                user_request=f"{question}\nAnalyzed channel: {channel}.",
                stimulus_context=stimulus_context,
            )
            events = assemble_agent_events(recorder.records, result)
            return ContextualRunExecutionResult(
                result=result,
                trace_events=project_agent_events(events),
                effective_capabilities=_terminal_capabilities(
                    mode=mode,
                    queued=queued_caps,
                    evidence=result.evidence,
                ),
            )

        repository = self._dependencies.repository
        inserted: list[str] = []
        owned: list[str] = []
        try:
            repository.put(test_source_record)
            inserted.append(test_source_record.meta.signal_id)
            owned.append(test_source_record.meta.signal_id)
            repository.put(test_analysis_record)
            inserted.append(test_analysis_id)
            owned.append(test_analysis_id)
            if reference_source_record is not None and reference_analysis_record is not None:
                repository.put(reference_source_record)
                inserted.append(reference_source_record.meta.signal_id)
                owned.append(reference_source_record.meta.signal_id)
                repository.put(reference_analysis_record)
                inserted.append(reference_analysis_id)  # type: ignore[arg-type]
                owned.append(reference_analysis_id)  # type: ignore[arg-type]
            await self._contextual_executor.submit(
                ContextualRunWorkItem(run_id=run_id, execute=execute),
                snapshot=snapshot,
                owned_signal_ids=tuple(owned),
            )
        except Exception:
            for signal_id in inserted:
                if repository.exists(signal_id):
                    repository.remove(signal_id)
            raise
        return ContextualRunSubmission(run_id=run_id, status="queued")

    def get_contextual_run(self, run_id: str) -> ContextualAppRunSnapshot:
        return self._contextual_store.get(run_id)

    async def wait_for_contextual_terminal(
        self,
        run_id: str,
        *,
        timeout_s: float | None = None,
    ) -> ContextualAppRunSnapshot:
        waiter = self._contextual_store.wait_for_terminal(run_id)
        if timeout_s is None:
            return await waiter
        return await asyncio.wait_for(waiter, timeout=timeout_s)

    async def aclose(self) -> None:
        await self._executor.aclose()
        await self._contextual_executor.aclose()

    def _cleanup_owned_signals(self, signal_ids: tuple[str, ...]) -> None:
        repository = self._dependencies.repository
        for signal_id in signal_ids:
            if repository.exists(signal_id):
                repository.remove(signal_id)

    def _load_wav_source(
        self,
        data: bytes,
        *,
        filename: str | None,
    ) -> tuple[SignalRecord, SourceSummary]:
        try:
            loaded = load_wav_bytes(data, filename=filename)
        except UnsupportedWavError as error:
            raise ApplicationError(
                AppErrorDetail(code="unsupported_wav", message=str(error))
            ) from error
        except InvalidWavError as error:
            raise ApplicationError(
                AppErrorDetail(code="invalid_wav", message=str(error))
            ) from error
        except SignalLimitExceededError as error:
            raise ApplicationError(
                AppErrorDetail(code="signal_limit_exceeded", message=str(error))
            ) from error
        display_name = loaded.source_info.filename or _DEFAULT_WAV_DISPLAY_NAME
        summary = SourceSummary(
            source_kind="wav",
            display_name=display_name,
            sample_rate_hz=loaded.source_info.sample_rate_hz,
            channels=loaded.source_info.channels,
            num_frames=loaded.source_info.num_frames,
            duration_s=loaded.source_info.duration_s,
            bits_per_sample=loaded.source_info.bits_per_sample,
        )
        return loaded.record, summary

    def _load_synthetic_source(
        self,
        preset_id: DemoPresetId,
    ) -> tuple[SignalRecord, SourceSummary]:
        record = build_demo_preset(preset_id)
        summary = SourceSummary(
            source_kind="synthetic",
            display_name=preset_id,
            sample_rate_hz=record.meta.sample_rate_hz,
            channels=_as_source_channels(record.meta.channels),
            num_frames=record.meta.num_samples,
            duration_s=record.meta.duration_s,
            preset_id=preset_id,
        )
        return record, summary

    async def _submit(
        self,
        *,
        user_request: str,
        channel: ChannelMode,
        source_builder: Callable[[], tuple[SignalRecord, SourceSummary]],
    ) -> RunSubmission:
        if not self._dependencies.planner_configured:
            raise PlannerNotConfiguredError(_planner_not_configured_detail())
        question = _normalize_question(user_request)
        source_record, source_summary = source_builder()
        try:
            selected = extract_segment(source_record, channel=channel)
        except UnsupportedChannelError as error:
            raise _invalid_request(str(error)) from error
        analysis_record = build_signal_record(
            selected,
            sample_rate_hz=source_record.meta.sample_rate_hz,
            source_type=source_record.meta.source_type,
            filename=source_record.meta.filename,
        )
        preview = build_waveform_preview(
            selected, sample_rate_hz=analysis_record.meta.sample_rate_hz
        )
        run_id = _new_run_id()
        snapshot = AppRunSnapshot(
            run_id=run_id,
            status="queued",
            created_at=self._clock(),
            user_request=question,
            analyzed_channel=channel,
            source=source_summary,
            planner_identity=self._dependencies.planner_identity,
            waveform_preview=preview,
        )
        analysis_id = analysis_record.meta.signal_id
        source_id = source_record.meta.signal_id

        async def execute() -> RunExecutionResult:
            inner = self._dependencies.planner_factory()
            recorder = RecordingPlanner(inner)
            runtime = DistortionDiagnosisRuntime(
                repository=self._dependencies.repository,
                tool_service=GuardedSignalToolService(self._dependencies.repository),
                planner=recorder,
                rule_engine=self._dependencies.rule_engine,
                rule_profile_loader=self._dependencies.rule_profile_loader,
                knowledge_index=self._dependencies.knowledge_index,
                causal_policy_version=self._dependencies.causal_policy_version,
            )
            result = await runtime.run(
                signal_id=analysis_id,
                user_request=f"{question}\nAnalyzed channel: {channel}.",
            )
            events = assemble_agent_events(recorder.records, result)
            return RunExecutionResult(
                result=result,
                trace_events=project_agent_events(events),
            )

        repository = self._dependencies.repository
        inserted: list[str] = []
        try:
            repository.put(source_record)
            inserted.append(source_id)
            repository.put(analysis_record)
            inserted.append(analysis_id)
            await self._executor.submit(
                RunWorkItem(run_id=run_id, execute=execute),
                snapshot=snapshot,
                owned_signal_ids=(source_id, analysis_id),
            )
        except Exception:
            for signal_id in inserted:
                if repository.exists(signal_id):
                    repository.remove(signal_id)
            raise
        return RunSubmission(run_id=run_id, status="queued")
