"""Planner-ablation utility study harness (additive; D038 / §19)."""

from signal_diag.evaluation.planner_ablation.baseline import (
    PlannerAblationFixedPipelineBaseline,
)
from signal_diag.evaluation.planner_ablation.decision import (
    StudyConclusion,
    decide_study_conclusion,
)
from signal_diag.evaluation.planner_ablation.executor import ProductSlotExecutor
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
    validate_scored_campaign_input,
)
from signal_diag.evaluation.planner_ablation.models import (
    PlannerAblationBaselineRequest,
    ProductSlotOutcome,
    ProductSlotRequest,
)

__all__ = [
    "PLANNER_ABLATION_SCORING_IDENTITY",
    "PLANNER_ABLATION_STUDY_ID",
    "PlannerAblationBaselineRequest",
    "PlannerAblationFixedPipelineBaseline",
    "ProductSlotExecutor",
    "ProductSlotOutcome",
    "ProductSlotRequest",
    "StudyConclusion",
    "decide_study_conclusion",
    "validate_scored_campaign_input",
]
