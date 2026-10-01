"""Study runner over injected product-slot executors."""

from __future__ import annotations

from signal_diag.evaluation.planner_ablation.executor import ProductSlotExecutor
from signal_diag.evaluation.planner_ablation.models import (
    ProductSlotOutcome,
    ProductSlotRequest,
)


async def run_product_slot(
    executor: ProductSlotExecutor,
    request: ProductSlotRequest,
) -> ProductSlotOutcome:
    return await executor.execute_product_slot(request)
