"""T-CX129–T-CX132: three-arm runner behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.evaluation.contextual.baseline import ContextualFixedPipelineBaseline
from signal_diag.evaluation.contextual.models import ArmResult, ContextualManifest
from signal_diag.evaluation.contextual.runner import (
    run_contextual_arms,
    run_fixed_pipeline_case,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.signal.synthetic import (
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools.service import SignalToolService


def _baseline(
    repository: InMemorySignalRepository,
) -> ContextualFixedPipelineBaseline:
    profile_root = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "signal_diag"
        / "rules"
        / "profiles"
    )
    return ContextualFixedPipelineBaseline(
        repository=repository,
        tool_service=SignalToolService(repository),
        rule_engine=RuleEngine(),
        profile_loader=YamlRuleProfileLoader(
            {
                "profile_s1_distortion": profile_root / "s1_distortion_v1.yaml",
                "profile_s1_contextual_comparison": (
                    profile_root / "s1_contextual_comparison_v1.yaml"
                ),
            }
        ),
    )


def _request(
    *,
    signal_id: str,
    mode: str = "single_signal",
    reference_signal_id: str | None = None,
    nominal_hz: float | None = None,
) -> object:
    from signal_diag.evaluation.contextual.models import ContextualBaselineRequest

    return ContextualBaselineRequest(
        case_id="case_truth_free",
        signal_id=signal_id,
        stimulus_context=StimulusContext(
            mode=mode,  # type: ignore[arg-type]
            test_signal_id=signal_id,
            reference_signal_id=reference_signal_id,
            nominal_fundamental_hz=nominal_hz,
            stimulus_kind="single_tone" if nominal_hz is not None else None,
            assertion_source="evaluation_manifest",
        ),
    )


def _test_only_oracle(case: object, arm: str) -> ArmResult:
    expected = tuple(case.expected_causal_set)  # type: ignore[attr-defined]
    if arm == "no_context_ablation" and "harmonic_distortion" in expected:
        predicted = tuple(item for item in expected if item != "harmonic_distortion")
        outcome = "supported_fault" if predicted else "inconclusive"
    else:
        predicted = expected
        outcome = case.expected_outcome  # type: ignore[attr-defined]
    return ArmResult(
        case_id=case.case_id,  # type: ignore[attr-defined]
        arm=arm,  # type: ignore[arg-type]
        status="ok",
        predicted_outcome=outcome,
        predicted_causal_set=predicted,
        evidence_refs_complete=True,
    )


def test_t_cx197_fixed_pipeline_request_excludes_truth_fields() -> None:
    from signal_diag.evaluation.contextual.models import ContextualBaselineRequest

    request = ContextualBaselineRequest(
        case_id="case_truth_free",
        signal_id="sig_test",
        stimulus_context=StimulusContext(
            mode="single_signal",
            test_signal_id="sig_test",
            assertion_source="evaluation_manifest",
        ),
    )

    assert set(request.model_dump()) == {
        "case_id",
        "signal_id",
        "stimulus_context",
    }
    for forbidden in (
        "expected_outcome",
        "expected_causal_set",
        "role",
        "confidence_tier",
        "transform_identity",
    ):
        assert forbidden not in request.model_dump()


def test_t_cx198_truth_free_baseline_is_public_harness_api() -> None:
    from signal_diag.evaluation.contextual import (
        ContextualBaselineRequest,
        ContextualFixedPipelineBaseline,
    )

    assert ContextualBaselineRequest.__name__ == "ContextualBaselineRequest"
    assert ContextualFixedPipelineBaseline.__name__ == (
        "ContextualFixedPipelineBaseline"
    )


@pytest.mark.asyncio
async def test_t_cx199_fixed_pipeline_rejects_manifest_case(
    validation_manifest: ContextualManifest,
) -> None:
    with pytest.raises(TypeError, match="ContextualBaselineRequest"):
        await run_fixed_pipeline_case(  # type: ignore[arg-type]
            validation_manifest.cases[0]
        )


def test_t_cx200_fixed_pipeline_source_has_no_truth_access() -> None:
    source = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "signal_diag"
        / "evaluation"
        / "contextual"
        / "baseline.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "expected_outcome",
        "expected_causal_set",
        "confidence_tier",
        "transform_identity",
        ".role",
    ):
        assert forbidden not in source


@pytest.mark.asyncio
async def test_t_cx201_fixed_pipeline_clean_uses_real_evidence() -> None:
    repository = InMemorySignalRepository()
    clean = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    repository.put(clean.record)

    result = await _baseline(repository).run(
        _request(signal_id=clean.record.meta.signal_id)  # type: ignore[arg-type]
    )

    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "no_supported_fault"
    assert {item.source_tool for item in result.evidence} == {
        "detect_clipping",
        "analyze_harmonic_distortion",
    }
    assert all(claim.evidence_refs for claim in result.diagnosis.claims)
    assert all(claim.rule_refs for claim in result.diagnosis.claims)


@pytest.mark.asyncio
async def test_t_cx202_fixed_pipeline_clipping_uses_substantial_gate() -> None:
    repository = InMemorySignalRepository()
    clipped = generate_clipped_sine(
        frequency_hz=440.0,
        duration_s=0.5,
        amplitude=1.0,
        clip_level=0.99,
    )
    repository.put(clipped.record)

    result = await _baseline(repository).run(
        _request(signal_id=clipped.record.meta.signal_id)  # type: ignore[arg-type]
    )

    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert {claim.fault_type for claim in result.diagnosis.claims} == {"clipping"}
    claim = result.diagnosis.claims[0]
    assert any(
        item.metric == "clipping_mechanism" and item.value is True
        for item in result.evidence
        if item.evidence_id in claim.evidence_refs
    )
    assert any(
        item.rule_id in {"rule_clipping_ratio_acceptable", "rule_flat_top_absent"}
        and item.judgment == "fail"
        for batch in result.rule_evaluation_batches
        for item in batch.evaluations
        if item.evaluation_id in claim.rule_refs
    )


@pytest.mark.asyncio
async def test_t_cx203_fixed_pipeline_paired_harmonic_uses_contextual_growth() -> None:
    repository = InMemorySignalRepository()
    reference = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    degraded = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.35},
        duration_s=0.5,
        fundamental_amplitude=0.5,
    )
    repository.put(reference.record)
    repository.put(degraded.record)

    result = await _baseline(repository).run(
        _request(
            signal_id=degraded.record.meta.signal_id,
            mode="paired_reference",
            reference_signal_id=reference.record.meta.signal_id,
        )  # type: ignore[arg-type]
    )

    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert {claim.fault_type for claim in result.diagnosis.claims} == {
        "harmonic_distortion"
    }
    assert any(
        item.rule_id == "rule_even_harmonic_growth_acceptable"
        and item.judgment == "fail"
        for batch in result.rule_evaluation_batches
        for item in batch.evaluations
    )


@pytest.mark.asyncio
async def test_t_cx204_fixed_pipeline_invalid_pair_is_inconclusive() -> None:
    repository = InMemorySignalRepository()
    reference = generate_sine(frequency_hz=220.0, duration_s=0.5, amplitude=0.5)
    test = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    repository.put(reference.record)
    repository.put(test.record)

    result = await _baseline(repository).run(
        _request(
            signal_id=test.record.meta.signal_id,
            mode="paired_reference",
            reference_signal_id=reference.record.meta.signal_id,
        )  # type: ignore[arg-type]
    )

    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.limitations


@pytest.mark.asyncio
async def test_t_cx205_nominal_harmonic_keeps_declaration_limitation() -> None:
    repository = InMemorySignalRepository()
    degraded = generate_harmonic_sine(
        fundamental_hz=440.0,
        harmonic_ratios={2: 0.35},
        duration_s=0.5,
        fundamental_amplitude=0.5,
    )
    repository.put(degraded.record)

    result = await _baseline(repository).run(
        _request(
            signal_id=degraded.record.meta.signal_id,
            mode="nominal_single_tone",
            nominal_hz=440.0,
        )  # type: ignore[arg-type]
    )

    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert {claim.fault_type for claim in result.diagnosis.claims} == {
        "harmonic_distortion"
    }
    assert any("declared single-tone" in item for item in result.diagnosis.limitations)


def test_t_cx129_three_arms_execute_once(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(
        validation_manifest, oracle=_test_only_oracle, execute_once=True
    )
    assert set(results) == {
        "contextual_agent",
        "fixed_pipeline",
        "no_context_ablation",
    }
    for arm_results in results.values():
        assert len(arm_results) == 20


@pytest.mark.asyncio
async def test_t_cx130_fixed_pipeline_is_conservative_on_domain_out() -> None:
    repository = InMemorySignalRepository()
    noise = generate_white_noise(duration_s=0.5, seed=130)
    repository.put(noise.record)
    result = await _baseline(repository).run(
        _request(signal_id=noise.record.meta.signal_id)  # type: ignore[arg-type]
    )
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert {claim.fault_type for claim in result.diagnosis.claims} == {
        "inconclusive"
    }


def test_t_cx131_ablation_cannot_claim_paired_harmonic(
    validation_manifest: ContextualManifest,
) -> None:
    results = run_contextual_arms(validation_manifest, oracle=_test_only_oracle)
    ablation = {
        item.case_id: item for item in results["no_context_ablation"]
    }
    harm = ablation["val_p_harm_1"]
    assert harm.predicted_outcome == "inconclusive"
    assert "harmonic_distortion" not in harm.predicted_causal_set


def test_t_cx132_ablation_uses_same_test_sha(
    validation_manifest: ContextualManifest,
) -> None:
    for slot in validation_manifest.paired_harmonic_slots:
        assert slot.contextual.test_wav_sha256 == slot.ablation.test_wav_sha256
