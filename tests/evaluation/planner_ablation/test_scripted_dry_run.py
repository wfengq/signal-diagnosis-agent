"""T-CX282, T-CX288: harness-only dry-run isolation."""

from __future__ import annotations

import struct
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
from signal_diag.evaluation.planner_ablation.baseline import (
    PlannerAblationFixedPipelineBaseline,
)
from signal_diag.evaluation.planner_ablation.campaign import (
    run_four_path_harness_dry_run,
)
from signal_diag.evaluation.planner_ablation.identity import (
    validate_scored_campaign_input,
)
from signal_diag.evaluation.planner_ablation.models import (
    PlannerAblationBaselineRequest,
    ProductSlotRequest,
)
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.synthetic import generate_sine
from signal_diag.tools.service import SignalToolService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
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


class _FailOnCallProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        raise AssertionError("provider must not be called in harness dry-run")


class _ImmediateFinishPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        return FinishDecision(
            task_assessment=_ASSESSMENT,
            outcome="inconclusive",
            claims=(),
            confidence_label="low",
        )


def _pcm_fmt(*, channels: int, rate: int, bits: int) -> bytes:
    block_align = channels * bits // 8
    return struct.pack(
        "<HHIIHH", 1, channels, rate, rate * block_align, block_align, bits
    )


def _riff_wave(*, fmt_payload: bytes, data: bytes) -> bytes:
    chunks = [b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload]
    chunks.append(b"data" + struct.pack("<I", len(data)) + data)
    body = b"WAVE" + b"".join(
        chunk + (b"\x00" if len(chunk) % 2 else b"") for chunk in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _wav_from_case(case: object) -> bytes:
    samples = case.record.samples[:, 0]  # type: ignore[attr-defined]
    rate = case.record.meta.sample_rate_hz  # type: ignore[attr-defined]
    pcm = np.clip(np.rint(samples * 32767.0), -32768, 32767).astype("<i2")
    return _riff_wave(
        fmt_payload=_pcm_fmt(channels=1, rate=rate, bits=16),
        data=pcm.tobytes(),
    )


@pytest.fixture
def provider_spy() -> _FailOnCallProvider:
    return _FailOnCallProvider()


@pytest.fixture
async def scripted_executor(provider_spy: _FailOnCallProvider) -> AppProductSlotExecutor:
    repo = InMemorySignalRepository()
    dependencies = ApplicationDependencies(
        repository=repo,
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
                "profile_s1_contextual_comparison_v9_10": (
                    PROJECT_ROOT
                    / "src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml"
                ),
            }
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
        causal_policy_version="v9_11_mode_aware_no_fault_recovery",
    )
    service = DiagnosisApplicationService(dependencies, clock=lambda: NOW)
    executor = AppProductSlotExecutor(service)
    yield executor
    await service.aclose()


@pytest.fixture
def study_baseline() -> PlannerAblationFixedPipelineBaseline:
    repo = InMemorySignalRepository()
    return PlannerAblationFixedPipelineBaseline(
        repository=repo,
        tool_service=SignalToolService(repo),
        rule_engine=RuleEngine(),
        profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": PROFILE_PATH,
                "profile_s1_contextual_comparison_v9_10": (
                    PROJECT_ROOT
                    / "src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml"
                ),
            }
        ),
    )


@pytest.mark.asyncio
async def test_t_cx282_four_executor_mode_paths_zero_provider_calls(
    scripted_executor: AppProductSlotExecutor,
    study_baseline: PlannerAblationFixedPipelineBaseline,
    provider_spy: _FailOnCallProvider,
) -> None:
    test = generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.25)
    ref = generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.25)
    study_baseline._repository.put(test.record)
    study_baseline._repository.put(ref.record)
    results = await run_four_path_harness_dry_run(
        scripted_executor=scripted_executor,
        baseline=study_baseline,
        single_product_request=ProductSlotRequest(
            case_id="dry_single",
            test_wav_bytes=_wav_from_case(test),
            mode="single_signal",
            user_request=USER_REQUEST,
        ),
        paired_product_request=ProductSlotRequest(
            case_id="dry_paired",
            test_wav_bytes=_wav_from_case(test),
            mode="paired_reference",
            reference_wav_bytes=_wav_from_case(ref),
            user_request=USER_REQUEST,
        ),
        single_baseline_request=PlannerAblationBaselineRequest(
            case_id="dry_single_fixed",
            signal_id=test.record.meta.signal_id,
            stimulus_context=StimulusContext(
                mode="single_signal",
                test_signal_id=test.record.meta.signal_id,
                assertion_source="evaluation_manifest",
            ),
        ),
        paired_baseline_request=PlannerAblationBaselineRequest(
            case_id="dry_paired_fixed",
            signal_id=test.record.meta.signal_id,
            stimulus_context=StimulusContext(
                mode="paired_reference",
                test_signal_id=test.record.meta.signal_id,
                reference_signal_id=ref.record.meta.signal_id,
                assertion_source="evaluation_manifest",
            ),
        ),
        provider_calls=provider_spy.calls,
    )
    assert len(results) == 4
    assert provider_spy.calls == 0
    assert all(item.execution_identity == "harness_only" for item in results)


def test_t_cx288_rejects_harness_only_relabeled_as_product_agent() -> None:
    with pytest.raises(ValueError, match="harness_only"):
        validate_scored_campaign_input(
            {
                "arm": "product_agent",
                "execution_identity": "harness_only",
                "planner_class": "RealLLMPlanner",
            }
        )
    with pytest.raises(ValueError, match="ScriptedPlanner"):
        validate_scored_campaign_input(
            {
                "arm": "product_agent",
                "execution_identity": "product_campaign",
                "planner_class": "ScriptedPlanner",
            }
        )
