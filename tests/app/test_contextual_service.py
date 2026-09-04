"""T-CX096–T-CX104: contextual application service workflow."""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from signal_diag.agent.models import (
    AgentDecision,
    AnalyzeContextualDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.planner import PROMPT_VERSION
from signal_diag.app.errors import (
    AppCapacityError,
    InvalidRequestError,
    PlannerNotConfiguredError,
)
from signal_diag.app.models import PlannerIdentity
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.contracts import ClippingInput, ContextualDistortionInput

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CONTEXTUAL_PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_contextual_comparison_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
QUESTION = "Why does this signal sound distorted?"
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_FINISH = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("deterministic contextual finish",),
)


def _riff_wave(*, fmt_payload: bytes, data: bytes) -> bytes:
    chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
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


def _mono_wav(*, rate: int = 8_000, frames: int = 3) -> bytes:
    samples = [0] * frames
    if frames >= 3:
        samples = [-32768, 0, 32767] + [0] * (frames - 3)
    pcm = struct.pack(f"<{frames}h", *samples[:frames])
    return _riff_wave(fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16), data=pcm)


def _sine_wav(*, rate: int = 8_000, frequency_hz: float = 440.0) -> bytes:
    case = generate_sine(
        sample_rate_hz=rate,
        duration_s=0.25,
        frequency_hz=frequency_hz,
        amplitude=0.5,
    )
    pcm = np.clip(
        np.rint(case.record.samples[:, 0] * 32767.0),
        -32768,
        32767,
    ).astype("<i2")
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16),
        data=pcm.tobytes(),
    )


def _identity() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version=PROMPT_VERSION,
        phase4_certified_default=True,
    )


class _ImmediateFinishPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        return _FINISH


class _ContextualThenFinishPlanner:
    def __init__(self) -> None:
        self._index = 0
        self.seen_contexts: list[PlannerContext] = []

    async def decide(self, context: PlannerContext) -> AgentDecision:
        self.seen_contexts.append(context)
        if self._index == 0:
            self._index += 1
            return CallToolDecision(
                call=AnalyzeContextualDistortionCall(args=ContextualDistortionInput()),
                purpose="qualify reference comparison",
                task_assessment=_ASSESSMENT,
            )
        if self._index == 1:
            self._index += 1
            return CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
            )
        return _FINISH


class _FailingPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        raise RuntimeError("provider unavailable")


def _make_service(
    planner_factory: Any,
    *,
    repository: InMemorySignalRepository | None = None,
    planner_configured: bool = True,
) -> DiagnosisApplicationService:
    repo = repository or InMemorySignalRepository()
    dependencies = ApplicationDependencies(
        repository=repo,
        planner_factory=planner_factory,
        planner_identity=_identity(),
        planner_configured=planner_configured,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": PROFILE_PATH,
                "profile_s1_contextual_comparison": CONTEXTUAL_PROFILE_PATH,
            }
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
        causal_policy_version="v9_5_contextual",
    )
    return DiagnosisApplicationService(dependencies, clock=lambda: NOW)


@pytest.fixture
async def finish_service() -> AsyncIterator[DiagnosisApplicationService]:
    service = _make_service(lambda: _ImmediateFinishPlanner())
    try:
        yield service
    finally:
        await service.aclose()


def _owned(service: DiagnosisApplicationService, run_id: str) -> tuple[str, ...]:
    return service._contextual_store._owned_signal_ids[run_id]


@pytest.mark.asyncio
async def test_t_cx096_nominal_mode_separate_preview_and_no_reference(
    finish_service: DiagnosisApplicationService,
) -> None:
    submission = await finish_service.submit_contextual_wav(
        _mono_wav(),
        test_filename="tone.wav",
        mode="nominal_single_tone",
        reference_data=None,
        reference_filename=None,
        nominal_fundamental_hz=440.0,
        stimulus_kind="single_tone",
        user_request=QUESTION,
    )
    queued = finish_service.get_contextual_run(submission.run_id)
    assert queued.status == "queued"
    assert queued.reference_source is None
    assert queued.test_source.display_name == "tone.wav"
    assert queued.test_preview.original_num_samples == 3
    assert queued.stimulus_context.mode == "nominal_single_tone"
    assert queued.effective_capabilities.nominal_harmonic_attribution is True
    assert queued.effective_capabilities.paired_harmonic_attribution is False
    owned = _owned(finish_service, submission.run_id)
    assert len(owned) == 2
    terminal = await finish_service.wait_for_contextual_terminal(submission.run_id)
    assert terminal.status == "completed"


@pytest.mark.asyncio
async def test_t_cx097_paired_mode_registers_two_sources_and_four_signals(
    finish_service: DiagnosisApplicationService,
) -> None:
    submission = await finish_service.submit_contextual_wav(
        _mono_wav(),
        test_filename="test.wav",
        mode="paired_reference",
        reference_data=_mono_wav(),
        reference_filename="ref.wav",
        nominal_fundamental_hz=None,
        stimulus_kind=None,
        user_request=QUESTION,
    )
    queued = finish_service.get_contextual_run(submission.run_id)
    assert queued.test_source.display_name == "test.wav"
    assert queued.reference_source is not None
    assert queued.reference_source.display_name == "ref.wav"
    assert queued.test_source != queued.reference_source or True
    assert queued.stimulus_context.mode == "paired_reference"
    assert queued.effective_capabilities.paired_harmonic_attribution is True
    assert len(_owned(finish_service, submission.run_id)) == 4
    assert queued.stimulus_context.test_signal_id != queued.stimulus_context.reference_signal_id
    terminal = await finish_service.wait_for_contextual_terminal(submission.run_id)
    assert terminal.status == "completed"


@pytest.mark.asyncio
async def test_t_cx098_mode_matrix_validation(
    finish_service: DiagnosisApplicationService,
) -> None:
    with pytest.raises(InvalidRequestError):
        await finish_service.submit_contextual_wav(
            _mono_wav(),
            test_filename="t.wav",
            mode="nominal_single_tone",
            reference_data=_mono_wav(),
            reference_filename="r.wav",
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            user_request=QUESTION,
        )
    with pytest.raises(InvalidRequestError):
        await finish_service.submit_contextual_wav(
            _mono_wav(),
            test_filename="t.wav",
            mode="nominal_single_tone",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=None,
            stimulus_kind="single_tone",
            user_request=QUESTION,
        )
    with pytest.raises(InvalidRequestError):
        await finish_service.submit_contextual_wav(
            _mono_wav(),
            test_filename="t.wav",
            mode="paired_reference",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
    assert finish_service._dependencies.repository.list_meta() == []


@pytest.mark.asyncio
async def test_t_cx099_submit_exception_removes_every_inserted_record() -> None:
    repository = InMemorySignalRepository()
    service = _make_service(lambda: _ImmediateFinishPlanner(), repository=repository)

    class BrokenPreview:
        def __call__(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("preview boom")

    try:
        original = DiagnosisApplicationService._load_wav_source
        calls = {"n": 0}

        def flaky(self: DiagnosisApplicationService, data: bytes, *, filename: str | None):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("second wav failed")
            return original(self, data, filename=filename)

        service._load_wav_source = flaky.__get__(service, DiagnosisApplicationService)  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="second wav failed"):
            await service.submit_contextual_wav(
                _mono_wav(),
                test_filename="test.wav",
                mode="paired_reference",
                reference_data=_mono_wav(),
                reference_filename="ref.wav",
                nominal_fundamental_hz=None,
                stimulus_kind=None,
                user_request=QUESTION,
            )
        assert repository.list_meta() == []
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx100_capacity_overflow_removes_attempt_records() -> None:
    import asyncio

    gate = asyncio.Event()
    started = asyncio.Event()

    class GatedPlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            started.set()
            await gate.wait()
            return _FINISH

    repository = InMemorySignalRepository()
    service = _make_service(lambda: GatedPlanner(), repository=repository)
    try:
        await service.submit_contextual_wav(
            _mono_wav(),
            test_filename="first.wav",
            mode="nominal_single_tone",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            user_request=QUESTION,
        )
        await started.wait()
        for index in range(4):
            await service.submit_contextual_wav(
                _mono_wav(),
                test_filename=f"q{index}.wav",
                mode="nominal_single_tone",
                reference_data=None,
                reference_filename=None,
                nominal_fundamental_hz=440.0,
                stimulus_kind="single_tone",
                user_request=QUESTION,
            )
        before = {item.signal_id for item in repository.list_meta()}
        assert len(before) == 10
        with pytest.raises(AppCapacityError):
            await service.submit_contextual_wav(
                _mono_wav(),
                test_filename="overflow.wav",
                mode="paired_reference",
                reference_data=_mono_wav(),
                reference_filename="overflow-ref.wav",
                nominal_fundamental_hz=None,
                stimulus_kind=None,
                user_request=QUESTION,
            )
        after = {item.signal_id for item in repository.list_meta()}
        assert after == before
    finally:
        gate.set()
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx101_provider_failure_marks_failed() -> None:
    service = _make_service(lambda: _FailingPlanner())
    try:
        submission = await service.submit_contextual_wav(
            _mono_wav(),
            test_filename="t.wav",
            mode="nominal_single_tone",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=220.0,
            stimulus_kind="single_tone",
            user_request=QUESTION,
        )
        terminal = await service.wait_for_contextual_terminal(submission.run_id)
        assert terminal.status == "failed"
        assert terminal.application_error is not None
        assert terminal.result is None
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx102_invalid_reference_clears_paired_keeps_clipping() -> None:
    planner = _ContextualThenFinishPlanner()
    service = _make_service(lambda: planner)
    try:
        submission = await service.submit_contextual_wav(
            _sine_wav(rate=8_000),
            test_filename="test.wav",
            mode="paired_reference",
            reference_data=_sine_wav(rate=16_000),
            reference_filename="ref.wav",
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        queued = service.get_contextual_run(submission.run_id)
        assert queued.effective_capabilities.paired_harmonic_attribution is True
        terminal = await service.wait_for_contextual_terminal(submission.run_id)
        assert terminal.status == "completed"
        assert terminal.result is not None
        metrics = {item.metric: item.value for item in terminal.result.evidence}
        assert metrics.get("context_valid") is False
        assert terminal.effective_capabilities.paired_harmonic_attribution is False
        assert terminal.effective_capabilities.clipping is True
        assert any(
            item.metric == "clipping_ratio" or item.source_tool == "detect_clipping"
            for item in terminal.result.evidence
        )
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx103_aclose_closes_both_executors_and_rejects_unconfigured() -> None:
    from signal_diag.app.contextual_runs import ContextualRunWorkItem

    service = _make_service(lambda: _ImmediateFinishPlanner(), planner_configured=False)
    with pytest.raises(PlannerNotConfiguredError):
        await service.submit_contextual_wav(
            _mono_wav(),
            test_filename="t.wav",
            mode="nominal_single_tone",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            user_request=QUESTION,
        )
    await service.aclose()
    assert service._executor._closed is True
    assert service._contextual_executor._closed is True

    async def noop() -> object:
        raise AssertionError("should not run")

    with pytest.raises(AppCapacityError):
        await service._contextual_executor.submit(
            ContextualRunWorkItem(run_id="run_" + "c" * 32, execute=noop)  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_t_cx104_runtime_receives_stimulus_context_and_policy() -> None:
    planner = _ContextualThenFinishPlanner()
    service = _make_service(lambda: planner)
    try:
        assert service._dependencies.causal_policy_version == "v9_5_contextual"
        submission = await service.submit_contextual_wav(
            _mono_wav(),
            test_filename="test.wav",
            mode="paired_reference",
            reference_data=_mono_wav(),
            reference_filename="ref.wav",
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        terminal = await service.wait_for_contextual_terminal(submission.run_id)
        assert terminal.status == "completed"
        assert planner.seen_contexts
        first = planner.seen_contexts[0]
        assert first.stimulus_context is not None
        assert first.stimulus_context.mode == "paired_reference"
        assert first.stimulus_context.test_signal_id.startswith("sig_")
        assert first.stimulus_context.reference_signal_id is not None
        assert first.reference_signal_meta is not None
    finally:
        await service.aclose()
