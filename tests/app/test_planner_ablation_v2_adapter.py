"""T-CX293 / T-CX294: v2 matched byte adapters, gates, guidance, provenance."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest

from signal_diag.agent.diagnosis import validate_finish_decision
from signal_diag.agent.models import (
    AgentDecision,
    AgentRunResult,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    DetectClippingCall,
    FinishDecision,
    PlannerContext,
    TaskAssessment,
)
from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.policies import AgentLimits
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.app import service as app_service_module
from signal_diag.app.contextual_models import ContextualAppRunSnapshot
from signal_diag.app.models import (
    AppErrorDetail,
    PlannerIdentity,
    SourceSummary,
    WaveformPoint,
    WaveformPreview,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.planner_ablation_v2_adapter import (
    _failure_cause_from_product_snapshot,
    _failure_kind_for_execute_error,
    build_fixed_arm_session,
    build_product_arm_session,
)
from signal_diag.app.service import ApplicationDependencies, DiagnosisApplicationService
from signal_diag.evaluation.planner_ablation.baseline import (
    _PAIRED_HARMONIC_RULES,
    _PAIRED_NO_FAULT_RULES,
    _matching,
    paired_clipping_supported,
    single_signal_clipping_supported,
)
from signal_diag.evaluation.planner_ablation.report_fields import guidance_parity_equal
from signal_diag.evaluation.planner_ablation.v2.campaign import run_schedule
from signal_diag.evaluation.planner_ablation.v2.models import (
    DEFAULT_STUDY_QUESTION,
    ByteRequest,
    CanonicalRequest,
    Schedule,
    SlotKey,
    StudyProtocolV2,
)
from signal_diag.evaluation.planner_ablation.v2.timing import (
    ControlledClock,
    measure_request,
    validate_request_timing,
)
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.signal.context import EffectiveCapabilities, StimulusContext
from signal_diag.signal.synthetic import (
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = PROJECT_ROOT / "src/signal_diag/rules/profiles/s1_distortion_v1.yaml"
CONTEXTUAL_PROFILE_PATH = (
    PROJECT_ROOT / "src/signal_diag/rules/profiles/s1_contextual_comparison_v9_10.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src/signal_diag/knowledge/corpus"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_CAUSAL = "v9_11_mode_aware_no_fault_recovery"
_INCONCLUSIVE = FinishDecision(
    task_assessment=_ASSESSMENT,
    outcome="inconclusive",
    claims=(),
    confidence_label="low",
    limitations=("scripted inconclusive finish",),
)


def _wav_from_case(case: object) -> bytes:
    # PCM32 preserves full-scale clipping_mechanism across encode/decode.
    return encode_pcm32_wav(
        case.record.samples,  # type: ignore[attr-defined]
        sample_rate_hz=case.record.meta.sample_rate_hz,  # type: ignore[attr-defined]
    )


class _FailOnCallProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        raise AssertionError("provider must not be called in offline study adapters")


class _ImmediateFinishPlanner:
    def __init__(self, provider: _FailOnCallProvider | None = None) -> None:
        self._provider = provider

    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        if self._provider is not None:
            assert self._provider.calls == 0
        return _INCONCLUSIVE


class _ToolsThenInconclusivePlanner:
    """Collect clipping + harmonic evidence then finish inconclusive (guidance parity)."""

    def __init__(self) -> None:
        self._index = 0

    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        if self._index == 0:
            self._index += 1
            return CallToolDecision(
                call=DetectClippingCall(args=ClippingInput()),
                purpose="collect clipping evidence",
                task_assessment=_ASSESSMENT,
            )
        if self._index == 1:
            self._index += 1
            return CallToolDecision(
                call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
                purpose="collect harmonic evidence",
            )
        return _INCONCLUSIVE


class _LegacyTrapService(DiagnosisApplicationService):
    async def submit_wav(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("study slots must not call submit_wav")

    async def wait_for_terminal(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("study slots must not call wait_for_terminal")


class _RecordingContextualService(_LegacyTrapService):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.submit_kwargs: dict[str, object] | None = None
        self.wait_run_ids: list[str] = []
        self.repo_object_ids: list[int] = []

    async def submit_contextual_wav(self, *args: object, **kwargs: object) -> object:
        self.submit_kwargs = dict(kwargs)
        if args:
            self.submit_kwargs["test_data"] = args[0]
        self.repo_object_ids.append(id(self._dependencies.repository))
        return await super().submit_contextual_wav(*args, **kwargs)

    async def wait_for_contextual_terminal(
        self, run_id: str, *args: object, **kwargs: object
    ) -> object:
        self.wait_run_ids.append(run_id)
        return await super().wait_for_contextual_terminal(run_id, *args, **kwargs)


def _profile_loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": PROFILE_PATH,
            "profile_s1_contextual_comparison_v9_10": CONTEXTUAL_PROFILE_PATH,
        }
    )


def _product_service(*, planner_factory: Any) -> _RecordingContextualService:
    return _RecordingContextualService(
        ApplicationDependencies(
            repository=InMemorySignalRepository(),
            planner_factory=planner_factory,
            planner_identity=PlannerIdentity(
                provider="deepseek",
                model="deepseek-v4-flash",
                prompt_version=PROMPT_VERSION,
                phase4_certified_default=True,
            ),
            planner_configured=True,
            rule_engine=RuleEngine(),
            rule_profile_loader=_profile_loader(),
            knowledge_index=KnowledgeIndex(CORPUS_PATH),
            causal_policy_version=_CAUSAL,  # type: ignore[arg-type]
        ),
        clock=lambda: NOW,
    )


@pytest.fixture
def provider_spy() -> _FailOnCallProvider:
    return _FailOnCallProvider()


@pytest.fixture
async def product_service(
    provider_spy: _FailOnCallProvider,
) -> AsyncIterator[_RecordingContextualService]:
    svc = _product_service(
        planner_factory=lambda: _ImmediateFinishPlanner(provider_spy),
    )
    try:
        yield svc
    finally:
        await svc.aclose()


def _finish_from_terminal(terminal: object) -> FinishDecision:
    assert terminal.task_assessment is not None  # type: ignore[attr-defined]
    assert terminal.outcome is not None  # type: ignore[attr-defined]
    limitations = terminal.limitations or ("reconstructed for gate matching",)  # type: ignore[attr-defined]
    return FinishDecision(
        task_assessment=terminal.task_assessment,  # type: ignore[attr-defined]
        outcome=terminal.outcome,  # type: ignore[attr-defined]
        claims=terminal.claims,  # type: ignore[attr-defined]
        confidence_label="medium",
        limitations=tuple(limitations),
    )


def _validate_terminal_finish(terminal: object) -> None:
    """Reconstruct finish inputs without altering refs or adding ground-truth claims."""
    if terminal.outcome is None or terminal.status != "completed":  # type: ignore[attr-defined]
        return
    decision = _finish_from_terminal(terminal)
    rule_evals = tuple(
        item
        for batch in terminal.rule_evaluation_batches  # type: ignore[attr-defined]
        for item in batch.evaluations
    )
    validate_finish_decision(
        decision,
        known_evidence_ids=frozenset(
            item.evidence_id for item in terminal.evidence  # type: ignore[attr-defined]
        ),
        known_rule_evaluation_ids=frozenset(item.evaluation_id for item in rule_evals),
        task_assessment=terminal.task_assessment,  # type: ignore[attr-defined]
        evidence=terminal.evidence,  # type: ignore[attr-defined]
        rule_evaluations=rule_evals,
        stimulus_context=terminal.stimulus_context,  # type: ignore[attr-defined]
        causal_policy_version=_CAUSAL,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_t_cx292_real_adapters_include_injected_phase_delays(
    product_service: _RecordingContextualService,
) -> None:
    advances = {"decode": 1.0, "execution": 2.0, "guidance": 3.0}
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.12, 3: 0.06},
        sample_rate_hz=8_000,
        duration_s=0.25,
        fundamental_amplitude=0.5,
    )
    request = ByteRequest(
        mode="single_signal",
        test_wav_bytes=_wav_from_case(harmonic),
        question=DEFAULT_STUDY_QUESTION,
    )

    clock_product = ControlledClock(start=10.0)
    product = build_product_arm_session(
        product_service,
        clock=clock_product,
        phase_advances=advances,
        offline_session=True,
    )
    product_terminal = await measure_request(
        product, request, clock=clock_product, deadline_s=120.0
    )
    assert product_terminal.timing is not None
    assert product_terminal.timing.elapsed_s == pytest.approx(6.0)
    validate_request_timing(product_terminal.timing)
    clock_product.advance(8.0)
    assert product_terminal.timing.elapsed_s == pytest.approx(6.0)

    clock_fixed = ControlledClock(start=10.0)
    fixed = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        clock=clock_fixed,
        phase_advances=advances,
        offline_session=True,
    )
    fixed_terminal = await measure_request(
        fixed, request, clock=clock_fixed, deadline_s=120.0
    )
    assert fixed_terminal.timing is not None
    assert fixed_terminal.timing.elapsed_s == pytest.approx(6.0)
    validate_request_timing(fixed_terminal.timing)
    clock_fixed.advance(9.0)
    assert fixed_terminal.timing.elapsed_s == pytest.approx(6.0)
    await product.aclose()
    await fixed.aclose()


@pytest.mark.asyncio
async def test_t_cx293_product_contextual_kwargs_and_fresh_repo(
    product_service: _RecordingContextualService,
    provider_spy: _FailOnCallProvider,
) -> None:
    test = generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.25)
    ref = generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.25)
    prior_repo_id = id(product_service._dependencies.repository)
    session = build_product_arm_session(product_service, offline_session=True)
    assert id(product_service._dependencies.repository) != prior_repo_id
    request = ByteRequest(
        mode="paired_reference",
        test_wav_bytes=_wav_from_case(test),
        reference_wav_bytes=_wav_from_case(ref),
        question=DEFAULT_STUDY_QUESTION,
        channel="mixdown",
    )
    terminal = await session.execute(request)
    assert provider_spy.calls == 0
    assert product_service.submit_kwargs is not None
    kwargs = product_service.submit_kwargs
    assert kwargs["channel"] == "mixdown"
    assert kwargs["mode"] == "paired_reference"
    assert kwargs["nominal_fundamental_hz"] is None
    assert kwargs["stimulus_kind"] is None
    assert kwargs["user_request"] == DEFAULT_STUDY_QUESTION
    assert kwargs["reference_data"] == request.reference_wav_bytes
    assert product_service.wait_run_ids == [terminal.run_id]
    assert terminal.stimulus_context is not None
    assert terminal.stimulus_context.mode == "paired_reference"
    assert terminal.stimulus_context.reference_signal_id is not None
    assert terminal.stimulus_context.nominal_fundamental_hz is None
    assert product_service.repo_object_ids
    await session.aclose()


@pytest.mark.asyncio
async def test_t_cx293_fixed_rejects_predecoded_signal_ids() -> None:
    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    with pytest.raises(TypeError, match="ByteRequest"):
        await session.execute(
            {  # type: ignore[arg-type]
                "mode": "single_signal",
                "signal_id": "sig_predecoded",
                "question": DEFAULT_STUDY_QUESTION,
            }
        )


@pytest.mark.asyncio
async def test_t_cx293_matching_gates_via_validate_finish_decision() -> None:
    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )

    clipped = generate_clipped_sine(
        frequency_hz=440.0,
        duration_s=0.5,
        amplitude=1.0,
        clip_level=0.99,
    )
    clip_terminal = await session.execute(
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=_wav_from_case(clipped),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert clip_terminal.status == "completed"
    assert clip_terminal.outcome == "supported_fault"
    assert single_signal_clipping_supported(
        clip_terminal.evidence,  # type: ignore[arg-type]
        tuple(
            item
            for batch in clip_terminal.rule_evaluation_batches
            for item in batch.evaluations
        ),
    )
    _validate_terminal_finish(clip_terminal)
    await session.aclose()

    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    noise = generate_white_noise(duration_s=0.5, seed=293)
    noise_terminal = await session.execute(
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=_wav_from_case(noise),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert noise_terminal.outcome == "inconclusive"
    _validate_terminal_finish(noise_terminal)
    await session.aclose()

    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    reference = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.18, 3: 0.08},
        duration_s=0.5,
        fundamental_amplitude=0.5,
    )
    harmonic_terminal = await session.execute(
        ByteRequest(
            mode="paired_reference",
            test_wav_bytes=_wav_from_case(harmonic),
            reference_wav_bytes=_wav_from_case(reference),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert harmonic_terminal.outcome == "supported_fault"
    rules = tuple(
        item
        for batch in harmonic_terminal.rule_evaluation_batches
        for item in batch.evaluations
    )
    assert _matching(rules, _PAIRED_HARMONIC_RULES) is not None
    # Paired harmonic gate is the five contextual rules; no even_order series gate.
    claim = next(
        c for c in harmonic_terminal.claims if c.fault_type == "harmonic_distortion"
    )
    assert all(
        not item.metric.endswith("even_order_present")
        for item in harmonic_terminal.evidence
        if item.evidence_id in claim.evidence_refs
        and item.metric not in {"test_series_kind"}
    )
    _validate_terminal_finish(harmonic_terminal)
    await session.aclose()

    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    clean = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    clean_ref = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    clean_terminal = await session.execute(
        ByteRequest(
            mode="paired_reference",
            test_wav_bytes=_wav_from_case(clean),
            reference_wav_bytes=_wav_from_case(clean_ref),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert clean_terminal.outcome == "no_supported_fault"
    clean_rules = tuple(
        item
        for batch in clean_terminal.rule_evaluation_batches
        for item in batch.evaluations
    )
    assert _matching(clean_rules, _PAIRED_NO_FAULT_RULES) is not None
    _validate_terminal_finish(clean_terminal)
    await session.aclose()

    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    degraded = generate_clipped_sine(
        frequency_hz=440.0,
        duration_s=0.5,
        amplitude=1.0,
        clip_level=0.99,
    )
    pair_clip = await session.execute(
        ByteRequest(
            mode="paired_reference",
            test_wav_bytes=_wav_from_case(degraded),
            reference_wav_bytes=_wav_from_case(clean_ref),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert pair_clip.outcome == "supported_fault"
    assert paired_clipping_supported(
        pair_clip.evidence,  # type: ignore[arg-type]
        tuple(
            item
            for batch in pair_clip.rule_evaluation_batches
            for item in batch.evaluations
        ),
    )
    _validate_terminal_finish(pair_clip)
    await session.aclose()

    session = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    invalid_ref = generate_white_noise(duration_s=0.5, seed=99)
    invalid_terminal = await session.execute(
        ByteRequest(
            mode="paired_reference",
            test_wav_bytes=_wav_from_case(clean),
            reference_wav_bytes=_wav_from_case(invalid_ref),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert invalid_terminal.outcome == "inconclusive"
    _validate_terminal_finish(invalid_terminal)
    await session.aclose()


@pytest.mark.asyncio
async def test_t_cx293_guidance_and_reference_parity_deterministic() -> None:
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.12, 3: 0.06},
        sample_rate_hz=8_000,
        duration_s=0.25,
        fundamental_amplitude=0.5,
    )
    request = ByteRequest(
        mode="single_signal",
        test_wav_bytes=_wav_from_case(harmonic),
        question=DEFAULT_STUDY_QUESTION,
    )
    product_svc = _product_service(planner_factory=lambda: _ToolsThenInconclusivePlanner())
    product = build_product_arm_session(product_svc, offline_session=True)
    fixed = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    product_terminal = await product.execute(request)
    fixed_terminal = await fixed.execute(request)
    assert product_terminal.outcome == "inconclusive"
    assert fixed_terminal.outcome == "inconclusive"
    assert product_terminal.guidance is not None
    assert fixed_terminal.guidance is not None
    assert guidance_parity_equal(product_terminal.guidance, fixed_terminal.guidance)
    assert product_terminal.guidance.summary == fixed_terminal.guidance.summary
    assert product_terminal.guidance.reason_codes == fixed_terminal.guidance.reason_codes
    assert (
        product_terminal.guidance.unlockable_modes
        == fixed_terminal.guidance.unlockable_modes
    )
    assert (
        product_terminal.guidance.required_inputs == fixed_terminal.guidance.required_inputs
    )
    assert product_terminal.stimulus_context is not None
    assert fixed_terminal.stimulus_context is not None
    assert product_terminal.stimulus_context.mode == fixed_terminal.stimulus_context.mode
    assert product_terminal.stimulus_context.nominal_fundamental_hz is None
    assert fixed_terminal.stimulus_context.nominal_fundamental_hz is None

    clock = ControlledClock()
    timed_svc = _product_service(planner_factory=lambda: _ImmediateFinishPlanner())
    timed_product = build_product_arm_session(
        timed_svc,
        clock=clock,
        offline_session=True,
    )
    measured = await measure_request(
        timed_product, request, clock=clock, deadline_s=120.0
    )
    assert measured.timing is not None
    assert measured.timing.residual_overhead_notes
    assert any(
        "preview" in note.lower() or "event" in note.lower()
        for note in measured.timing.residual_overhead_notes
    )
    await product.aclose()
    await fixed.aclose()
    await timed_product.aclose()
    await product_svc.aclose()
    await timed_svc.aclose()


def test_execute_error_classification_oserror_is_infrastructure() -> None:
    assert _failure_kind_for_execute_error(OSError("disk")) == "infrastructure"
    assert _failure_kind_for_execute_error(TimeoutError()) == "infrastructure"
    assert _failure_kind_for_execute_error(ConnectionError()) == "infrastructure"
    assert (
        _failure_kind_for_execute_error(RuntimeError("max_planner_retries"))
        == "behavioral"
    )
    assert _failure_kind_for_execute_error(RuntimeError("weird")) == "unknown"


@pytest.mark.asyncio
async def test_product_session_oserror_returns_infrastructure_terminal(
    product_service: _RecordingContextualService,
) -> None:
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.12},
        sample_rate_hz=8_000,
        duration_s=0.2,
        fundamental_amplitude=0.5,
    )
    request = ByteRequest(
        mode="single_signal",
        test_wav_bytes=_wav_from_case(harmonic),
        question=DEFAULT_STUDY_QUESTION,
    )

    async def boom(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OSError("simulated transport disk failure")

    product_service.submit_contextual_wav = boom  # type: ignore[method-assign]
    session = build_product_arm_session(product_service, offline_session=True)
    terminal = await session.execute(request)
    assert terminal.status == "failed"
    assert terminal.failure_cause is not None
    assert terminal.failure_cause.kind == "infrastructure"
    await session.aclose()


@pytest.mark.asyncio
async def test_t_cx294_provenance_harness_only_for_scripted_and_fake_client(
    provider_spy: _FailOnCallProvider,
) -> None:
    scripted = _product_service(
        planner_factory=lambda: _ImmediateFinishPlanner(provider_spy),
    )
    session = build_product_arm_session(scripted, offline_session=True)
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.12},
        sample_rate_hz=8_000,
        duration_s=0.2,
        fundamental_amplitude=0.5,
    )
    terminal = await session.execute(
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=_wav_from_case(harmonic),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert terminal.provenance.execution_identity == "harness_only"
    assert terminal.provenance.offline_session is True
    assert terminal.provenance.planner_class == "_ImmediateFinishPlanner"
    await session.aclose()
    await scripted.aclose()

    fake = _product_service(
        planner_factory=lambda: RealLLMPlanner(
            provider="deepseek",
            api_key="unused",
            model="deepseek-v4-flash",
            client=provider_spy,  # type: ignore[arg-type]
        ),
    )
    fake_session = build_product_arm_session(fake, offline_session=True)
    preview = fake_session.provenance_preview()
    assert preview.execution_identity == "harness_only"
    assert preview.planner_class == "RealLLMPlanner"
    assert preview.provider_client_bound is True
    await fake_session.aclose()
    await fake.aclose()

    fixed = build_fixed_arm_session(
        profile_loader=_profile_loader(),
        offline_session=True,
    )
    fixed_terminal = await fixed.execute(
        ByteRequest(
            mode="single_signal",
            test_wav_bytes=_wav_from_case(harmonic),
            question=DEFAULT_STUDY_QUESTION,
        )
    )
    assert fixed_terminal.provenance.execution_identity == "harness_only"
    assert (
        fixed_terminal.provenance.planner_class
        == "PlannerAblationFixedPipelineBaseline"
    )
    await fixed.aclose()
    assert provider_spy.calls == 0


class _OSErrorOnDecidePlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        raise OSError("disk full during decide")


class _AlwaysCallToolPlanner:
    async def decide(self, context: PlannerContext) -> AgentDecision:
        del context
        return CallToolDecision(
            call=DetectClippingCall(args=ClippingInput()),
            purpose="budget probe",
            task_assessment=_ASSESSMENT,
        )


def _minimal_contextual_snapshot(
    *,
    status: Literal["completed", "failed"],
    application_error: AppErrorDetail | None = None,
    result: AgentRunResult | None = None,
) -> ContextualAppRunSnapshot:
    test_source = SourceSummary(
        source_kind="wav",
        display_name="test.wav",
        sample_rate_hz=8_000,
        channels=1,
        num_frames=100,
        duration_s=0.0125,
        bits_per_sample=32,
    )
    preview = WaveformPreview(
        sample_rate_hz=8_000,
        original_num_samples=1,
        points=(WaveformPoint(sample_index=0, time_s=0.0, amplitude=0.0),),
    )
    identity = PlannerIdentity(
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version=PROMPT_VERSION,
        phase4_certified_default=True,
    )
    stimulus = StimulusContext(
        mode="single_signal",
        test_signal_id="sig_test",
        assertion_source="user_supplied",
    )
    run_id = "run_" + "a" * 32
    common = {
        "run_id": run_id,
        "created_at": NOW,
        "started_at": NOW,
        "finished_at": NOW,
        "user_request": DEFAULT_STUDY_QUESTION,
        "analyzed_channel": "mixdown",
        "test_source": test_source,
        "reference_source": None,
        "stimulus_context": stimulus,
        "effective_capabilities": EffectiveCapabilities(clipping=True),
        "test_preview": preview,
        "planner_identity": identity,
    }
    if status == "completed":
        return ContextualAppRunSnapshot(
            status="completed",
            result=result,
            **common,
        )
    return ContextualAppRunSnapshot(
        status="failed",
        application_error=application_error,
        **common,
    )


def test_failure_cause_from_product_snapshot_internal_error_is_infrastructure() -> None:
    snapshot = _minimal_contextual_snapshot(
        status="failed",
        application_error=AppErrorDetail(
            code="internal_error",
            message="diagnosis execution failed",
        ),
    )
    status, cause = _failure_cause_from_product_snapshot(snapshot, None)
    assert status == "failed"
    assert cause is not None
    assert cause.kind == "infrastructure"
    assert cause.detail.startswith("internal_error:")


def test_failure_cause_from_product_snapshot_runtime_error_termination() -> None:
    result = AgentRunResult(
        run_id="run_agent",
        status="error",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="runtime_error",
        errors=("planner exploded",),
    )
    snapshot = _minimal_contextual_snapshot(status="completed", result=result)
    status, cause = _failure_cause_from_product_snapshot(snapshot, result)
    assert status == "failed"
    assert cause is not None
    assert cause.kind == "infrastructure"
    assert cause.detail == "runtime_error"


def test_failure_cause_from_product_snapshot_max_tool_calls_is_behavioral() -> None:
    result = AgentRunResult(
        run_id="run_agent",
        status="error",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        termination_reason="max_tool_calls",
    )
    snapshot = _minimal_contextual_snapshot(status="completed", result=result)
    status, cause = _failure_cause_from_product_snapshot(snapshot, result)
    assert status == "failed"
    assert cause is not None
    assert cause.kind == "behavioral"
    assert cause.detail == "max_tool_calls"


def _mini_two_slot_schedule() -> Schedule:
    request = ByteRequest(
        mode="single_signal",
        test_wav_bytes=_wav_from_case(
            generate_sine(frequency_hz=440.0, sample_rate_hz=8_000, duration_s=0.1)
        ),
        question=DEFAULT_STUDY_QUESTION,
    )
    key_a = "a" * 64
    key_b = "b" * 64
    canonical = (
        CanonicalRequest(
            request_key=key_a,
            mode="single_signal",
            representative_scenario_id="scenario_a",
            byte_request=request,
        ),
        CanonicalRequest(
            request_key=key_b,
            mode="single_signal",
            representative_scenario_id="scenario_b",
            byte_request=request,
        ),
    )
    slots = (
        SlotKey(request_key=key_a, arm="product_agent", round_index=0),
        SlotKey(request_key=key_b, arm="product_agent", round_index=0),
    )
    return Schedule(
        canonical_requests=canonical,
        scenario_aliases={},
        slots=slots,
        schedule_digest="c" * 64,
    )


@pytest.mark.asyncio
async def test_product_oserror_on_decide_stops_campaign() -> None:
    service = _product_service(planner_factory=lambda: _OSErrorOnDecidePlanner())
    schedule = _mini_two_slot_schedule()
    protocol = StudyProtocolV2(deadline_s=30.0)

    async def factory(slot: SlotKey) -> object:
        del slot
        return build_product_arm_session(service, offline_session=True)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )
    await service.aclose()
    assert record.status == "infrastructure_stopped"
    assert record.unstarted_slot_count >= 1
    first = record.slot_records[0]
    assert first.terminal is not None
    assert first.terminal.failure_cause is not None
    assert first.terminal.failure_cause.kind in {"infrastructure", "unknown"}
    assert record.slot_records[1].status == "unstarted"


@pytest.mark.asyncio
async def test_product_budget_exhaustion_continues_campaign(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_init = DistortionDiagnosisRuntime.__init__

    def _limited_init(self: DistortionDiagnosisRuntime, *args: object, **kwargs: object) -> None:
        kwargs["limits"] = AgentLimits(max_tool_calls=1)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(
        app_service_module.DistortionDiagnosisRuntime,
        "__init__",
        _limited_init,
    )
    service = _product_service(planner_factory=lambda: _AlwaysCallToolPlanner())
    schedule = _mini_two_slot_schedule()
    protocol = StudyProtocolV2(deadline_s=60.0)
    attempts: list[SlotKey] = []

    async def factory(slot: SlotKey) -> object:
        attempts.append(slot)
        return build_product_arm_session(service, offline_session=True)

    record = await run_schedule(
        schedule,
        protocol,
        factory,
        execution_mode="offline",
        wall_timeout=False,
    )
    await service.aclose()
    assert len(attempts) == 2
    assert record.status == "completed"
    assert record.slot_records[0].terminal is not None
    assert record.slot_records[0].terminal.failure_cause is not None
    assert record.slot_records[0].terminal.failure_cause.kind == "behavioral"
    assert record.slot_records[1].status in {"completed", "failed"}
    assert record.slot_records[1].status != "unstarted"


def test_fixed_arm_slot_digests_are_unique_per_schedule_slot() -> None:
    from signal_diag.app.planner_ablation_v2_adapter import (
        StudyResourceObserver,
        build_fixed_arm_session,
    )

    digests: list[str] = []
    run_ids: list[str] = []
    for idx in range(2):
        observer = StudyResourceObserver(slot_id=f"fixed_slot_{idx}_{'a'*60}")
        session = build_fixed_arm_session(
            profile_loader=_profile_loader(),
            observer=observer,
            offline_session=True,
        )
        observer.associate_run_id(f"run_fixed_{idx}")
        ledger = session.resource_snapshot(worker_drained=True)
        digests.append(ledger.slot_key_digest)
        run_ids.append(ledger.run_id or "")
    assert digests[0] != digests[1]
    assert "fixed" not in digests
    assert run_ids[0] != run_ids[1]
