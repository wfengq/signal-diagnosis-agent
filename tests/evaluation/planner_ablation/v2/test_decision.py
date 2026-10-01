"""T-CX297: v2 parameterized decision bands and negative cases."""

from __future__ import annotations

import pytest

from signal_diag.evaluation.planner_ablation.v2.decision import decide
from signal_diag.evaluation.planner_ablation.v2.models import (
    ArmModeRoundCell,
    ArmModeTotals,
    GuidanceCell,
    LatencyStats,
    MetricTables,
    OptionalRate,
    PrerequisiteReport,
    StudyProtocolV2,
    UpgradeCell,
)


def _rate(n: int, d: int) -> OptionalRate:
    if d == 0:
        return OptionalRate(numerator=0, denominator=0, value=None, evaluable=False)
    return OptionalRate(numerator=n, denominator=d, value=n / d, evaluable=True)


def _latency(*, mean: float, p95: float | None = None, count: int = 10) -> LatencyStats:
    return LatencyStats(
        count=count,
        mean_s=mean,
        median_s=mean,
        p95_s=mean if p95 is None else p95,
        max_s=max(mean, p95 or mean),
    )


def _prereq(**overrides: object) -> PrerequisiteReport:
    base = {
        "identity_ok": True,
        "timing_ok": True,
        "oracle_ok": True,
        "report_parity_ok": True,
        "matching_ok": True,
        "campaign_complete": True,
        "product_safety_ok": True,
        "fixed_safety_ok": True,
        "positive_claims_evaluable": True,
        "pinned_gate_identity_ok": True,
        "reason_codes": (),
        "all_passed": True,
    }
    base.update(overrides)
    if base.get("all_passed") is True:
        # Keep consistent unless explicitly overridden.
        pass
    return PrerequisiteReport(**base)  # type: ignore[arg-type]


def _cell(
    *,
    arm: str,
    mode: str,
    round_index: int,
    quality_n: int,
    denom: int,
    usefulness_n: int | None = None,
    completion_n: int | None = None,
    mean_s: float = 1.0,
    p95_s: float = 1.2,
    mean_tools: float = 2.0,
    correct_keys: frozenset[str] | None = None,
    safety_ok: bool = True,
    positive_claims: int = 1,
) -> ArmModeRoundCell:
    u = quality_n if usefulness_n is None else usefulness_n
    c = denom if completion_n is None else completion_n
    keys = correct_keys if correct_keys is not None else frozenset(
        {f"k{i}" for i in range(quality_n)}
    )
    return ArmModeRoundCell(
        arm=arm,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        round_index=round_index,
        scheduled_denominator=denom,
        quality=_rate(quality_n, denom),
        outcome_accuracy=_rate(quality_n, denom),
        usefulness=_rate(u, denom),
        completion=_rate(c, denom),
        unsupported_positive_claims=_rate(0, positive_claims),
        grounding=_rate(positive_claims, positive_claims),
        positive_claim_count=positive_claims,
        claim_data_complete=True,
        safety_ok=safety_ok,
        latency=_latency(mean=mean_s, p95=p95_s, count=denom),
        tool_action_count=int(mean_tools * denom),
        mean_tool_actions=mean_tools,
        quality_correct_keys=keys,
    )


def _upgrade(arm: str, round_index: int, s: int = 6) -> UpgradeCell:
    return UpgradeCell(
        arm=arm,  # type: ignore[arg-type]
        round_index=round_index,
        u_size=7,
        c_size=6,
        s_count=s,
        s_over_u=_rate(s, 7),
        s_over_c=_rate(s, 6),
        invalid_reference_abstention_correct=True,
        incremental_gain_count=s,
        already_met_not_incremental_count=0,
    )


def _guidance(arm: str, round_index: int, n: int = 4) -> GuidanceCell:
    return GuidanceCell(
        arm=arm,  # type: ignore[arg-type]
        round_index=round_index,
        g_size=4,
        emitted_count=n,
        emitted_and_correct=_rate(n, 4),
        conditional_template_ok=_rate(n, n) if n else _rate(0, 0),
    )


def _equal_tables(
    *,
    product_mean: float = 1.0,
    fixed_mean: float = 0.80,
    product_p95: float = 1.5,
    fixed_p95: float = 1.2,
    product_tools: float = 3.0,
    fixed_tools: float = 2.0,
    product_quality: int = 8,
    fixed_quality: int = 8,
    denom_single: int = 9,
    denom_paired: int = 10,
    product_keys_single: frozenset[str] | None = None,
    fixed_keys_single: frozenset[str] | None = None,
    mutate_cell=None,
) -> MetricTables:
    cells: list[ArmModeRoundCell] = []
    upgrades: list[UpgradeCell] = []
    guidance: list[GuidanceCell] = []
    for round_index in range(3):
        for mode, denom in (("single_signal", denom_single), ("paired_reference", denom_paired)):
            pq = product_quality
            fq = fixed_quality
            if mode == "single_signal":
                p_keys = (
                    product_keys_single
                    if product_keys_single is not None
                    else frozenset({f"ps{i}" for i in range(pq)})
                )
                f_keys = (
                    fixed_keys_single
                    if fixed_keys_single is not None
                    else frozenset({f"ps{i}" for i in range(fq)})
                )
            else:
                # Shared key namespace so equal counts do not look like planner gains.
                p_keys = frozenset({f"pp{i}" for i in range(pq)})
                f_keys = frozenset({f"pp{i}" for i in range(fq)})
            product = _cell(
                arm="product_agent",
                mode=mode,
                round_index=round_index,
                quality_n=pq,
                denom=denom,
                mean_s=product_mean,
                p95_s=product_p95,
                mean_tools=product_tools,
                correct_keys=p_keys,
            )
            fixed = _cell(
                arm="fixed_pipeline",
                mode=mode,
                round_index=round_index,
                quality_n=fq,
                denom=denom,
                mean_s=fixed_mean,
                p95_s=fixed_p95,
                mean_tools=fixed_tools,
                correct_keys=f_keys,
            )
            if mutate_cell is not None:
                product, fixed = mutate_cell(round_index, mode, product, fixed)
            cells.extend([product, fixed])
        upgrades.extend(
            [
                _upgrade("product_agent", round_index),
                _upgrade("fixed_pipeline", round_index),
            ]
        )
        guidance.extend(
            [
                _guidance("product_agent", round_index),
                _guidance("fixed_pipeline", round_index),
            ]
        )
    totals = []
    for arm in ("product_agent", "fixed_pipeline"):
        for mode, denom in (("single_signal", 27), ("paired_reference", 30)):
            q = product_quality * 3 if arm == "product_agent" else fixed_quality * 3
            totals.append(
                ArmModeTotals(
                    arm=arm,  # type: ignore[arg-type]
                    mode=mode,  # type: ignore[arg-type]
                    scheduled_denominator=denom,
                    quality=_rate(q, denom),
                    usefulness=_rate(q, denom),
                    completion=_rate(denom, denom),
                )
            )
    return MetricTables(
        cells=tuple(cells),
        upgrade_cells=tuple(upgrades),
        guidance_cells=tuple(guidance),
        arm_mode_totals=tuple(totals),
        descriptive_record_count=114,
        scheduled_slot_count=114,
        campaign_records_complete=True,
        partial_campaign=False,
    )


def _protocol() -> StudyProtocolV2:
    return StudyProtocolV2()


def test_fixed_dominance_at_exact_savings_boundary() -> None:
    # Exactly 20% and 0.100s: product mean 0.5, fixed mean 0.4
    metrics = _equal_tables(product_mean=0.5, fixed_mean=0.4)
    result = decide(_protocol(), metrics, _prereq())
    assert result.machine_candidate == "fixed_pipeline_dominance"
    assert result.eligible_conclusion == "fixed_pipeline_dominance"
    assert result.review_status == "pending"


@pytest.mark.parametrize(
    "product_mean,fixed_mean",
    [
        (0.5, 0.4001),  # ratio just below 0.20
        (0.5, 0.401),  # absolute saving just below 0.100 when targeting boundary
    ],
)
def test_dominance_blocked_when_either_savings_just_below(
    product_mean: float, fixed_mean: float
) -> None:
    # Case A: ratio < 0.20
    # Case B: use means where ratio ok but absolute < 0.100
    if fixed_mean == 0.401:
        # absolute saving = 0.099 < 0.100; ratio = 0.099/0.5 = 0.198 < 0.20 also
        metrics = _equal_tables(product_mean=1.0, fixed_mean=0.901)
        # absolute=0.099, ratio=0.099
    else:
        metrics = _equal_tables(product_mean=product_mean, fixed_mean=fixed_mean)
    result = decide(_protocol(), metrics, _prereq())
    assert result.eligible_conclusion == "insufficient_evidence"


def test_dominance_requires_both_ratio_and_absolute() -> None:
    # Absolute ok (0.15) but ratio only 0.15/1.0 = 0.15 < 0.20
    metrics = _equal_tables(product_mean=1.0, fixed_mean=0.85)
    assert decide(_protocol(), metrics, _prereq()).eligible_conclusion == (
        "insufficient_evidence"
    )
    # Ratio ok (0.25) but absolute 0.05 < 0.100
    metrics2 = _equal_tables(product_mean=0.2, fixed_mean=0.15)
    assert decide(_protocol(), metrics2, _prereq()).eligible_conclusion == (
        "insufficient_evidence"
    )
    # Both ok
    metrics3 = _equal_tables(product_mean=1.0, fixed_mean=0.8)
    assert decide(_protocol(), metrics3, _prereq()).eligible_conclusion == (
        "fixed_pipeline_dominance"
    )


def test_one_mode_round_quality_regression_blocks_dominance() -> None:
    def mutate(round_index, mode, product, fixed):
        if round_index == 1 and mode == "single_signal":
            fixed = fixed.model_copy(
                update={
                    "quality": _rate(7, 9),
                    "quality_correct_keys": frozenset({f"ps{i}" for i in range(7)}),
                }
            )
        return product, fixed

    metrics = _equal_tables(product_mean=0.5, fixed_mean=0.4, mutate_cell=mutate)
    result = decide(_protocol(), metrics, _prereq())
    assert result.eligible_conclusion == "insufficient_evidence"
    assert any("quality_regression" in c for c in result.reason_codes)


def test_worse_p95_or_mean_actions_blocks_dominance() -> None:
    metrics_p95 = _equal_tables(
        product_mean=0.5, fixed_mean=0.4, product_p95=1.0, fixed_p95=1.1
    )
    assert decide(_protocol(), metrics_p95, _prereq()).eligible_conclusion == (
        "insufficient_evidence"
    )
    metrics_tools = _equal_tables(
        product_mean=0.5,
        fixed_mean=0.4,
        product_tools=2.0,
        fixed_tools=2.5,
    )
    assert decide(_protocol(), metrics_tools, _prereq()).eligible_conclusion == (
        "insufficient_evidence"
    )


def test_zero_positive_claims_bad_timing_incomplete_campaign() -> None:
    metrics = _equal_tables(product_mean=0.5, fixed_mean=0.4)
    # Zero positive claims via prerequisites
    prereq = _prereq(
        positive_claims_evaluable=False,
        all_passed=False,
        reason_codes=("positive_claims_not_evaluable",),
    )
    assert decide(_protocol(), metrics, prereq).eligible_conclusion == (
        "insufficient_evidence"
    )

    prereq_timing = _prereq(
        timing_ok=False,
        matching_ok=False,
        all_passed=False,
        reason_codes=("invalid_timing",),
    )
    assert decide(_protocol(), metrics, prereq_timing).eligible_conclusion == (
        "insufficient_evidence"
    )

    incomplete = metrics.model_copy(
        update={"partial_campaign": True, "campaign_records_complete": False}
    )
    assert decide(_protocol(), incomplete, _prereq()).eligible_conclusion == (
        "insufficient_evidence"
    )


def test_planner_advantage_same_mode_all_rounds() -> None:
    # Product has one extra correct key in single_signal every round.
    product_keys = frozenset({f"ps{i}" for i in range(9)})
    fixed_keys = frozenset({f"ps{i}" for i in range(8)})

    def mutate(round_index, mode, product, fixed):
        if mode == "single_signal":
            product = product.model_copy(
                update={
                    "quality": _rate(9, 9),
                    "usefulness": _rate(9, 9),
                    "quality_correct_keys": product_keys,
                    "mean_s": 1.0,
                    "latency": _latency(mean=1.0, p95=1.2),
                    "mean_tool_actions": 3.0,
                }
            )
            fixed = fixed.model_copy(
                update={
                    "quality": _rate(8, 9),
                    "usefulness": _rate(8, 9),
                    "quality_correct_keys": fixed_keys,
                    "latency": _latency(mean=1.0, p95=1.2),
                    "mean_tool_actions": 3.0,
                }
            )
        else:
            # Equal paired quality; no latency dominance path intended.
            product = product.model_copy(
                update={"latency": _latency(mean=1.0), "mean_tool_actions": 3.0}
            )
            fixed = fixed.model_copy(
                update={"latency": _latency(mean=1.0), "mean_tool_actions": 3.0}
            )
        return product, fixed

    metrics = _equal_tables(
        product_mean=1.0,
        fixed_mean=1.0,
        product_quality=9,
        fixed_quality=9,
        mutate_cell=mutate,
    )
    result = decide(_protocol(), metrics, _prereq())
    assert result.machine_candidate == "planner_advantage"
    assert result.eligible_conclusion == "planner_advantage"
    assert result.review_status == "pending"


def test_mode_switching_quality_gains_do_not_qualify() -> None:
    # Round 0/1 gain in single; round 2 gain in paired only — not same mode all rounds.
    def mutate(round_index, mode, product, fixed):
        product = product.model_copy(
            update={"latency": _latency(mean=1.0), "mean_tool_actions": 3.0}
        )
        fixed = fixed.model_copy(
            update={"latency": _latency(mean=1.0), "mean_tool_actions": 3.0}
        )
        if round_index < 2 and mode == "single_signal":
            product = product.model_copy(
                update={
                    "quality": _rate(9, 9),
                    "quality_correct_keys": frozenset({f"ps{i}" for i in range(9)}),
                }
            )
            fixed = fixed.model_copy(
                update={
                    "quality": _rate(8, 9),
                    "quality_correct_keys": frozenset({f"ps{i}" for i in range(8)}),
                }
            )
        elif round_index == 2 and mode == "paired_reference":
            product = product.model_copy(
                update={
                    "quality": _rate(10, 10),
                    "quality_correct_keys": frozenset({f"pp{i}" for i in range(10)}),
                }
            )
            fixed = fixed.model_copy(
                update={
                    "quality": _rate(9, 10),
                    "quality_correct_keys": frozenset({f"pp{i}" for i in range(9)}),
                }
            )
        return product, fixed

    metrics = _equal_tables(mutate_cell=mutate)
    result = decide(_protocol(), metrics, _prereq())
    assert result.eligible_conclusion == "insufficient_evidence"
    assert any("no_same_mode_quality_gain" in c for c in result.reason_codes)


def test_utility_only_gains_do_not_qualify_as_planner_advantage() -> None:
    def mutate(round_index, mode, product, fixed):
        # Equal quality; product usefulness higher.
        product = product.model_copy(
            update={
                "usefulness": _rate(9, 9) if mode == "single_signal" else _rate(10, 10),
                "latency": _latency(mean=1.0),
                "mean_tool_actions": 3.0,
            }
        )
        fixed = fixed.model_copy(
            update={
                "usefulness": _rate(5, 9) if mode == "single_signal" else _rate(5, 10),
                "latency": _latency(mean=1.0),
                "mean_tool_actions": 3.0,
            }
        )
        return product, fixed

    metrics = _equal_tables(mutate_cell=mutate)
    result = decide(_protocol(), metrics, _prereq())
    assert result.eligible_conclusion == "insufficient_evidence"
    assert result.machine_candidate == "insufficient_evidence"


def test_three_exact_conclusions_independently() -> None:
    dominance = decide(
        _protocol(),
        _equal_tables(product_mean=0.5, fixed_mean=0.4),
        _prereq(),
    )
    assert dominance.eligible_conclusion == "fixed_pipeline_dominance"

    def mutate(round_index, mode, product, fixed):
        if mode == "single_signal":
            product = product.model_copy(
                update={
                    "quality": _rate(9, 9),
                    "usefulness": _rate(9, 9),
                    "quality_correct_keys": frozenset({f"ps{i}" for i in range(9)}),
                    "latency": _latency(mean=1.0),
                    "mean_tool_actions": 3.0,
                }
            )
            fixed = fixed.model_copy(
                update={
                    "quality": _rate(8, 9),
                    "usefulness": _rate(8, 9),
                    "quality_correct_keys": frozenset({f"ps{i}" for i in range(8)}),
                    "latency": _latency(mean=1.0),
                    "mean_tool_actions": 3.0,
                }
            )
        else:
            product = product.model_copy(
                update={"latency": _latency(mean=1.0), "mean_tool_actions": 3.0}
            )
            fixed = fixed.model_copy(
                update={"latency": _latency(mean=1.0), "mean_tool_actions": 3.0}
            )
        return product, fixed

    planner = decide(_protocol(), _equal_tables(mutate_cell=mutate), _prereq())
    assert planner.eligible_conclusion == "planner_advantage"

    insufficient = decide(
        _protocol(),
        _equal_tables(product_mean=1.0, fixed_mean=1.0),
        _prereq(),
    )
    assert insufficient.eligible_conclusion == "insufficient_evidence"
