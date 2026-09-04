"""Shared diagnosis application service."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, runtime_checkable

from signal_diag.agent.planner import PlannerModel
from signal_diag.agent.diagnosis import CausalPolicyVersion
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
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
from signal_diag.app.presets import build_demo_preset, list_demo_presets
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
from signal_diag.tools.service import SignalToolService

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


class DiagnosisApplicationService:
    def __init__(
        self,
        dependencies: ApplicationDependencies,
        *,
        clock: Callable[[], datetime] | None = None,
        store: InMemoryRunStore | None = None,
        executor: BoundedRunExecutor | None = None,
    ) -> None:
        self._dependencies = dependencies
        self._clock = clock or _utc_now
        self._store = store or InMemoryRunStore(cleanup=self._cleanup_owned_signals)
        self._executor = executor or BoundedRunExecutor(self._store, clock=self._clock)

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

    async def aclose(self) -> None:
        await self._executor.aclose()

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
                tool_service=SignalToolService(self._dependencies.repository),
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
