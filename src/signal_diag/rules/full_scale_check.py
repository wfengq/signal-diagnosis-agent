"""Full-scale check models, repeat accounting, eligibility, and judgment (V0.3 §23)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from signal_diag.rules.regression import (
    ComparisonProfile,
    ComparisonRecord,
    MetricStatus,
    _declarations_block_regression,
)
from signal_diag.tools.regression_full_scale import (
    FullScaleFacts,
    verify_full_scale_facts,
)
from signal_diag.tools.regression_measurement import (
    ComparisonSide,
    InputIdentity,
    MeasurementBundle,
    _canonical_json,
)

FULL_SCALE_MIN_PCM_BIT_DEPTH = 16
TOLERATED_DIFFERENCE_ID = "one_step_of_coarser_depth_one_sided_plus_depth_conversion"

DeclarationAnswer = Literal["yes", "no", "unknown"]

FullScaleTransition = Literal[
    "no_to_no",
    "no_to_yes",
    "yes_to_yes_increase",
    "yes_to_yes_equal",
    "yes_to_yes_decrease",
    "yes_to_no",
]


class FullScaleDeclarations(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    periodic_test_signal: DeclarationAnswer = "unknown"
    baseline_independent_render: DeclarationAnswer = "unknown"
    candidate_independent_render: DeclarationAnswer = "unknown"


class FullScaleMethodFloor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    floor_id: str
    version: str
    facts_version: str
    full_scale_threshold: float
    min_consecutive_samples: int
    min_samples_per_period: float = Field(gt=0)
    min_periods_in_range: float = Field(gt=0)
    zone_below_threshold: float = Field(ge=0)
    zone_above_threshold: float = Field(ge=0)
    zone_min_counted_samples: int | None = Field(default=None, ge=0)
    count_floor_samples: int | None = Field(default=None, ge=0)
    count_floor_ratio: float | None = Field(default=None, ge=0)
    tolerated_difference: Literal["one_step_of_coarser_depth_one_sided_plus_depth_conversion"]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_count_floors(self) -> FullScaleMethodFloor:
        if self.count_floor_samples is None and self.count_floor_ratio is None:
            raise ValueError("count_floor_samples or count_floor_ratio required")
        return self


def full_scale_floor_digest(floor: FullScaleMethodFloor) -> str:
    payload = floor.model_dump(mode="json")
    payload.pop("digest", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class FullScaleSubmission(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: str
    parent_comparison_id: str | None
    link_kind: Literal["repeat", "repair", "recommendation"] | None
    record: ComparisonRecord
    declarations: FullScaleDeclarations
    baseline_facts: FullScaleFacts | None
    candidate_facts: FullScaleFacts | None


class UncountedRepeat(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_id: str
    side: ComparisonSide
    reason: str


class FullScaleCheckRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    anchor_comparison_id: str
    anchor_digest: str
    repeat_comparison_ids: tuple[str, ...]
    uncounted_repeats: tuple[UncountedRepeat, ...]
    declarations: tuple[tuple[str, FullScaleDeclarations], ...]
    baseline_renders: tuple[FullScaleFacts, ...]
    candidate_renders: tuple[FullScaleFacts, ...]
    counted_baseline_repeats: int
    counted_candidate_repeats: int
    byte_identical_repeats: tuple[tuple[str, ComparisonSide], ...]
    floor: FullScaleMethodFloor | None
    status: MetricStatus
    transition: FullScaleTransition | None
    count_difference: int | None
    unmet_conditions: tuple[str, ...]
    unevaluated_conditions: tuple[str, ...]
    supersedes: str | None
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def load_approved_full_scale_floor_yaml(
    path: Path,
) -> tuple[FullScaleMethodFloor, dict[str, Any]]:
    """Load one approved floor YAML; validate digest; return floor and provenance."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "floor" not in payload:
        raise ValueError("approved full-scale floor YAML must contain a floor mapping")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("approved full-scale floor YAML must contain provenance")
    floor = FullScaleMethodFloor.model_validate(payload["floor"])
    if full_scale_floor_digest(floor) != floor.digest:
        raise ValueError("approved full-scale floor digest mismatch")
    return floor, provenance


def _load_product_approved_full_scale_floors() -> tuple[FullScaleMethodFloor, ...]:
    path = (
        Path(__file__).resolve().parent
        / "profiles"
        / "s1_full_scale_floor_round_1.yaml"
    )
    floor, _provenance = load_approved_full_scale_floor_yaml(path)
    return (floor,)


PRODUCT_APPROVED_FULL_SCALE_FLOORS: tuple[FullScaleMethodFloor, ...] = (
    _load_product_approved_full_scale_floors()
)

_BOTH_SIDES: tuple[ComparisonSide, ComparisonSide] = ("baseline", "candidate")


def resolve_anchor_id(
    comparison_id: str,
    submissions: Mapping[str, FullScaleSubmission],
) -> str:
    current = comparison_id
    seen: set[str] = set()
    while True:
        if current in seen:
            raise ValueError("comparison parent chain contains a cycle")
        seen.add(current)
        submission = submissions.get(current)
        if submission is None:
            raise ValueError(f"unknown comparison_id: {current}")
        if submission.link_kind != "repeat" or submission.parent_comparison_id is None:
            return current
        current = submission.parent_comparison_id


def select_counted_repeats(
    anchor: FullScaleSubmission,
    repeats: Sequence[FullScaleSubmission],
) -> tuple[tuple[FullScaleFacts, ...], tuple[FullScaleFacts, ...], tuple[UncountedRepeat, ...]]:
    baseline_counts: list[FullScaleFacts] = []
    candidate_counts: list[FullScaleFacts] = []
    uncounted: list[UncountedRepeat] = []

    anchor_base_id = anchor.record.baseline_bundle.identity
    anchor_cand_id = anchor.record.candidate_bundle.identity
    anchor_conditions = anchor.record.conditions

    for repeat in repeats:
        if repeat.link_kind != "repeat":
            continue
        cid = repeat.comparison_id
        sides_blocked: dict[ComparisonSide, str] = {}
        decl_block = _declarations_block_regression(repeat.record.conditions)

        # Reason priority per side: not_declared_independent, facts_missing,
        # declarations_block, then selection/range/rate/version mismatches.
        for side in _BOTH_SIDES:
            if not _independent_declared(repeat.declarations, side):
                sides_blocked[side] = "not_declared_independent"
                continue
            facts = repeat.baseline_facts if side == "baseline" else repeat.candidate_facts
            if facts is None:
                sides_blocked[side] = "facts_missing"
                continue
            if decl_block is not None:
                sides_blocked[side] = "declarations_block"

        open_sides = tuple(side for side in _BOTH_SIDES if side not in sides_blocked)
        if open_sides:
            if _identity_mismatch(anchor_base_id, repeat.record.baseline_bundle.identity) or (
                _identity_mismatch(anchor_cand_id, repeat.record.candidate_bundle.identity)
            ):
                for side in open_sides:
                    sides_blocked[side] = "selection_mismatch"
            elif _range_mismatch(anchor_base_id, repeat.record.baseline_bundle.identity) or (
                _range_mismatch(anchor_cand_id, repeat.record.candidate_bundle.identity)
            ):
                for side in open_sides:
                    sides_blocked[side] = "range_mismatch"
            elif anchor_base_id.sample_rate_hz != repeat.record.baseline_bundle.identity.sample_rate_hz or (
                anchor_cand_id.sample_rate_hz != repeat.record.candidate_bundle.identity.sample_rate_hz
            ):
                for side in open_sides:
                    sides_blocked[side] = "sample_rate_mismatch"
            elif (
                anchor_conditions.baseline_version != repeat.record.conditions.baseline_version
                or anchor_conditions.candidate_version != repeat.record.conditions.candidate_version
            ):
                for side in open_sides:
                    sides_blocked[side] = "version_mismatch"

        for side in _BOTH_SIDES:
            if side in sides_blocked:
                uncounted.append(
                    UncountedRepeat(comparison_id=cid, side=side, reason=sides_blocked[side])
                )
            else:
                facts = repeat.baseline_facts if side == "baseline" else repeat.candidate_facts
                assert facts is not None
                if side == "baseline":
                    baseline_counts.append(facts)
                else:
                    candidate_counts.append(facts)

    return tuple(baseline_counts), tuple(candidate_counts), tuple(uncounted)


def assert_product_profile_allowed(profile: ComparisonProfile | None) -> None:
    if profile is None:
        return
    for rule in profile.rules:
        if rule.metric == "clipping_ratio":
            raise ValueError("clipping_ratio rules are not allowed on the product regression profile")


def evaluate_full_scale_check(
    *,
    check_id: str,
    anchor: FullScaleSubmission,
    repeats: Sequence[FullScaleSubmission],
    floor: FullScaleMethodFloor | None,
    supersedes: str | None,
) -> FullScaleCheckRecord:
    base_rep, cand_rep, uncounted = select_counted_repeats(anchor, repeats)
    anchor_base = anchor.baseline_facts
    anchor_cand = anchor.candidate_facts

    baseline_renders: tuple[FullScaleFacts, ...] = ()
    candidate_renders: tuple[FullScaleFacts, ...] = ()
    if anchor_base is not None:
        baseline_renders = (anchor_base,) + base_rep
    if anchor_cand is not None:
        candidate_renders = (anchor_cand,) + cand_rep

    byte_identical: list[tuple[str, ComparisonSide]] = []
    for repeat in repeats:
        if repeat.link_kind != "repeat":
            continue
        if (
            anchor_base is not None
            and repeat.baseline_facts is not None
            and repeat.baseline_facts.wav_sha256 == anchor_base.wav_sha256
            and repeat.baseline_facts in base_rep
        ):
            byte_identical.append((repeat.comparison_id, "baseline"))
        if (
            anchor_cand is not None
            and repeat.candidate_facts is not None
            and repeat.candidate_facts.wav_sha256 == anchor_cand.wav_sha256
            and repeat.candidate_facts in cand_rep
        ):
            byte_identical.append((repeat.comparison_id, "candidate"))

    declarations: list[tuple[str, FullScaleDeclarations]] = [
        (anchor.comparison_id, anchor.declarations)
    ]
    for repeat in repeats:
        declarations.append((repeat.comparison_id, repeat.declarations))

    unmet: list[str] = []
    unevaluated: list[str] = []

    if anchor_base is None:
        unmet.append("facts_missing:baseline")
    if anchor_cand is None:
        unmet.append("facts_missing:candidate")

    decl_block = _declarations_block_regression(anchor.record.conditions)
    if decl_block is not None:
        unmet.append(f"declarations_block:{decl_block}")

    conditions = anchor.record.conditions
    identity = anchor.record.baseline_bundle.identity
    both_facts = anchor_base is not None and anchor_cand is not None

    if len(base_rep) < 1:
        unmet.append("repeat_missing:baseline")
    if len(cand_rep) < 1:
        unmet.append("repeat_missing:candidate")
    if (
        anchor_base is not None
        and len(base_rep) >= 1
        and not _renders_consistent(anchor_base, base_rep)
    ):
        unmet.append("renders_inconsistent:baseline")
    if (
        anchor_cand is not None
        and len(cand_rep) >= 1
        and not _renders_consistent(anchor_cand, cand_rep)
    ):
        unmet.append("renders_inconsistent:candidate")
    if conditions.baseline_version == conditions.candidate_version:
        unmet.append("same_version")
    if anchor.declarations.periodic_test_signal != "yes":
        unmet.append("periodic_not_declared")
    if (
        anchor_base is not None
        and anchor_base.pcm_bit_depth < FULL_SCALE_MIN_PCM_BIT_DEPTH
    ):
        unmet.append("bit_depth_below_16:baseline")
    if (
        anchor_cand is not None
        and anchor_cand.pcm_bit_depth < FULL_SCALE_MIN_PCM_BIT_DEPTH
    ):
        unmet.append("bit_depth_below_16:candidate")

    floor_ok = _floor_identity_ok(floor, anchor_base, anchor_cand)
    if not floor_ok:
        unmet.append("floor_missing")
        unevaluated.extend(
            (
                "samples_per_period_below_domain",
                "periods_in_range_below_domain",
                "critical_zone_reviewed",
            )
        )

    f0 = conditions.nominal_fundamental_hz
    fundamental_ok = f0 is not None and math.isfinite(f0) and f0 > 0
    if not fundamental_ok:
        unmet.append("fundamental_not_declared")
    elif floor_ok and floor is not None and f0 is not None:
        sr = identity.sample_rate_hz
        if sr / f0 < floor.min_samples_per_period:
            unmet.append("samples_per_period_below_domain")
        analyzed_for_periods: int | None = None
        if both_facts:
            assert anchor_base is not None
            analyzed_for_periods = anchor_base.analyzed_samples
        elif anchor_base is not None:
            analyzed_for_periods = anchor_base.analyzed_samples
        elif anchor_cand is not None:
            analyzed_for_periods = anchor_cand.analyzed_samples
        if (
            analyzed_for_periods is not None
            and analyzed_for_periods * f0 / sr < floor.min_periods_in_range
        ):
            unmet.append("periods_in_range_below_domain")

    if anchor_base is not None or anchor_cand is not None:
        step = _quantization_step(anchor_base, anchor_cand)
        if anchor_base is not None:
            threshold = anchor_base.full_scale_threshold
        else:
            assert anchor_cand is not None
            threshold = anchor_cand.full_scale_threshold
        zone_floor = floor if floor_ok else None
        if (
            not _facts_missing_side(unmet, "baseline")
            and any(
                _in_critical_zone(
                    facts,
                    threshold=threshold,
                    step=step,
                    floor=zone_floor,
                )
                for facts in baseline_renders
            )
        ):
            unmet.append("critical_zone:baseline")
        if (
            not _facts_missing_side(unmet, "candidate")
            and any(
                _in_critical_zone(
                    facts,
                    threshold=threshold,
                    step=step,
                    floor=zone_floor,
                )
                for facts in candidate_renders
            )
        ):
            unmet.append("critical_zone:candidate")

    transition: FullScaleTransition | None = None
    count_difference: int | None = None
    if both_facts:
        assert anchor_base is not None and anchor_cand is not None
        transition = _transition(anchor_base, anchor_cand)
        count_difference = anchor_cand.counted_samples - anchor_base.counted_samples

    status = _resolve_status(unmet, unevaluated)
    if (
        not unmet
        and not unevaluated
        and both_facts
        and floor is not None
        and transition is not None
        and anchor_base is not None
    ):
        status = _judgment_status(transition, count_difference, anchor_base, floor)

    record_without_digest = FullScaleCheckRecord(
        check_id=check_id,
        anchor_comparison_id=anchor.comparison_id,
        anchor_digest=anchor.record.digest,
        repeat_comparison_ids=tuple(r.comparison_id for r in repeats),
        uncounted_repeats=uncounted,
        declarations=tuple(declarations),
        baseline_renders=baseline_renders,
        candidate_renders=candidate_renders,
        counted_baseline_repeats=len(base_rep),
        counted_candidate_repeats=len(cand_rep),
        byte_identical_repeats=tuple(byte_identical),
        floor=floor if floor_ok else None,
        status=status,
        transition=transition,
        count_difference=count_difference,
        unmet_conditions=tuple(unmet),
        unevaluated_conditions=tuple(unevaluated),
        supersedes=supersedes,
        digest="0" * 64,
    )
    return record_without_digest.model_copy(
        update={"digest": _check_record_digest(record_without_digest)},
    )


def validate_full_scale_check_record(
    record: FullScaleCheckRecord,
    *,
    anchor: FullScaleSubmission,
    repeats: Sequence[FullScaleSubmission],
    approved_floors: Sequence[FullScaleMethodFloor] = PRODUCT_APPROVED_FULL_SCALE_FLOORS,
) -> None:
    if _check_record_digest(record) != record.digest:
        raise ValueError("full-scale check record digest mismatch")
    if record.floor is not None and record.floor not in approved_floors:
        raise ValueError("floor is not in the product approved registry")
    applicable = _applicable_approved_floors(
        approved_floors,
        anchor.baseline_facts,
        anchor.candidate_facts,
    )
    if applicable and record.floor not in applicable:
        raise ValueError("applicable approved floor must be present on the check record")
    for facts in record.baseline_renders:
        verify_full_scale_facts(facts, _bundle_for_facts(facts, anchor, repeats))
    for facts in record.candidate_renders:
        verify_full_scale_facts(facts, _bundle_for_facts(facts, anchor, repeats))
    expected = evaluate_full_scale_check(
        check_id=record.check_id,
        anchor=anchor,
        repeats=repeats,
        floor=record.floor,
        supersedes=record.supersedes,
    )
    if expected.model_dump() != record.model_dump():
        raise ValueError("full-scale check record does not match recomputed evaluation")


def _bundle_for_facts(
    facts: FullScaleFacts,
    anchor: FullScaleSubmission,
    repeats: Sequence[FullScaleSubmission],
) -> MeasurementBundle:
    # Match the submission slot that carries these facts. Identity fields alone
    # are not unique when independently encoded WAVs share the same bytes.
    for submission in (anchor, *repeats):
        if submission.baseline_facts == facts:
            return submission.record.baseline_bundle
        if submission.candidate_facts == facts:
            return submission.record.candidate_bundle
    raise ValueError("full-scale facts do not match any submission bundle")


def _applicable_approved_floors(
    approved_floors: Sequence[FullScaleMethodFloor],
    baseline: FullScaleFacts | None,
    candidate: FullScaleFacts | None,
) -> tuple[FullScaleMethodFloor, ...]:
    matched: list[FullScaleMethodFloor] = []
    for floor in approved_floors:
        if _floor_identity_ok(floor, baseline, candidate):
            matched.append(floor)
    return tuple(matched)


def _check_record_digest(record: FullScaleCheckRecord) -> str:
    payload = record.model_dump(mode="json")
    payload.pop("digest", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _independent_declared(declarations: FullScaleDeclarations, side: ComparisonSide) -> bool:
    if side == "baseline":
        return declarations.baseline_independent_render == "yes"
    return declarations.candidate_independent_render == "yes"


def _identity_mismatch(anchor: InputIdentity, other: InputIdentity) -> bool:
    return anchor.tool_parameter_snapshot != other.tool_parameter_snapshot


def _range_mismatch(anchor: InputIdentity, other: InputIdentity) -> bool:
    return (
        anchor.resolved_start_sample != other.resolved_start_sample
        or anchor.resolved_end_sample != other.resolved_end_sample
    )


def _renders_consistent(anchor: FullScaleFacts, repeats: Sequence[FullScaleFacts]) -> bool:
    for item in repeats:
        if item.counted_samples != anchor.counted_samples or item.state != anchor.state:
            return False
    return True


def _floor_identity_ok(
    floor: FullScaleMethodFloor | None,
    baseline: FullScaleFacts | None,
    candidate: FullScaleFacts | None,
) -> bool:
    if floor is None:
        return False
    if baseline is None or candidate is None:
        return False
    if full_scale_floor_digest(floor) != floor.digest:
        return False
    for facts in (baseline, candidate):
        if (
            floor.facts_version != facts.facts_version
            or floor.full_scale_threshold != facts.full_scale_threshold
            or floor.min_consecutive_samples != facts.min_consecutive_samples
        ):
            return False
    return True


def _quantization_step(
    baseline: FullScaleFacts | None,
    candidate: FullScaleFacts | None,
) -> float:
    bits: list[int] = []
    if baseline is not None:
        bits.append(baseline.pcm_bit_depth)
    if candidate is not None:
        bits.append(candidate.pcm_bit_depth)
    if not bits:
        return 2.0 ** -24
    min_bits = min(bits)
    return max(2.0 ** -(min_bits - 1), 2.0 ** -24)


def _in_critical_zone(
    facts: FullScaleFacts,
    *,
    threshold: float,
    step: float,
    floor: FullScaleMethodFloor | None,
) -> bool:
    if facts.state == "no":
        margin = step
        if floor is not None:
            margin = max(floor.zone_below_threshold, step)
        return facts.peak_abs >= threshold - margin
    if floor is None:
        return False
    above = facts.peak_abs <= threshold + floor.zone_above_threshold
    below_min = (
        floor.zone_min_counted_samples is not None
        and facts.counted_samples < floor.zone_min_counted_samples
    )
    return above or below_min


def _facts_missing_side(unmet: Sequence[str], side: ComparisonSide) -> bool:
    return f"facts_missing:{side}" in unmet


def _transition(baseline: FullScaleFacts, candidate: FullScaleFacts) -> FullScaleTransition:
    b_yes = baseline.state == "yes"
    c_yes = candidate.state == "yes"
    if not b_yes and not c_yes:
        return "no_to_no"
    if not b_yes and c_yes:
        return "no_to_yes"
    if b_yes and not c_yes:
        return "yes_to_no"
    diff = candidate.counted_samples - baseline.counted_samples
    if diff > 0:
        return "yes_to_yes_increase"
    if diff < 0:
        return "yes_to_yes_decrease"
    return "yes_to_yes_equal"


def _resolve_status(unmet: Sequence[str], unevaluated: Sequence[str]) -> MetricStatus:
    for code in unmet:
        if code.startswith(
            ("facts_missing:", "declarations_block:", "renders_inconsistent:")
        ):
            return "not_comparable"
    if unmet or unevaluated:
        return "descriptive_only"
    return "no_regression_detected"


def _judgment_status(
    transition: FullScaleTransition,
    count_difference: int | None,
    baseline: FullScaleFacts,
    floor: FullScaleMethodFloor,
) -> MetricStatus:
    if transition in ("no_to_no", "yes_to_no", "yes_to_yes_decrease", "yes_to_yes_equal"):
        return "no_regression_detected"
    if transition == "no_to_yes":
        return "regression_detected"
    if transition == "yes_to_yes_increase":
        diff = count_difference or 0
        over_samples = floor.count_floor_samples is not None and diff > floor.count_floor_samples
        over_ratio = False
        if floor.count_floor_ratio is not None:
            over_ratio = diff / baseline.analyzed_samples > floor.count_floor_ratio
        if floor.count_floor_samples is not None and floor.count_floor_ratio is not None:
            return "regression_detected" if over_samples and over_ratio else "no_regression_detected"
        if floor.count_floor_samples is not None:
            return "regression_detected" if over_samples else "no_regression_detected"
        return "regression_detected" if over_ratio else "no_regression_detected"
    return "no_regression_detected"
