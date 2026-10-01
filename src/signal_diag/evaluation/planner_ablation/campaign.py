"""Harness-only dry-run campaign helpers (never scored evidence)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

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


class ProviderCallCounter(Protocol):
    @property
    def calls(self) -> int:
        ...


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
    provider: ProviderCallCounter,
) -> tuple[ProductSlotOutcome, DryRunSlotResult]:
    outcome = await executor.execute_product_slot(request)
    harness_outcome = outcome.model_copy(
        update={
            "execution_identity": "harness_only",
            "planner_class": outcome.planner_class,
        }
    )
    return harness_outcome, DryRunSlotResult(
        executor_kind="scripted_product",
        mode=request.mode,
        execution_identity="harness_only",
        planner_class=outcome.planner_class,
        provider_calls=provider.calls,
    )


async def run_harness_dry_run_fixed_slot(
    baseline: PlannerAblationFixedPipelineBaseline,
    request: PlannerAblationBaselineRequest,
) -> tuple[FixedPipelineOutcome, DryRunSlotResult]:
    result = await baseline.run(request)
    raw_mode = request.stimulus_context.mode
    if raw_mode not in ("single_signal", "paired_reference"):
        raise ValueError("harness dry-run supports single_signal and paired_reference only")
    mode: StudyMode = raw_mode
    guidance = derive_context_guidance_from_baseline(mode=mode, baseline=result)
    outcome = FixedPipelineOutcome(
        case_id=request.case_id,
        mode=mode,
        baseline_result=result,
        context_guidance=guidance,
    )
    return outcome, DryRunSlotResult(
        executor_kind="fixed_pipeline",
        mode=mode,
        execution_identity="harness_only",
        planner_class=type(baseline).__name__,
        provider_calls=0,
    )


async def run_four_path_harness_dry_run(
    *,
    scripted_executor: ProductSlotExecutor,
    baseline: PlannerAblationFixedPipelineBaseline,
    single_product_request: ProductSlotRequest,
    paired_product_request: ProductSlotRequest,
    single_baseline_request: PlannerAblationBaselineRequest,
    paired_baseline_request: PlannerAblationBaselineRequest,
    provider: ProviderCallCounter,
) -> tuple[DryRunSlotResult, ...]:
    _, single_product = await run_harness_dry_run_product_slot(
        scripted_executor, single_product_request, provider=provider
    )
    _, paired_product = await run_harness_dry_run_product_slot(
        scripted_executor, paired_product_request, provider=provider
    )
    _, single_fixed = await run_harness_dry_run_fixed_slot(baseline, single_baseline_request)
    _, paired_fixed = await run_harness_dry_run_fixed_slot(baseline, paired_baseline_request)
    return (single_product, paired_product, single_fixed, paired_fixed)
