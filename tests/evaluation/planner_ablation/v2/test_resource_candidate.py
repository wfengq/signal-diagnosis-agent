"""Resource-candidate validation negatives (Task 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from signal_diag.app.planner_ablation_v2_adapter import _resolve_product_provenance
from signal_diag.evaluation.planner_ablation.v2.models import CandidateManifestV2
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    validate_resource_candidate,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEV2_ROOT = (
    PROJECT_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2"
)


def test_fixture_budget_cannot_make_production_candidate_ready() -> None:
    # Validator must be invoked; missing extension never authorizes readiness.
    candidate = CandidateManifestV2.model_construct(resource_extension=None)
    result = validate_resource_candidate(candidate, repository_root=PROJECT_ROOT)
    assert result.ready is False
    assert "missing_resource_extension" in result.reasons


def test_forged_resource_extension_dict_is_rejected() -> None:
    candidate = CandidateManifestV2.model_construct(
        resource_extension={
            "resource_policy": "planner_ablation_resource_v1",
            "telemetry_schema": "planner_ablation_telemetry_v1",
            "fixture_only": False,
        }
    )
    result = validate_resource_candidate(candidate, repository_root=PROJECT_ROOT)
    assert result.ready is False
    assert any(r.startswith("invalid_resource_extension") for r in result.reasons)


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


def test_build_candidate_enforces_validation_result_not_ignored() -> None:
    from signal_diag.evaluation.planner_ablation.v2.sealing import (
        validate_resource_candidate,
    )

    # Construction must apply validation readiness: forged extensions stay not-ready.
    candidate = CandidateManifestV2.model_construct(
        resource_extension={
            "resource_policy": "planner_ablation_resource_v1",
            "telemetry_schema": "planner_ablation_telemetry_v1",
            "fixture_only": False,
        },
        seal_ready=True,
        label_review=None,
    )
    result = validate_resource_candidate(candidate, repository_root=PROJECT_ROOT)
    assert result.ready is False
    assert any(r.startswith("invalid_resource_extension") for r in result.reasons)
    # Production build path copies this into seal_ready=False (see sealing.py).
    assert not (result.ready and candidate.seal_ready)


def test_generate_seal_omitting_extension_requires_legacy_fixture_flag(
    tmp_path: Path,
) -> None:
    from signal_diag.evaluation.planner_ablation.v2.models import CandidateManifestV2
    from signal_diag.evaluation.planner_ablation.v2.sealing import generate_seal

    candidate = CandidateManifestV2.model_construct(
        seal_ready=True,
        resource_extension=None,
        study_id="study_s1_planner_ablation_dev_2",
        scoring_identity="signal_diag.planner_ablation_scoring",
        scoring_version="2.0.0-dev.1",
        slots=(),
    )
    with pytest.raises(ValueError, match="legacy_fixture_seal|resource_extension"):
        generate_seal(candidate, tmp_path / "prod_seal")


def test_invalid_resource_extension_prefix_is_rejected_by_startswith() -> None:
    result = validate_resource_candidate(
        CandidateManifestV2.model_construct(
            resource_extension={"resource_policy": "planner_ablation_resource_v1"}
        ),
        repository_root=PROJECT_ROOT,
    )
    assert result.ready is False
    assert any(r.startswith("invalid_resource_extension") for r in result.reasons)
    assert "invalid_resource_extension" not in result.reasons
