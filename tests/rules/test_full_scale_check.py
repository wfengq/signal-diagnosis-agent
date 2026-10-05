"""T-CX350–T-CX367: full-scale check rules."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from signal_diag.rules.full_scale_check import (
    FullScaleDeclarations,
    assert_product_profile_allowed,
    evaluate_full_scale_check,
    resolve_anchor_id,
    select_counted_repeats,
    validate_full_scale_check_record,
)
from signal_diag.signal import TimeRange
from tests.rules.full_scale_fixtures import (
    FIXTURE_FLOOR,
    eligible,
    index,
    make_submission,
    redigest,
    sine,
)
from tests.rules.regression_fixtures import (
    build_fixture_clipping_profile,
    build_fixture_thd_profile,
)


def _status(anchor, repeats, floor=FIXTURE_FLOOR):
    record = evaluate_full_scale_check(
        check_id="chk_1",
        anchor=anchor,
        repeats=repeats,
        floor=floor,
        supersedes=None,
    )
    return record.status, record.transition, record.unmet_conditions, record.unevaluated_conditions


def test_t_cx365_anchor_resolution() -> None:
    subs = index(
        make_submission(comparison_id="a"),
        make_submission(comparison_id="r1", parent="a", kind="repeat"),
        make_submission(comparison_id="r2", parent="r1", kind="repeat"),
        make_submission(comparison_id="fix", parent="a", kind="repair"),
        make_submission(comparison_id="rec", parent="a", kind="recommendation"),
        make_submission(comparison_id="r3", parent="fix", kind="repeat"),
    )
    assert [resolve_anchor_id(k, subs) for k in ("a", "r1", "r2", "fix", "rec", "r3")] == [
        "a",
        "a",
        "a",
        "fix",
        "rec",
        "fix",
    ]


def test_t_cx358_counted_repeat_rules() -> None:
    anchor = make_submission(comparison_id="a")
    indep = FullScaleDeclarations(
        baseline_independent_render="yes", candidate_independent_render="yes"
    )
    ok = make_submission(comparison_id="r1", parent="a", kind="repeat", declarations=indep)
    one_side = make_submission(
        comparison_id="r2",
        parent="a",
        kind="repeat",
        declarations=FullScaleDeclarations(candidate_independent_render="yes"),
    )
    other_range = make_submission(
        comparison_id="r3",
        parent="a",
        kind="repeat",
        declarations=indep,
        time_range=TimeRange(start_s=0.0, end_s=1.0),
    )
    other_version = make_submission(
        comparison_id="r4",
        parent="a",
        kind="repeat",
        declarations=indep,
        candidate_version="v9",
    )
    blocked = make_submission(
        comparison_id="r5",
        parent="a",
        kind="repeat",
        declarations=indep,
        same_input="unknown",
    )
    base, cand, uncounted = select_counted_repeats(
        anchor, (ok, one_side, other_range, other_version, blocked)
    )
    assert len(base) == 1 and len(cand) == 2
    assert {(u.comparison_id, u.side, u.reason) for u in uncounted} == {
        ("r2", "baseline", "not_declared_independent"),
        ("r3", "baseline", "selection_mismatch"),
        ("r3", "candidate", "selection_mismatch"),
        ("r4", "baseline", "version_mismatch"),
        ("r4", "candidate", "version_mismatch"),
        ("r5", "baseline", "declarations_block"),
        ("r5", "candidate", "declarations_block"),
    }


def test_t_cx358_other_reasons_and_byte_identical_marking() -> None:
    anchor = make_submission(comparison_id="a", baseline=(2000, 0.995), candidate=(2000, 0.995))
    indep = FullScaleDeclarations(
        baseline_independent_render="yes", candidate_independent_render="yes"
    )
    same_bytes = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        declarations=indep,
        baseline=(2000, 0.995),
        candidate=(2000, 0.995),
    )
    no_facts = make_submission(
        comparison_id="r2",
        parent="a",
        kind="repeat",
        declarations=indep,
        drop_facts="candidate",
    )
    other_threshold = make_submission(
        comparison_id="r3",
        parent="a",
        kind="repeat",
        declarations=indep,
        full_scale_threshold=0.98,
    )
    _, _, uncounted = select_counted_repeats(anchor, (same_bytes, no_facts, other_threshold))
    assert ("r2", "candidate", "facts_missing") in {
        (u.comparison_id, u.side, u.reason) for u in uncounted
    }
    assert ("r3", "baseline", "selection_mismatch") in {
        (u.comparison_id, u.side, u.reason) for u in uncounted
    }
    rec = evaluate_full_scale_check(
        check_id="c", anchor=anchor, repeats=(same_bytes,), floor=None, supersedes=None
    )
    assert set(rec.byte_identical_repeats) == {("r1", "baseline"), ("r1", "candidate")}


def test_t_cx358_anchor_independence_declarations_are_ignored() -> None:
    anchor = make_submission(
        comparison_id="a",
        declarations=FullScaleDeclarations(
            baseline_independent_render="yes", candidate_independent_render="yes"
        ),
    )
    assert select_counted_repeats(anchor, ()) == ((), (), ())


def test_t_cx360_product_profile_guard() -> None:
    assert_product_profile_allowed(None)
    assert_product_profile_allowed(build_fixture_thd_profile())
    with pytest.raises(ValueError, match="clipping_ratio"):
        assert_product_profile_allowed(build_fixture_clipping_profile())


def test_declarations_default_unknown_and_forbid_extra() -> None:
    assert FullScaleDeclarations().model_dump() == {
        "periodic_test_signal": "unknown",
        "baseline_independent_render": "unknown",
        "candidate_independent_render": "unknown",
    }
    with pytest.raises(ValidationError):
        FullScaleDeclarations(approved=True)


@pytest.mark.parametrize(
    "baseline,candidate,status,transition",
    [
        ((0, 0.5), (0, 0.6), "no_regression_detected", "no_to_no"),
        ((0, 0.5), (2000, 0.995), "regression_detected", "no_to_yes"),
        ((2000, 0.995), (2011, 0.995), "regression_detected", "yes_to_yes_increase"),
        ((2000, 0.995), (2010, 0.995), "no_regression_detected", "yes_to_yes_increase"),
        ((2000, 0.995), (2000, 0.995), "no_regression_detected", "yes_to_yes_equal"),
        ((2000, 0.995), (1500, 0.995), "no_regression_detected", "yes_to_yes_decrease"),
        ((2000, 0.995), (0, 0.5), "no_regression_detected", "yes_to_no"),
    ],
)
def test_t_cx352_353_354_transition_table(baseline, candidate, status, transition) -> None:
    anchor, repeats = eligible(baseline=baseline, candidate=candidate)
    assert _status(anchor, repeats) == (status, transition, (), ())


@pytest.mark.parametrize(
    "overrides,code,status",
    [
        ({"periodic": "unknown"}, "periodic_not_declared", "descriptive_only"),
        ({"periodic": "no"}, "periodic_not_declared", "descriptive_only"),
        ({"candidate_version": "v1"}, "same_version", "descriptive_only"),
        ({"nominal_fundamental_hz": None}, "fundamental_not_declared", "descriptive_only"),
        ({"nominal_fundamental_hz": 4000.0}, "samples_per_period_below_domain", "descriptive_only"),
        ({"nominal_fundamental_hz": 2.0}, "periods_in_range_below_domain", "descriptive_only"),
        ({"bits": (8, 16)}, "bit_depth_below_16:baseline", "descriptive_only"),
        ({"full_scale_threshold": 0.98}, "floor_missing", "descriptive_only"),
        ({"drop_repeats": "candidate"}, "repeat_missing:candidate", "descriptive_only"),
        ({"same_input": "unknown"}, "declarations_block:same_input=unknown", "not_comparable"),
        (
            {"repeatability": "observed_variable"},
            "declarations_block:repeatability=observed_variable",
            "not_comparable",
        ),
        ({"repeat_candidate": (2400, 0.995)}, "renders_inconsistent:candidate", "not_comparable"),
        ({"drop_facts": "candidate"}, "facts_missing:candidate", "not_comparable"),
    ],
)
def test_t_cx356_359_362_366_each_gate_blocks_a_large_onset(overrides, code, status) -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(20000, 1.0), **overrides)
    got_status, _, unmet, _ = _status(anchor, repeats)
    assert got_status == status and code in unmet


def test_t_cx357_no_side_within_one_step_is_inside_zone() -> None:
    anchor, repeats = eligible(baseline=(0, 0.9899902), candidate=(800, 0.9900208))
    status, transition, unmet, _ = _status(anchor, repeats)
    assert status == "descriptive_only" and transition == "no_to_yes"
    assert "critical_zone:baseline" in unmet and "critical_zone:candidate" in unmet


def test_t_cx357_fixed_minimum_holds_without_floor() -> None:
    anchor, repeats = eligible(baseline=(0, 0.9899902), candidate=(800, 0.9900208))
    _, _, unmet, _ = _status(anchor, repeats, floor=None)
    assert "critical_zone:baseline" in unmet


def test_t_cx357_isolated_over_threshold_no_side_is_inside_zone() -> None:
    anchor, repeats = eligible(
        baseline=(0, 0.5), baseline_isolated=40, candidate=(2000, 0.995)
    )
    assert anchor.baseline_facts.counted_samples == 0
    assert anchor.baseline_facts.over_threshold_uncounted == 40
    assert "critical_zone:baseline" in _status(anchor, repeats)[2]


def test_critical_zone_covers_counted_repeats() -> None:
    # Anchor baseline is normal; its counted repeat has counted=0 but 40
    # isolated over-threshold samples (critical zone on that render).
    anchor, _repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    noisy = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        declarations=FullScaleDeclarations(
            baseline_independent_render="yes",
            candidate_independent_render="yes",
        ),
        baseline=(0, 0.5),
        baseline_isolated=40,
        candidate=(2000, 0.995),
    )
    status, _, unmet, _ = _status(anchor, (noisy,))
    assert status == "descriptive_only" and "critical_zone:baseline" in unmet


def test_t_cx363_no_floor_means_no_judged_status() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(20000, 1.0))
    status, _, unmet, unevaluated = _status(anchor, repeats, floor=None)
    assert status == "descriptive_only" and unmet == ("floor_missing",)
    assert unevaluated == (
        "samples_per_period_below_domain",
        "periods_in_range_below_domain",
        "critical_zone_reviewed",
    )
    mismatched = redigest(FIXTURE_FLOOR.model_copy(update={"full_scale_threshold": 0.98}))
    assert "floor_missing" in _status(anchor, repeats, floor=mismatched)[2]
    broken = FIXTURE_FLOOR.model_copy(update={"count_floor_samples": 0})
    assert "floor_missing" in _status(anchor, repeats, floor=broken)[2]


def test_t_cx366_not_comparable_precedes_descriptive_and_all_are_listed() -> None:
    anchor, repeats = eligible(
        baseline=(0, 0.5),
        candidate=(20000, 1.0),
        same_input="no",
        periodic="unknown",
        candidate_version="v1",
    )
    status, _, unmet, _ = _status(anchor, repeats, floor=None)
    assert status == "not_comparable"
    assert {
        "declarations_block:same_input=no",
        "periodic_not_declared",
        "same_version",
        "floor_missing",
    } <= set(unmet)


def test_t_cx350_ratio_difference_never_changes_status() -> None:
    anchor, repeats = eligible(
        baseline_samples=sine(amplitude=0.5), candidate_samples=sine(amplitude=0.01)
    )
    ratio = anchor.record.candidate_bundle.clipping.result.clipping_ratio
    assert ratio > 0.5 and anchor.candidate_facts.counted_samples == 0
    assert _status(anchor, repeats)[:2] == ("no_regression_detected", "no_to_no")


def test_t_cx356_periodic_declaration_is_read_from_the_anchor_only() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995), periodic="unknown")
    declared = repeats[0].model_copy(
        update={
            "declarations": repeats[0].declarations.model_copy(
                update={"periodic_test_signal": "yes"}
            )
        }
    )
    assert "periodic_not_declared" in _status(anchor, (declared,))[2]


def test_t_cx361_sub_full_scale_pair_gets_no_regression_signal() -> None:
    anchor, repeats = eligible(
        baseline_samples=np.clip(sine(amplitude=1.2), -0.5, 0.5),
        candidate_samples=np.clip(sine(amplitude=1.2), -0.9, 0.9),
    )
    assert anchor.record.clipping_facts[0].flat_top_detected is True
    assert _status(anchor, repeats)[:2] == ("no_regression_detected", "no_to_no")


def test_t_cx367_validation_recomputes_and_rejects_tampering() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    rec = evaluate_full_scale_check(
        check_id="chk_1",
        anchor=anchor,
        repeats=repeats,
        floor=FIXTURE_FLOOR,
        supersedes=None,
    )
    validate_full_scale_check_record(
        rec, anchor=anchor, repeats=repeats, approved_floors=(FIXTURE_FLOOR,)
    )
    for update in (
        {"status": "no_regression_detected"},
        {"unmet_conditions": ("same_version",)},
        {"counted_candidate_repeats": 5},
        {"transition": "no_to_no"},
        {"repeat_comparison_ids": ()},
    ):
        with pytest.raises(ValueError):
            validate_full_scale_check_record(
                redigest(rec.model_copy(update=update)),
                anchor=anchor,
                repeats=repeats,
                approved_floors=(FIXTURE_FLOOR,),
            )
    with pytest.raises(ValueError):
        validate_full_scale_check_record(
            rec.model_copy(update={"digest": "0" * 64}),
            anchor=anchor,
            repeats=repeats,
            approved_floors=(FIXTURE_FLOOR,),
        )


def test_t_cx363_unapproved_floor_fails_validation() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    rec = evaluate_full_scale_check(
        check_id="chk_1",
        anchor=anchor,
        repeats=repeats,
        floor=FIXTURE_FLOOR,
        supersedes=None,
    )
    assert rec.status == "regression_detected"
    with pytest.raises(ValueError, match="floor"):
        validate_full_scale_check_record(rec, anchor=anchor, repeats=repeats)
