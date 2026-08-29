"""Checkpoint H — public evaluation models (T125–T132)."""

from __future__ import annotations

from collections.abc import Callable
from math import inf, nan
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from signal_diag.evaluation.models import (
    ClippedSineSignalSpec,
    CombinedDistortionSignalSpec,
    CombinedIdentifiabilitySpec,
    DatasetManifest,
    DatasetValidationIssue,
    DatasetValidationReport,
    EvaluationCase,
    EvidenceCondition,
    HarmonicRatioSpec,
    HarmonicSineSignalSpec,
    RunScore,
    SineSignalSpec,
    SyntheticSignalSpec,
    WhiteNoiseSignalSpec,
)
from tests.evaluation.conftest import (
    make_condition,
    make_dataset_manifest,
    make_evaluation_case,
    make_sufficient_set,
)

SIGNAL_SPEC_ADAPTER = TypeAdapter(SyntheticSignalSpec)


def test_t125_manifest_identity_and_immutability() -> None:
    manifest = make_dataset_manifest()
    assert manifest.schema_version == "1.0"
    assert manifest.version == "1.0.0"
    assert isinstance(manifest.cases, tuple)
    assert isinstance(manifest.cases[0].observable_conditions, tuple)
    with pytest.raises(ValidationError):
        manifest.dataset_id = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        make_dataset_manifest(schema_version="2.0")
    with pytest.raises(ValidationError):
        make_dataset_manifest(version="1.0")


def test_t126_signal_spec_discriminator() -> None:
    parsed = SIGNAL_SPEC_ADAPTER.validate_python(
        {"generator": "sine", "frequency_hz": 200.0}
    )
    assert isinstance(parsed, SineSignalSpec)
    clipped = SIGNAL_SPEC_ADAPTER.validate_python(
        {"generator": "clipped_sine", "frequency_hz": 200.0, "clip_level": 0.5}
    )
    assert isinstance(clipped, ClippedSineSignalSpec)
    harmonic = SIGNAL_SPEC_ADAPTER.validate_python(
        {
            "generator": "harmonic_sine",
            "fundamental_hz": 200.0,
            "harmonic_ratios": [{"order": 2, "ratio": 0.1}],
        }
    )
    assert isinstance(harmonic, HarmonicSineSignalSpec)
    combined = SIGNAL_SPEC_ADAPTER.validate_python(
        {
            "generator": "combined_distortion",
            "fundamental_hz": 200.0,
            "harmonic_ratios": [{"order": 2, "ratio": 0.1}],
            "clip_level": 0.5,
        }
    )
    assert isinstance(combined, CombinedDistortionSignalSpec)
    noise = SIGNAL_SPEC_ADAPTER.validate_python({"generator": "white_noise"})
    assert isinstance(noise, WhiteNoiseSignalSpec)
    with pytest.raises(ValidationError):
        SIGNAL_SPEC_ADAPTER.validate_python(
            {"generator": "square", "frequency_hz": 200.0}
        )


@pytest.mark.parametrize(
    "factory, kwargs",
    [
        (SineSignalSpec, {"frequency_hz": 0.0}),
        (SineSignalSpec, {"frequency_hz": -1.0}),
        (SineSignalSpec, {"frequency_hz": inf}),
        (SineSignalSpec, {"frequency_hz": nan}),
        (SineSignalSpec, {"frequency_hz": 200.0, "sample_rate_hz": 0}),
        (SineSignalSpec, {"frequency_hz": 200.0, "duration_s": 0.0}),
        (SineSignalSpec, {"frequency_hz": 200.0, "amplitude": 0.0}),
        (SineSignalSpec, {"frequency_hz": 200.0, "amplitude": 1.1}),
        (ClippedSineSignalSpec, {"frequency_hz": 200.0, "clip_level": 0.0}),
        (ClippedSineSignalSpec, {"frequency_hz": 200.0, "clip_level": 1.1}),
        (WhiteNoiseSignalSpec, {"rms": 0.0}),
        (WhiteNoiseSignalSpec, {"rms": inf}),
    ],
)
def test_t127_signal_parameter_validation(
    factory: type[object],
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        factory(**kwargs)  # type: ignore[misc]


@pytest.mark.parametrize(
    "harmonic_ratios",
    [
        (),
        (HarmonicRatioSpec(order=2, ratio=0.0),),
        (
            HarmonicRatioSpec(order=2, ratio=0.1),
            HarmonicRatioSpec(order=2, ratio=0.2),
        ),
    ],
)
def test_t128_harmonic_ratio_validation(
    harmonic_ratios: tuple[HarmonicRatioSpec, ...],
) -> None:
    with pytest.raises(ValidationError):
        HarmonicRatioSpec(order=1, ratio=0.1)
    with pytest.raises(ValidationError):
        HarmonicRatioSpec(order=2, ratio=-0.1)
    with pytest.raises(ValidationError):
        HarmonicRatioSpec(order=2, ratio=inf)
    with pytest.raises(ValidationError):
        HarmonicSineSignalSpec(
            fundamental_hz=200.0,
            harmonic_ratios=harmonic_ratios,
        )
    with pytest.raises(ValidationError):
        CombinedDistortionSignalSpec(
            fundamental_hz=200.0,
            harmonic_ratios=harmonic_ratios,
            clip_level=0.5,
        )
    valid = HarmonicSineSignalSpec(
        fundamental_hz=200.0,
        harmonic_ratios=(
            HarmonicRatioSpec(order=2, ratio=0.0),
            HarmonicRatioSpec(order=3, ratio=0.1),
        ),
    )
    assert valid.harmonic_ratios[1].order == 3


def test_t129_evidence_condition_strictness() -> None:
    true_condition = make_condition(
        expected_value=True,
        comparator="eq",
        metric="clipping_detected",
        supports_claims=("clipping",),
    )
    int_condition = make_condition(
        condition_id="cond_count",
        expected_value=1,
        comparator="eq",
        metric="clipped_samples",
        supports_claims=("clipping",),
    )
    assert true_condition.expected_value is True
    assert type(true_condition.expected_value) is bool
    assert type(int_condition.expected_value) is int
    assert not (
        type(true_condition.expected_value) is type(int_condition.expected_value)
        and true_condition.expected_value == int_condition.expected_value
    )
    with pytest.raises(ValidationError):
        make_condition(tool_name="unknown_tool")
    with pytest.raises(ValidationError):
        make_condition(metric="")
    with pytest.raises(ValidationError):
        make_condition(validity="invalid")
    with pytest.raises(ValidationError):
        make_condition(comparator="approx")
    with pytest.raises(ValidationError):
        EvidenceCondition(
            condition_id="cond_extra",
            tool_name="detect_clipping",
            metric="clipping_ratio",
            validity="valid",
            comparator="lte",
            expected_value=0.01,
            unexpected_field=True,  # type: ignore[call-arg]
        )


def _rebuild_case(case: EvaluationCase, **overrides: Any) -> EvaluationCase:
    payload = case.model_dump()
    payload.update(overrides)
    return EvaluationCase.model_validate(payload)


def _mutate_set(case: EvaluationCase, **updates: Any) -> EvaluationCase:
    current = case.sufficient_evidence_sets[0].model_dump()
    current.update(updates)
    return _rebuild_case(case, sufficient_evidence_sets=[current])


@pytest.mark.parametrize(
    "mutator",
    [
        lambda case: _mutate_set(case, condition_refs=()),
        lambda case: _mutate_set(case, supported_claims=()),
        lambda case: _mutate_set(case, acceptable_outcomes=()),
        lambda case: _mutate_set(
            case,
            condition_refs=("cond_primary", "cond_primary"),
        ),
        lambda case: _mutate_set(
            case,
            supported_claims=("no_supported_fault", "no_supported_fault"),
        ),
        lambda case: _mutate_set(
            case,
            acceptable_outcomes=("no_supported_fault", "no_supported_fault"),
        ),
        lambda case: _mutate_set(case, condition_refs=("cond_missing",)),
        lambda case: _rebuild_case(
            case,
            observable_conditions=(
                make_condition(),
                make_condition(metric="clipping_detected"),
            ),
        ),
        lambda case: _rebuild_case(
            case,
            sufficient_evidence_sets=(
                make_sufficient_set(),
                make_sufficient_set(supported_claims=("no_supported_fault",)),
            ),
        ),
    ],
    ids=[
        "empty_condition_refs",
        "empty_supported_claims",
        "empty_acceptable_outcomes",
        "duplicate_condition_refs",
        "duplicate_supported_claims",
        "duplicate_acceptable_outcomes",
        "unknown_condition_ref",
        "duplicate_condition_id",
        "duplicate_evidence_set_id",
    ],
)
def test_t130_sufficient_set_references(
    mutator: Callable[[EvaluationCase], EvaluationCase],
) -> None:
    with pytest.raises(ValidationError):
        mutator(make_evaluation_case("clean"))


@pytest.mark.parametrize(
    ("category", "mutator"),
    [
        ("clean", lambda case: _rebuild_case(case, category="clipping")),
        (
            "clean",
            lambda case: _rebuild_case(case, causal_faults=("clipping",)),
        ),
        (
            "clean",
            lambda case: _rebuild_case(
                case, acceptable_outcomes=("supported_fault",)
            ),
        ),
        (
            "clean",
            lambda case: _rebuild_case(case, knowledge_policy="required"),
        ),
        (
            "clean",
            lambda case: _rebuild_case(case, knowledge_tags=("clipping",)),
        ),
        (
            "clean",
            lambda case: _rebuild_case(
                case,
                identifiability=CombinedIdentifiabilitySpec(
                    signature_metric="harmonic_order_2_relative_amplitude",
                    minimum_absolute_separation=0.05,
                ),
            ),
        ),
        (
            "combined",
            lambda case: _rebuild_case(case, identifiability=None),
        ),
        (
            "combined",
            lambda case: _rebuild_case(
                case, causal_faults=("harmonic_distortion", "clipping")
            ),
        ),
        (
            "invalid_noise",
            lambda case: _rebuild_case(case, requires_limitation=False),
        ),
        (
            "invalid_noise",
            lambda case: _rebuild_case(case, knowledge_tags=()),
        ),
        (
            "clipping",
            lambda case: _rebuild_case(
                case, signal=SineSignalSpec(frequency_hz=200.0)
            ),
        ),
    ],
    ids=[
        "category_mismatch",
        "causal_faults_mismatch",
        "outcomes_mismatch",
        "knowledge_policy_mismatch",
        "not_needed_knowledge_tags",
        "identifiability_on_clean",
        "combined_missing_identifiability",
        "causal_fault_order",
        "invalid_noise_limitation",
        "required_knowledge_tags_empty",
        "generator_mismatch",
    ],
)
def test_t131_case_consistency(
    category: str,
    mutator: Callable[[EvaluationCase], EvaluationCase],
) -> None:
    for valid_category in (
        "clean",
        "clipping",
        "harmonic",
        "combined",
        "invalid_noise",
    ):
        built = make_evaluation_case(valid_category)
        assert built.category == valid_category
        assert built.signal.generator == {
            "clean": "sine",
            "clipping": "clipped_sine",
            "harmonic": "harmonic_sine",
            "combined": "combined_distortion",
            "invalid_noise": "white_noise",
        }[valid_category]
    with pytest.raises(ValidationError):
        mutator(make_evaluation_case(category))


@pytest.mark.parametrize(
    "mutator",
    [
        lambda manifest: make_dataset_manifest(
            cases=(manifest.cases[0], manifest.cases[0])
        ),
        lambda manifest: make_dataset_manifest(rule_profile_id="s1_distortion"),
        lambda manifest: make_dataset_manifest(version="1.0"),
        lambda manifest: make_dataset_manifest(rule_profile_id=""),
        lambda manifest: make_dataset_manifest(
            cases=(
                make_evaluation_case("clean"),
                _mutate_set(
                    make_evaluation_case("clipping", case_id="case_clipping_dev_01"),
                    condition_refs=("cond_from_other_case",),
                ),
            )
        ),
    ],
    ids=[
        "duplicate_case_id",
        "profile_id_pattern",
        "dataset_version_semver",
        "empty_profile_id",
        "unresolved_internal_ref",
    ],
)
def test_t132_manifest_identity_and_references(
    mutator: Callable[[DatasetManifest], DatasetManifest],
) -> None:
    valid = make_dataset_manifest(
        cases=(
            make_evaluation_case("clean"),
            make_evaluation_case("clipping", case_id="case_clipping_dev_01"),
        )
    )
    assert valid.rule_profile_id == "profile_s1_distortion"
    assert valid.rule_profile_version == "1.0.0-demo"
    with pytest.raises(ValidationError):
        mutator(valid)


def test_dataset_validation_report_valid_iff_issues_empty() -> None:
    issue = DatasetValidationIssue(
        code="seed_mismatch",
        case_id="case_clean_dev_01",
        message="seeded reconstruction mismatch",
    )
    ok = DatasetValidationReport(
        dataset_id="s1-distortion-synthetic",
        dataset_version="1.0.0",
        valid=True,
        checked_case_ids=("case_clean_dev_01",),
        issues=(),
    )
    assert ok.valid is True
    assert ok.issues == ()
    invalid = DatasetValidationReport(
        dataset_id="s1-distortion-synthetic",
        dataset_version="1.0.0",
        valid=False,
        checked_case_ids=("case_clean_dev_01",),
        issues=(issue,),
    )
    assert invalid.valid is False
    assert invalid.issues == (issue,)
    with pytest.raises(ValidationError):
        DatasetValidationReport(
            dataset_id="s1-distortion-synthetic",
            dataset_version="1.0.0",
            valid=True,
            checked_case_ids=("case_clean_dev_01",),
            issues=(issue,),
        )
    with pytest.raises(ValidationError):
        DatasetValidationReport(
            dataset_id="s1-distortion-synthetic",
            dataset_version="1.0.0",
            valid=False,
            checked_case_ids=("case_clean_dev_01",),
            issues=(),
        )


def _minimal_run_score(**overrides: Any) -> RunScore:
    payload: dict[str, Any] = {
        "trace_id": "trace_agent_case_invariants_01_01",
        "case_id": "case_invariants_01",
        "run_slot": 1,
        "execution_path": "agent",
        "expected_faults": (),
        "predicted_faults": (),
        "acceptable_outcomes": ("no_supported_fault",),
        "predicted_outcome": "no_supported_fault",
        "causal_exact_set_correct": True,
        "outcome_correct": True,
        "grounded_claims": 0,
        "scored_claims": 0,
        "unsupported_fault_claims": 0,
        "predicted_fault_claims": 0,
        "first_tool_correct": True,
        "appropriate_replans": 0,
        "replan_opportunities": 0,
        "unnecessary_tool_actions": 0,
        "tool_actions": 0,
        "timely_stop": True,
        "correct_rule_actions": 0,
        "rule_action_opportunities": 0,
        "required_knowledge_actions": 0,
        "required_knowledge_opportunities": 0,
        "unnecessary_knowledge_actions": 0,
        "knowledge_actions": 0,
        "cited_knowledge_actions": 0,
        "planner_calls": 0,
        "completion_reason": "planner_finished",
    }
    payload.update(overrides)
    return RunScore(**payload)


def test_run_score_accepts_consistent_numerator_denominator_pairs() -> None:
    score = _minimal_run_score(
        grounded_claims=1,
        scored_claims=2,
        unsupported_fault_claims=1,
        predicted_fault_claims=2,
        appropriate_replans=1,
        replan_opportunities=1,
        unnecessary_tool_actions=1,
        tool_actions=3,
        correct_rule_actions=1,
        rule_action_opportunities=1,
        required_knowledge_actions=1,
        required_knowledge_opportunities=1,
        unnecessary_knowledge_actions=1,
        knowledge_actions=2,
        cited_knowledge_actions=1,
        planner_calls=4,
    )
    assert score.appropriate_replans <= score.replan_opportunities
    assert score.grounded_claims <= score.scored_claims


@pytest.mark.parametrize(
    ("numerator_field", "denominator_field"),
    [
        ("grounded_claims", "scored_claims"),
        ("unsupported_fault_claims", "predicted_fault_claims"),
        ("appropriate_replans", "replan_opportunities"),
        ("unnecessary_tool_actions", "tool_actions"),
        ("correct_rule_actions", "rule_action_opportunities"),
        ("required_knowledge_actions", "required_knowledge_opportunities"),
        ("unnecessary_knowledge_actions", "knowledge_actions"),
        ("cited_knowledge_actions", "knowledge_actions"),
    ],
)
def test_run_score_rejects_success_count_above_denominator(
    numerator_field: str,
    denominator_field: str,
) -> None:
    with pytest.raises(ValidationError):
        _minimal_run_score(**{numerator_field: 2, denominator_field: 1})
