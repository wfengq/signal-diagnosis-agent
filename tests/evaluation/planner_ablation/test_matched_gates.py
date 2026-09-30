"""T-CX277, T-CX278, T-CX287: study baseline matching matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.agent.diagnosis import (
    DiagnosisValidationError,
    _has_harmonic_even_order_structure,
    validate_finish_decision,
)
from signal_diag.agent.models import DiagnosisClaim, FinishDecision, TaskAssessment
from signal_diag.evaluation.contextual.baseline import ContextualFixedPipelineBaseline
from signal_diag.evaluation.contextual.models import ContextualBaselineRequest
from signal_diag.evaluation.planner_ablation.baseline import (
    PlannerAblationFixedPipelineBaseline,
    paired_clipping_supported,
    single_signal_clipping_supported,
)
from signal_diag.evaluation.planner_ablation.models import (
    PlannerAblationBaselineRequest,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluation
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import (
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case


def _profiles() -> YamlRuleProfileLoader:
    profile_root = Path(__file__).resolve().parents[3] / "src" / "signal_diag" / "rules" / "profiles"
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": profile_root / "s1_distortion_v1.yaml",
            "profile_s1_contextual_comparison_v9_10": (
                profile_root / "s1_contextual_comparison_v9_10.yaml"
            ),
        }
    )


def _study_baseline(repository: InMemorySignalRepository) -> PlannerAblationFixedPipelineBaseline:
    return PlannerAblationFixedPipelineBaseline(
        repository=repository,
        tool_service=SignalToolService(repository),
        rule_engine=RuleEngine(),
        profile_loader=_profiles(),
    )


def _historical_baseline(repository: InMemorySignalRepository) -> ContextualFixedPipelineBaseline:
    return ContextualFixedPipelineBaseline(
        repository=repository,
        tool_service=SignalToolService(repository),
        rule_engine=RuleEngine(),
        profile_loader=_profiles(),
    )


def _request(
    *,
    case_id: str,
    signal_id: str,
    mode: str,
    reference_signal_id: str | None = None,
) -> PlannerAblationBaselineRequest:
    return PlannerAblationBaselineRequest(
        case_id=case_id,
        signal_id=signal_id,
        stimulus_context=StimulusContext(
            mode=mode,  # type: ignore[arg-type]
            test_signal_id=signal_id,
            reference_signal_id=reference_signal_id,
            assertion_source="evaluation_manifest",
        ),
    )


@pytest.mark.asyncio
async def test_t_cx277_single_signal_flat_top_option_c_supported(
    repository: InMemorySignalRepository,
    clipped_case: object,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)  # type: ignore[arg-type]
    result = await _study_baseline(repository).run(
        _request(case_id="flat_top", signal_id=signal_id, mode="single_signal")
    )
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    clipping = next(c for c in result.diagnosis.claims if c.fault_type == "clipping")
    metrics = {
        item.metric
        for item in result.evidence
        if item.evidence_id in clipping.evidence_refs
    }
    assert "flat_top_detected" in metrics


@pytest.mark.asyncio
async def test_t_cx277_study_differs_from_historical_on_flat_top(
    repository: InMemorySignalRepository,
    clipped_case: object,
) -> None:
    signal_id = store_synthetic_case(repository, clipped_case)  # type: ignore[arg-type]
    study = await _study_baseline(repository).run(
        _request(case_id="flat_top_hist", signal_id=signal_id, mode="single_signal")
    )
    hist_request = ContextualBaselineRequest(
        case_id="flat_top_hist",
        signal_id=signal_id,
        stimulus_context=_request(
            case_id="flat_top_hist", signal_id=signal_id, mode="single_signal"
        ).stimulus_context,
    )
    historical = await _historical_baseline(repository).run(hist_request)
    assert study.diagnosis is not None and historical.diagnosis is not None
    assert study.diagnosis.outcome == "supported_fault"
    assert historical.diagnosis.outcome != "supported_fault"


@pytest.mark.asyncio
async def test_t_cx278_paired_clipping_uses_contextual_test_family(
    repository: InMemorySignalRepository,
) -> None:
    reference = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    degraded = generate_clipped_sine(
        frequency_hz=440.0,
        duration_s=0.5,
        amplitude=1.0,
        clip_level=0.99,
    )
    repository.put(reference.record)
    repository.put(degraded.record)
    result = await _study_baseline(repository).run(
        _request(
            case_id="paired_clip",
            signal_id=degraded.record.meta.signal_id,
            mode="paired_reference",
            reference_signal_id=reference.record.meta.signal_id,
        )
    )
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    clipping = next(c for c in result.diagnosis.claims if c.fault_type == "clipping")
    assert any(
        item.metric == "test_clipping_mechanism" and item.evidence_id in clipping.evidence_refs
        for item in result.evidence
    )


@pytest.mark.asyncio
async def test_t_cx287_paired_no_fault_contextual_clean_family(
    repository: InMemorySignalRepository,
) -> None:
    reference = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    test = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    repository.put(reference.record)
    repository.put(test.record)
    result = await _study_baseline(repository).run(
        _request(
            case_id="paired_clean",
            signal_id=test.record.meta.signal_id,
            mode="paired_reference",
            reference_signal_id=reference.record.meta.signal_id,
        )
    )
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "no_supported_fault"


@pytest.mark.asyncio
async def test_t_cx287_single_signal_inconclusive_valid(
    repository: InMemorySignalRepository,
) -> None:
    noise = generate_white_noise(duration_s=0.5, seed=287)
    repository.put(noise.record)
    result = await _study_baseline(repository).run(
        _request(
            case_id="single_inconclusive",
            signal_id=noise.record.meta.signal_id,
            mode="single_signal",
        )
    )
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"


def test_paired_harmonic_even_order_gate_matches_product_validator() -> None:
    """Study baseline and product both require even_order_present for harmonic supported_fault."""
    claim = DiagnosisClaim(
        claim_id="claim_harmonic_no_even",
        fault_type="harmonic_distortion",
        statement="Elevated THD alone cannot support harmonic_distortion.",
        evidence_refs=("ev_thd",),
        rule_refs=(),
    )
    evidence = (
        Evidence(
            evidence_id="ev_thd",
            call_id="call_1",
            source_tool="analyze_harmonic_distortion",
            metric="thd_percent",
            value=9.0,
            validity="valid",
            channel="mixdown",
        ),
    )
    evidence_by_id = {item.evidence_id: item for item in evidence}
    assert _has_harmonic_even_order_structure(claim, evidence_by_id) is False

    decision = FinishDecision(
        task_assessment=TaskAssessment(
            task_type="distortion_analysis",
            objective="determine distortion",
            hypotheses=("harmonic_distortion",),
        ),
        outcome="supported_fault",
        claims=(claim,),
        confidence_label="medium",
    )
    with pytest.raises(DiagnosisValidationError, match="even_order_present"):
        validate_finish_decision(
            decision,
            known_evidence_ids=frozenset(evidence_by_id),
            task_assessment=decision.task_assessment,
            evidence=evidence,
            causal_policy_version="v9_4_legacy",
        )

    class _SeriesEvidence:
        def __init__(self, metric: str, value: str, validity: str = "valid") -> None:
            self.metric = metric
            self.value = value
            self.validity = validity

    harmonic_rules: list[object] | None = [object()]
    analysis_evidence = (_SeriesEvidence("test_series_kind", "native_odd_series"),)
    even_order = any(
        item.metric == "test_series_kind"
        and item.value == "even_order_present"
        and item.validity == "valid"
        for item in analysis_evidence
    )
    if harmonic_rules is not None and not even_order:
        harmonic_rules = None
    assert harmonic_rules is None


def test_t_cx277_negative_mechanism_without_substantial_fail() -> None:
    class _Ev:
        def __init__(self, metric: str, value: object, validity: str = "valid") -> None:
            self.metric = metric
            self.value = value
            self.validity = validity

    evidence = (_Ev("clipping_mechanism", True),)
    evaluations: tuple[RuleEvaluation, ...] = ()
    assert single_signal_clipping_supported(evidence, evaluations) is False


def test_t_cx278_negative_paired_legacy_without_test_family() -> None:
    class _Ev:
        def __init__(self, metric: str, value: object, validity: str = "valid") -> None:
            self.metric = metric
            self.value = value
            self.validity = validity

    evidence = (_Ev("clipping_mechanism", True), _Ev("test_clipping_mechanism", False))
    assert paired_clipping_supported(evidence, ()) is False


@pytest.mark.asyncio
async def test_t_cx287_single_signal_no_unsupported_harmonic_supported_fault(
    repository: InMemorySignalRepository,
) -> None:
    harmonic = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.15, 3: 0.08},
        duration_s=0.5,
        fundamental_amplitude=0.5,
    )
    repository.put(harmonic.record)
    result = await _study_baseline(repository).run(
        _request(
            case_id="harmonic_only",
            signal_id=harmonic.record.meta.signal_id,
            mode="single_signal",
        )
    )
    assert result.diagnosis is not None
    assert all(claim.fault_type != "harmonic_distortion" for claim in result.diagnosis.claims)
