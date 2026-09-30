"""T-CX276: real contextual service integration via app adapter."""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from signal_diag.agent.models import (
    AgentDecision,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.planner import PROMPT_VERSION
from signal_diag.app.models import PlannerIdentity
from signal_diag.app.planner_ablation_adapter import AppProductSlotExecutor
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.evaluation.planner_ablation.models import ProductSlotRequest
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.signal.synthetic import generate_harmonic_sine, generate_sine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = PROJECT_ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
CONTEXTUAL_PROFILE_PATH = (
    PROJECT_ROOT / "src/signal_diag/rules/profiles/s1_contextual_comparison_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src/signal_diag/knowledge/corpus"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
USER_REQUEST = "Diagnose supported S1 distortion conservatively."
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_INCONCLUSIVE = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("scripted inconclusive finish",),
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


def _wav_from_case(case: object) -> bytes:
    samples = case.record.samples[:, 0]  # type: ignore[attr-defined]
    rate = case.record.meta.sample_rate_hz  # type: ignore[attr-defined]
    pcm = np.clip(np.rint(samples * 32767.0), -32768, 32767).astype("<i2")
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16),
        data=pcm.tobytes(),
    )


class _ImmediateFinishPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        return _INCONCLUSIVE


class _LegacyTrapService(DiagnosisApplicationService):
    async def submit_wav(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("study slots must not call submit_wav")

    async def wait_for_terminal(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("study slots must not call wait_for_terminal")


def _service() -> DiagnosisApplicationService:
    dependencies = ApplicationDependencies(
        repository=InMemorySignalRepository(),
        planner_factory=lambda: _ImmediateFinishPlanner(),
        planner_identity=PlannerIdentity(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version=PROMPT_VERSION,
            phase4_certified_default=True,
        ),
        planner_configured=True,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": PROFILE_PATH,
                "profile_s1_contextual_comparison": CONTEXTUAL_PROFILE_PATH,
            }
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
        causal_policy_version="v9_11_mode_aware_no_fault_recovery",
    )
    return _LegacyTrapService(dependencies, clock=lambda: NOW)


@pytest.fixture
async def service() -> AsyncIterator[DiagnosisApplicationService]:
    svc = _service()
    try:
        yield svc
    finally:
        await svc.aclose()


@pytest.mark.asyncio
async def test_t_cx276_adapter_returns_contextual_snapshot_with_guidance(
    service: DiagnosisApplicationService,
) -> None:
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.12, 3: 0.06},
        sample_rate_hz=8_000,
        duration_s=0.25,
        fundamental_amplitude=0.5,
    )
    executor = AppProductSlotExecutor(service)
    outcome = await executor.execute_product_slot(
        ProductSlotRequest(
            case_id="case_guidance",
            test_wav_bytes=_wav_from_case(harmonic),
            test_filename="test.wav",
            mode="single_signal",
            user_request=USER_REQUEST,
        )
    )
    assert outcome.terminal_status == "completed"
    assert outcome.result is not None
    assert outcome.result.diagnosis is not None
    assert outcome.result.diagnosis.outcome == "inconclusive"
    assert outcome.context_guidance is not None
    assert outcome.context_guidance.reason_codes


@pytest.mark.asyncio
async def test_t_cx276_paired_reference_contextual_submit_kwargs(
    service: DiagnosisApplicationService,
) -> None:
    test = generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.25)
    ref = generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.25)
    executor = AppProductSlotExecutor(service)
    outcome = await executor.execute_product_slot(
        ProductSlotRequest(
            case_id="case_paired",
            test_wav_bytes=_wav_from_case(test),
            test_filename="test.wav",
            mode="paired_reference",
            reference_wav_bytes=_wav_from_case(ref),
            reference_filename="ref.wav",
            user_request=USER_REQUEST,
        )
    )
    assert outcome.mode == "paired_reference"
    assert outcome.terminal_status == "completed"
