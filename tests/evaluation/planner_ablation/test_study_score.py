"""Study scoring chain: grounding, safety, and dual-arm conclusion."""

from __future__ import annotations

import pytest

from signal_diag.agent.models import (
    AgentRunResult,
    DiagnosisClaim,
    StructuredDiagnosis,
)
from signal_diag.evaluation.models import BaselineDiagnosis, BaselineRunResult
from signal_diag.evaluation.planner_ablation.decision import (
    StudyConclusion,
    StudyDecisionProtocol,
)
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
)
from signal_diag.evaluation.planner_ablation.models import (
    FixedPipelineOutcome,
    ProductSlotOutcome,
)
from signal_diag.evaluation.planner_ablation.scoring import (
    ScoringPopulationError,
    claim_population_denominator,
)
from signal_diag.evaluation.planner_ablation.study_score import (
    StudyOracleLabel,
    StudySlotKey,
    VerifiedStudyInput,
    build_study_comparison_metrics,
    content_digest,
    primary_quality_rate,
    project_fixed_outcome,
    project_product_outcome,
    score_planner_ablation_study,
    study_input_from_verified_manifest,
    unsupported_positive_claim_rate,
    verified_study_input,
    verify_study_input,
)
from signal_diag.tools.evidence import Evidence


def _protocol(**overrides: object) -> StudyDecisionProtocol:
    base = {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "non_inferiority_max_gap": 0.05,
        "material_improvement_ratio": 0.20,
        "n_unit": "scorable_slots",
        "advantage_endpoint": "quality",
    }
    base.update(overrides)
    return StudyDecisionProtocol(**base)  # type: ignore[arg-type]


_TEST_INPUT_IDENTITY = "a" * 64
_TEST_CODE_IDENTITY = "b" * 64


def _study(
    *,
    schedule: tuple[StudySlotKey, ...],
    oracle: tuple[StudyOracleLabel, ...],
    **protocol_kw: object,
) -> VerifiedStudyInput:
    return verified_study_input(
        protocol=_protocol(**protocol_kw),
        schedule=schedule,
        oracle=oracle,
        input_identity=_TEST_INPUT_IDENTITY,
        code_identity=_TEST_CODE_IDENTITY,
    )


def _product_slot(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "arm": "product_agent",
        "execution_identity": "product_campaign",
        "planner_class": "RealLLMPlanner",
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "scheduled": True,
        "mode": "single_signal",
        "case_id": "default_case",
    }
    base.update(fields)
    return base


def _fixed_slot(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "arm": "fixed_pipeline",
        "execution_identity": "product_campaign",
        "planner_class": "PlannerAblationFixedPipelineBaseline",
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "scheduled": True,
        "mode": "single_signal",
        "case_id": "default_case",
    }
    base.update(fields)
    return base


def _grounded_clip_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            evidence_id="ev_clip",
            call_id="call_1",
            source_tool="detect_clipping",
            metric="clipping_ratio",
            value=0.03,
            validity="valid",
            channel="mixdown",
        ),
    )


def _grounded_clip_claim() -> dict[str, object]:
    return {
        "claim_id": "c_clip",
        "fault_type": "clipping",
        "evidence_refs": ("ev_clip",),
        "rule_refs": (),
    }


def _dual_arm_slots(
    *,
    case_id: str = "clip_case",
    product_outcome: str = "supported_fault",
    fixed_outcome: str = "no_supported_fault",
    product_claims: tuple[dict[str, object], ...] | None = None,
    fixed_claims: tuple[dict[str, object], ...] | None = None,
    product_completed: bool = True,
    fixed_completed: bool = True,
) -> tuple[dict[str, object], dict[str, object]]:
    evidence = _grounded_clip_evidence()
    if product_claims is None:
        product_claims = (_grounded_clip_claim(),) if product_outcome == "supported_fault" else ()
    if fixed_claims is None:
        fixed_claims = (
            (
                {
                    "claim_id": "c_nf",
                    "fault_type": "no_supported_fault",
                    "evidence_refs": ("ev_clip",),
                    "rule_refs": (),
                },
            )
            if fixed_outcome == "no_supported_fault"
            else (_grounded_clip_claim(),)
        )
    product = _product_slot(
        case_id=case_id,
        completed_diagnosis=product_completed,
        diagnosis_outcome=product_outcome,
        evidence=evidence,
        claims=product_claims,
    )
    fixed = _fixed_slot(
        case_id=case_id,
        completed_diagnosis=fixed_completed,
        diagnosis_outcome=fixed_outcome,
        evidence=evidence,
        claims=fixed_claims,
    )
    return product, fixed


def test_multi_claim_grounding_counts_each_claim() -> None:
    evidence = (
        Evidence(
            evidence_id="ev_1",
            call_id="call_1",
            source_tool="detect_clipping",
            metric="clipping_ratio",
            value=0.02,
            validity="valid",
            channel="mixdown",
        ),
    )
    slots = (
        _product_slot(
            completed_diagnosis=True,
            evidence=evidence,
            claims=(
                {
                    "claim_id": "c1",
                    "fault_type": "clipping",
                    "evidence_refs": ("ev_1",),
                    "rule_refs": (),
                },
                {
                    "claim_id": "c2",
                    "fault_type": "harmonic_distortion",
                    "evidence_refs": ("ev_missing",),
                    "rule_refs": (),
                },
            ),
        ),
    )
    population = claim_population_denominator(slots)
    assert population.denominator == 2
    assert population.numerator == 1
    rate, safety_ok = unsupported_positive_claim_rate(slots)
    assert rate == 0.5
    assert safety_ok is False


def test_zero_claim_population_blocks_evaluable_population() -> None:
    key = StudySlotKey(case_id="c1", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="c1",
            mode="single_signal",
            expected_outcome="no_supported_fault",
            expected_causal_faults=(),
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    product = (
        _product_slot(
            case_id="c1",
            completed_diagnosis=True,
            claims=(),
            diagnosis_outcome="no_supported_fault",
        ),
    )
    fixed = (
        _fixed_slot(
            case_id="c1",
            completed_diagnosis=True,
            claims=(),
            diagnosis_outcome="no_supported_fault",
        ),
    )
    with pytest.raises(ScoringPopulationError):
        claim_population_denominator(product)
    built = build_study_comparison_metrics(
        study=study,
        product_slots=product,
        fixed_slots=fixed,
    )
    assert built.metrics.evaluable_population is False
    assert built.metrics.product_safety_ok is False
    assert built.metrics.fixed_safety_ok is False
    assert built.population_identity == content_digest((key,))


def test_behavioral_failure_stays_in_completion_denominator() -> None:
    slots = (
        _product_slot(completed_diagnosis=False, terminal_reached=True),
        _product_slot(completed_diagnosis=True, diagnosis_outcome="no_supported_fault", claims=()),
    )
    from signal_diag.evaluation.planner_ablation.scoring import (
        diagnosis_completion_rate,
    )

    completion = diagnosis_completion_rate(slots)
    assert completion.denominator == 2
    assert completion.numerator == 1


def test_empty_oracle_rejects_and_cannot_yield_fixed_dominance() -> None:
    key = StudySlotKey(case_id="a", mode="single_signal")
    with pytest.raises(ValueError, match="oracle must be non-empty"):
        VerifiedStudyInput(
            protocol=_protocol(),
            schedule=(key,),
            oracle=(),
            population_identity=content_digest((key,)),
            oracle_identity=_TEST_CODE_IDENTITY,
            input_identity=_TEST_INPUT_IDENTITY,
            code_identity=_TEST_CODE_IDENTITY,
        )
    product, fixed = _dual_arm_slots()
    with pytest.raises(ValueError):
        score_planner_ablation_study(
            study=VerifiedStudyInput.model_construct(
                protocol=_protocol(),
                schedule=(key,),
                oracle=(),
                population_identity=content_digest((key,)),
                oracle_identity=_TEST_CODE_IDENTITY,
                input_identity=_TEST_INPUT_IDENTITY,
                code_identity=_TEST_CODE_IDENTITY,
            ),
            product_slots=(product,),
            fixed_slots=(fixed,),
            fixed_latency_improvement_ratio=0.25,
        )


def test_incomplete_oracle_cover_rejects() -> None:
    keys = (
        StudySlotKey(case_id="a", mode="single_signal"),
        StudySlotKey(case_id="b", mode="single_signal"),
    )
    oracle = (
        StudyOracleLabel(
            case_id="a",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    with pytest.raises(ValueError, match="oracle missing"):
        _study(schedule=keys, oracle=oracle)


def test_quality_failure_stays_in_primary_denominator() -> None:
    keys = (
        StudySlotKey(case_id="a", mode="single_signal"),
        StudySlotKey(case_id="b", mode="single_signal"),
    )
    oracle = (
        StudyOracleLabel(
            case_id="a",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
        StudyOracleLabel(
            case_id="b",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    oracle_index = {label.slot_key: label for label in oracle}
    ok, fail = _dual_arm_slots(case_id="a"), _dual_arm_slots(case_id="b")
    product_ok = ok[0]
    product_fail = {
        **fail[0],
        "completed_diagnosis": False,
    }
    rate = primary_quality_rate(
        (product_ok, product_fail),
        oracle_index,
        schedule=keys,
    )
    assert rate.numerator == 1
    assert rate.denominator == 2
    assert rate.value == 0.5

    from signal_diag.evaluation.planner_ablation.study_score import (
        _schedule_diagnosis_completion_rate,
    )

    completion = _schedule_diagnosis_completion_rate((product_ok, product_fail))
    assert completion == 0.5


def test_duplicate_schedule_oracle_and_slot_keys_reject() -> None:
    dup_key = StudySlotKey(case_id="a", mode="single_signal")
    with pytest.raises(ValueError, match="duplicate schedule"):
        _study(
            schedule=(dup_key, dup_key),
            oracle=(
                StudyOracleLabel(
                    case_id="a",
                    mode="single_signal",
                    expected_outcome="no_supported_fault",
                ),
            ),
        )
    with pytest.raises(ValueError, match="duplicate oracle"):
        _study(
            schedule=(dup_key,),
            oracle=(
                StudyOracleLabel(
                    case_id="a",
                    mode="single_signal",
                    expected_outcome="no_supported_fault",
                ),
                StudyOracleLabel(
                    case_id="a",
                    mode="single_signal",
                    expected_outcome="supported_fault",
                    expected_causal_faults=("clipping",),
                ),
            ),
        )
    study = _study(
        schedule=(dup_key,),
        oracle=(
            StudyOracleLabel(
                case_id="a",
                mode="single_signal",
                expected_outcome="supported_fault",
                expected_causal_faults=("clipping",),
            ),
        ),
    )
    slot = _dual_arm_slots()[0]
    with pytest.raises(ValueError, match="duplicate slot"):
        build_study_comparison_metrics(
            study=study,
            product_slots=(slot, slot),
            fixed_slots=_dual_arm_slots()[1:],
        )


def test_missing_slot_and_arm_case_set_mismatch_reject() -> None:
    key_a = StudySlotKey(case_id="a", mode="single_signal")
    key_b = StudySlotKey(case_id="b", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="a",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
        StudyOracleLabel(
            case_id="b",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    study = _study(schedule=(key_a, key_b), oracle=oracle)
    product_a, fixed_a = _dual_arm_slots(case_id="a")
    with pytest.raises(ValueError, match="missing scheduled"):
        build_study_comparison_metrics(
            study=study,
            product_slots=(product_a,),
            fixed_slots=(fixed_a, _dual_arm_slots(case_id="b")[1]),
        )
    product_b, fixed_b = _dual_arm_slots(case_id="b")
    with pytest.raises(ValueError, match="not in schedule"):
        build_study_comparison_metrics(
            study=study,
            product_slots=(product_a, product_b, _product_slot(case_id="extra")),
            fixed_slots=(fixed_a, fixed_b),
        )


def test_conclusion_planner_advantage_unique() -> None:
    key = StudySlotKey(case_id="clip_case", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="clip_case",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    evidence = _grounded_clip_evidence()
    product, fixed = _dual_arm_slots(
        product_outcome="supported_fault",
        fixed_outcome="no_supported_fault",
        fixed_claims=(_grounded_clip_claim(),),
    )
    fixed = {
        **fixed,
        "evidence": evidence,
    }
    product = {
        **product,
        "evidence": evidence,
    }
    conclusion = score_planner_ablation_study(
        study=study,
        product_slots=(product,),
        fixed_slots=(fixed,),
        fixed_latency_improvement_ratio=0.0,
    )
    assert conclusion == StudyConclusion.PLANNER_ADVANTAGE


def test_conclusion_fixed_pipeline_dominance_unique() -> None:
    key = StudySlotKey(case_id="clip_case", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="clip_case",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    product, fixed = _dual_arm_slots(
        product_outcome="supported_fault",
        fixed_outcome="supported_fault",
    )
    conclusion = score_planner_ablation_study(
        study=study,
        product_slots=(product,),
        fixed_slots=(fixed,),
        fixed_latency_improvement_ratio=0.25,
    )
    assert conclusion == StudyConclusion.FIXED_PIPELINE_DOMINANCE


def test_zero_positive_claims_block_dominance() -> None:
    key = StudySlotKey(case_id="clip_case", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="clip_case",
            mode="single_signal",
            expected_outcome="no_supported_fault",
            expected_causal_faults=(),
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    evidence = _grounded_clip_evidence()
    nf_claim = (
        {
            "claim_id": "c_nf",
            "fault_type": "no_supported_fault",
            "evidence_refs": ("ev_clip",),
            "rule_refs": (),
        },
    )
    product = _product_slot(
        case_id="clip_case",
        completed_diagnosis=True,
        diagnosis_outcome="no_supported_fault",
        evidence=evidence,
        claims=nf_claim,
    )
    fixed = _fixed_slot(
        case_id="clip_case",
        completed_diagnosis=True,
        diagnosis_outcome="no_supported_fault",
        evidence=evidence,
        claims=nf_claim,
    )
    conclusion = score_planner_ablation_study(
        study=study,
        product_slots=(product,),
        fixed_slots=(fixed,),
        fixed_latency_improvement_ratio=0.25,
    )
    assert conclusion == StudyConclusion.INSUFFICIENT_EVIDENCE


def test_conclusion_insufficient_evidence_safety_fail_unique() -> None:
    key = StudySlotKey(case_id="clip_case", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="clip_case",
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    evidence = _grounded_clip_evidence()
    product = _product_slot(
        case_id="clip_case",
        completed_diagnosis=True,
        diagnosis_outcome="supported_fault",
        evidence=evidence,
        claims=(
            _grounded_clip_claim(),
            {
                "claim_id": "c_bad",
                "fault_type": "harmonic_distortion",
                "evidence_refs": ("ev_missing",),
                "rule_refs": (),
            },
        ),
    )
    fixed = _dual_arm_slots()[1]
    conclusion = score_planner_ablation_study(
        study=study,
        product_slots=(product,),
        fixed_slots=(fixed,),
        fixed_latency_improvement_ratio=0.25,
    )
    assert conclusion == StudyConclusion.INSUFFICIENT_EVIDENCE


def test_project_product_and_fixed_outcome_into_scoring_slots() -> None:
    evidence = _grounded_clip_evidence()
    diagnosis = StructuredDiagnosis(
        run_id="run_test",
        task_type="distortion_analysis",
        outcome="supported_fault",
        claims=(
                DiagnosisClaim(
                    claim_id="claim_clip",
                    fault_type="clipping",
                    statement="clip",
                    evidence_refs=("ev_clip",),
                    rule_refs=(),
                ),
        ),
        confidence_label="medium",
        limitations=(),
        termination_reason="planner_finished",
        tool_call_count=1,
    )
    agent_result = AgentRunResult(
        run_id="run_test",
        status="success",
        diagnosis=diagnosis,
        observations=(),
        evidence=evidence,
        tool_history=(),
        termination_reason="planner_finished",
        rule_evaluation_batches=(),
    )
    product_outcome = ProductSlotOutcome(
        run_id="run_test",
        mode="single_signal",
        terminal_status="completed",
        result=agent_result,
        planner_class="RealLLMPlanner",
        execution_identity="product_campaign",
    )
    product_slot = project_product_outcome(product_outcome, case_id="clip_case")
    assert product_slot["completed_diagnosis"] is True
    assert product_slot["diagnosis_outcome"] == "supported_fault"

    baseline = BaselineRunResult(
        run_id="baseline_test",
        status="success",
        diagnosis=BaselineDiagnosis(
            run_id="baseline_test",
            outcome="no_supported_fault",
            claims=(),
            confidence_label="medium",
            tool_call_count=1,
            rule_evaluation_batches=(),
        ),
        observations=(),
        evidence=evidence,
        tool_history=(),
        completion_reason="baseline_completed",
        rule_evaluation_batches=(),
    )
    fixed_outcome = FixedPipelineOutcome(
        case_id="clip_case",
        mode="single_signal",
        baseline_result=baseline,
    )
    fixed_slot = project_fixed_outcome(fixed_outcome)
    assert fixed_slot["arm"] == "fixed_pipeline"
    assert fixed_slot["case_id"] == "clip_case"


def test_project_fixed_inconclusive_counts_as_completed() -> None:
    evidence = _grounded_clip_evidence()
    baseline = BaselineRunResult(
        run_id="baseline_inconclusive",
        status="inconclusive",
        diagnosis=BaselineDiagnosis(
            run_id="baseline_inconclusive",
            outcome="inconclusive",
            claims=(),
            confidence_label="low",
            tool_call_count=1,
            rule_evaluation_batches=(),
        ),
        observations=(),
        evidence=evidence,
        tool_history=(),
        completion_reason="insufficient_evidence",
        rule_evaluation_batches=(),
    )
    slot = project_fixed_outcome(
        FixedPipelineOutcome(
            case_id="noise_case",
            mode="single_signal",
            baseline_result=baseline,
        )
    )
    assert slot["completed_diagnosis"] is True
    assert slot["diagnosis_outcome"] == "inconclusive"


def test_project_fixed_true_failure_not_completed() -> None:
    baseline = BaselineRunResult(
        run_id="baseline_failed",
        status="error",
        diagnosis=None,
        observations=(),
        evidence=(),
        tool_history=(),
        completion_reason="runtime_error",
        rule_evaluation_batches=(),
    )
    slot = project_fixed_outcome(
        FixedPipelineOutcome(
            case_id="fail_case",
            mode="single_signal",
            baseline_result=baseline,
        )
    )
    assert slot["completed_diagnosis"] is False


def test_descheduled_slot_rejects_at_score() -> None:
    key = StudySlotKey(case_id="a", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="a",
            mode="single_signal",
            expected_outcome="no_supported_fault",
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    product, fixed = _dual_arm_slots(case_id="a")
    product = {**product, "scheduled": False}
    with pytest.raises(ValueError, match="descheduled"):
        build_study_comparison_metrics(
            study=study,
            product_slots=(product,),
            fixed_slots=(fixed,),
        )


def test_oracle_identity_binds_content() -> None:
    key = StudySlotKey(case_id="a", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="a",
            mode="single_signal",
            expected_outcome="no_supported_fault",
        ),
    )
    with pytest.raises(ValueError, match="oracle_identity"):
        VerifiedStudyInput(
            protocol=_protocol(),
            schedule=(key,),
            oracle=oracle,
            population_identity=content_digest((key,)),
            oracle_identity="c" * 64,
            input_identity=_TEST_INPUT_IDENTITY,
            code_identity=_TEST_CODE_IDENTITY,
        )


def test_study_input_from_verified_manifest_round_trip() -> None:
    key = StudySlotKey(case_id="m1", mode="paired_reference")
    oracle = (
        StudyOracleLabel(
            case_id="m1",
            mode="paired_reference",
            expected_outcome="inconclusive",
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    manifest: dict[str, object] = {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "decision_protocol": study.protocol.model_dump(),
        "schedule": [key.model_dump()],
        "oracle": [oracle[0].model_dump()],
        "population_identity": study.population_identity,
        "oracle_identity": study.oracle_identity,
        "input_identity": study.input_identity,
        "code_identity": study.code_identity,
    }
    parsed = study_input_from_verified_manifest(manifest)
    assert parsed == study


def test_study_input_from_verified_manifest_rejects_tampered_oracle() -> None:
    key = StudySlotKey(case_id="m1", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="m1",
            mode="single_signal",
            expected_outcome="no_supported_fault",
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    manifest: dict[str, object] = {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "decision_protocol": study.protocol.model_dump(),
        "schedule": [key.model_dump()],
        "oracle": [
            {
                **oracle[0].model_dump(),
                "expected_outcome": "supported_fault",
                "expected_causal_faults": ("clipping",),
            }
        ],
        "population_identity": study.population_identity,
        "oracle_identity": study.oracle_identity,
        "input_identity": study.input_identity,
        "code_identity": study.code_identity,
    }
    with pytest.raises(ValueError, match="oracle_identity"):
        study_input_from_verified_manifest(manifest)


def test_study_input_from_verified_manifest_rejects_protocol_mismatch() -> None:
    key = StudySlotKey(case_id="m1", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="m1",
            mode="single_signal",
            expected_outcome="no_supported_fault",
        ),
    )
    study = _study(schedule=(key,), oracle=oracle)
    protocol = study.protocol.model_dump()
    protocol["study_id"] = "study_foreign"
    manifest: dict[str, object] = {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "decision_protocol": protocol,
        "schedule": [key.model_dump()],
        "oracle": [oracle[0].model_dump()],
        "population_identity": study.population_identity,
        "oracle_identity": study.oracle_identity,
        "input_identity": study.input_identity,
        "code_identity": study.code_identity,
    }
    with pytest.raises(ValueError, match="protocol identity mismatch"):
        study_input_from_verified_manifest(manifest)


def test_verify_study_input_rejects_foreign_protocol() -> None:
    key = StudySlotKey(case_id="c1", mode="single_signal")
    oracle = (
        StudyOracleLabel(
            case_id="c1",
            mode="single_signal",
            expected_outcome="no_supported_fault",
        ),
    )
    study = VerifiedStudyInput.model_construct(
        protocol=_protocol(study_id="foreign"),
        schedule=(key,),
        oracle=oracle,
        population_identity=content_digest((key,)),
        oracle_identity=content_digest(oracle),
        input_identity=_TEST_INPUT_IDENTITY,
        code_identity=_TEST_CODE_IDENTITY,
    )
    with pytest.raises(ValueError, match="foreign study"):
        verify_study_input(study)


@pytest.mark.asyncio
async def test_baseline_inconclusive_integration_scores_completed(
    repository: object,
) -> None:
    from signal_diag.signal.repository import InMemorySignalRepository
    from signal_diag.signal.synthetic import generate_sine, generate_white_noise
    from tests.evaluation.planner_ablation.test_matched_gates import (
        _request,
        _study_baseline,
    )

    repo = repository
    assert isinstance(repo, InMemorySignalRepository)
    baseline_runner = _study_baseline(repo)

    noise = generate_white_noise(duration_s=0.5, seed=287)
    repo.put(noise.record)
    single_baseline = await baseline_runner.run(
        _request(
            case_id="single_inconclusive",
            signal_id=noise.record.meta.signal_id,
            mode="single_signal",
        )
    )
    reference = generate_sine(frequency_hz=440.0, duration_s=0.5, amplitude=0.5)
    paired_noise = generate_white_noise(duration_s=0.5, seed=288)
    repo.put(reference.record)
    repo.put(paired_noise.record)
    paired_baseline = await baseline_runner.run(
        _request(
            case_id="paired_inconclusive",
            signal_id=paired_noise.record.meta.signal_id,
            mode="paired_reference",
            reference_signal_id=reference.record.meta.signal_id,
        )
    )

    schedule = (
        StudySlotKey(case_id="single_inconclusive", mode="single_signal"),
        StudySlotKey(case_id="paired_inconclusive", mode="paired_reference"),
    )
    oracle = (
        StudyOracleLabel(
            case_id="single_inconclusive",
            mode="single_signal",
            expected_outcome="inconclusive",
        ),
        StudyOracleLabel(
            case_id="paired_inconclusive",
            mode="paired_reference",
            expected_outcome="inconclusive",
        ),
    )
    study = _study(schedule=schedule, oracle=oracle)

    fixed_slots: list[dict[str, object]] = []
    product_slots: list[dict[str, object]] = []
    for case_id, mode, baseline_result in (
        ("single_inconclusive", "single_signal", single_baseline),
        ("paired_inconclusive", "paired_reference", paired_baseline),
    ):
        assert baseline_result.diagnosis is not None
        assert baseline_result.diagnosis.outcome == "inconclusive"
        fixed = project_fixed_outcome(
            FixedPipelineOutcome(
                case_id=case_id,
                mode=mode,  # type: ignore[arg-type]
                baseline_result=baseline_result,
            )
        )
        assert fixed["completed_diagnosis"] is True
        fixed_slots.append(fixed)
        product_slots.append(
            {
                **fixed,
                "arm": "product_agent",
                "planner_class": "RealLLMPlanner",
            }
        )

    built = build_study_comparison_metrics(
        study=study,
        product_slots=product_slots,
        fixed_slots=fixed_slots,
    )
    assert built.metrics.product_completion == 1.0
    assert built.metrics.fixed_completion == 1.0
    assert built.metrics.product_primary_quality == 1.0
    assert built.metrics.fixed_primary_quality == 1.0
