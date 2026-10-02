"""Codex revise round 2. These tests fail on tip 75c3f99."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from signal_diag.agent.models import TaskAssessment
from signal_diag.agent.provider_telemetry import (
    attach_sdk_observation,
    build_audited_sdk_observation_profile,
)
from signal_diag.agent.telemetry import TelemetryBinding
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    CampaignPreflightError,
    reject_online_preflight,
    run_schedule,
)
from signal_diag.evaluation.planner_ablation.v2.models import (
    STUDY_ID_V2,
    ByteRequest,
    CanonicalRequest,
    ExecutionProvenance,
    Schedule,
    SlotKey,
    StudyProtocolV2,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    InstalledSdkIdentity,
    ReportedUsage,
    ResourceAssessment,
    ResourceCandidateValidation,
    ResourceObservation,
    SlotResourceLedger,
    VerifiedResourceAdmission,
)
from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
    aggregate_resource_ledger,
    validate_campaign_resource_totals,
)
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    generate_seal,
    make_complete_budget_assessment,
    validate_resource_candidate,
    verify_manifest,
)
from tests.evaluation.planner_ablation.v2.test_resource_candidate import (
    _candidate_with_proof_reference,
    _file_sha256,
)

_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_KEY = "a" * 64
_DIGEST = "c" * 64
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_LABEL_REVIEW = (
    "docs/evaluations/v0_3/planner_ablation/"
    "study_s1_planner_ablation_dev_2/LABEL_REVIEW.md"
)
_RESOURCE_BOUNDS = (
    "docs/evaluations/v0_3/planner_ablation/"
    "study_s1_planner_ablation_dev_2/RESOURCE_BOUNDS.md"
)


def _budget():
    return make_complete_budget_assessment(
        planner_calls_per_slot_bound=1,
        transport_attempts_per_call_bound=1,
        input_token_bound_per_call=1,
        output_token_bound_per_call=1,
    )


def _open_assessment() -> ResourceAssessment:
    return ResourceAssessment(
        planner_turn_ceiling=4,
        sdk_attempt_factor=1,
        http_send_factor=1,
        http_send_ceiling=3,
        sdk_attempt_ceiling_per_slot=4,
        logical_call_ceiling=4,
        input_token_ceiling=300,
        output_token_ceiling=150,
        execution_blocked=False,
        blockers=(),
        seal_ready=False,
        fixture_only=False,
    )


def _ledger(**overrides: object) -> SlotResourceLedger:
    payload: dict[str, object] = {
        "slot_key_digest": "slot-round2",
        "run_id": "run_round2",
        "events": (),
        "planner_turn_count": 0,
        "repair_attempt_count": 0,
        "logical_call_count": 0,
        "sdk_attempt_count": 0,
        "http_send_attempt_count": 0,
        "worker_drained": True,
        "telemetry_invalid": False,
        "incomplete": True,
        "closed": False,
    }
    payload.update(overrides)
    return SlotResourceLedger(**payload)  # type: ignore[arg-type]


def _forged_admission() -> VerifiedResourceAdmission:
    fields = {
        "ready": True,
        "fixture_only": False,
        "execution_blocked": False,
        "resource_policy": "planner_ablation_resource_v1",
        "candidate_digest": "a" * 64,
        "extension_digest": "b" * 64,
        "assessment_digest": "c" * 64,
        "authorization_binding_digest": "d" * 64,
        "seal_digest": "e" * 64,
    }
    try:
        return VerifiedResourceAdmission(**fields)  # type: ignore[arg-type]
    except ValidationError:
        return VerifiedResourceAdmission.model_construct(
            ready=True,
            fixture_only=False,
            execution_blocked=False,
            resource_policy="planner_ablation_resource_v1",
        )


def _identity() -> InstalledSdkIdentity:
    return InstalledSdkIdentity(
        openai_version="3.20.0",
        openai_source_digest="c" * 64,
        native_http_family="httpx",
        native_http_version="0.28.1",
        httpcore_version="1.0.9",
        source_file_digests={"openai/_base_client.py": "d" * 64},
        supported=True,
    )


def _mock_openai() -> object:
    import importlib

    transport = httpx.MockTransport(lambda request: httpx.Response(204))
    http_client = httpx.AsyncClient(transport=transport)
    openai = importlib.import_module("openai")
    return openai.AsyncOpenAI(
        api_key="test-key",
        base_url="https://example.test/v1",
        http_client=http_client,
    )


def test_forged_admission_and_placeholder_strings_do_not_open_online() -> None:
    with pytest.raises(
        CampaignPreflightError,
        match="online_path_not_authorized_in_offline_scope",
    ):
        reject_online_preflight(
            verified_seal_digest="not-a-verified-seal",
            authorization_reference="not-an-authorized-grant",
            budget=_budget(),
            verified_resource_admission=_forged_admission(),
            candidate=None,
            validation=ResourceCandidateValidation(ready=False, fixture_only=True),
            repository_root=_PROJECT_ROOT,
        )


@pytest.mark.asyncio
async def test_online_schedule_refuses_forged_admission_before_factory() -> None:
    calls: list[SlotKey] = []
    slot = SlotKey(request_key=_KEY, arm="product_agent", round_index=0)
    request = ByteRequest(
        mode="single_signal",
        test_wav_bytes=b"RIFF____WAVEfmt ",
        question="Diagnose supported S1 distortion conservatively.",
    )
    schedule = Schedule(
        canonical_requests=(
            CanonicalRequest(
                request_key=_KEY,
                mode="single_signal",
                representative_scenario_id="scenario_aaaaaaaa",
                byte_request=request,
            ),
        ),
        scenario_aliases={},
        slots=(slot,),
        schedule_digest=_DIGEST,
    )

    async def factory(key: SlotKey) -> object:
        calls.append(key)

        class _Session:
            async def execute(self, byte_request: ByteRequest) -> StudyTerminal:
                del byte_request
                return StudyTerminal(
                    run_id="run_forged",
                    arm=slot.arm,
                    mode="single_signal",
                    status="completed",
                    outcome="inconclusive",
                    claims=(),
                    task_assessment=_ASSESSMENT,
                    provenance=ExecutionProvenance(
                        planner_class="ScriptedPlanner",
                        execution_identity="harness_only",
                        provider_client_bound=False,
                        offline_session=True,
                    ),
                    slot_key=slot,
                    request_key=slot.request_key,
                )

            async def aclose(self) -> None:
                return None

        return _Session()

    with pytest.raises(
        CampaignPreflightError,
        match="online_path_not_authorized_in_offline_scope",
    ):
        await run_schedule(
            schedule,
            StudyProtocolV2(deadline_s=30.0),
            factory,  # type: ignore[arg-type]
            execution_mode="online",
            wall_timeout=False,
            budget_assessment=_budget(),
            verified_seal_digest="f" * 64,
            authorization_reference="not-an-authorized-grant",
            resource_policy="planner_ablation_resource_v1",
            resource_assessment=_open_assessment(),
            verified_resource_admission=_forged_admission(),
        )
    assert calls == []


def test_reviewed_prefix_does_not_prove_redirect_zero_use() -> None:
    events: list[dict[str, object]] = []
    for idx, outcome in enumerate(("redirect", "success")):
        send_id = f"http_{idx}"
        events.append(
            {
                "kind": "http_send",
                "phase": "start",
                "correlation_id": send_id,
                "send_id": send_id,
                "sequence_id": f"s{idx}",
            }
        )
        events.append(
            {
                "kind": "http_send",
                "phase": "end",
                "correlation_id": send_id,
                "send_id": send_id,
                "sequence_id": f"e{idx}",
                "outcome": outcome,
                "zero_use_proof": "reviewed:made-up",
            }
        )
    events.append(
        {
            "kind": "usage",
            "status": "complete",
            "send_id": "http_1",
            "sequence_id": "u1",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        }
    )
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    observation = aggregate_resource_ledger(
        _ledger(
            events=tuple(events),
            http_send_attempt_count=2,
            reported_usage_subtotal=usage,
            exact_total_tokens=2,
            incomplete=False,
            closed=True,
        ),
        assessment=_open_assessment(),
    )
    assert observation.exact_total_tokens is None
    assert any(
        item.startswith("redirect_without_zero_use_proof:")
        for item in observation.blockers
    )


def test_lifecycle_end_before_start_blocks() -> None:
    observation = aggregate_resource_ledger(
        _ledger(
            events=(
                {
                    "kind": "planner_turn",
                    "phase": "end",
                    "correlation_id": "t1",
                    "sequence_id": "end",
                },
                {
                    "kind": "planner_turn",
                    "phase": "start",
                    "correlation_id": "t1",
                    "sequence_id": "start",
                },
            ),
            planner_turn_count=1,
        ),
        assessment=_open_assessment(),
    )
    assert "lifecycle_end_before_start:planner_turn:t1" in observation.blockers


def test_duplicate_sequence_id_blocks() -> None:
    observation = aggregate_resource_ledger(
        _ledger(
            events=(
                {
                    "kind": "http_send",
                    "phase": "start",
                    "correlation_id": "h1",
                    "send_id": "h1",
                    "sequence_id": "same",
                },
                {
                    "kind": "http_send",
                    "phase": "end",
                    "correlation_id": "h1",
                    "send_id": "h1",
                    "sequence_id": "same",
                    "outcome": "success",
                },
            ),
            http_send_attempt_count=1,
        ),
        assessment=_open_assessment(),
    )
    assert "duplicate_sequence_id:same" in observation.blockers


def test_http_attempt_must_match_existing_sdk_attempt() -> None:
    observation = aggregate_resource_ledger(
        _ledger(
            events=(
                {
                    "kind": "http_send",
                    "phase": "start",
                    "correlation_id": "h1",
                    "send_id": "h1",
                    "sequence_id": "s1",
                    "attempt_id": "missing-sdk",
                },
                {
                    "kind": "http_send",
                    "phase": "end",
                    "correlation_id": "h1",
                    "send_id": "h1",
                    "sequence_id": "s2",
                    "attempt_id": "missing-sdk",
                    "outcome": "success",
                },
            ),
            http_send_attempt_count=1,
        ),
        assessment=_open_assessment(),
    )
    assert "http_send_parent_missing:missing-sdk" in observation.blockers


def test_sdk_call_must_match_existing_logical_call() -> None:
    observation = aggregate_resource_ledger(
        _ledger(
            events=(
                {
                    "kind": "sdk_attempt",
                    "phase": "start",
                    "correlation_id": "a1",
                    "sequence_id": "s1",
                    "call_id": "missing-call",
                },
                {
                    "kind": "sdk_attempt",
                    "phase": "end",
                    "correlation_id": "a1",
                    "sequence_id": "s2",
                    "call_id": "missing-call",
                },
            ),
            sdk_attempt_count=1,
        ),
        assessment=_open_assessment(),
    )
    assert "sdk_attempt_parent_missing:missing-call" in observation.blockers


def test_usage_without_http_send_blocks() -> None:
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=0, total_tokens=1)
    observation = aggregate_resource_ledger(
        _ledger(
            events=(
                {
                    "kind": "usage",
                    "status": "complete",
                    "send_id": "no-such-send",
                    "sequence_id": "u1",
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "total_tokens": 1,
                },
            ),
            reported_usage_subtotal=usage,
            exact_total_tokens=1,
        ),
        assessment=_open_assessment(),
    )
    assert any(item.startswith("usage_without_send") for item in observation.blockers)


def test_label_review_cannot_prove_numeric_bounds() -> None:
    matched = validate_resource_candidate(
        _candidate_with_proof_reference(
            _LABEL_REVIEW,
            _file_sha256(_LABEL_REVIEW),
        ),
        repository_root=_PROJECT_ROOT,
    )
    assert "proof_acceptance_inapplicable_file:planner_turn_ceiling" in matched.reasons


def test_label_review_file_must_contain_approved_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = b"review pending\napproved=false\n"
    digest = hashlib.sha256(body).hexdigest()
    real_read = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self.name == "LABEL_REVIEW.md":
            return body
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    candidate = _candidate_with_proof_reference(_RESOURCE_BOUNDS, "a" * 64)
    extension = dict(candidate.resource_extension or {})
    extension["fixture_only"] = False
    extension["label_review_source_path"] = _LABEL_REVIEW
    extension["label_review_source_digest"] = digest
    from signal_diag.evaluation.planner_ablation.v2.models import LabelReviewResult

    candidate = candidate.model_copy(
        update={
            "resource_extension": extension,
            "label_review": LabelReviewResult(approved=True, review_status="approved"),
        }
    )
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert result.ready is False
    assert "label_review_disk_not_approved" in result.reasons


def test_capability_and_provider_refs_reject_label_review() -> None:
    digest = _file_sha256(_LABEL_REVIEW)
    result = validate_resource_candidate(
        _candidate_with_proof_reference(
            _RESOURCE_BOUNDS,
            _file_sha256(_RESOURCE_BOUNDS),
            capability_updates={
                "fixture_only": False,
                "offline_evidence_reference": _LABEL_REVIEW,
                "offline_evidence_digest": digest,
            },
            provider_updates={
                "fixture_only": False,
                "source_reference": _LABEL_REVIEW,
                "source_digest": digest,
            },
        ),
        repository_root=_PROJECT_ROOT,
    )
    assert "offline_evidence_inapplicable_file" in result.reasons
    assert "provider_limits_source_inapplicable_file" in result.reasons


def test_resource_bounds_remain_applicable_for_numeric_and_capability_refs() -> None:
    digest = _file_sha256(_RESOURCE_BOUNDS)
    result = validate_resource_candidate(
        _candidate_with_proof_reference(
            _RESOURCE_BOUNDS,
            digest,
            capability_updates={
                "fixture_only": False,
                "offline_evidence_reference": _RESOURCE_BOUNDS,
                "offline_evidence_digest": digest,
            },
            provider_updates={
                "fixture_only": False,
                "source_reference": _RESOURCE_BOUNDS,
                "source_digest": digest,
            },
        ),
        repository_root=_PROJECT_ROOT,
    )
    assert "proof_acceptance_inapplicable_file:planner_turn_ceiling" not in result.reasons
    assert "offline_evidence_inapplicable_file" not in result.reasons
    assert "provider_limits_source_inapplicable_file" not in result.reasons
    assert "unauthenticated_offline_evidence" not in result.reasons
    assert "unauthenticated_provider_limits_source" not in result.reasons


def test_profile_field_drift_does_not_attach() -> None:
    installed = build_audited_sdk_observation_profile()
    drifted = (
        replace(installed, httpcore_version="9.9.9"),
        replace(installed, native_http_version="0.0.0"),
        replace(installed, native_http_family="urllib"),
        replace(installed, max_retries_default=installed.max_retries_default + 1),
        replace(installed, sdk_attempts_per_call=installed.sdk_attempts_per_call + 1),
        replace(
            installed,
            source_file_digests=(("openai/_base_client.py", "ab" * 32),),
        ),
    )
    for profile in drifted:
        binding = TelemetryBinding(slot_id="slot_drift", sink=lambda _event: None)
        client = _mock_openai()
        descriptor = attach_sdk_observation(
            client,
            binding=binding,
            profile=profile,
            allow_fixture_offline_boundary=True,
        )
        assert descriptor.origin == "unsupported"
        assert getattr(client, "_signal_diag_observation_attached", False) is False


def test_campaign_logical_calls_use_logical_ceiling_not_planner_turns() -> None:
    assessment = _open_assessment()
    turns_over_logical_under = ResourceObservation(
        planner_turn_count=10,
        repair_attempt_count=0,
        logical_call_count=1,
        sdk_attempt_count=1,
        http_send_attempt_count=1,
        acceptance_blocked=False,
        incomplete=False,
    )
    quiet = validate_campaign_resource_totals(
        [turns_over_logical_under],
        assessment=assessment,
    )
    assert "campaign_planner_turn_ceiling_exceeded" not in quiet

    logical_over = ResourceObservation(
        planner_turn_count=1,
        repair_attempt_count=0,
        logical_call_count=9,
        sdk_attempt_count=1,
        http_send_attempt_count=1,
        acceptance_blocked=False,
        incomplete=False,
    )
    blocked = validate_campaign_resource_totals([logical_over], assessment=assessment)
    assert "campaign_logical_call_ceiling_exceeded" in blocked


def test_matching_installed_identity_clears_unavailable_blocker() -> None:
    result = validate_resource_candidate(
        _candidate_with_proof_reference(_RESOURCE_BOUNDS, _file_sha256(_RESOURCE_BOUNDS)),
        repository_root=_PROJECT_ROOT,
        installed_sdk_identity=_identity(),
    )
    assert "installed_sdk_identity_unavailable" not in result.reasons


def test_generate_seal_forwards_installed_sdk_identity(tmp_path: Path) -> None:
    from signal_diag.evaluation.planner_ablation.v2 import sealing as sealing_mod
    from signal_diag.evaluation.planner_ablation.v2.models import CandidateManifestV2

    seen: dict[str, object] = {}
    identity = _identity()

    def spy(candidate, *, repository_root, installed_sdk_identity=None):  # type: ignore[no-untyped-def]
        del candidate, repository_root
        seen["identity"] = installed_sdk_identity
        return ResourceCandidateValidation(
            ready=False,
            reasons=("spy_blocked",),
            fixture_only=True,
        )

    original = sealing_mod.validate_resource_candidate
    sealing_mod.validate_resource_candidate = spy  # type: ignore[assignment]
    try:
        candidate = CandidateManifestV2.model_construct(
            study_id=STUDY_ID_V2,
            scoring_identity="signal_diag.planner_ablation_scoring",
            scoring_version="2.0.0-dev.1",
            seal_ready=True,
            resource_extension={"resource_policy": "planner_ablation_resource_v1"},
            slots=(),
        )
        with pytest.raises(ValueError, match="spy_blocked"):
            generate_seal(
                candidate,
                tmp_path / "seal",
                repository_root=tmp_path,
                installed_sdk_identity=identity,
            )
    finally:
        sealing_mod.validate_resource_candidate = original
    assert seen.get("identity") == identity


def test_verify_manifest_accepts_installed_sdk_identity(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_manifest(
            tmp_path / "missing-seal",
            repository_root=tmp_path,
            input_root=tmp_path,
            installed_sdk_identity=_identity(),
        )


def test_make_verified_resource_admission_refuses_unready_validation() -> None:
    from signal_diag.evaluation.planner_ablation.v2.models import CandidateManifestV2
    from signal_diag.evaluation.planner_ablation.v2.sealing import (
        make_verified_resource_admission,
    )

    candidate = CandidateManifestV2.model_construct(
        candidate_digest="a" * 64,
        resource_extension=None,
    )
    with pytest.raises(ValueError, match="online_path_not_authorized_in_offline_scope"):
        make_verified_resource_admission(
            candidate,
            ResourceCandidateValidation(ready=False, fixture_only=True),
            seal_digest="f" * 64,
            authorization_reference="not-an-authorized-grant",
            repository_root=_PROJECT_ROOT,
        )
