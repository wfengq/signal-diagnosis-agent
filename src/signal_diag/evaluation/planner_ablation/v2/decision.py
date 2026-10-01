"""V2 planner-ablation decision language (dev_2).

Derives constrained regressions and latency savings from metric tables.
Callers cannot supply safety/matching booleans or a latency improvement ratio.
Machine decision remains distinct from human review and product authority.
"""

from __future__ import annotations

from signal_diag.evaluation.planner_ablation.v2.models import (
    ArmModeRoundCell,
    DecisionResult,
    GuidanceCell,
    MachineConclusion,
    MetricTables,
    PrerequisiteReport,
    StudyMode,
    StudyProtocolV2,
    UpgradeCell,
)


def _cell(
    metrics: MetricTables,
    *,
    arm: str,
    mode: StudyMode,
    round_index: int,
) -> ArmModeRoundCell:
    for cell in metrics.cells:
        if (
            cell.arm == arm
            and cell.mode == mode
            and cell.round_index == round_index
        ):
            return cell
    raise KeyError(f"missing metric cell {arm}/{mode}/r{round_index}")


def _upgrade(
    metrics: MetricTables, *, arm: str, round_index: int
) -> UpgradeCell:
    for cell in metrics.upgrade_cells:
        if cell.arm == arm and cell.round_index == round_index:
            return cell
    raise KeyError(f"missing upgrade cell {arm}/r{round_index}")


def _guidance(
    metrics: MetricTables, *, arm: str, round_index: int
) -> GuidanceCell:
    for cell in metrics.guidance_cells:
        if cell.arm == arm and cell.round_index == round_index:
            return cell
    raise KeyError(f"missing guidance cell {arm}/r{round_index}")


def _rate_non_inferior(
    challenger: float | None,
    reference: float | None,
    *,
    tolerance: float,
) -> bool:
    """Exactly zero loss without epsilon; compare without pre-threshold rounding."""
    if challenger is None or reference is None:
        return False
    return challenger + tolerance >= reference


def _upgrade_non_inferior(fixed: UpgradeCell, product: UpgradeCell) -> bool:
    if not fixed.s_over_u.evaluable or not product.s_over_u.evaluable:
        return False
    if fixed.s_count < product.s_count:
        return False
    # Zero C is not-evaluable; cannot claim non-inferior success.
    return fixed.c_size != 0 and product.c_size != 0


def _guidance_non_inferior(fixed: GuidanceCell, product: GuidanceCell) -> bool:
    if not fixed.emitted_and_correct.evaluable or not product.emitted_and_correct.evaluable:
        return False
    return fixed.emitted_and_correct.numerator >= product.emitted_and_correct.numerator


def _latency_dominance_ok(
    product: ArmModeRoundCell,
    fixed: ArmModeRoundCell,
    *,
    ratio: float,
    absolute_s: float,
) -> bool:
    from decimal import Decimal

    p_mean = product.latency.mean_s
    f_mean = fixed.latency.mean_s
    if p_mean is None or f_mean is None or p_mean <= 0.0:
        return False
    # Decimal avoids binary float drift at exact (0.20, 0.100) boundaries.
    p = Decimal(str(p_mean))
    f = Decimal(str(f_mean))
    saving = p - f
    if p <= 0:
        return False
    saving_ratio = saving / p
    if saving_ratio < Decimal(str(ratio)):
        return False
    if saving < Decimal(str(absolute_s)):
        return False
    p_p95 = product.latency.p95_s
    f_p95 = fixed.latency.p95_s
    if p_p95 is None or f_p95 is None:
        return False
    if Decimal(str(f_p95)) > Decimal(str(p_p95)):
        return False
    if product.mean_tool_actions is None or fixed.mean_tool_actions is None:
        return False
    return not Decimal(str(fixed.mean_tool_actions)) > Decimal(str(product.mean_tool_actions))


def _fixed_dominance(
    protocol: StudyProtocolV2,
    metrics: MetricTables,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    tol = protocol.quality_loss_tolerance
    modes: tuple[StudyMode, ...] = ("single_signal", "paired_reference")
    for round_index in range(protocol.rounds):
        for mode in modes:
            product = _cell(
                metrics,
                arm="product_agent",
                mode=mode,
                round_index=round_index,
            )
            fixed = _cell(
                metrics,
                arm="fixed_pipeline",
                mode=mode,
                round_index=round_index,
            )
            if not _rate_non_inferior(
                fixed.quality.value, product.quality.value, tolerance=tol
            ):
                reasons.append(f"quality_regression:{mode}:r{round_index}")
            if not _rate_non_inferior(
                fixed.usefulness.value, product.usefulness.value, tolerance=tol
            ):
                reasons.append(f"usefulness_regression:{mode}:r{round_index}")
            if not _rate_non_inferior(
                fixed.completion.value, product.completion.value, tolerance=tol
            ):
                reasons.append(f"completion_regression:{mode}:r{round_index}")
            if not _latency_dominance_ok(
                product,
                fixed,
                ratio=protocol.material_improvement_ratio,
                absolute_s=protocol.material_absolute_saving_s,
            ):
                reasons.append(f"latency_or_action_gate_failed:{mode}:r{round_index}")

        product_u = _upgrade(metrics, arm="product_agent", round_index=round_index)
        fixed_u = _upgrade(metrics, arm="fixed_pipeline", round_index=round_index)
        if not _upgrade_non_inferior(fixed_u, product_u):
            reasons.append(f"upgrade_regression:r{round_index}")
        product_g = _guidance(metrics, arm="product_agent", round_index=round_index)
        fixed_g = _guidance(metrics, arm="fixed_pipeline", round_index=round_index)
        if not _guidance_non_inferior(fixed_g, product_g):
            reasons.append(f"guidance_regression:r{round_index}")

    return (not reasons, tuple(reasons))


def _planner_advantage(
    protocol: StudyProtocolV2,
    metrics: MetricTables,
) -> tuple[bool, tuple[str, ...]]:
    """Quality sole primary: +1 correct key in the SAME mode in ALL 3 rounds."""
    if protocol.primary_endpoint != "quality":
        return False, ("primary_endpoint_not_quality",)

    modes: tuple[StudyMode, ...] = ("single_signal", "paired_reference")
    reasons: list[str] = []
    tol = protocol.quality_loss_tolerance

    # Find a mode with >=1 extra correct key in every round.
    qualifying_modes: list[StudyMode] = []
    for mode in modes:
        ok_all_rounds = True
        for round_index in range(protocol.rounds):
            product = _cell(
                metrics,
                arm="product_agent",
                mode=mode,
                round_index=round_index,
            )
            fixed = _cell(
                metrics,
                arm="fixed_pipeline",
                mode=mode,
                round_index=round_index,
            )
            extra = len(product.quality_correct_keys - fixed.quality_correct_keys)
            # Also allow pure count superiority when keys differ only by count.
            count_extra = product.quality.numerator - fixed.quality.numerator
            if extra < 1 and count_extra < 1:
                ok_all_rounds = False
                break
            if count_extra < 1 and extra < 1:
                ok_all_rounds = False
                break
        if ok_all_rounds:
            qualifying_modes.append(mode)

    if not qualifying_modes:
        return False, ("no_same_mode_quality_gain_all_rounds",)

    # No quality regression in the other mode; no utility/completion/upgrade/guidance regression.
    for round_index in range(protocol.rounds):
        for mode in modes:
            product = _cell(
                metrics,
                arm="product_agent",
                mode=mode,
                round_index=round_index,
            )
            fixed = _cell(
                metrics,
                arm="fixed_pipeline",
                mode=mode,
                round_index=round_index,
            )
            if mode not in qualifying_modes and not _rate_non_inferior(
                product.quality.value, fixed.quality.value, tolerance=tol
            ):
                reasons.append(f"quality_regression_other_mode:{mode}:r{round_index}")
            if not _rate_non_inferior(
                product.usefulness.value, fixed.usefulness.value, tolerance=tol
            ):
                reasons.append(f"usefulness_regression:{mode}:r{round_index}")
            if not _rate_non_inferior(
                product.completion.value, fixed.completion.value, tolerance=tol
            ):
                reasons.append(f"completion_regression:{mode}:r{round_index}")

        product_u = _upgrade(metrics, arm="product_agent", round_index=round_index)
        fixed_u = _upgrade(metrics, arm="fixed_pipeline", round_index=round_index)
        if product_u.s_count < fixed_u.s_count:
            reasons.append(f"upgrade_regression:r{round_index}")
        product_g = _guidance(metrics, arm="product_agent", round_index=round_index)
        fixed_g = _guidance(metrics, arm="fixed_pipeline", round_index=round_index)
        if (
            product_g.emitted_and_correct.numerator
            < fixed_g.emitted_and_correct.numerator
        ):
            reasons.append(f"guidance_regression:r{round_index}")

    return (not reasons, tuple(reasons))


def decide(
    protocol: StudyProtocolV2,
    metrics: MetricTables,
    prerequisites: PrerequisiteReport,
) -> DecisionResult:
    """Machine candidate from metrics/prerequisites. review_status stays pending."""
    reasons: list[str] = []

    # Partial / incomplete campaigns never enter the complete comparison path.
    if metrics.partial_campaign or not metrics.campaign_records_complete:
        reasons.append("incomplete_campaign")
        return DecisionResult(
            machine_candidate="insufficient_evidence",
            eligible_conclusion="insufficient_evidence",
            reason_codes=tuple(dict.fromkeys([*prerequisites.reason_codes, *reasons])),
            review_status="pending",
        )

    if not prerequisites.all_passed:
        reasons.extend(prerequisites.reason_codes)
        if not reasons:
            reasons.append("prerequisites_failed")
        conclusion: MachineConclusion = "insufficient_evidence"
        return DecisionResult(
            machine_candidate=conclusion,
            eligible_conclusion=conclusion,
            reason_codes=tuple(dict.fromkeys(reasons)),
            review_status="pending",
        )

    dominance_ok, dominance_reasons = _fixed_dominance(protocol, metrics)
    if dominance_ok:
        return DecisionResult(
            machine_candidate="fixed_pipeline_dominance",
            eligible_conclusion="fixed_pipeline_dominance",
            reason_codes=(),
            review_status="pending",
        )

    planner_ok, planner_reasons = _planner_advantage(protocol, metrics)
    if planner_ok:
        return DecisionResult(
            machine_candidate="planner_advantage",
            eligible_conclusion="planner_advantage",
            reason_codes=(),
            review_status="pending",
        )

    reasons.extend(dominance_reasons)
    reasons.extend(planner_reasons)
    if not reasons:
        reasons.append("no_accepted_band")
    return DecisionResult(
        machine_candidate="insufficient_evidence",
        eligible_conclusion="insufficient_evidence",
        reason_codes=tuple(dict.fromkeys(reasons)),
        review_status="pending",
    )
