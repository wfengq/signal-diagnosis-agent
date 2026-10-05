"""Task 9B: full-scale check validation gaps (plan revision 4)."""

from __future__ import annotations

import numpy as np
import pytest

from signal_diag.rules.full_scale_check import (
    FullScaleDeclarations,
    evaluate_full_scale_check,
    validate_full_scale_check_record,
)
from signal_diag.tools.regression_full_scale import (
    measure_full_scale_facts,
    verify_full_scale_facts,
)
from tests.rules.full_scale_fixtures import (
    FIXTURE_FLOOR,
    eligible,
    make_submission,
    measured,
    q16,
    redigest,
    shaped,
    sine,
)


def _non_flat_top_samples(*, runs: int = 100) -> np.ndarray:
    """Runs of exactly two over-threshold samples (min flat-top length is 3)."""
    samples = sine(amplitude=0.25)
    value = q16(0.9905)
    index = 1000
    for _ in range(runs):
        samples[index : index + 2] = value
        index += 50
    return samples


def _indep() -> FullScaleDeclarations:
    return FullScaleDeclarations(
        baseline_independent_render="yes",
        candidate_independent_render="yes",
    )


def test_9b1_rejects_swapped_repeat_facts() -> None:
    anchor, _ = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    repeat = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        declarations=_indep(),
        baseline=(0, 0.5),
        candidate=(2000, 0.995),
    )
    swapped = repeat.model_copy(
        update={
            "baseline_facts": repeat.candidate_facts,
            "candidate_facts": repeat.baseline_facts,
        }
    )
    record = evaluate_full_scale_check(
        check_id="c",
        anchor=anchor,
        repeats=(swapped,),
        floor=FIXTURE_FLOOR,
        supersedes=None,
    )
    with pytest.raises(ValueError):
        validate_full_scale_check_record(
            record,
            anchor=anchor,
            repeats=(swapped,),
            approved_floors=(FIXTURE_FLOOR,),
        )


def test_9b1_rejects_zeroed_repeat_bundle_digest() -> None:
    anchor, _ = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    repeat = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        declarations=_indep(),
        baseline=(0, 0.5),
        candidate=(2000, 0.995),
    )
    zeroed = redigest(
        repeat.candidate_facts.model_copy(update={"bundle_digest": "0" * 64})
    )
    tampered = repeat.model_copy(update={"candidate_facts": zeroed})
    record = evaluate_full_scale_check(
        check_id="c",
        anchor=anchor,
        repeats=(tampered,),
        floor=FIXTURE_FLOOR,
        supersedes=None,
    )
    with pytest.raises(ValueError):
        validate_full_scale_check_record(
            record,
            anchor=anchor,
            repeats=(tampered,),
            approved_floors=(FIXTURE_FLOOR,),
        )


def test_9b1_rejects_stale_facts_digest_on_repeat() -> None:
    anchor, _ = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    repeat = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        declarations=_indep(),
        baseline=(0, 0.5),
        candidate=(2000, 0.995),
    )
    stale = repeat.candidate_facts.model_copy(
        update={"counted_samples": repeat.candidate_facts.counted_samples - 2}
    )
    tampered = repeat.model_copy(update={"candidate_facts": stale})
    record = evaluate_full_scale_check(
        check_id="c",
        anchor=anchor,
        repeats=(tampered,),
        floor=FIXTURE_FLOOR,
        supersedes=None,
    )
    with pytest.raises(ValueError, match="digest"):
        validate_full_scale_check_record(
            record,
            anchor=anchor,
            repeats=(tampered,),
            approved_floors=(FIXTURE_FLOOR,),
        )


def test_9b1_rejects_counted_above_clipped_samples() -> None:
    samples = _non_flat_top_samples()
    bundle, repo, _ = measured(samples, side="candidate", bits=16)
    facts = measure_full_scale_facts(
        repository=repo, bundle=bundle, pcm_bit_depth=16
    )
    assert facts is not None
    clipped = bundle.clipping.result.clipped_samples
    bad = redigest(
        facts.model_copy(update={"counted_samples": clipped + 1, "state": "yes"})
    )
    with pytest.raises(ValueError, match="clipped_samples"):
        verify_full_scale_facts(bad, bundle)


def test_9b1_rejects_count_rewrite_when_flat_top_absent() -> None:
    samples = _non_flat_top_samples()
    bundle, repo, _ = measured(samples, side="candidate", bits=16)
    facts = measure_full_scale_facts(
        repository=repo, bundle=bundle, pcm_bit_depth=16
    )
    assert facts is not None
    assert bundle.clipping.result.flat_top_detected is False
    assert facts.counted_samples == bundle.clipping.result.clipped_samples
    bad = redigest(
        facts.model_copy(update={"counted_samples": facts.counted_samples - 2})
    )
    with pytest.raises(ValueError, match="flat_top|clipped_samples"):
        verify_full_scale_facts(bad, bundle)


def test_9b1_flat_top_count_rewrite_within_clipped_is_accepted_residual_risk() -> None:
    """§23.5 residual risk: with flat-top, counts cannot be recomputed.

    Changing counted_samples to another positive value ≤ clipped_samples and
    redigesting all digests stays internally consistent; validation does not
    reject it (plan revision 4; the review's 2400→2000 case).
    """
    anchor, _ = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    repeat = make_submission(
        comparison_id="r1",
        parent="a",
        kind="repeat",
        declarations=_indep(),
        baseline=(0, 0.5),
        candidate=(2400, 0.995),
    )
    assert repeat.candidate_facts is not None
    clipped = repeat.record.candidate_bundle.clipping.result.clipped_samples
    assert repeat.record.candidate_bundle.clipping.result.flat_top_detected is True
    assert 2000 <= clipped
    rewritten = redigest(
        repeat.candidate_facts.model_copy(update={"counted_samples": 2000})
    )
    tampered = repeat.model_copy(update={"candidate_facts": rewritten})
    record = evaluate_full_scale_check(
        check_id="c",
        anchor=anchor,
        repeats=(tampered,),
        floor=FIXTURE_FLOOR,
        supersedes=None,
    )
    assert record.status == "regression_detected"
    validate_full_scale_check_record(
        record,
        anchor=anchor,
        repeats=(tampered,),
        approved_floors=(FIXTURE_FLOOR,),
    )


def test_9b3_rejects_counted_plus_uncounted_over_analyzed() -> None:
    samples = shaped(2000, 0.995)
    bundle, repo, _ = measured(samples, side="candidate", bits=16)
    facts = measure_full_scale_facts(
        repository=repo, bundle=bundle, pcm_bit_depth=16
    )
    assert facts is not None
    clipped = bundle.clipping.result.clipped_samples
    # Keep counted within the clipped bound so the analyzed-sum rule is the gap.
    bad = redigest(
        facts.model_copy(
            update={
                "counted_samples": min(clipped, facts.counted_samples),
                "over_threshold_uncounted": facts.analyzed_samples,
                "state": "yes",
            }
        )
    )
    with pytest.raises(ValueError, match="analyzed"):
        verify_full_scale_facts(bad, bundle)


def test_9b3_rejects_peak_below_threshold_with_over_threshold_counts() -> None:
    samples = shaped(0, 0.5)
    bundle, repo, _ = measured(samples, side="candidate", bits=16)
    facts = measure_full_scale_facts(
        repository=repo, bundle=bundle, pcm_bit_depth=16
    )
    assert facts is not None
    assert facts.counted_samples == 0
    assert facts.peak_abs < facts.full_scale_threshold
    bad = redigest(facts.model_copy(update={"over_threshold_uncounted": 1}))
    with pytest.raises(ValueError, match="peak_abs|threshold"):
        verify_full_scale_facts(bad, bundle)


def test_9b7_applicable_approved_floor_cannot_be_dropped() -> None:
    anchor, repeats = eligible(baseline=(0, 0.5), candidate=(2000, 0.995))
    dropped = evaluate_full_scale_check(
        check_id="c",
        anchor=anchor,
        repeats=repeats,
        floor=None,
        supersedes=None,
    )
    assert dropped.status == "descriptive_only"
    with pytest.raises(ValueError, match="floor"):
        validate_full_scale_check_record(
            dropped,
            anchor=anchor,
            repeats=repeats,
            approved_floors=(FIXTURE_FLOOR,),
        )
