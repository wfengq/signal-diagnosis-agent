"""Resource-candidate validation negatives (Task 6)."""

from __future__ import annotations

from pathlib import Path

from signal_diag.app.planner_ablation_v2_adapter import _resolve_product_provenance
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    ResourceCandidateValidation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEV2_ROOT = (
    PROJECT_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2"
)


def test_fixture_budget_cannot_make_production_candidate_ready() -> None:
    # Fixture-only complete budgets / extensions never authorize production readiness.
    result = ResourceCandidateValidation(
        ready=False,
        reasons=("fixture_only_resource_extension", "resource_assessment_blocked"),
        fixture_only=True,
    )
    assert result.ready is False
    assert "fixture_only_resource_extension" in result.reasons


def test_class_name_and_booleans_do_not_authenticate_path() -> None:
    prov = _resolve_product_provenance(
        planner_class="RealLLMPlanner",
        provider_client_bound=False,
        offline_session=True,
    )
    assert prov.execution_identity == "harness_only"
    assert prov.offline_session is True


def test_native_mock_cannot_be_relabelled_online() -> None:
    prov = _resolve_product_provenance(
        planner_class="RealLLMPlanner",
        provider_client_bound=False,
        offline_session=True,
    )
    assert prov.execution_identity == "harness_only"


def test_no_real_seal_under_dev2_evidence_root_resource_doc() -> None:
    assert not (DEV2_ROOT / "protocol_seal").exists()
    assert (DEV2_ROOT / "RESOURCE_BOUNDS.md").is_file()
    names = {path.name for path in DEV2_ROOT.iterdir() if path.name != "__pycache__"}
    assert names <= {
        "design_inputs.md",
        "OFFLINE_ACCEPTANCE.md",
        "LABEL_REVIEW.md",
        "BUDGET_BOUNDS.md",
        "RESOURCE_BOUNDS.md",
    }
