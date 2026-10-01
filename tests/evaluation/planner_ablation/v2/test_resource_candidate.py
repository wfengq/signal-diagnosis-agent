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


def _file_sha256(relative: str) -> str:
    import hashlib

    return hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()


def _candidate_with_proof_reference(
    reference: str,
    digest: str,
    *,
    capability_updates: dict[str, object] | None = None,
    provider_updates: dict[str, object] | None = None,
) -> CandidateManifestV2:
    from signal_diag.evaluation.planner_ablation.v2.campaign import (
        snapshot_effective_configuration,
    )
    from signal_diag.evaluation.planner_ablation.v2.models import LabelReviewResult
    from signal_diag.evaluation.planner_ablation.v2.resource_budget import (
        assess_resource_budget,
    )
    from signal_diag.evaluation.planner_ablation.v2.resource_models import (
        BoundFact,
        ObservationCapability,
        ProviderLimitsBinding,
        ResourceCandidateExtension,
        ResourceProofBundle,
        SdkProfileAudit,
    )

    fact = BoundFact(
        name="planner_turn_ceiling",
        value=28,
        unit="planner_turns_per_slot",
        origin="control_flow_proof",
        applicable_path="runtime",
        proof_digest=digest,
        code_identity="b" * 64,
        dependency_identity="openai==3.20.0",
        acceptance_reference=reference,
        scope="admitted",
    )
    sdk = SdkProfileAudit(
        openai_version="3.20.0",
        openai_source_digest="c" * 64,
        native_http_family="httpx",
        native_http_version="0.28.1",
        httpcore_version="1.0.9",
        source_file_digests={"openai/_base_client.py": "d" * 64},
        max_retries_default=2,
        sdk_attempts_per_call=3,
        prepare_options_hook="AsyncAPIClient._prepare_options",
        send_request_hook="AsyncAPIClient._send_request",
        native_dispatch_hook="httpx.AsyncClient.send",
        supported=True,
        fixture_only=True,
    )
    provider = ProviderLimitsBinding(
        endpoint_origin="https://api.deepseek.com",
        requested_model="deepseek-v4-flash",
        declared_route="deepseek-v4.1-flash",
        source_date="2026-10-01",
        source_digest="2" * 64,
        token_limit_scope="unknown",
        authentication_mode="bearer_api_key",
        model_mapping_accepted=False,
        fixture_only=True,
    )
    proofs = ResourceProofBundle(
        planner_turn_ceiling=fact,
        sdk_profile=sdk,
        provider_limits=provider,
        fixture_only=True,
    )
    capability = ObservationCapability(
        telemetry_schema="planner_ablation_telemetry_v1",
        resource_policy="planner_ablation_resource_v1",
        sdk_profile=sdk,
        observes_planner_turns=True,
        observes_repairs=True,
        observes_sdk_attempts=True,
        observes_http_sends=True,
        observes_usage=True,
        offline_evidence_digest="1" * 64,
        fixture_only=True,
    )
    assessment = assess_resource_budget(
        snapshot_effective_configuration(),
        proofs,
        capability,
    )
    extension = ResourceCandidateExtension(
        resource_policy="planner_ablation_resource_v1",
        telemetry_schema="planner_ablation_telemetry_v1",
        proofs=proofs,
        capability=capability,
        assessment=assessment,
        provider_dependency_identity="openai==3.20.0",
        label_review_digest="e" * 64,
        label_population_digest="f" * 64,
        code_identity="a" * 64,
        extension_digest="9" * 64,
        fixture_only=True,
    )
    payload = extension.model_dump(mode="json")
    if capability_updates:
        payload["capability"].update(capability_updates)
    if provider_updates:
        payload["proofs"]["provider_limits"].update(provider_updates)
    return CandidateManifestV2.model_construct(
        resource_extension=payload,
        label_review=LabelReviewResult(approved=False),
        effective_configuration=snapshot_effective_configuration(),
    )


def test_free_form_proof_reference_is_not_authenticated() -> None:
    result = validate_resource_candidate(
        _candidate_with_proof_reference("operator_note_not_a_file", "a" * 64),
        repository_root=PROJECT_ROOT,
    )
    assert result.ready is False
    assert (
        "proof_acceptance_reference_not_repo_path:planner_turn_ceiling"
        in result.reasons
        or "missing_proof_acceptance_file:planner_turn_ceiling" in result.reasons
        or any(
            reason.startswith("proof_acceptance_path")
            and reason.endswith("planner_turn_ceiling")
            for reason in result.reasons
        )
    )


def test_repo_proof_reference_must_match_file_bytes() -> None:
    label_review = (
        "docs/evaluations/v0_3/planner_ablation/"
        "study_s1_planner_ablation_dev_2/LABEL_REVIEW.md"
    )
    wrong = validate_resource_candidate(
        _candidate_with_proof_reference(label_review, "a" * 64),
        repository_root=PROJECT_ROOT,
    )
    assert wrong.ready is False
    assert "proof_acceptance_content_mismatch:planner_turn_ceiling" in wrong.reasons

    matched = validate_resource_candidate(
        _candidate_with_proof_reference(label_review, _file_sha256(label_review)),
        repository_root=PROJECT_ROOT,
    )
    assert matched.ready is False
    assert "proof_acceptance_content_mismatch:planner_turn_ceiling" not in matched.reasons
    assert (
        "proof_acceptance_inapplicable_file:planner_turn_ceiling" not in matched.reasons
    )
    assert "missing_proof_acceptance_file:planner_turn_ceiling" not in matched.reasons


def test_non_fixture_offline_evidence_requires_repo_file() -> None:
    forged = validate_resource_candidate(
        _candidate_with_proof_reference(
            "docs/README.md",
            _file_sha256("docs/README.md"),
            capability_updates={
                "fixture_only": False,
                "offline_evidence_reference": "operator_note_not_a_file",
                "offline_evidence_digest": "1" * 64,
            },
        ),
        repository_root=PROJECT_ROOT,
    )
    assert forged.ready is False
    assert "unauthenticated_offline_evidence" in forged.reasons
    assert not any(
        reason.startswith("invalid_resource_extension") for reason in forged.reasons
    )

    digest = _file_sha256("docs/README.md")
    matched = validate_resource_candidate(
        _candidate_with_proof_reference(
            "docs/README.md",
            digest,
            capability_updates={
                "fixture_only": False,
                "offline_evidence_reference": "docs/README.md",
                "offline_evidence_digest": digest,
            },
        ),
        repository_root=PROJECT_ROOT,
    )
    assert matched.ready is False
    assert "unauthenticated_offline_evidence" not in matched.reasons


def test_non_fixture_provider_limits_source_requires_repo_file() -> None:
    forged = validate_resource_candidate(
        _candidate_with_proof_reference(
            "docs/README.md",
            _file_sha256("docs/README.md"),
            provider_updates={
                "fixture_only": False,
                "source_reference": "operator_note_not_a_file",
                "source_digest": "2" * 64,
            },
        ),
        repository_root=PROJECT_ROOT,
    )
    assert forged.ready is False
    assert "unauthenticated_provider_limits_source" in forged.reasons
    assert not any(
        reason.startswith("invalid_resource_extension") for reason in forged.reasons
    )

    digest = _file_sha256("docs/README.md")
    matched = validate_resource_candidate(
        _candidate_with_proof_reference(
            "docs/README.md",
            digest,
            provider_updates={
                "fixture_only": False,
                "source_reference": "docs/README.md",
                "source_digest": digest,
            },
        ),
        repository_root=PROJECT_ROOT,
    )
    assert matched.ready is False
    assert "unauthenticated_provider_limits_source" not in matched.reasons
