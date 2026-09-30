"""Study identity and scored-input validation."""

from __future__ import annotations

from collections.abc import Mapping

PLANNER_ABLATION_STUDY_ID = "study_s1_planner_ablation_dev_1"
PLANNER_ABLATION_SCORING_IDENTITY = "signal_diag.planner_ablation_scoring"
PLANNER_ABLATION_SCORING_VERSION = "1.0.0-dev.1"

_REQUIRED_PROVENANCE_FIELDS = (
    "arm",
    "execution_identity",
    "planner_class",
    "study_id",
    "scoring_identity",
)


def validate_study_identity(study_id: str) -> None:
    if study_id != PLANNER_ABLATION_STUDY_ID:
        raise ValueError(f"foreign study identity: {study_id}")


def validate_scoring_identity_derivation(
    *,
    study_id: str,
    scoring_identity: str,
    derivation: str,
) -> None:
    """T-CX280: reject foreign identities and wrong denominator derivation labels."""
    validate_study_identity(study_id)
    if scoring_identity != PLANNER_ABLATION_SCORING_IDENTITY:
        raise ValueError(f"foreign scoring identity: {scoring_identity}")
    allowed = {
        "completion_slots",
        "claim_completed_diagnosis",
        "outcome_population",
    }
    if derivation not in allowed:
        raise ValueError(f"unsupported denominator derivation: {derivation}")


def validate_scored_campaign_input(record: Mapping[str, object]) -> None:
    """T-CX288: reject harness-only / Scripted artifacts even if arm is rewritten."""
    for field in _REQUIRED_PROVENANCE_FIELDS:
        if field not in record:
            raise ValueError(f"missing scored provenance field: {field}")
    study_id = str(record["study_id"])
    scoring_identity = str(record["scoring_identity"])
    validate_study_identity(study_id)
    if scoring_identity != PLANNER_ABLATION_SCORING_IDENTITY:
        raise ValueError(f"foreign scoring identity: {scoring_identity}")

    execution_identity = record.get("execution_identity")
    if execution_identity == "harness_only":
        raise ValueError("harness_only execution_identity is not scored evidence")
    if execution_identity not in ("product_campaign",):
        raise ValueError(f"unknown execution_identity: {execution_identity}")

    arm = record.get("arm")
    if arm not in ("product_agent", "fixed_pipeline"):
        raise ValueError(f"unknown scored arm: {arm}")
    if arm == "scripted_agent":
        raise ValueError("scripted_agent arm is harness-only")
    if arm == "product_agent" and execution_identity != "product_campaign":
        raise ValueError("product_agent arm requires product_campaign execution_identity")

    planner_class = str(record.get("planner_class", ""))
    if planner_class.endswith("ScriptedPlanner"):
        raise ValueError("ScriptedPlanner artifacts are not scored product_agent evidence")
