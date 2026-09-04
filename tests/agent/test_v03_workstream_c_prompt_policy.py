"""V0.3 Workstream C — conservative agent policy (T-C-001..T-C-028). Contract tests only."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from signal_diag.agent.models import (
    AgentDecision,
    AgentRunResult,
    AnalyzeHarmonicDistortionCall,
    CallToolDecision,
    ClippingInput,
    DetectClippingCall,
    DiagnosisClaim,
    EvaluateRulesDecision,
    FinishDecision,
    HarmonicDistortionInput,
    PlannerContext,
    PlannerOutputError,
    RetrieveKnowledgeDecision,
    TaskAssessment,
)
from signal_diag.agent.planner import _parse_agent_decision
from signal_diag.agent.prompts import _S1_PROMPT_V8_1
from signal_diag.agent.prompts_v03 import (
    _S1_PROMPT_V9_1,
    _S1_PROMPT_V9_2,
    _S1_PROMPT_V9_3,
    _S1_PROMPT_V9_4,
)
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation, RuleJudgment
from signal_diag.signal import (
    SyntheticCase,
    generate_combined_distortion,
    load_wav_bytes,
)
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case
from tests.dsp.v03_prerequisite_helpers import make_subharmonic_lock_sine

_V03_PROMPT_VERSION = "v0.3-s1-planner-9.4"
# Historical: real-model v9.2 failure SHA is 8fc065ba... in agent_v9_2_dev_run;
# workspace later drifted to the frozen SHA below and must not be reused as product.
_FROZEN_V92_WORKSPACE_SHA256 = (
    "4dc9716099d7dd37e35949aa11325f096f5f5213a0b0067c1119affc95545984"
)
_FROZEN_V93_SHA256 = (
    "9fd0436e57b0d7db57abdfa3e2a87aca4e704d7c1f70adf781b1af967776554a"
)
_FROZEN_V94_SHA256 = (
    "a29c9cda17bd4bf1d922880610609e32f0670b3eecb984a1e3afa16671e806af"
)
_FROZEN_V81_SHA256 = (
    "f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca"
)
_FROZEN_V91_SHA256 = (
    "2193c8e221cf5e1abd3abe98105745c5685912f14fb7e76c7aa033b4c1568672"
)

_NUMERIC_THRESHOLD_PATTERN = re.compile(
    r"\b(\d+\.?\d*)\s*%\s*(THD|thd)|h2\s*/\s*h3|fundamental_relative_energy\s*[<>=]",
    re.IGNORECASE,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)

FinishBuilder = Callable[[PlannerContext], FinishDecision]


class _V03RoutePlanner:
    """Scripted route with rule evaluation for Workstream C policy tests."""

    def __init__(
        self,
        steps: list[AgentDecision],
        finish_builder: FinishBuilder,
    ) -> None:
        self._steps = steps
        self._finish_builder = finish_builder
        self._index = 0

    async def decide(self, context: PlannerContext) -> AgentDecision:
        if self._index < len(self._steps):
            decision = self._steps[self._index]
            if (
                self._index == 0
                and getattr(decision, "task_assessment", None) is None
            ):
                decision = decision.model_copy(
                    update={
                        "task_assessment": TaskAssessment(
                            task_type="distortion_analysis",
                            objective="determine why the signal sounds distorted",
                            hypotheses=("clipping", "harmonic_distortion"),
                        )
                    }
                )
            self._index += 1
            return decision
        return self._finish_builder(context)


def _v03_prompt_spec() -> object:
    return _S1_PROMPT_V9_4


def _evidence_by_metric(context: PlannerContext, metric: str) -> str:
    for item in context.evidence:
        if item.metric == metric:
            return item.evidence_id
    raise AssertionError(f"missing evidence metric: {metric}")


def _evidence_by_metric_value(context: PlannerContext, metric: str, value: object) -> str:
    for item in context.evidence:
        if item.metric == metric and item.value == value:
            return item.evidence_id
    raise AssertionError(f"missing evidence metric={metric} value={value!r}")


def _assert_not_supported_fault_success(result: AgentRunResult) -> None:
    if result.diagnosis is not None:
        assert result.diagnosis.outcome != "supported_fault"
    assert result.status != "success" or (
        result.diagnosis is not None and result.diagnosis.outcome != "supported_fault"
    )


DEV_WAV_DIR = (
    PROJECT_ROOT
    / "docs"
    / "evaluations"
    / "v0_3"
    / "dev"
    / "study_v0_3_dev_1"
    / "wav"
)


def _store_dev_wav(repository: InMemorySignalRepository, case_id: str) -> str:
    path = DEV_WAV_DIR / f"v03dev_{case_id}.wav"
    record = load_wav_bytes(path.read_bytes(), filename=path.name).record
    repository.put(record)
    return record.meta.signal_id


def _evaluation(
    context: PlannerContext,
    rule_id: str,
    *,
    judgment: RuleJudgment | None = None,
) -> RuleEvaluation:
    for batch in context.rule_evaluation_batches:
        for item in batch.evaluations:
            if item.rule_id == rule_id and (
                judgment is None or item.judgment == judgment
            ):
                return item
    raise AssertionError(f"missing rule evaluation: {rule_id}")


def _evaluate_rules_decision() -> EvaluateRulesDecision:
    return EvaluateRulesDecision(
        profile_id="profile_s1_distortion",
        evidence_refs=(),
        purpose="apply configured S1 demonstration limits",
    )


async def _run_v03_route(
    repository: InMemorySignalRepository,
    signal_id: str,
    planner: _V03RoutePlanner,
) -> AgentRunResult:
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=planner,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
    )
    return await runtime.run(
        signal_id=signal_id,
        user_request="Why does this signal sound distorted?",
    )


def _harmonic_only_steps() -> list[AgentDecision]:
    return [
        CallToolDecision(
            call=DetectClippingCall(args=ClippingInput()),
            purpose="rule out clipping before harmonic assessment",
        ),
        CallToolDecision(
            call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
            purpose="measure harmonic content",
        ),
        _evaluate_rules_decision(),
    ]


def _combined_steps() -> list[AgentDecision]:
    return [
        CallToolDecision(
            call=DetectClippingCall(args=ClippingInput()),
            purpose="detect clipping",
        ),
        CallToolDecision(
            call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
            purpose="measure harmonic distortion",
        ),
        _evaluate_rules_decision(),
    ]


@pytest.mark.asyncio
async def test_t_c_001_scripted_inconclusive_path_accepted_for_valid_thd_fail(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    """Runtime must accept inconclusive when valid=true, THD FAIL, no clipping mechanism."""
    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_thd_no_mechanism",
                    fault_type="inconclusive",
                    statement=(
                        "Valid harmonic measurement with THD rule FAIL, but no "
                        "same-run distortion-mechanism Evidence."
                    ),
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="low",
            limitations=(
                (
                    "THD rule FAIL establishes elevated harmonic content, not causal "
                    "harmonic_distortion without additional distortion-mechanism Evidence."
                ),
            ),
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.status == "inconclusive"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_t_c_002_inconclusive_requires_refs_and_limitations(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_thd_no_mechanism",
                    fault_type="inconclusive",
                    statement="THD FAIL without causal mechanism Evidence.",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="low",
            limitations=(
                "THD FAIL alone does not establish causal harmonic_distortion.",
            ),
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), finish),
    )
    assert result.diagnosis is not None
    claim = result.diagnosis.claims[0]
    assert claim.evidence_refs
    assert claim.rule_refs
    assert result.diagnosis.limitations
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        evaluation.evaluation_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert set(claim.evidence_refs) <= evidence_ids
    assert set(claim.rule_refs) <= rule_ids


@pytest.mark.asyncio
async def test_t_c_003_combined_distortion_supported_fault_not_regressed(
    repository: InMemorySignalRepository,
) -> None:
    combined_case = generate_combined_distortion(
        fundamental_hz=200.0,
        harmonic_ratios={2: 0.10, 3: 0.05},
        clip_level=1.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=1.2,
    )
    signal_id = store_synthetic_case(repository, combined_case)

    def finish(context: PlannerContext) -> FinishDecision:
        clip_eval = _evaluation(context, "rule_flat_top_absent", judgment="fail")
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip_combined",
                    fault_type="clipping",
                    statement="Clipping is affirmatively supported.",
                    evidence_refs=(
                        _evidence_by_metric_value(context, "clipping_mechanism", True),
                        _evidence_by_metric(context, "clipping_ratio"),
                    ),
                    rule_refs=(clip_eval.evaluation_id,),
                ),
                DiagnosisClaim(
                    claim_id="claim_harm_combined",
                    fault_type="harmonic_distortion",
                    statement=(
                        "Independent harmonic distortion supported with clipping "
                        "mechanism Evidence present."
                    ),
                    evidence_refs=(
                        _evidence_by_metric_value(
                            context, "series_kind", "even_order_present"
                        ),
                    ),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="high",
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_combined_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    fault_types = {claim.fault_type for claim in result.diagnosis.claims}
    assert fault_types == {"clipping", "harmonic_distortion"}


def test_t_c_004_prompt_contains_no_numeric_thresholds() -> None:
    spec = _v03_prompt_spec()
    text = spec.system_prompt  # type: ignore[attr-defined]
    assert _NUMERIC_THRESHOLD_PATTERN.search(text) is None


def test_t_c_005_v81_sha256_frozen_and_v03_version_present() -> None:
    v81_sha = hashlib.sha256(_S1_PROMPT_V8_1.system_prompt.encode("utf-8")).hexdigest()
    assert v81_sha == _FROZEN_V81_SHA256
    v91_sha = hashlib.sha256(_S1_PROMPT_V9_1.system_prompt.encode("utf-8")).hexdigest()
    assert v91_sha == _FROZEN_V91_SHA256
    v92_sha = hashlib.sha256(_S1_PROMPT_V9_2.system_prompt.encode("utf-8")).hexdigest()
    assert v92_sha == _FROZEN_V92_WORKSPACE_SHA256
    assert _S1_PROMPT_V9_2.version == "v0.3-s1-planner-9.2"
    spec = _v03_prompt_spec()
    assert spec.version == _V03_PROMPT_VERSION  # type: ignore[attr-defined]
    assert spec is _S1_PROMPT_V9_4
    v93_sha = hashlib.sha256(_S1_PROMPT_V9_3.system_prompt.encode("utf-8")).hexdigest()
    assert v93_sha == _FROZEN_V93_SHA256
    v94_sha = hashlib.sha256(_S1_PROMPT_V9_4.system_prompt.encode("utf-8")).hexdigest()
    assert v94_sha == _FROZEN_V94_SHA256


def test_t_c_006_section3_clarifies_thd_fail_not_causal_harmonic() -> None:
    spec = _v03_prompt_spec()
    text = spec.system_prompt  # type: ignore[attr-defined]
    assert "rule_thd_acceptable" in text or "THD" in text
    assert "does not, by itself, establish" in text or "does not by itself establish" in text
    assert "harmonic_distortion" in text


def _invalid_harmonic_steps() -> list[AgentDecision]:
    return [
        CallToolDecision(
            call=DetectClippingCall(args=ClippingInput()),
            purpose="rule out clipping before harmonic assessment",
        ),
        CallToolDecision(
            call=AnalyzeHarmonicDistortionCall(args=HarmonicDistortionInput()),
            purpose="measure harmonic content",
        ),
    ]


@pytest.mark.asyncio
async def test_t_c_007_invalid_harmonic_direct_inconclusive_without_knowledge(
    repository: InMemorySignalRepository,
) -> None:
    """valid=false / unreliable harmonic may finish inconclusive without retrieve_knowledge."""
    from signal_diag.signal import SignalMeta, SignalRecord

    samples = make_subharmonic_lock_sine(700.0)
    repository.put(
        SignalRecord(
            meta=SignalMeta(
                signal_id="sig_invalid_harmonic",
                source_type="generated",
                filename="invalid_harmonic.wav",
                sample_rate_hz=48_000,
                channels=1,
                num_samples=len(samples),
                duration_s=len(samples) / 48_000,
                original_dtype="float32",
            ),
            samples=samples.reshape(-1, 1),
        )
    )

    def finish(context: PlannerContext) -> FinishDecision:
        valid_ev = next(
            item.evidence_id
            for item in context.evidence
            if item.metric == "valid"
        )
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_invalid_harmonic",
                    fault_type="inconclusive",
                    statement=(
                        "Harmonic measurement is invalid; causal S1 attribution "
                        "is not supported."
                    ),
                    evidence_refs=(valid_ev,),
                    rule_refs=(),
                ),
            ),
            confidence_label="low",
            limitations=(
                "Harmonic distortion analysis is invalid on this signal.",
            ),
        )

    result = await _run_v03_route(
        repository,
        "sig_invalid_harmonic",
        _V03RoutePlanner(_invalid_harmonic_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.knowledge_retrievals == ()


@pytest.mark.asyncio
async def test_t_c_008_invalid_inconclusive_requires_refs_and_limitations(
    repository: InMemorySignalRepository,
) -> None:
    from signal_diag.signal import SignalMeta, SignalRecord

    samples = make_subharmonic_lock_sine(700.0)
    repository.put(
        SignalRecord(
            meta=SignalMeta(
                signal_id="sig_invalid_harmonic_refs",
                source_type="generated",
                filename="invalid_harmonic.wav",
                sample_rate_hz=48_000,
                channels=1,
                num_samples=len(samples),
                duration_s=len(samples) / 48_000,
                original_dtype="float32",
            ),
            samples=samples.reshape(-1, 1),
        )
    )

    def finish(context: PlannerContext) -> FinishDecision:
        valid_ev = next(
            item.evidence_id
            for item in context.evidence
            if item.metric == "valid"
        )
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_invalid_harmonic",
                    fault_type="inconclusive",
                    statement="Invalid harmonic measurement.",
                    evidence_refs=(valid_ev,),
                    rule_refs=(),
                ),
            ),
            confidence_label="low",
            limitations=("Harmonic analysis invalid.",),
        )

    result = await _run_v03_route(
        repository,
        "sig_invalid_harmonic_refs",
        _V03RoutePlanner(_invalid_harmonic_steps(), finish),
    )
    assert result.diagnosis is not None
    claim = result.diagnosis.claims[0]
    assert claim.evidence_refs
    assert result.diagnosis.limitations


def test_t_c_009_prompt_allows_direct_inconclusive_without_knowledge() -> None:
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "valid=false" in text
    assert "NOT required" in text or "not required" in text
    assert "Do not call retrieve_knowledge unless" in text


def test_t_c_010_missing_query_text_is_planner_output_error() -> None:
    """Malformed retrieve_knowledge (missing query_text) fails schema validation."""
    payload = {
        "decision_type": "retrieve_knowledge",
        "purpose": "explain invalid harmonic measurement",
        "tags": [],
    }
    with pytest.raises(PlannerOutputError, match="query_text"):
        _parse_agent_decision(json.dumps(payload))


def test_t_c_011_retrieve_knowledge_requires_non_empty_query_text() -> None:
    decision = RetrieveKnowledgeDecision(
        query_text="harmonic valid false unreliable f0 attribution limits",
        purpose="context-derived corpus lookup for invalid harmonic case",
    )
    assert decision.query_text.strip()
    assert "harmonic valid false" in decision.query_text



def _store_generated_mono(
    repository: InMemorySignalRepository,
    *,
    signal_id: str,
    samples,
    filename: str,
) -> None:
    from signal_diag.signal import SignalMeta, SignalRecord

    n = int(samples.shape[0])
    repository.put(
        SignalRecord(
            meta=SignalMeta(
                signal_id=signal_id,
                source_type="generated",
                filename=filename,
                sample_rate_hz=48_000,
                channels=1,
                num_samples=n,
                duration_s=n / 48_000,
                original_dtype="float32",
            ),
            samples=samples.reshape(-1, 1),
        )
    )


def _square_like_samples():
    import numpy as np

    n = 48_000
    t = np.arange(n, dtype=np.float64) / 48_000.0
    # Amplitude below full-scale: native odd-harmonic richness, no injected clipping.
    return (0.5 * np.sign(np.sin(2.0 * np.pi * 440.0 * t))).astype(np.float32)


def _prefer_evidence(context: PlannerContext, *metrics: str) -> str:
    for metric in metrics:
        for item in context.evidence:
            if item.metric == metric:
                return item.evidence_id
    if context.evidence:
        return context.evidence[0].evidence_id
    raise AssertionError("missing evidence")


def _optional_thd_fail_refs(context: PlannerContext) -> tuple[str, ...]:
    try:
        return (_evaluation(context, "rule_thd_acceptable", judgment="fail").evaluation_id,)
    except AssertionError:
        return ()


@pytest.mark.asyncio
async def test_t_c_012_multi_tone_thd_fail_without_mechanism_is_inconclusive(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    """e5b7a3c6 path: valid THD FAIL + no distortion mechanism -> not harmonic_distortion."""
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "Multi-tone structure" in text
    assert "Do not emit harmonic_distortion as supported_fault from THD FAIL alone" in text

    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_multi_tone_no_mechanism",
                    fault_type="inconclusive",
                    statement=(
                        "Valid harmonic measurement with THD rule FAIL, but multi-tone "
                        "structure is not a distortion mechanism."
                    ),
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="low",
            limitations=(
                (
                    "THD FAIL is not causal harmonic_distortion without independent "
                    "distortion-mechanism Evidence."
                ),
            ),
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.status == "inconclusive"
    fault_types = {claim.fault_type for claim in result.diagnosis.claims}
    assert "harmonic_distortion" not in fault_types
    assert result.diagnosis.outcome != "supported_fault"


@pytest.mark.asyncio
async def test_t_c_013_native_square_without_clipping_mechanism_is_inconclusive(
    repository: InMemorySignalRepository,
) -> None:
    """6d3f5be4 path: native harmonic-rich square, no injected distortion -> not clipping."""
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "square-like" in text
    assert "Do not infer clipping from harmonic richness" in text

    _store_generated_mono(
        repository,
        signal_id="sig_c013_square",
        samples=_square_like_samples(),
        filename="square_like.wav",
    )

    def finish(context: PlannerContext) -> FinishDecision:
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_square_not_clipping",
                    fault_type="inconclusive",
                    statement=(
                        "Native harmonic-rich square-like spectrum without independent "
                        "clipping-mechanism Evidence."
                    ),
                    evidence_refs=(_prefer_evidence(context, "thd_percent", "valid"),),
                    rule_refs=_optional_thd_fail_refs(context),
                ),
            ),
            confidence_label="low",
            limitations=(
                (
                    "Harmonic richness of a square-like waveform is not clipping without "
                    "same-run detect_clipping mechanism Evidence."
                ),
            ),
        )

    result = await _run_v03_route(
        repository,
        "sig_c013_square",
        _V03RoutePlanner(_harmonic_only_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    fault_types = {claim.fault_type for claim in result.diagnosis.claims}
    assert "clipping" not in fault_types
    assert result.diagnosis.outcome != "supported_fault"


@pytest.mark.asyncio
async def test_t_c_014_invalid_harmonic_must_not_support_clipping_fault(
    repository: InMemorySignalRepository,
) -> None:
    """29fb17a0 path: valid=false harmonic must not become clipping supported_fault."""
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "valid=false" in text
    assert "must not be used as causal Evidence for clipping" in text
    assert "Invalid harmonic measurement is not a supported_fault" in text

    samples = make_subharmonic_lock_sine(700.0)
    _store_generated_mono(
        repository,
        signal_id="sig_c014_invalid_harmonic",
        samples=samples,
        filename="invalid_harmonic_c014.wav",
    )

    def finish(context: PlannerContext) -> FinishDecision:
        valid_ev = next(
            item.evidence_id
            for item in context.evidence
            if item.metric == "valid"
        )
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_invalid_not_clipping",
                    fault_type="inconclusive",
                    statement=(
                        "Invalid harmonic measurement is not causal clipping or "
                        "harmonic_distortion."
                    ),
                    evidence_refs=(valid_ev,),
                    rule_refs=(),
                ),
            ),
            confidence_label="low",
            limitations=(
                "Invalid harmonic analysis cannot support a causal S1 fault.",
            ),
        )

    result = await _run_v03_route(
        repository,
        "sig_c014_invalid_harmonic",
        _V03RoutePlanner(_invalid_harmonic_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.status == "inconclusive"
    fault_types = {claim.fault_type for claim in result.diagnosis.claims}
    assert "clipping" not in fault_types
    assert "harmonic_distortion" not in fault_types
    assert result.diagnosis.outcome != "supported_fault"



def _inconclusive_finish(context: PlannerContext, statement: str) -> FinishDecision:
    return FinishDecision(
        outcome="inconclusive",
        claims=(
            DiagnosisClaim(
                claim_id="claim_mechanism_inconclusive",
                fault_type="inconclusive",
                statement=statement,
                evidence_refs=(_prefer_evidence(context, "series_kind", "thd_percent", "valid"),),
                rule_refs=_optional_thd_fail_refs(context),
            ),
        ),
        confidence_label="low",
        limitations=(
            "Same-run mechanism Evidence does not support a causal S1 supported_fault.",
        ),
    )


@pytest.mark.asyncio
async def test_t_c_015_injected_harmonic_supported_fault_accepted(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "b2e4d0f3c915e827")

    def finish(context: PlannerContext) -> FinishDecision:
        kind_id = _evidence_by_metric_value(context, "series_kind", "even_order_present")
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_injected_h2",
                    fault_type="harmonic_distortion",
                    statement="Injected H2 supported by series_kind even_order_present.",
                    evidence_refs=(kind_id,),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="medium",
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert result.diagnosis.claims[0].fault_type == "harmonic_distortion"


@pytest.mark.asyncio
async def test_t_c_016_two_tone_multi_partial_harmonic_supported_fault_rejected(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "e5b7a3c6f2481b5a")

    def reject_finish(context: PlannerContext) -> FinishDecision:
        kind_id = _evidence_by_metric_value(context, "series_kind", "multi_partial")
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_two_tone_harmonic",
                    fault_type="harmonic_distortion",
                    statement="Two-tone multi_partial is not causal harmonic_distortion.",
                    evidence_refs=(kind_id,),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="medium",
        )

    rejected = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), reject_finish),
    )
    _assert_not_supported_fault_success(rejected)

    accepted = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(
            _harmonic_only_steps(),
            lambda context: _inconclusive_finish(
                context,
                "Two-tone multi_partial is not a causal harmonic mechanism.",
            ),
        ),
    )
    assert accepted.termination_reason == "planner_finished"
    assert accepted.diagnosis is not None
    assert accepted.diagnosis.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_t_c_017_square_native_odd_clipping_supported_fault_rejected(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "6d3f5be41ac093d2")

    def reject_finish(context: PlannerContext) -> FinishDecision:
        assert any(
            item.metric == "series_kind" and item.value == "native_odd_series"
            for item in context.evidence
        )
        clip_id = _evidence_by_metric_value(context, "clipping_mechanism", False)
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_square_clipping",
                    fault_type="clipping",
                    statement="Native square is not clipping.",
                    evidence_refs=(clip_id,),
                ),
            ),
            confidence_label="medium",
        )

    rejected = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), reject_finish),
    )
    _assert_not_supported_fault_success(rejected)

    accepted = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(
            _harmonic_only_steps(),
            lambda context: _inconclusive_finish(
                context,
                "Native odd series without clipping_mechanism is inconclusive.",
            ),
        ),
    )
    assert accepted.termination_reason == "planner_finished"
    assert accepted.diagnosis is not None
    assert accepted.diagnosis.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_t_c_018_triangle_native_odd_harmonic_supported_fault_rejected(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "7e4a6cf52bd1a4e3")

    def reject_finish(context: PlannerContext) -> FinishDecision:
        kind_id = _evidence_by_metric_value(context, "series_kind", "native_odd_series")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_triangle_harmonic",
                    fault_type="harmonic_distortion",
                    statement="Native triangle odd series is not causal harmonic_distortion.",
                    evidence_refs=(kind_id,),
                ),
            ),
            confidence_label="medium",
        )

    rejected = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), reject_finish),
    )
    _assert_not_supported_fault_success(rejected)

    accepted = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(
            _harmonic_only_steps(),
            lambda context: _inconclusive_finish(
                context,
                "Native odd series is not causal harmonic_distortion.",
            ),
        ),
    )
    assert accepted.termination_reason == "planner_finished"
    assert accepted.diagnosis is not None
    assert accepted.diagnosis.outcome == "inconclusive"


@pytest.mark.asyncio
async def test_t_c_019_invalid_harmonic_not_applicable_inconclusive_accepted(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "29fb17a0d68c5f9e")

    def inconclusive_finish(context: PlannerContext) -> FinishDecision:
        kind_id = _evidence_by_metric_value(context, "series_kind", "not_applicable")
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_invalid_29fb",
                    fault_type="inconclusive",
                    statement="Invalid harmonic measurement is not a supported_fault.",
                    evidence_refs=(kind_id,),
                ),
            ),
            confidence_label="low",
            limitations=("Harmonic analysis is not_applicable on this signal.",),
        )

    accepted = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_invalid_harmonic_steps(), inconclusive_finish),
    )
    assert accepted.termination_reason == "planner_finished"
    assert accepted.diagnosis is not None
    assert accepted.diagnosis.outcome == "inconclusive"

    clip_mechanism = None

    def clipping_finish(context: PlannerContext) -> FinishDecision:
        nonlocal clip_mechanism
        clip_item = next(
            item for item in context.evidence if item.metric == "clipping_mechanism"
        )
        clip_mechanism = clip_item.value
        # Cite a non-mechanism clipping metric so this is rejected unless the
        # planner also includes clipping_mechanism=true. Gold 29fb currently
        # has full-scale hits from a couple of +/-1 samples.
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_invalid_as_clipping",
                    fault_type="clipping",
                    statement="Invalid harmonic must not become clipping without mechanism.",
                    evidence_refs=(_evidence_by_metric(context, "clipping_detected"),),
                ),
            ),
            confidence_label="medium",
        )

    rejected = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_invalid_harmonic_steps(), clipping_finish),
    )
    assert clip_mechanism is True
    _assert_not_supported_fault_success(rejected)


@pytest.mark.asyncio
async def test_t_c_020_full_scale_clip_supported_fault_accepted(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "c3f5e1a4d026f938")

    def finish(context: PlannerContext) -> FinishDecision:
        clip_id = _evidence_by_metric_value(context, "clipping_mechanism", True)
        clip_eval = _evaluation(context, "rule_flat_top_absent", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_full_scale_clip",
                    fault_type="clipping",
                    statement="Full-scale clipping supported by clipping_mechanism.",
                    evidence_refs=(clip_id,),
                    rule_refs=(clip_eval.evaluation_id,),
                ),
            ),
            confidence_label="high",
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_combined_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert result.diagnosis.claims[0].fault_type == "clipping"


def test_t_c_021_prompt_cites_mechanism_evidence_without_numeric_thresholds() -> None:
    spec = _v03_prompt_spec()
    text = spec.system_prompt  # type: ignore[attr-defined]
    assert _NUMERIC_THRESHOLD_PATTERN.search(text) is None
    assert "series_kind" in text
    assert "even_order_present" in text
    assert "clipping_mechanism" in text


@pytest.mark.asyncio
async def test_t_c_022_harmonic_supported_fault_citing_only_thd_is_rejected(
    repository: InMemorySignalRepository,
    harmonic_case: SyntheticCase,
) -> None:
    signal_id = store_synthetic_case(repository, harmonic_case)

    def finish(context: PlannerContext) -> FinishDecision:
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_thd_only",
                    fault_type="harmonic_distortion",
                    statement="THD FAIL without even_order_present.",
                    evidence_refs=(_evidence_by_metric(context, "thd_percent"),),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="medium",
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_harmonic_only_steps(), finish),
    )
    _assert_not_supported_fault_success(result)


@pytest.mark.asyncio
async def test_t_c_023_positive_fault_with_sibling_no_supported_fault_rejected(
    repository: InMemorySignalRepository,
) -> None:
    """Combined path: clipping + sibling no_supported_fault must not succeed."""
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "not emitted as an additional cause beside a supported fault" in text

    signal_id = _store_dev_wav(repository, "c3f5e1a4d026f938")

    def finish(context: PlannerContext) -> FinishDecision:
        clip_id = _evidence_by_metric_value(context, "clipping_mechanism", True)
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_clip_ok",
                    fault_type="clipping",
                    statement="Clipping supported by mechanism Evidence.",
                    evidence_refs=(clip_id,),
                ),
                DiagnosisClaim(
                    claim_id="claim_sibling_no_fault",
                    fault_type="no_supported_fault",
                    statement="Sibling empty-cause claim must not accompany clipping.",
                    evidence_refs=(clip_id,),
                ),
            ),
            confidence_label="medium",
        )

    rejected = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_combined_steps(), finish),
    )
    _assert_not_supported_fault_success(rejected)


@pytest.mark.asyncio
async def test_t_c_024_sparse_full_scale_mechanism_alone_is_not_causal_clipping(
    repository: InMemorySignalRepository,
) -> None:
    """29fb: clipping_mechanism=true without substantial rule FAIL is not causal."""
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "clipping_mechanism alone is not sufficient" in text.lower() or (
        "Clipping_mechanism alone is not sufficient" in text
    )

    signal_id = _store_dev_wav(repository, "29fb17a0d68c5f9e")

    def reject_finish(context: PlannerContext) -> FinishDecision:
        assert any(
            item.metric == "valid" and item.value is False for item in context.evidence
        )
        clip_id = _evidence_by_metric_value(context, "clipping_mechanism", True)
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_sparse_fs_only",
                    fault_type="clipping",
                    statement="Mechanism alone must not support causal clipping.",
                    evidence_refs=(clip_id,),
                ),
            ),
            confidence_label="medium",
        )

    rejected = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_invalid_harmonic_steps(), reject_finish),
    )
    _assert_not_supported_fault_success(rejected)

    def inconclusive_finish(context: PlannerContext) -> FinishDecision:
        kind_id = _evidence_by_metric_value(context, "series_kind", "not_applicable")
        return FinishDecision(
            outcome="inconclusive",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_29fb_inconclusive",
                    fault_type="inconclusive",
                    statement=(
                        "Invalid harmonic plus sparse full-scale samples without "
                        "substantial clipping rule FAIL."
                    ),
                    evidence_refs=(kind_id,),
                ),
            ),
            confidence_label="low",
            limitations=(
                (
                    "Two isolated full-scale samples are not causal clipping; "
                    "harmonic analysis remains invalid."
                ),
            ),
        )

    accepted = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_invalid_harmonic_steps(), inconclusive_finish),
    )
    assert accepted.termination_reason == "planner_finished"
    assert accepted.diagnosis is not None
    assert accepted.diagnosis.outcome == "inconclusive"


def test_t_c_025_prompt_states_even_order_present_positive_path() -> None:
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "even_order_present" in text
    assert "not true injection provenance" in text
    assert "supported_fault" in text
    assert "harmonic_distortion" in text
    assert (
        "When same-run series_kind Evidence equals even_order_present" in text
        or "series_kind Evidence whose value is even_order_present" in text
    )


@pytest.mark.asyncio
async def test_t_c_026_invalid_harmonic_does_not_block_sufficient_clipping(
    repository: InMemorySignalRepository,
) -> None:
    """valid=false must not auto-negate mechanism + substantial rule FAIL clipping."""
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "does not automatically negate" in text

    import numpy as np

    base = make_subharmonic_lock_sine(700.0)
    clipped = np.clip(base.astype(np.float64) * 2.5, -0.99, 0.99).astype(np.float32)
    _store_generated_mono(
        repository,
        signal_id="sig_c026_invalid_plus_clip",
        samples=clipped,
        filename="invalid_plus_clip.wav",
    )

    def finish(context: PlannerContext) -> FinishDecision:
        assert any(
            item.metric == "valid" and item.value is False for item in context.evidence
        )
        clip_id = _evidence_by_metric_value(context, "clipping_mechanism", True)
        clip_eval = _evaluation(context, "rule_flat_top_absent", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_sufficient_clip_despite_invalid_h",
                    fault_type="clipping",
                    statement="Sufficient clipping Evidence remains valid.",
                    evidence_refs=(clip_id,),
                    rule_refs=(clip_eval.evaluation_id,),
                ),
            ),
            confidence_label="medium",
            limitations=("Harmonic analysis is invalid on this signal.",),
        )

    result = await _run_v03_route(
        repository,
        "sig_c026_invalid_plus_clip",
        _V03RoutePlanner(_combined_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert result.diagnosis.claims[0].fault_type == "clipping"


@pytest.mark.asyncio
async def test_t_c_027_combined_dev_wav_supports_clip_and_even_order(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _store_dev_wav(repository, "d4a6f2b5e1370a49")

    def finish(context: PlannerContext) -> FinishDecision:
        clip_id = _evidence_by_metric_value(context, "clipping_mechanism", True)
        kind_id = _evidence_by_metric_value(context, "series_kind", "even_order_present")
        clip_eval = _evaluation(context, "rule_flat_top_absent", judgment="fail")
        thd_eval = _evaluation(context, "rule_thd_acceptable", judgment="fail")
        return FinishDecision(
            outcome="supported_fault",
            claims=(
                DiagnosisClaim(
                    claim_id="claim_d4a6_clip",
                    fault_type="clipping",
                    statement="Rematerialized combined clipping.",
                    evidence_refs=(clip_id,),
                    rule_refs=(clip_eval.evaluation_id,),
                ),
                DiagnosisClaim(
                    claim_id="claim_d4a6_h",
                    fault_type="harmonic_distortion",
                    statement="Rematerialized combined even-order structure.",
                    evidence_refs=(kind_id,),
                    rule_refs=(thd_eval.evaluation_id,),
                ),
            ),
            confidence_label="high",
        )

    result = await _run_v03_route(
        repository,
        signal_id,
        _V03RoutePlanner(_combined_steps(), finish),
    )
    assert result.termination_reason == "planner_finished"
    assert result.status == "success"
    assert result.diagnosis is not None
    assert {c.fault_type for c in result.diagnosis.claims} == {
        "clipping",
        "harmonic_distortion",
    }


def test_t_c_028_prompt_requires_substantial_clipping_rule_fail() -> None:
    text = _v03_prompt_spec().system_prompt  # type: ignore[attr-defined]
    assert "rule_clipping_ratio_acceptable" in text
    assert "rule_flat_top_absent" in text
    assert "substantial" in text.lower()
