"""Harness-only dry-run campaign helpers (never scored evidence)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from signal_diag.evaluation.planner_ablation.baseline import (
    PlannerAblationFixedPipelineBaseline,
)
from signal_diag.evaluation.planner_ablation.executor import ProductSlotExecutor
from signal_diag.evaluation.planner_ablation.models import (
    FixedPipelineOutcome,
    PlannerAblationBaselineRequest,
    ProductSlotOutcome,
    ProductSlotRequest,
)
from signal_diag.evaluation.planner_ablation.report_fields import (
    derive_context_guidance_from_baseline,
)

StudyMode = Literal["single_signal", "paired_reference"]


@dataclass(frozen=True)
class DryRunSlotResult:
    executor_kind: Literal["scripted_product", "fixed_pipeline"]
    mode: StudyMode
    execution_identity: Literal["harness_only"]
    planner_class: str
    provider_calls: int


async def run_harness_dry_run_product_slot(
    executor: ProductSlotExecutor,
    request: ProductSlotRequest,
    *,
    provider_calls: int,
) -> ProductSlotOutcome:
    outcome = await executor.execute_product_slot(request)
    return outcome.model_copy(
        update={
            "execution_identity": "harness_only",
            "planner_class": outcome.planner_class,
        }
    )


async def run_harness_dry_run_fixed_slot(
    baseline: PlannerAblationFixedPipelineBaseline,
    request: PlannerAblationBaselineRequest,
) -> FixedPipelineOutcome:
    result = await baseline.run(request)
    raw_mode = request.stimulus_context.mode
    if raw_mode not in ("single_signal", "paired_reference"):
        raise ValueError("harness dry-run supports single_signal and paired_reference only")
    mode: StudyMode = raw_mode
    guidance = derive_context_guidance_from_baseline(mode=mode, baseline=result)
    return FixedPipelineOutcome(
        case_id=request.case_id,
        mode=mode,
        baseline_result=result,
        context_guidance=guidance,
    )


async def run_four_path_harness_dry_run(
    *,
    scripted_executor: ProductSlotExecutor,
    baseline: PlannerAblationFixedPipelineBaseline,
    single_product_request: ProductSlotRequest,
    paired_product_request: ProductSlotRequest,
    single_baseline_request: PlannerAblationBaselineRequest,
    paired_baseline_request: PlannerAblationBaselineRequest,
    provider_calls: int,
) -> tuple[DryRunSlotResult, ...]:
    await run_harness_dry_run_product_slot(
        scripted_executor, single_product_request, provider_calls=provider_calls
    )
    await run_harness_dry_run_product_slot(
        scripted_executor, paired_product_request, provider_calls=provider_calls
    )
    await run_harness_dry_run_fixed_slot(baseline, single_baseline_request)
    await run_harness_dry_run_fixed_slot(baseline, paired_baseline_request)
    return (
        DryRunSlotResult(
            executor_kind="scripted_product",
            mode="single_signal",
            execution_identity="harness_only",
            planner_class="ScriptedPlanner",
            provider_calls=provider_calls,
        ),
        DryRunSlotResult(
            executor_kind="scripted_product",
            mode="paired_reference",
            execution_identity="harness_only",
            planner_class="ScriptedPlanner",
            provider_calls=provider_calls,
        ),
        DryRunSlotResult(
            executor_kind="fixed_pipeline",
            mode="single_signal",
            execution_identity="harness_only",
            planner_class="PlannerAblationFixedPipelineBaseline",
            provider_calls=0,
        ),
        DryRunSlotResult(
            executor_kind="fixed_pipeline",
            mode="paired_reference",
            execution_identity="harness_only",
            planner_class="PlannerAblationFixedPipelineBaseline",
            provider_calls=0,
        ),
    )
