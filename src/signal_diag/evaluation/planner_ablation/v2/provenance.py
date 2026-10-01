"""Scored-product provenance gates for planner-ablation v2 (dev_2).

Offline Scripted / fake-client sessions are immutable harness_only evidence.
Relabeling arm or planner class strings cannot elevate them to scored product
ingestion. Bundle digests bind stored provenance; alteration invalidates the
binding. Digests authenticate the sealed bytes under study control — they do
not authenticate arbitrary maliciously fabricated artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from signal_diag.evaluation.planner_ablation.v2.models import (
    SCORING_IDENTITY_V2,
    STUDY_ID_V2,
    CampaignRecord,
    ExecutionProvenance,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.population import canonical_json

_APPROVED_PRODUCT_PLANNER = "RealLLMPlanner"
_REQUIRED_FIELDS = (
    "arm",
    "execution_identity",
    "planner_class",
    "study_id",
    "scoring_identity",
    "offline_session",
    "provider_client_bound",
    "verified_online_context",
)


class ProvenanceRejection(ValueError):
    """Raised when an artifact is refused for scored product ingestion."""


def campaign_bundle_digest(record: CampaignRecord) -> str:
    """SHA-256 of the canonical campaign ledger (binds stored provenance)."""
    payload = record.model_dump(mode="json")
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verify_campaign_bundle_binding(
    record: CampaignRecord,
    expected_digest: str,
) -> None:
    """Fail closed when stored provenance or other ledger bytes drift."""
    actual = campaign_bundle_digest(record)
    if actual != expected_digest:
        raise ProvenanceRejection(
            "campaign bundle binding digest mismatch; altered provenance or "
            "ledger bytes invalidate the binding"
        )


def terminal_to_scored_record(
    terminal: StudyTerminal,
    *,
    study_id: str = STUDY_ID_V2,
    scoring_identity: str = SCORING_IDENTITY_V2,
    verified_online_context: bool = False,
) -> dict[str, Any]:
    """Project a terminal into the scored-ingestion provenance shape."""
    return {
        "arm": terminal.arm,
        "execution_identity": terminal.provenance.execution_identity,
        "planner_class": terminal.provenance.planner_class,
        "study_id": study_id,
        "scoring_identity": scoring_identity,
        "offline_session": terminal.provenance.offline_session,
        "provider_client_bound": terminal.provenance.provider_client_bound,
        "verified_online_context": verified_online_context,
    }


def validate_scored_product_ingestion(record: Mapping[str, object]) -> None:
    """Reject harness-only / relabeled / fake-client artifacts for scored use.

    Class-name strings alone are insufficient. Exact approved product planner
    type and verified online execution context are required. Scripted,
    fake-client RealLLMPlanner, synthetic fixtures, and any offline session
    remain non-scored.
    """
    for field in _REQUIRED_FIELDS:
        if field not in record:
            raise ProvenanceRejection(f"missing scored provenance field: {field}")

    study_id = str(record["study_id"])
    if study_id != STUDY_ID_V2:
        raise ProvenanceRejection(f"foreign study identity: {study_id}")

    scoring_identity = str(record["scoring_identity"])
    if scoring_identity != SCORING_IDENTITY_V2:
        raise ProvenanceRejection(f"foreign scoring identity: {scoring_identity}")

    execution_identity = record.get("execution_identity")
    if execution_identity == "harness_only":
        raise ProvenanceRejection(
            "harness_only execution_identity is not scored product evidence"
        )
    if execution_identity != "product_campaign":
        raise ProvenanceRejection(f"unknown execution_identity: {execution_identity}")

    offline_session = record.get("offline_session")
    if offline_session is not False:
        raise ProvenanceRejection(
            "offline_session artifacts cannot pass verified-context scored ingestion"
        )

    if record.get("verified_online_context") is not True:
        raise ProvenanceRejection(
            "verified_online_context required for scored product ingestion"
        )

    provider_client_bound = record.get("provider_client_bound")
    if provider_client_bound is not False:
        # Injected fake/test clients are not the approved online provider path.
        raise ProvenanceRejection(
            "provider_client_bound fake-client / injected client is harness_only"
        )

    arm = record.get("arm")
    if arm not in ("product_agent", "fixed_pipeline"):
        raise ProvenanceRejection(f"unknown scored arm: {arm}")

    planner_class = str(record.get("planner_class", ""))
    if "ScriptedPlanner" in planner_class or planner_class.startswith("_"):
        raise ProvenanceRejection(
            "ScriptedPlanner / harness planner artifacts are not scored product evidence"
        )
    if arm == "product_agent" and planner_class != _APPROVED_PRODUCT_PLANNER:
        raise ProvenanceRejection(
            "product_campaign product_agent requires RealLLMPlanner provenance"
        )
    if arm == "fixed_pipeline" and planner_class == _APPROVED_PRODUCT_PLANNER:
        raise ProvenanceRejection(
            "fixed_pipeline arm cannot claim RealLLMPlanner provenance"
        )


def reject_relabeled_harness_terminal(
    terminal: StudyTerminal,
    *,
    rewrite: Mapping[str, object] | None = None,
) -> None:
    """Rewrite arm/class labels on a harness terminal and assert rejection."""
    base = terminal_to_scored_record(terminal)
    if rewrite:
        base.update(dict(rewrite))
    validate_scored_product_ingestion(base)


def assert_harness_only_provenance(provenance: ExecutionProvenance) -> None:
    """Offline sessions must remain harness_only regardless of planner class."""
    if provenance.execution_identity != "harness_only":
        raise ProvenanceRejection(
            "offline / fake-client provenance must remain harness_only"
        )
    if not provenance.offline_session:
        raise ProvenanceRejection("offline session flag must stay true offline")
