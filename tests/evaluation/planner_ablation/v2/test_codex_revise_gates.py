"""Codex revise regressions for resource admission, closure, and proof scope.

These tests encode the gates that tip f590efc still accepts.
"""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest
from pydantic import ValidationError

from signal_diag.agent.models import TaskAssessment
from signal_diag.evaluation.planner_ablation.v2.campaign import (
    CampaignPreflightError,
    inspect_limits,
    reject_online_preflight,
    run_schedule,
    snapshot_effective_configuration,
)
from signal_diag.evaluation.planner_ablation.v2.models import (
    ByteRequest,
    CanonicalRequest,
    ExecutionProvenance,
    LabelReviewResult,
    Schedule,
    SlotKey,
    StudyProtocolV2,
    StudyTerminal,
)
from signal_diag.evaluation.planner_ablation.v2.resource_budget import (
    assess_resource_budget,
)
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    BoundFact,
    ObservationCapability,
    ProviderLimitsBinding,
    ReportedUsage,
    ResourceAssessment,
    ResourceProofBundle,
    SdkProfileAudit,
    SlotResourceLedger,
)
from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
    aggregate_resource_ledger,
)
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    make_complete_budget_assessment,
    validate_resource_candidate,
    verify_manifest,
)

_ASSESSMENT = TaskAssessment(
    task_type="distortion_analysis",
    objective="determine why the signal sounds distorted",
    hypotheses=("clipping", "harmonic_distortion"),
)
_KEY_A = "a" * 64
_KEY_B = "b" * 64
_DIGEST = "c" * 64
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_LABEL_REVIEW = (
    "docs/evaluations/v0_3/planner_ablation/"
    "study_s1_planner_ablation_dev_2/LABEL_REVIEW.md"
)


def _open_assessment(**overrides: object) -> ResourceAssessment:
    payload: dict[str, object] = {
        "planner_turn_ceiling": 4,
        "sdk_attempt_factor": 1,
        "http_send_factor": 1,
        "http_send_ceiling": 3,
        "sdk_attempt_ceiling_per_slot": 4,
        "logical_call_ceiling": 4,
        "input_token_ceiling": 300,
        "output_token_ceiling": 150,
        "execution_blocked": False,
        "blockers": (),
        "seal_ready": False,
        "fixture_only": True,
    }
    payload.update(overrides)
    return ResourceAssessment(**payload)  # type: ignore[arg-type]


def _closed_ledger(**overrides: object) -> SlotResourceLedger:
    payload: dict[str, object] = {
        "slot_key_digest": "slot-under-test",
        "run_id": "run_closed",
        "events": (),
        "planner_turn_count": 0,
        "repair_attempt_count": 0,
        "logical_call_count": 0,
        "sdk_attempt_count": 0,
        "http_send_attempt_count": 0,
        "exact_total_tokens": 0,
        "potential_token_exposure": 0,
        "pending_event_ids": (),
        "worker_drained": True,
        "telemetry_invalid": False,
        "incomplete": False,
        "closed": True,
    }
    payload.update(overrides)
    return SlotResourceLedger(**payload)  # type: ignore[arg-type]


def _byte_request() -> ByteRequest:
    return ByteRequest(
        mode="single_signal",
        test_wav_bytes=b"RIFF____WAVEfmt ",
        question="Diagnose supported S1 distortion conservatively.",
    )


def _schedule(slots: tuple[SlotKey, ...]) -> Schedule:
    request = _byte_request()
    keys = tuple(dict.fromkeys(slot.request_key for slot in slots))
    canonical = tuple(
        CanonicalRequest(
            request_key=key,
            mode="single_signal",
            representative_scenario_id=f"scenario_{key[:8]}",
            byte_request=request,
        )
        for key in keys
    )
    return Schedule(
        canonical_requests=canonical,
        scenario_aliases={},
        slots=slots,
        schedule_digest=_DIGEST,
    )


def _completed(slot: SlotKey) -> StudyTerminal:
    return StudyTerminal(
        run_id=f"run_{slot.request_key[:8]}",
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


class _Session:
    def __init__(self, slot: SlotKey) -> None:
        self._slot = slot

    async def execute(self, request: ByteRequest) -> StudyTerminal:
        del request
        return _completed(self._slot)

    async def aclose(self) -> None:
        return None


def test_reject_online_preflight_rejects_synthetic_budget_and_arbitrary_strings() -> None:
    budget = make_complete_budget_assessment(
        planner_calls_per_slot_bound=1,
        transport_attempts_per_call_bound=1,
        input_token_bound_per_call=1,
        output_token_bound_per_call=1,
    )
    assert budget.seal_ready is True
    with pytest.raises(CampaignPreflightError, match="missing_verified_resource_admission"):
        reject_online_preflight(
            verified_seal_digest="f" * 64,
            authorization_reference="not-a-verified-grant",
            budget=budget,
        )


@pytest.mark.asyncio
async def test_online_schedule_refuses_before_session_factory() -> None:
    calls: list[SlotKey] = []
    slot = SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0)
    budget = make_complete_budget_assessment(
        planner_calls_per_slot_bound=1,
        transport_attempts_per_call_bound=1,
        input_token_bound_per_call=1,
        output_token_bound_per_call=1,
    )

    async def factory(key: SlotKey) -> _Session:
        calls.append(key)
        return _Session(key)

    with pytest.raises(
        CampaignPreflightError,
        match="missing_verified_resource_admission|missing_resource_policy",
    ):
        await run_schedule(
            _schedule((slot,)),
            StudyProtocolV2(deadline_s=30.0),
            factory,
            execution_mode="online",
            wall_timeout=False,
            budget_assessment=budget,
            verified_seal_digest="f" * 64,
            authorization_reference="not-a-verified-grant",
            resource_assessment=_open_assessment(),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_resource_policy_refuses_blocked_assessment_before_session_factory() -> None:
    calls: list[SlotKey] = []
    slot = SlotKey(request_key=_KEY_A, arm="product_agent", round_index=0)

    async def factory(key: SlotKey) -> _Session:
        calls.append(key)
        return _Session(key)

    blocked = _open_assessment(
        execution_blocked=True,
        blockers=("unproved_http_send_bound",),
        seal_ready=False,
    )
    with pytest.raises(CampaignPreflightError, match="resource_assessment"):
        await run_schedule(
            _schedule((slot,)),
            StudyProtocolV2(deadline_s=30.0),
            factory,
            execution_mode="offline",
            wall_timeout=False,
            resource_policy="planner_ablation_resource_v1",
            resource_assessment=blocked,
        )
    assert calls == []


def test_product_empty_exact_zero_blocks_acceptance() -> None:
    observation = aggregate_resource_ledger(
        _closed_ledger(exact_total_tokens=0),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None
    assert "exact_total_not_event_justified" in observation.blockers


def test_planner_turn_start_only_blocks_acceptance() -> None:
    observation = aggregate_resource_ledger(
        _closed_ledger(
            events=(
                {
                    "kind": "planner_turn",
                    "phase": "start",
                    "correlation_id": "t1",
                },
            ),
            planner_turn_count=1,
            exact_total_tokens=None,
        ),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.incomplete is True
    assert any(item.startswith("unpaired_start:planner_turn:") for item in observation.blockers)


def test_redirect_without_zero_use_proof_is_not_an_exact_total() -> None:
    events: list[dict[str, object]] = []
    for idx, outcome in enumerate(("redirect", "redirect", "success")):
        send_id = f"http_{idx}"
        events.append(
            {
                "kind": "http_send",
                "phase": "start",
                "correlation_id": send_id,
                "send_id": send_id,
            }
        )
        events.append(
            {
                "kind": "http_send",
                "phase": "end",
                "correlation_id": send_id,
                "send_id": send_id,
                "outcome": outcome,
            }
        )
    events.append(
        {
            "kind": "usage",
            "status": "complete",
            "send_id": "http_2",
            "prompt_tokens": 16,
            "completion_tokens": 10,
            "total_tokens": 26,
        }
    )
    usage = ReportedUsage(prompt_tokens=16, completion_tokens=10, total_tokens=26)
    observation = aggregate_resource_ledger(
        _closed_ledger(
            events=tuple(events),
            http_send_attempt_count=3,
            reported_usage_subtotal=usage,
            exact_total_tokens=26,
            potential_token_exposure=300,
        ),
        assessment=_open_assessment(),
    )
    assert observation.exact_total_tokens is None
    assert observation.reported_usage_subtotal == usage
    assert observation.potential_token_exposure == 300
    assert observation.acceptance_blocked is True
    assert any(
        item.startswith("redirect_without_zero_use_proof:") for item in observation.blockers
    )


def test_reported_usage_rejects_bool_and_negative_subdivisions() -> None:
    with pytest.raises(ValidationError):
        ReportedUsage(prompt_tokens=True, completion_tokens=1, total_tokens=2)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ReportedUsage(
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            reasoning_tokens=-1,
        )


def test_readme_bound_fact_is_inapplicable_even_when_digest_matches() -> None:
    from tests.evaluation.planner_ablation.v2.test_resource_candidate import (
        _candidate_with_proof_reference,
        _file_sha256,
    )

    matched = validate_resource_candidate(
        _candidate_with_proof_reference(
            "docs/README.md",
            _file_sha256("docs/README.md"),
        ),
        repository_root=_PROJECT_ROOT,
    )
    assert matched.ready is False
    assert "proof_acceptance_inapplicable_file:planner_turn_ceiling" in matched.reasons


def test_caller_approved_label_review_does_not_bind_disk_file() -> None:
    from tests.evaluation.planner_ablation.v2.test_resource_candidate import (
        _candidate_with_proof_reference,
        _file_sha256,
    )

    candidate = _candidate_with_proof_reference(
        _LABEL_REVIEW,
        _file_sha256(_LABEL_REVIEW),
    )
    extension = dict(candidate.resource_extension or {})
    extension["fixture_only"] = False
    candidate = candidate.model_copy(
        update={
            "resource_extension": extension,
            "label_review": LabelReviewResult(approved=True, review_status="approved"),
        }
    )
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert result.ready is False
    assert any(
        reason.startswith("label_review_disk_") for reason in result.reasons
    )
    assert candidate.label_review.approved is True


def test_validate_resource_candidate_does_not_import_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.evaluation.planner_ablation.v2.test_resource_candidate import (
        _candidate_with_proof_reference,
        _file_sha256,
    )

    class _ForbiddenSdkImport(BaseException):
        pass

    real_import = builtins.__import__

    def guarded(name: str, *args: object, **kwargs: object) -> object:
        if name == "openai" or name.startswith("signal_diag.agent.provider_telemetry"):
            raise _ForbiddenSdkImport(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    result = validate_resource_candidate(
        _candidate_with_proof_reference("docs/README.md", _file_sha256("docs/README.md")),
        repository_root=_PROJECT_ROOT,
    )
    assert result.ready is False
    assert "installed_sdk_identity_unavailable" in result.reasons


def test_resource_readiness_ignores_legacy_explicit_flags() -> None:
    config = snapshot_effective_configuration()
    assert config.request_timeout_explicit is False
    assert config.max_tokens_explicit is False
    legacy = inspect_limits(config)
    assert legacy.execution_blocked is True

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
        fixture_only=False,
    )
    provider = ProviderLimitsBinding(
        endpoint_origin="https://api.deepseek.com",
        requested_model="deepseek-v4-flash",
        declared_route="deepseek-v4-flash",
        source_date="2026-10-01",
        source_digest="2" * 64,
        token_limit_scope="admitted",
        authentication_mode="bearer_api_key",
        model_mapping_accepted=True,
        fixture_only=False,
    )

    def fact(name: str, value: int, unit: str, origin: str) -> BoundFact:
        return BoundFact(
            name=name,
            value=value,
            unit=unit,
            origin=origin,  # type: ignore[arg-type]
            applicable_path="product_deepseek_chat",
            proof_digest="a" * 64,
            code_identity="b" * 64,
            dependency_identity="openai==3.20.0",
            acceptance_reference="fixture",
            scope="admitted",
        )

    proofs = ResourceProofBundle(
        planner_turn_ceiling=fact(
            "planner_turn_ceiling", 28, "planner_turns_per_slot", "control_flow_proof"
        ),
        sdk_attempt_factor=fact(
            "sdk_attempt_factor", 3, "sdk_attempts_per_logical_call", "sdk_default_audit"
        ),
        http_send_factor=fact(
            "http_send_factor", 4, "http_sends_per_sdk_attempt", "sdk_default_audit"
        ),
        all_outcome_token_ceiling=fact(
            "all_outcome_token_ceiling", 10, "tokens_per_http_send", "provider_spec"
        ),
        request_timeout=fact("request_timeout", 600, "seconds", "sdk_default_audit"),
        sdk_profile=sdk,
        provider_limits=provider,
        fixture_only=False,
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
        fixture_only=False,
    )
    assessment = assess_resource_budget(config, proofs, capability)
    assert assessment.execution_blocked is False
    assert assessment.request_timeout_explicit is False
    assert assessment.transport_retry_override_explicit is False
    assert assessment.seal_ready is True
    assert assessment.fixture_only is False


@pytest.mark.asyncio
async def test_slot_digest_mismatch_is_not_silently_overwritten() -> None:
    from signal_diag.app.planner_ablation_v2_adapter import StudyResourceObserver

    slot = SlotKey(request_key=_KEY_A, arm="fixed_pipeline", round_index=0)
    observer = StudyResourceObserver(slot_id="not-the-schedule-digest")

    class _Fixed:
        def __init__(self) -> None:
            self._observer = observer

        async def execute(self, request: ByteRequest) -> StudyTerminal:
            del request
            terminal = _completed(slot)
            observer.associate_run_id(terminal.run_id)
            return terminal

        async def aclose(self) -> None:
            return None

        def resource_snapshot(self, *, worker_drained: bool) -> object:
            return observer.resource_snapshot(worker_drained=worker_drained)

    async def factory(key: SlotKey) -> _Fixed:
        del key
        return _Fixed()

    record = await run_schedule(
        _schedule((slot,)),
        StudyProtocolV2(deadline_s=30.0),
        factory,
        execution_mode="offline",
        wall_timeout=False,
        resource_policy="planner_ablation_resource_v1",
        resource_assessment=_open_assessment(execution_blocked=False, blockers=()),
    )
    ledger = record.slot_records[0].resource_ledger
    assert ledger is not None
    assert ledger["slot_key_digest"] == "not-the-schedule-digest"
    assert record.status == "resource_stopped"
    assert record.slot_records[0].resource_stop_reason == "slot_digest_mismatch"


@pytest.mark.asyncio
async def test_product_empty_exact_zero_on_final_slot_blocks_conclusion() -> None:
    from signal_diag.evaluation.planner_ablation.v2.decision import decide
    from tests.evaluation.planner_ablation.v2.test_decision import (
        _equal_tables,
        _prereq,
        _protocol,
    )

    first = SlotKey(request_key=_KEY_A, arm="fixed_pipeline", round_index=0)
    last = SlotKey(request_key=_KEY_B, arm="product_agent", round_index=0)

    class _Snap:
        def __init__(self, slot: SlotKey, *, empty_product: bool) -> None:
            self._slot = slot
            self._empty_product = empty_product

        async def execute(self, request: ByteRequest) -> StudyTerminal:
            del request
            return _completed(self._slot)

        async def aclose(self) -> None:
            return None

        def resource_snapshot(self, *, worker_drained: bool) -> SlotResourceLedger:
            del worker_drained
            if self._empty_product:
                return _closed_ledger(
                    slot_key_digest=f"{self._slot.request_key}:{self._slot.arm}:{self._slot.round_index}",
                    run_id=f"run_{self._slot.request_key[:8]}",
                    exact_total_tokens=0,
                )
            return _closed_ledger(
                slot_key_digest=f"{self._slot.request_key}:{self._slot.arm}:{self._slot.round_index}",
                run_id=f"run_{self._slot.request_key[:8]}",
                exact_total_tokens=0,
            )

    async def factory(slot: SlotKey) -> _Snap:
        return _Snap(slot, empty_product=slot.arm == "product_agent")

    record = await run_schedule(
        _schedule((first, last)),
        StudyProtocolV2(deadline_s=30.0),
        factory,
        execution_mode="offline",
        wall_timeout=False,
        resource_policy="planner_ablation_resource_v1",
        resource_assessment=_open_assessment(),
    )
    assert record.slot_records[0].attempt_count == 1
    assert record.status == "resource_stopped"
    assert record.accepted_conclusion_available is False
    assert record.slot_records[-1].resource_stop_reason is not None
    product_keys = frozenset({f"ps{i}" for i in range(9)})
    fixed_keys = frozenset({f"ps{i}" for i in range(8)})

    def mutate(round_index, mode, product, fixed):  # type: ignore[no-untyped-def]
        del round_index
        if mode == "single_signal":
            product = product.model_copy(
                update={
                    "quality": product.quality.model_copy(
                        update={"numerator": 9, "value": 1.0}
                    ),
                    "quality_correct_keys": product_keys,
                }
            )
            fixed = fixed.model_copy(
                update={"quality_correct_keys": fixed_keys}
            )
        return product, fixed

    metrics = _equal_tables(
        product_mean=1.0,
        fixed_mean=1.0,
        product_quality=9,
        fixed_quality=8,
        mutate_cell=mutate,
    )
    passing = decide(_protocol(), metrics, _prereq())
    assert passing.machine_candidate == "planner_advantage"
    blocked = decide(
        _protocol(),
        metrics,
        _prereq(
            all_passed=False,
            resource_observation_ok=False,
            reason_codes=(record.status,),
        ),
    )
    assert blocked.machine_candidate == "insufficient_evidence"
    assert blocked.eligible_conclusion != "fixed_pipeline_dominance"


def test_legacy_fixture_seal_is_not_production_verify_manifest(
    tmp_path: Path,
) -> None:
    from tests.evaluation.planner_ablation.v2.test_sealing import (
        _build_ready_candidate,
        _init_fixture_repo,
    )

    repo, inputs = _init_fixture_repo(tmp_path)
    destination = tmp_path / "protocol_seal"
    candidate = _build_ready_candidate(repo, inputs)
    from signal_diag.evaluation.planner_ablation.v2.sealing import generate_seal

    generate_seal(candidate, destination, legacy_fixture_seal=True)
    study = verify_manifest(destination, repository_root=repo, input_root=inputs)
    assert study.construction_path == "legacy_fixture_seal"
