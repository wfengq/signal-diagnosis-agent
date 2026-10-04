"""Regression comparison rules (Task 3)."""

from __future__ import annotations

import hashlib
import math

import pytest

from signal_diag.rules.regression import (
    ComparisonConditions,
    ComparisonRecord,
    compare_measurements,
    validate_comparison_record,
)
from signal_diag.signal import (
    InMemorySignalRepository,
    TimeRange,
    generate_clipped_sine,
    generate_harmonic_sine,
    generate_sine,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.regression_measurement import (
    InputIdentity,
    MeasurementSelection,
    ToolParameterSnapshot,
    measure_output,
    measurement_bundle_digest,
)
from signal_diag.tools.results import ToolResult
from tests.rules.regression_fixtures import (
    build_fixture_both_metrics_profile,
    build_fixture_clipping_profile,
    build_fixture_relative_profile,
    build_fixture_thd_profile,
)


def _rehashed(bundle):
    return bundle.model_copy(update={"digest": measurement_bundle_digest(bundle)})


def _conditions(**overrides: object) -> ComparisonConditions:
    base = {
        "baseline_version": "v1",
        "candidate_version": "v2",
        "stimulus_key": "sine-200",
        "parameters_key": "default",
        "same_input": "yes",
        "parameters_unchanged": "yes",
        "aligned_ranges": "yes",
        "repeatability": "declared_deterministic",
    }
    base.update(overrides)
    return ComparisonConditions(**base)


def _selection(
    *,
    channel: str = "left",
    fundamental_hz: float | None = 200.0,
    threshold: float = 0.99,
) -> MeasurementSelection:
    return MeasurementSelection(
        clipping=ClippingInput(channel=channel, full_scale_threshold=threshold),
        harmonic=HarmonicDistortionInput(channel=channel, fundamental_hz=fundamental_hz),
    )


def _bundle_from_case(
    *,
    case,
    run_id: str,
    side: str,
    selection: MeasurementSelection,
    wav_sha256: str | None = None,
) -> tuple[InMemorySignalRepository, object]:
    repository = InMemorySignalRepository()
    repository.put(case.record)
    signal_id = case.record.meta.signal_id
    digest = wav_sha256 or hashlib.sha256(b"fixture-bytes").hexdigest()
    time_range = selection.clipping.time_range or TimeRange()
    start = round(time_range.start_s * case.record.meta.sample_rate_hz)
    end = (
        case.record.meta.num_samples
        if time_range.end_s is None
        else min(
            round(time_range.end_s * case.record.meta.sample_rate_hz),
            case.record.meta.num_samples,
        )
    )
    identity = InputIdentity(
        run_id=run_id,
        side=side,
        wav_sha256=digest,
        signal_id=signal_id,
        sample_rate_hz=case.record.meta.sample_rate_hz,
        source_channels=case.record.meta.channels,
        total_frames=case.record.meta.num_samples,
        resolved_start_sample=start,
        resolved_end_sample=end,
        channel=selection.clipping.channel,
        tool_parameter_snapshot=ToolParameterSnapshot(
            clipping=selection.clipping,
            harmonic=selection.harmonic,
        ),
    )
    bundle = measure_output(
        repository=repository,
        identity=identity,
        selection=selection,
    )
    return repository, bundle


def _pair(
    baseline_case,
    candidate_case,
    *,
    baseline_run: str = "run_base",
    candidate_run: str = "run_cand",
    selection: MeasurementSelection | None = None,
) -> tuple[object, object]:
    selection = selection or _selection()
    _, baseline = _bundle_from_case(
        case=baseline_case,
        run_id=baseline_run,
        side="baseline",
        selection=selection,
    )
    _, candidate = _bundle_from_case(
        case=candidate_case,
        run_id=candidate_run,
        side="candidate",
        selection=selection,
        wav_sha256=hashlib.sha256(b"candidate-bytes").hexdigest(),
    )
    return baseline, candidate


def test_fixture_profile_boundary() -> None:
    profile = build_fixture_clipping_profile()
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    baseline, candidate = _pair(clean, clean)
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    clipping = _metric(record, "clipping_ratio")
    assert clipping.status == "no_regression_detected"
    assert clipping.rule_ref == "rule_fixture_clipping_ratio"

    shifted = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.401,
    )
    _, candidate_shift = _bundle_from_case(
        case=shifted,
        run_id="run_shift",
        side="candidate",
        selection=_selection(),
    )
    at_min = compare_measurements(
        baseline,
        candidate_shift,
        conditions=_conditions(),
        profile=profile,
    )
    assert _metric(at_min, "clipping_ratio").status in {
        "no_regression_detected",
        "regression_detected",
    }

    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.95,
        clip_level=0.35,
    )
    _, candidate_clip = _bundle_from_case(
        case=clipped,
        run_id="run_clip",
        side="candidate",
        selection=_selection(),
    )
    over = compare_measurements(
        baseline,
        candidate_clip,
        conditions=_conditions(),
        profile=profile,
    )
    assert _metric(over, "clipping_ratio").status == "regression_detected"


def test_no_profile_is_descriptive() -> None:
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.95,
        clip_level=0.35,
    )
    baseline, candidate = _pair(clean, clipped)
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=None,
    )
    clipping = _metric(record, "clipping_ratio")
    assert clipping.status == "descriptive_only"
    assert clipping.rule_ref is None
    assert record.overall_regression_pass is None


def test_relative_difference_rejects_small_denominator() -> None:
    profile = build_fixture_relative_profile()
    zero_base = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    tiny = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    baseline, candidate = _pair(zero_base, tiny)
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    clipping = _metric(record, "clipping_ratio")
    base_ref = clipping.baseline_ref
    assert base_ref is not None
    assert abs(base_ref.value) <= profile.rules[0].denominator_floor
    assert clipping.status == "not_comparable"
    assert "denominator" in clipping.reason_codes[0]

    floor_case = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.05,
    )
    baseline2, candidate2 = _pair(floor_case, floor_case)
    record2 = compare_measurements(
        baseline2,
        candidate2,
        conditions=_conditions(),
        profile=profile,
    )
    assert _metric(record2, "clipping_ratio").difference is not None
    assert math.isfinite(_metric(record2, "clipping_ratio").difference or 0.0)

    thd_profile = build_fixture_thd_profile()
    harmonic = generate_harmonic_sine(
        fundamental_hz=200.0,
        harmonic_ratios={2: 0.1},
        sample_rate_hz=48_000,
        duration_s=0.25,
    )
    base_h, cand_h = _pair(harmonic, harmonic)
    thd_record = compare_measurements(
        base_h,
        cand_h,
        conditions=_conditions(),
        profile=thd_profile,
    )
    thd = _metric(thd_record, "thd_percent")
    if thd.difference is not None:
        assert thd.difference_unit == "percentage_points"


@pytest.mark.parametrize(
    ("mutator_name", "expected_substring"),
    [
        ("wrong_unit", "unit"),
        ("wrong_tool", "source_tool"),
        ("wrong_config", "tool_parameter"),
        ("wrong_range", "resolved"),
        ("invalid_harmonic", "harmonic"),
        ("missing_evidence", "evidence"),
        ("swapped_side_run", "mismatch"),
        ("same_id_different_run", "mismatch"),
        ("bool_value", "float"),
        ("tampered_difference", "mismatch"),
        ("tampered_status", "mismatch"),
    ],
)
def test_admission_and_integrity_rejects(mutator_name: str, expected_substring: str) -> None:
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    baseline, candidate = _pair(clean, clean)
    profile = build_fixture_clipping_profile()
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    if mutator_name == "tampered_difference":
        bad = record.model_copy(
            update={
                "metric_comparisons": (
                    record.metric_comparisons[0].model_copy(update={"difference": 9.99}),
                    *record.metric_comparisons[1:],
                )
            }
        )
        with pytest.raises(ValueError, match=expected_substring):
            validate_comparison_record(bad)
        return
    if mutator_name == "tampered_status":
        tampered_status = (
            "regression_detected"
            if record.metric_comparisons[0].status != "regression_detected"
            else "descriptive_only"
        )
        bad = record.model_copy(
            update={
                "metric_comparisons": (
                    record.metric_comparisons[0].model_copy(
                        update={"status": tampered_status}
                    ),
                    *record.metric_comparisons[1:],
                )
            }
        )
        with pytest.raises(ValueError, match=expected_substring):
            validate_comparison_record(bad)
        return

    mutator = _MUTATORS[mutator_name]
    try:
        mutator(baseline, candidate, profile)
    except ValueError as error:
        assert expected_substring in str(error)
    else:
            if mutator_name == "invalid_harmonic":
                invalid = _rehashed(
                    candidate.model_copy(
                        update={
                            "harmonic": candidate.harmonic.model_copy(
                                update={"status": "invalid"}
                            ),
                        }
                    )
                )
                record = compare_measurements(
                    baseline,
                    invalid,
                    conditions=_conditions(),
                    profile=build_fixture_thd_profile(),
                )
                assert "harmonic" in _metric(record, "thd_percent").reason_codes[0]
                return
            pytest.fail(f"expected ValueError containing {expected_substring}")


def test_existing_fault_and_partial_coverage_are_preserved() -> None:
    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.95,
        clip_level=0.35,
    )
    baseline, candidate = _pair(clipped, clipped)
    profile = build_fixture_clipping_profile()
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    facts = {item.side: item for item in record.clipping_facts}
    assert facts["baseline"].flat_top_detected is True
    assert facts["candidate"].flat_top_detected is True
    assert facts["baseline"].tool_status == "success"
    assert any(item.check_id == "thd_percent" for item in record.coverage)
    assert record.overall_regression_pass is not True

    error_clip = ToolResult(
        call_id=baseline.clipping.call_id,
        tool_name="detect_clipping",
        status="error",
        error_message="injected clipping tool failure",
    )
    broken = _rehashed(baseline.model_copy(update={"clipping": error_clip}))
    record_err = compare_measurements(
        broken,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    assert record_err.overall_regression_pass is False
    assert any(
        item.check_id == "tool_success" and item.status == "failed"
        for item in record_err.coverage
    )


def test_thd_blocked_without_applicability_and_incompatible_fundamentals() -> None:
    profile_clipping_only = build_fixture_clipping_profile()
    harmonic_a = generate_harmonic_sine(
        fundamental_hz=200.0,
        harmonic_ratios={2: 0.1},
        sample_rate_hz=48_000,
        duration_s=0.25,
    )
    harmonic_b = generate_harmonic_sine(
        fundamental_hz=400.0,
        harmonic_ratios={2: 0.1},
        sample_rate_hz=48_000,
        duration_s=0.25,
    )
    selection = _selection(fundamental_hz=None)
    base, cand = _pair(harmonic_a, harmonic_b, selection=selection)
    record = compare_measurements(
        base,
        cand,
        conditions=_conditions(),
        profile=profile_clipping_only,
    )
    thd = _metric(record, "thd_percent")
    assert thd.status == "not_comparable"
    assert "harmonic_applicability" in thd.reason_codes[0]

    thd_profile = build_fixture_thd_profile()
    record2 = compare_measurements(
        base,
        cand,
        conditions=_conditions(),
        profile=thd_profile,
    )
    thd2 = _metric(record2, "thd_percent")
    assert thd2.status == "not_comparable"
    assert "fundamental" in thd2.reason_codes[0]


def _metric(record: ComparisonRecord, metric: str):
    for item in record.metric_comparisons:
        if item.metric == metric:
            return item
    raise AssertionError(f"missing metric {metric}")


def _mutate_wrong_unit(baseline, candidate, profile):
    cand = _rehashed(
        candidate.model_copy(
            update={
                "clipping": candidate.clipping.model_copy(
                    update={
                        "evidence": tuple(
                            item.model_copy(update={"unit": "%"})
                            if item.metric == "clipping_ratio"
                            else item
                            for item in candidate.clipping.evidence
                        )
                    }
                )
            }
        )
    )
    compare_measurements(baseline, cand, conditions=_conditions(), profile=profile)


def _mutate_wrong_tool(baseline, candidate, profile):
    cand = _rehashed(
        candidate.model_copy(
            update={
                "clipping": candidate.clipping.model_copy(
                    update={
                        "evidence": tuple(
                            item.model_copy(update={"source_tool": "analyze_spectrum"})
                            if item.metric == "clipping_ratio"
                            else item
                            for item in candidate.clipping.evidence
                        )
                    }
                )
            }
        )
    )
    compare_measurements(baseline, cand, conditions=_conditions(), profile=profile)


def _mutate_wrong_config(baseline, candidate, profile):
    other_selection = _selection(threshold=0.5)
    cand = _rehashed(
        candidate.model_copy(
            update={
                "identity": candidate.identity.model_copy(
                    update={
                        "tool_parameter_snapshot": ToolParameterSnapshot(
                            clipping=other_selection.clipping,
                            harmonic=other_selection.harmonic,
                        )
                    }
                )
            }
        )
    )
    compare_measurements(baseline, cand, conditions=_conditions(), profile=profile)


def _mutate_wrong_range(baseline, candidate, profile):
    cand = _rehashed(
        candidate.model_copy(
            update={
                "identity": candidate.identity.model_copy(
                    update={
                        "resolved_end_sample": candidate.identity.resolved_end_sample - 10
                    }
                )
            }
        )
    )
    compare_measurements(baseline, cand, conditions=_conditions(), profile=profile)


def _mutate_invalid_harmonic(baseline, candidate, profile):
    return None


def _mutate_missing_evidence(baseline, candidate, profile):
    cand = _rehashed(
        candidate.model_copy(
            update={
                "clipping": candidate.clipping.model_copy(update={"evidence": ()}),
            }
        )
    )
    compare_measurements(baseline, cand, conditions=_conditions(), profile=profile)


def _mutate_swapped_side_run(baseline, candidate, profile):
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    ref = record.metric_comparisons[0].candidate_ref
    if ref is None:
        raise ValueError("missing ref")
    bad_ref = ref.model_copy(update={"side": "baseline"})
    bad = record.model_copy(
        update={
            "metric_comparisons": (
                record.metric_comparisons[0].model_copy(update={"candidate_ref": bad_ref}),
                *record.metric_comparisons[1:],
            )
        }
    )
    validate_comparison_record(bad)


def _mutate_same_id_different_run(baseline, candidate, profile):
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=profile,
    )
    base_ref = record.metric_comparisons[0].baseline_ref
    cand_ref = record.metric_comparisons[0].candidate_ref
    if base_ref is None or cand_ref is None:
        raise ValueError("missing ref")
    bad = record.model_copy(
        update={
            "metric_comparisons": (
                record.metric_comparisons[0].model_copy(
                    update={
                        "candidate_ref": cand_ref.model_copy(
                            update={"evidence_id": "ev_tampered_not_in_bundle"}
                        )
                    }
                ),
                *record.metric_comparisons[1:],
            )
        }
    )
    validate_comparison_record(bad)


def _mutate_bool_value(baseline, candidate, profile):
    cand = _rehashed(
        candidate.model_copy(
            update={
                "clipping": candidate.clipping.model_copy(
                    update={
                        "evidence": tuple(
                            item.model_copy(update={"value": True})
                            if item.metric == "clipping_ratio"
                            else item
                            for item in candidate.clipping.evidence
                        )
                    }
                )
            }
        )
    )
    compare_measurements(baseline, cand, conditions=_conditions(), profile=profile)


_MUTATORS = {
    "wrong_unit": _mutate_wrong_unit,
    "wrong_tool": _mutate_wrong_tool,
    "wrong_config": _mutate_wrong_config,
    "wrong_range": _mutate_wrong_range,
    "invalid_harmonic": _mutate_invalid_harmonic,
    "missing_evidence": _mutate_missing_evidence,
    "swapped_side_run": _mutate_swapped_side_run,
    "same_id_different_run": _mutate_same_id_different_run,
    "bool_value": _mutate_bool_value,
}


def test_validate_rejects_tampered_overall_and_derived_fields() -> None:
    import json

    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    baseline, candidate = _pair(clean, clean)
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=None,
        comparison_id="cmp_integrity",
    )
    assert record.overall_regression_pass is None

    payload = json.loads(record.model_dump_json())
    payload["overall_regression_pass"] = True
    tampered = ComparisonRecord.model_validate(payload)
    with pytest.raises(ValueError, match="mismatch"):
        validate_comparison_record(tampered)

    for field, value in (
        ("coverage", []),
        ("required_checks", []),
        ("clipping_facts", []),
        ("profile_id", "forged_profile"),
    ):
        forged = json.loads(record.model_dump_json())
        forged[field] = value
        with pytest.raises(ValueError, match="mismatch"):
            validate_comparison_record(ComparisonRecord.model_validate(forged))


def test_bundle_side_and_run_identity_are_enforced() -> None:
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    baseline, candidate = _pair(clean, clean)
    with pytest.raises(ValueError, match="identity.side"):
        compare_measurements(candidate, baseline, conditions=_conditions(), profile=None)
    same_run_as_candidate = _rehashed(
        baseline.model_copy(
            update={
                "identity": baseline.identity.model_copy(update={"side": "candidate"})
            }
        )
    )
    with pytest.raises(ValueError, match="run_id must differ"):
        compare_measurements(
            baseline,
            same_run_as_candidate,
            conditions=_conditions(),
            profile=None,
        )


def test_stale_bundle_digest_is_rejected() -> None:
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.4,
    )
    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.95,
        clip_level=0.35,
    )
    baseline, candidate = _pair(clean, clipped)
    new_result = candidate.clipping.result.model_copy(update={"clipping_ratio": 0.25})
    new_evidence = tuple(
        item.model_copy(update={"value": 0.25})
        if item.metric == "clipping_ratio"
        else item
        for item in candidate.clipping.evidence
    )
    stale = candidate.model_copy(
        update={
            "clipping": candidate.clipping.model_copy(
                update={"result": new_result, "evidence": new_evidence}
            )
        }
    )
    assert stale.digest == candidate.digest
    with pytest.raises(ValueError, match="bundle digest mismatch"):
        compare_measurements(
            baseline,
            stale,
            conditions=_conditions(),
            profile=build_fixture_clipping_profile(),
        )


def test_required_checks_block_overall_pass_when_skipped() -> None:
    harmonic = generate_harmonic_sine(
        fundamental_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        harmonic_ratios={2: 0.05, 3: 0.03},
    )
    baseline, candidate = _pair(harmonic, harmonic)
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=build_fixture_thd_profile(),
    )
    assert _metric(record, "clipping_ratio").status == "descriptive_only"
    assert _metric(record, "thd_percent").status == "no_regression_detected"
    assert any(
        item.check_id == "clipping_ratio" and item.status == "skipped"
        for item in record.coverage
    )
    assert record.overall_regression_pass is False


def test_repeatability_unknown_blocks_formal_judgment() -> None:
    harmonic = generate_harmonic_sine(
        fundamental_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        harmonic_ratios={2: 0.05, 3: 0.03},
    )
    baseline, candidate = _pair(harmonic, harmonic)
    profile = build_fixture_both_metrics_profile()
    ok = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(repeatability="declared_deterministic"),
        profile=profile,
    )
    assert ok.overall_regression_pass is True
    unknown = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(repeatability="unknown"),
        profile=profile,
    )
    assert unknown.overall_regression_pass is False
    assert any(
        item.check_id == "declarations" and item.status == "blocked"
        for item in unknown.coverage
    )
    variable = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(repeatability="observed_variable"),
        profile=profile,
    )
    assert variable.overall_regression_pass is False


def test_dual_metric_overall_pass_requires_no_regression() -> None:
    clean = generate_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.5,
    )
    harmonic_match = generate_harmonic_sine(
        fundamental_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        fundamental_amplitude=0.5,
        harmonic_ratios={2: 0.05, 3: 0.03},
    )
    harmonic_regress = generate_harmonic_sine(
        fundamental_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        fundamental_amplitude=0.5,
        harmonic_ratios={2: 0.2, 3: 0.1},
    )
    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        amplitude=0.95,
        clip_level=0.35,
    )
    profile = build_fixture_both_metrics_profile()

    all_ok_base, all_ok_cand = _pair(harmonic_match, harmonic_match)
    all_ok = compare_measurements(
        all_ok_base,
        all_ok_cand,
        conditions=_conditions(),
        profile=profile,
    )
    assert _metric(all_ok, "clipping_ratio").status == "no_regression_detected"
    assert _metric(all_ok, "thd_percent").status == "no_regression_detected"
    assert all(
        item.status == "satisfied"
        for item in all_ok.coverage
        if item.check_id in all_ok.required_checks
    )
    assert all_ok.overall_regression_pass is True

    clip_base, clip_cand = _pair(clean, clipped)
    clip_reg = compare_measurements(
        clip_base,
        clip_cand,
        conditions=_conditions(),
        profile=profile,
    )
    assert _metric(clip_reg, "clipping_ratio").status == "regression_detected"
    assert any(
        item.check_id == "clipping_ratio" and item.status == "satisfied"
        for item in clip_reg.coverage
    )
    assert clip_reg.overall_regression_pass is False

    thd_base, thd_cand = _pair(clean, harmonic_regress)
    thd_reg = compare_measurements(
        thd_base,
        thd_cand,
        conditions=_conditions(),
        profile=profile,
    )
    assert _metric(thd_reg, "thd_percent").status == "regression_detected"
    assert any(
        item.check_id == "thd_percent" and item.status == "satisfied"
        for item in thd_reg.coverage
    )
    assert thd_reg.overall_regression_pass is False
    validate_comparison_record(thd_reg)


def test_sourceref_json_rebuild_rejects_non_float_values() -> None:
    import json

    from signal_diag.rules.regression import SourceRef

    harmonic = generate_harmonic_sine(
        fundamental_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=0.25,
        harmonic_ratios={2: 0.05, 3: 0.03},
    )
    baseline, candidate = _pair(harmonic, harmonic)
    record = compare_measurements(
        baseline,
        candidate,
        conditions=_conditions(),
        profile=build_fixture_thd_profile(),
    )
    ref = _metric(record, "thd_percent").baseline_ref
    assert ref is not None
    for value in (False, 0, "0.0"):
        payload = json.loads(ref.model_dump_json())
        payload["value"] = value
        with pytest.raises(Exception, match="finite float"):
            SourceRef.model_validate(payload)
