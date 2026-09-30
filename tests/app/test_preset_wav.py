"""T-CX269–T-CX274: Demo preset WAV materialization and held-bytes upgrade."""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from signal_diag.agent.models import (
    AgentDecision,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.planner import PROMPT_VERSION
from signal_diag.app.api import create_app
from signal_diag.app.contextual_runs import InMemoryContextualRunStore
from signal_diag.app.errors import RunNotFoundError, UnknownPresetError
from signal_diag.app.models import AppErrorEnvelope, PlannerIdentity
from signal_diag.app.presets import build_demo_preset, render_demo_preset_wav
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository, load_wav_bytes
from signal_diag.tools.contracts import HarmonicDistortionInput
from signal_diag.tools.service import SignalToolService

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
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
QUESTION = "Why does this signal sound distorted?"
PRESET_IDS = (
    "clean_periodic",
    "clipping",
    "harmonic_distortion",
    "combined_distortion",
    "noise_inconclusive",
)
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
    limitations=("deterministic finish",),
)


def _identity() -> PlannerIdentity:
    return PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version=PROMPT_VERSION,
        phase4_certified_default=True,
    )


def _make_service(
    planner_factory: Any,
    *,
    contextual_store: InMemoryContextualRunStore | None = None,
) -> DiagnosisApplicationService:
    dependencies = ApplicationDependencies(
        repository=InMemorySignalRepository(),
        planner_factory=planner_factory,
        planner_identity=_identity(),
        planner_configured=True,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": PROFILE_PATH,
                "profile_s1_contextual_comparison": CONTEXTUAL_PROFILE_PATH,
            }
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    return DiagnosisApplicationService(
        dependencies,
        clock=lambda: NOW,
        contextual_store=contextual_store,
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


def _tiny_ref_wav() -> bytes:
    pcm = struct.pack("<hhh", -32768, 0, 32767)
    return _riff_wave(fmt_payload=_pcm_fmt(channels=1, rate=8_000, bits=16), data=pcm)


def _encode_multipart(
    *,
    fields: dict[str, bytes],
    files: list[tuple[str, str, bytes]],
    boundary: str = "----PresetWavBoundary",
) -> tuple[bytes, str]:
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            ).encode("ascii")
            + value
            + b"\r\n"
        )
    for field_name, filename, payload in files:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: audio/wav\r\n\r\n"
            ).encode("ascii")
            + payload
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


@pytest.fixture
async def finish_service() -> AsyncIterator[DiagnosisApplicationService]:
    class _Immediate:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            return _FINISH

    service = _make_service(lambda: _Immediate())
    try:
        yield service
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx269_preset_wav_route_deterministic_pcm32_without_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/v1/presets/harmonic_distortion/wav")
            second = await client.get("/api/v1/presets/harmonic_distortion/wav")
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("audio/wav")
    assert first.content == second.content
    assert first.content == render_demo_preset_wav("harmonic_distortion")
    loaded = load_wav_bytes(first.content)
    assert loaded.source_info.bits_per_sample == 32
    assert loaded.source_info.format_tag == "pcm"
    assert loaded.source_info.channels == 1
    assert loaded.source_info.sample_rate_hz == 48_000
    assert loaded.record.meta.num_samples == 48_000
    disposition = first.headers.get("content-disposition", "").casefold()
    for preset_id in PRESET_IDS:
        assert preset_id not in disposition


def test_t_cx270_preset_wav_preserves_discrete_evidence_anchors() -> None:
    repository = InMemorySignalRepository()
    tools = SignalToolService(repository)
    for preset_id in ("harmonic_distortion", "clipping", "clean_periodic"):
        memory = build_demo_preset(preset_id)
        wav_bytes = render_demo_preset_wav(preset_id)
        roundtrip = load_wav_bytes(wav_bytes).record
        repository.put(memory)
        repository.put(roundtrip)
        mem_h = tools.analyze_harmonic_distortion(
            memory.meta.signal_id, HarmonicDistortionInput()
        )
        wav_h = tools.analyze_harmonic_distortion(
            roundtrip.meta.signal_id, HarmonicDistortionInput()
        )
        assert mem_h.status == "success" and wav_h.status == "success"
        assert mem_h.result is not None and wav_h.result is not None
        assert mem_h.result.thd_percent == pytest.approx(
            wav_h.result.thd_percent, rel=1e-3, abs=1e-3
        )
        assert mem_h.result.fundamental_frequency_hz == pytest.approx(
            wav_h.result.fundamental_frequency_hz, rel=1e-3, abs=1e-2
        )


@pytest.mark.asyncio
async def test_t_cx271_unknown_preset_wav_returns_unknown_preset(
    finish_service: DiagnosisApplicationService,
) -> None:
    app = create_app(service=finish_service)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/presets/not_a_demo_preset/wav")
    assert response.status_code == 422
    detail = AppErrorEnvelope.model_validate(response.json()).error
    assert detail.code == "unknown_preset"
    with pytest.raises(UnknownPresetError):
        render_demo_preset_wav("not_a_demo_preset")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_t_cx272_preset_filename_input_wav_never_leaks_preset_id() -> None:
    seen: list[PlannerContext] = []

    class _CapturePlanner:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            seen.append(context)
            return _FINISH

    service = _make_service(lambda: _CapturePlanner())
    try:
        wav_bytes = render_demo_preset_wav("harmonic_distortion")
        submission = await service.submit_contextual_wav(
            wav_bytes,
            test_filename="input.wav",
            mode="single_signal",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        await service.wait_for_contextual_terminal(submission.run_id)
    finally:
        await service.aclose()

    assert seen
    meta = seen[0].signal_meta
    assert meta.filename == "input.wav"
    meta_blob = repr(meta.model_dump(mode="json")).casefold()
    for token in (
        "harmonic_distortion",
        "clean_periodic",
        "combined_distortion",
        "noise_inconclusive",
        "preset_id",
    ):
        assert token not in meta_blob


@pytest.mark.asyncio
async def test_t_cx273_harmonic_preset_wav_emits_guidance() -> None:
    class _HarmonicThenFinish:
        def __init__(self) -> None:
            self._index = 0

        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            if self._index == 0:
                self._index += 1
                return CallToolDecision(
                    call=AnalyzeHarmonicDistortionCall(
                        args=HarmonicDistortionInput()
                    ),
                    purpose="measure harmonic structure",
                    task_assessment=_ASSESSMENT,
                )
            return _FINISH

    service = _make_service(lambda: _HarmonicThenFinish())
    try:
        wav_bytes = render_demo_preset_wav("harmonic_distortion")
        submission = await service.submit_contextual_wav(
            wav_bytes,
            test_filename="input.wav",
            mode="single_signal",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        terminal = await service.wait_for_contextual_terminal(submission.run_id)
        assert terminal.context_guidance is not None
        assert terminal.context_guidance.reason_codes == (
            "harmonic_attribution_requires_context",
        )
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_t_cx274_held_bytes_upgrade_survives_parent_eviction() -> None:
    class _Immediate:
        async def decide(self, context: PlannerContext) -> AgentDecision:
            del context
            return _FINISH

    store = InMemoryContextualRunStore(terminal_limit=1, cleanup=lambda _ids: None)
    service = _make_service(lambda: _Immediate(), contextual_store=store)
    try:
        held = render_demo_preset_wav("harmonic_distortion")
        parent = await service.submit_contextual_wav(
            held,
            test_filename="input.wav",
            mode="single_signal",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        await service.wait_for_contextual_terminal(parent.run_id)

        filler = await service.submit_contextual_wav(
            held,
            test_filename="input.wav",
            mode="single_signal",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        await service.wait_for_contextual_terminal(filler.run_id)
        with pytest.raises(RunNotFoundError):
            service.get_contextual_run(parent.run_id)

        paired = await service.submit_contextual_wav(
            held,
            test_filename="input.wav",
            mode="paired_reference",
            reference_data=_tiny_ref_wav(),
            reference_filename="ref.wav",
            nominal_fundamental_hz=None,
            stimulus_kind=None,
            user_request=QUESTION,
        )
        paired_terminal = await service.wait_for_contextual_terminal(paired.run_id)
        assert paired_terminal.status == "completed"
        assert paired_terminal.stimulus_context.mode == "paired_reference"

        nominal = await service.submit_contextual_wav(
            held,
            test_filename="input.wav",
            mode="nominal_single_tone",
            reference_data=None,
            reference_filename=None,
            nominal_fundamental_hz=220.0,
            stimulus_kind="single_tone",
            user_request=QUESTION,
        )
        nominal_terminal = await service.wait_for_contextual_terminal(nominal.run_id)
        assert nominal_terminal.status == "completed"
        assert nominal_terminal.stimulus_context.mode == "nominal_single_tone"
        assert nominal_terminal.stimulus_context.nominal_fundamental_hz == 220.0
    finally:
        await service.aclose()


def test_t_cx269_render_bytes_identical_across_calls() -> None:
    a = render_demo_preset_wav("noise_inconclusive")
    b = render_demo_preset_wav("noise_inconclusive")
    assert a == b
    assert a[:4] == b"RIFF"
    # fmt bits = 32
    assert struct.unpack_from("<H", a, 34)[0] == 32
