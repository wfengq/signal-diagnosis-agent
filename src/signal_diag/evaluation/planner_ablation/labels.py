"""Scoring attribution labels for planner-ablation study arms."""

from __future__ import annotations

from typing import Literal

PlannerAttributionLabel = Literal["planner_skill", "deterministic_product_behavior"]


def guidance_attribution_label() -> PlannerAttributionLabel:
    """context_guidance is never planner skill (§19.3 / T-CX279)."""
    return "deterministic_product_behavior"


def assert_guidance_not_planner_attributed(label: PlannerAttributionLabel) -> None:
    if label == "planner_skill":
        raise ValueError("context_guidance must not be scored as planner skill")
