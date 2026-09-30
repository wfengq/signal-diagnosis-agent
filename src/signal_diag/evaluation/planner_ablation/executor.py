"""Injected executor protocol for study product slots."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from signal_diag.evaluation.planner_ablation.models import (
    ProductSlotOutcome,
    ProductSlotRequest,
)


@runtime_checkable
class ProductSlotExecutor(Protocol):
    """Application-backed product slot; evaluation depends only on this surface."""

    async def execute_product_slot(
        self,
        request: ProductSlotRequest,
    ) -> ProductSlotOutcome: ...
