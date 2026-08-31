"""Checkpoint X — shared application service and composition (T246–T252)."""

from __future__ import annotations

import ast
import json
import re
import struct
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.agent.models import (
    AgentDecision,
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
from signal_diag.agent.planner import (
    DEFAULT_DEEPSEEK_MODEL,
    PROMPT_VERSION,
    RealLLMPlanner,
    ScriptedPlanner,
    _build_user_message,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.app import DiagnosisApplicationService, build_product_service
from signal_diag.app.errors import (
    AppCapacityError,
    InvalidRequestError,
    PlannerNotConfiguredError,
    RunNotFoundError,
    UnknownPresetError,
)
from signal_diag.app.models import DemoPresetId, PlannerIdentity
from signal_diag.app.presets import list_demo_presets
from signal_diag.app.service import ApplicationDependencies
from signal_diag.evaluation.recording import RecordingPlanner
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import (
    InMemorySignalRepository,
    extract_segment,
    generate_clipped_sine,
)
from signal_diag.tools.service import SignalToolService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
SERVICE_PATH = PROJECT_ROOT / "src" / "signal_diag" / "app" / "service.py"
COMPOSITION_PATH = PROJECT_ROOT / "src" / "signal_diag" / "app" / "composition.py"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
QUESTION = "Why does this signal sound distorted?"
PRESET_IDS: tuple[DemoPresetId, ...] = (
    "clean_periodic",
    "clipping",
    "harmonic_distortion",
    "combined_distortion",
    "noise_inconclusive",
)
RUN_ID_RE = r"^run_[0-9a-f]{32}$"
SIGNAL_ID_RE = r"^sig_[0-9a-f]{32}$"
FORBIDDEN_PLANNER_TOKENS = (
    "preset_id",
    "combined_distortion",
    "fault_labels",
    "ground_truth",
    "acceptable_first_tools",
    "target_status",
    "samples",
    "waveform",
)
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_FINISH_DECISION = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("deterministic test finish without additional tools",),
)
_FINISH_JSON = json.dumps(
    {
        "decision_type": "finish",
        "task_assessment": {
            "task_type": "distortion_analysis",
            "objective": "determine why the signal sounds distorted",
            "hypotheses": ["clipping", "harmonic_distortion"],
        },
        "outcome": "inconclusive",
        "claims": [],
        "confidence_label": "low",
        "limitations": ["deterministic test finish without additional tools"],
    }
)


def _riff_wave(*, fmt_payload: bytes, data: bytes, extra: tuple[bytes, ...] = ()) -> bytes:
    chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
    chunks.extend(extra)
    chunks.append(b"data" + struct.pack("<I", len(data)) + data)
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * bits // 8
    return struct.pack(
        "<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits
    )


def _mono_extrema_wav(*, rate: int = 8_000) -> bytes:
    pcm = struct.pack("<hhh", -32768, 0, 32767)
    return _riff_wave(fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16), data=pcm)


def _stereo_distinct_wav(*, rate: int = 8_000) -> bytes:
    pcm = struct.pack("<6h", 32767, -8192, 0, 16384, -32768, 4096)
    return _riff_wave(fmt_payload=_pcm_fmt(channels=2, rate=rate, bits=16), data=pcm)


def _clipped_sine_wav() -> bytes:
    case = generate_clipped_sine(
        frequency_hz=220.0,
        sample_rate_hz=8_000,
        duration_s=0.25,
        amplitude=1.2,
        clip_level=0.65,
    )
    pcm = np.clip(
        np.rint(case.record.samples[:, 0] * 32767.0),
        -32768,
        32767,
    ).astype("<i2")
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16),
        data=pcm.tobytes(),
    )


def _identity(
    *,
    model: str = DEFAULT_DEEPSEEK_MODEL,
    certified: bool = True,
) -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model=model,
        prompt_version=PROMPT_VERSION,
        phase4_certified_default=certified,
    )


def _json_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for nested in value.values():
            keys.update(_json_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_json_keys(item))
    return keys


class _ImmediateFinishPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        return _FINISH_DECISION


class _S1RoutePlanner:
    def __init__(self) -> None:
        self._index = 0

    async def decide(self, context: PlannerContext) -> AgentDecision:
        steps: list[AgentDecision] = [
            CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
                task_assessment=_ASSESSMENT,
            ),
            CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="collect harmonic evidence",
            ),
            EvaluateRulesDecision(
                profile_id="profile_s1_distortion",
                evidence_refs=(),
                purpose="apply configured S1 demonstration limits",
            ),
            RetrieveKnowledgeDecision(
                query_text="clipping harmonic distortion inconclusive",
                tags=("clipping", "harmonic-distortion", "inconclusive"),
                purpose="explain observed distortion findings",
            ),
        ]
        if self._index < len(steps):
            decision = steps[self._index]
            self._index += 1
            return decision
        evidence_ids = tuple(item.evidence_id for item in context.evidence)
        rule_ids = tuple(
            evaluation.evaluation_id
            for batch in context.rule_evaluation_batches
            for evaluation in batch.evaluations
        )
        knowledge_ids = tuple(item.retrieval_id for item in context.knowledge_retrievals)
        return FinishDecision(
            task_assessment=_ASSESSMENT,
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_service",
                    fault_type="inconclusive",
                    statement="Service-path finish cites same-run artifacts.",
                    evidence_refs=evidence_ids,
                    rule_refs=rule_ids,
                    knowledge_refs=knowledge_ids,
                ),
            ),
            confidence_label="low",
            limitations=("Deterministic service-path finish.",),
        )


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _CapturingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse([_FakeChoice(_FakeMessage(_FINISH_JSON))])


@dataclass
class _FakeChat:
    completions: _CapturingCompletions


@dataclass
class _FakeClient:
    chat: _FakeChat


def _finish_factory() -> Any:
    return _ImmediateFinishPlanner()


def _s1_factory() -> Any:
    return _S1RoutePlanner()


def _make_service(
    planner_factory: Any,
    *,
    repository: InMemorySignalRepository | None = None,
    planner_configured: bool = True,
    planner_identity: PlannerIdentity | None = None,
) -> DiagnosisApplicationService:
    repo = repository or InMemorySignalRepository()
    dependencies = ApplicationDependencies(
        repository=repo,
        planner_factory=planner_factory,
        planner_identity=planner_identity or _identity(),
        planner_configured=planner_configured,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    return DiagnosisApplicationService(dependencies, clock=lambda: NOW)


@pytest.fixture
async def finish_service() -> AsyncIterator[DiagnosisApplicationService]:
    service = _make_service(_finish_factory)
    try:
        yield service
    finally:
        await service.aclose()


def _assert_same_run_refs(snapshot: Any) -> None:
    result = snapshot.result
    assert result is not None
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


def _owned_ids(service: DiagnosisApplicationService, run_id: str) -> tuple[str, ...]:
    return service._store._owned_signal_ids[run_id]


@pytest.mark.asyncio
async def test_t246_wav_submission_registers_preview_and_executes(
    finish_service: DiagnosisApplicationService,
) -> None:
    wav = _mono_extrema_wav()
    submission = await finish_service.submit_wav(
        wav,
        filename=r"..\uploads\demo.wav",
        user_request=QUESTION,
        channel="mixdown",
    )
    assert submission.status == "queued"
    assert re.fullmatch(RUN_ID_RE, submission.run_id)
    queued = finish_service.get_run(submission.run_id)
    assert queued.status == "queued"
    assert queued.source.source_kind == "wav"
    assert queued.source.display_name == "demo.wav"
    assert queued.source.sample_rate_hz == 8_000
    assert queued.source.channels == 1
    assert queued.source.num_frames == 3
    assert queued.source.bits_per_sample == 16
    assert queued.source.preset_id is None
    assert queued.user_request == QUESTION
    assert queued.analyzed_channel == "mixdown"
    assert queued.waveform_preview.original_num_samples == 3
    assert queued.planner_identity == _identity()
    owned = _owned_ids(finish_service, submission.run_id)
    assert len(owned) == 2
    source_id, analysis_id = owned
    repository = finish_service._dependencies.repository
    source = repository.get(source_id)
    analysis = repository.get(analysis_id)
    assert source.meta.channels == 1
    assert analysis.meta.channels == 1
    assert source.meta.signal_id != analysis.meta.signal_id
    np.testing.assert_array_equal(
        analysis.samples[:, 0],
        extract_segment(source, channel="mixdown"),
    )
    terminal = await finish_service.wait_for_terminal(submission.run_id)
    assert terminal.status == "completed"
    assert terminal.result is not None
    assert terminal.application_error is None
    assert terminal.trace_events
    assert terminal.result.run_id.startswith("run_")
    fetched = finish_service.get_run(submission.run_id)
    assert fetched.status == "completed"
    assert fetched.run_id == submission.run_id


@pytest.mark.asyncio
async def test_t246_capacity_failure_removes_both_signal_ids() -> None:
    gate = __import__("asyncio").Event()
    started = __import__("asyncio").Event()

    class GatedPlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            started.set()
            await gate.wait()
            return _FINISH_DECISION

    repository = InMemorySignalRepository()
    service = _make_service(lambda: GatedPlanner(), repository=repository)
    try:
        await service.submit_wav(
            _mono_extrema_wav(),
            filename="first.wav",
            user_request=QUESTION,
        )
        await started.wait()
        queued = []
        for index in range(4):
            queued.append(
                await service.submit_wav(
                    _mono_extrema_wav(),
                    filename=f"q{index}.wav",
                    user_request=QUESTION,
                )
            )
        before = {item.signal_id for item in repository.list_meta()}
        assert len(before) == 10
        with pytest.raises(AppCapacityError) as exc:
            await service.submit_wav(
                _mono_extrema_wav(),
                filename="overflow.wav",
                user_request=QUESTION,
            )
        assert exc.value.detail.code == "capacity_exceeded"
        after = {item.signal_id for item in repository.list_meta()}
        assert after == before
        assert "overflow" not in " ".join(
            meta.filename or "" for meta in repository.list_meta()
        )
    finally:
        gate.set()
        await service.aclose()


@pytest.mark.asyncio
async def test_t247_every_preset_uses_same_registration_shape(
    finish_service: DiagnosisApplicationService,
) -> None:
    assert finish_service.list_presets() == list_demo_presets()
    for preset_id in PRESET_IDS:
        submission = await finish_service.submit_synthetic(
            preset_id,
            user_request=QUESTION,
            channel="mixdown",
        )
        queued = finish_service.get_run(submission.run_id)
        assert queued.status == "queued"
        assert queued.source.source_kind == "synthetic"
        assert queued.source.preset_id == preset_id
        assert queued.source.bits_per_sample is None
        assert queued.source.channels == 1
        assert queued.source.display_name == preset_id
        owned = _owned_ids(finish_service, submission.run_id)
        assert len(owned) == 2
        terminal = await finish_service.wait_for_terminal(submission.run_id)
        assert terminal.status == "completed"
        assert terminal.result is not None
        assert terminal.waveform_preview.points
        assert terminal.planner_identity.provider == "deepseek"
    with pytest.raises(UnknownPresetError) as unknown:
        await finish_service.submit_synthetic(
            "missing_preset",  # type: ignore[arg-type]
            user_request=QUESTION,
        )
    assert unknown.value.detail.code == "unknown_preset"


@pytest.mark.asyncio
async def test_t248_channel_realization_and_mono_right_rejection(
    finish_service: DiagnosisApplicationService,
) -> None:
    repository = finish_service._dependencies.repository
    mono = await finish_service.submit_wav(
        _mono_extrema_wav(),
        filename="mono.wav",
        user_request=QUESTION,
        channel="left",
    )
    mono_terminal = await finish_service.wait_for_terminal(mono.run_id)
    assert mono_terminal.analyzed_channel == "left"
    mono_source = repository.get(_owned_ids(finish_service, mono.run_id)[0])
    mono_analysis = repository.get(_owned_ids(finish_service, mono.run_id)[1])
    assert mono_analysis.meta.channels == 1
    np.testing.assert_array_equal(
        mono_analysis.samples[:, 0],
        extract_segment(mono_source, channel="left"),
    )

    before_right = {item.signal_id for item in repository.list_meta()}
    with pytest.raises(InvalidRequestError) as rejected:
        await finish_service.submit_wav(
            _mono_extrema_wav(),
            filename="mono-right.wav",
            user_request=QUESTION,
            channel="right",
        )
    assert rejected.value.detail.code == "invalid_request"
    assert {item.signal_id for item in repository.list_meta()} == before_right

    stereo = _stereo_distinct_wav()
    for channel in ("left", "right", "mixdown"):
        submission = await finish_service.submit_wav(
            stereo,
            filename="stereo.wav",
            user_request=QUESTION,
            channel=channel,
        )
        terminal = await finish_service.wait_for_terminal(submission.run_id)
        assert terminal.analyzed_channel == channel
        source_id, analysis_id = _owned_ids(finish_service, submission.run_id)
        source = repository.get(source_id)
        analysis = repository.get(analysis_id)
        assert source.meta.channels == 2
        assert analysis.meta.channels == 1
        np.testing.assert_allclose(
            analysis.samples[:, 0],
            extract_segment(source, channel=channel),
            rtol=0.0,
            atol=0.0,
        )


@pytest.mark.asyncio
async def test_t249_request_integrity_and_forbidden_planner_payload() -> None:
    completions = _CapturingCompletions()

    def factory() -> RealLLMPlanner:
        return RealLLMPlanner(
            provider="deepseek",
            api_key="sk-test",
            base_url="https://example.invalid",
            model=DEFAULT_DEEPSEEK_MODEL,
            client=_FakeClient(_FakeChat(completions)),
        )

    service = _make_service(factory)
    try:
        with pytest.raises(InvalidRequestError) as empty:
            await service.submit_synthetic(
                "clipping",
                user_request="   ",
            )
        assert empty.value.detail.code == "invalid_request"
        with pytest.raises(InvalidRequestError) as too_long:
            await service.submit_synthetic(
                "clipping",
                user_request="x" * 2001,
            )
        assert too_long.value.detail.code == "invalid_request"
        padded = f"  {QUESTION}  "
        trimmed = await service.submit_synthetic(
            "clipping",
            user_request=padded,
            channel="left",
        )
        queued = service.get_run(trimmed.run_id)
        assert queued.user_request == QUESTION
        assert "Analyzed channel" not in queued.user_request
        limit = await service.submit_synthetic(
            "combined_distortion",
            user_request="y" * 2000,
            channel="mixdown",
        )
        assert service.get_run(limit.run_id).user_request == "y" * 2000
        await service.wait_for_terminal(trimmed.run_id)
        await service.wait_for_terminal(limit.run_id)
        assert completions.calls
        content = completions.calls[-1]["messages"][1]["content"]
        received_context = PlannerContext.model_validate(
            json.loads(content)["planner_context"]
        )
        serialized = _build_user_message(
            received_context, prompt_version=PROMPT_VERSION
        )
        forbidden = (
            "preset_id",
            "combined_distortion",
            "fault_labels",
            "ground_truth",
            "acceptable_first_tools",
            "target_status",
            "samples",
            "waveform",
        )
        keys = _json_keys(json.loads(serialized))
        assert all(item not in keys for item in forbidden)
        assert all(
            item not in serialized
            for item in forbidden
            if item not in {"samples", "waveform"}
        )
        assert received_context.user_request.startswith("y" * 2000)
        assert received_context.user_request.endswith("Analyzed channel: mixdown.")
        assert "combined_distortion" not in received_context.user_request
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t250_each_run_gets_fresh_planner_runtime_and_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planners: list[object] = []
    runtimes: list[object] = []
    recorders: list[object] = []
    tools: list[object] = []
    original_runtime = DistortionDiagnosisRuntime.__init__
    original_recorder = RecordingPlanner.__init__
    original_tools = SignalToolService.__init__

    def tracking_runtime(self: DistortionDiagnosisRuntime, **kwargs: Any) -> None:
        runtimes.append(self)
        original_runtime(self, **kwargs)

    def tracking_recorder(
        self: RecordingPlanner,
        planner: Any,
        **kwargs: Any,
    ) -> None:
        recorders.append(self)
        original_recorder(self, planner, **kwargs)

    def tracking_tools(self: SignalToolService, *args: Any, **kwargs: Any) -> None:
        tools.append(self)
        original_tools(self, *args, **kwargs)

    monkeypatch.setattr(DistortionDiagnosisRuntime, "__init__", tracking_runtime)
    monkeypatch.setattr(RecordingPlanner, "__init__", tracking_recorder)
    monkeypatch.setattr(SignalToolService, "__init__", tracking_tools)

    def factory() -> _ImmediateFinishPlanner:
        planner = _ImmediateFinishPlanner()
        planners.append(planner)
        return planner

    service = _make_service(factory)
    try:
        first = await service.submit_synthetic("clipping", user_request=QUESTION)
        second = await service.submit_synthetic("noise_inconclusive", user_request=QUESTION)
        first_done = await service.wait_for_terminal(first.run_id)
        second_done = await service.wait_for_terminal(second.run_id)
        assert first_done.status == "completed"
        assert second_done.status == "completed"
        assert first_done.run_id != second_done.run_id
        assert first_done.result is not None
        assert second_done.result is not None
        assert first_done.result.run_id != second_done.result.run_id
        first_obs = {item.observation_id for item in first_done.result.observations}
        second_obs = {item.observation_id for item in second_done.result.observations}
        assert first_obs.isdisjoint(second_obs)
        assert len(planners) == 2
        assert planners[0] is not planners[1]
        assert len(runtimes) == 2
        assert runtimes[0] is not runtimes[1]
        assert len(recorders) == 2
        assert recorders[0] is not recorders[1]
        assert len(tools) == 2
        assert tools[0] is not tools[1]
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t251_product_defaults_and_missing_credentials_before_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-secret-should-not-be-read")
    monkeypatch.setenv("DEEPSEEK_MODEL", "process-model-should-not-be-read")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://process.example.invalid")
    empty = build_product_service(environ={})
    configured = None
    defaults = None
    try:
        assert empty._dependencies.planner_configured is False
        assert empty._dependencies.planner_identity.provider == "deepseek"
        assert empty._dependencies.planner_identity.model == DEFAULT_DEEPSEEK_MODEL
        assert empty._dependencies.planner_identity.prompt_version == PROMPT_VERSION
        assert empty._dependencies.planner_identity.phase4_certified_default is True
        repository = empty._dependencies.repository
        with pytest.raises(PlannerNotConfiguredError) as exc:
            await empty.submit_wav(
                _mono_extrema_wav(),
                filename="denied.wav",
                user_request=QUESTION,
            )
        assert exc.value.detail.code == "planner_not_configured"
        assert "ScriptedPlanner" in exc.value.detail.message
        assert repository.list_meta() == []
        with pytest.raises(RunNotFoundError):
            empty.get_run("run_" + "0" * 32)
        source = COMPOSITION_PATH.read_text(encoding="utf-8")
        assert "ScriptedPlanner" not in source
        assert "fastapi" not in source.lower()
        tree = ast.parse(source, filename=str(COMPOSITION_PATH))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                assert name != "ScriptedPlanner"
        configured = build_product_service(
            environ={
                "DEEPSEEK_API_KEY": "sk-test",
                "DEEPSEEK_MODEL": "deepseek-not-certified",
                "DEEPSEEK_BASE_URL": "https://example.invalid",
            }
        )
        identity = configured._dependencies.planner_identity
        assert configured._dependencies.planner_configured is True
        assert identity.model == "deepseek-not-certified"
        assert identity.phase4_certified_default is False
        planner = configured._dependencies.planner_factory()
        assert isinstance(planner, RealLLMPlanner)
        assert not isinstance(planner, ScriptedPlanner)
        defaults = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
        assert defaults._dependencies.planner_identity.model == DEFAULT_DEEPSEEK_MODEL
        assert defaults._dependencies.planner_identity.prompt_version == (
            "v0.2-s1-planner-8.1"
        )
        assert defaults._dependencies.planner_identity.phase4_certified_default is True
        service_source = SERVICE_PATH.read_text(encoding="utf-8")
        assert "fastapi" not in service_source.lower()
        service_tree = ast.parse(service_source, filename=str(SERVICE_PATH))
        for node in ast.walk(service_tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != "ScriptedPlanner"
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                assert name != "ScriptedPlanner"
    finally:
        await empty.aclose()
        if configured is not None:
            await configured.aclose()
        if defaults is not None:
            await defaults.aclose()


@pytest.mark.asyncio
async def test_t251_unconfigured_synthetic_does_not_insert_or_reserve() -> None:
    repository = InMemorySignalRepository()
    service = _make_service(
        _finish_factory,
        repository=repository,
        planner_configured=False,
    )
    try:
        with pytest.raises(PlannerNotConfiguredError):
            await service.submit_synthetic("clipping", user_request=QUESTION)
        assert repository.list_meta() == []
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t252_representative_wav_clipping_and_synthetic_noise_paths() -> None:
    service = _make_service(_s1_factory)
    try:
        wav_submission = await service.submit_wav(
            _clipped_sine_wav(),
            filename="clipping.wav",
            user_request=QUESTION,
            channel="mixdown",
        )
        wav_done = await service.wait_for_terminal(wav_submission.run_id)
        assert wav_done.status == "completed"
        assert wav_done.result is not None
        assert wav_done.result.evidence
        assert wav_done.result.rule_evaluation_batches
        assert wav_done.result.knowledge_retrievals
        _assert_same_run_refs(wav_done)
        assert wav_done.trace_events
        noise_submission = await service.submit_synthetic(
            "noise_inconclusive",
            user_request=QUESTION,
            channel="mixdown",
        )
        noise_done = await service.wait_for_terminal(noise_submission.run_id)
        assert noise_done.status == "completed"
        assert noise_done.result is not None
        assert noise_done.result.evidence
        assert noise_done.result.rule_evaluation_batches
        assert noise_done.result.knowledge_retrievals
        _assert_same_run_refs(noise_done)
        assert noise_done.trace_events
        kinds = {event.kind for event in noise_done.trace_events}
        assert {"planner", "observation", "rule", "knowledge"} <= kinds
    finally:
        await service.aclose()
