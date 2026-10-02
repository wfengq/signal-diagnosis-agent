"""Codex revise round 3: event graph, proof facts, label binding, usage, BoundFact."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from signal_diag.evaluation.planner_ablation.v2.models import LabelReviewResult
from signal_diag.evaluation.planner_ablation.v2.resource_models import (
    BoundFact,
    ReportedUsage,
)
from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
    aggregate_resource_ledger,
)
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    validate_resource_candidate,
)
from tests.evaluation.planner_ablation.v2.test_codex_revise_round2 import (
    _LABEL_REVIEW,
    _RESOURCE_BOUNDS,
    _ledger,
    _open_assessment,
)
from tests.evaluation.planner_ablation.v2.test_resource_candidate import (
    _candidate_with_proof_reference,
    _file_sha256,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _allow_dirty_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation tests stub code bindings while the working tree is dirty."""

    from signal_diag.evaluation.planner_ablation.v2 import sealing

    def _stub_bindings(repository_root: Path):
        return sealing.CodeBindingsV2(
            implementation_commit="0" * 40,
            aggregate_code_identity="a" * 64,
            bound_file_digests={},
            entry_script_digests={},
            prompt_module_digest="b" * 64,
            prompt_version="v0.3-s1-planner-9.11",
            profile_digests={},
            corpus_digests={},
            dependency_versions={"openai": "3.20.0"},
            python_version="3.12.0",
        )

    monkeypatch.setattr(sealing, "collect_code_bindings", _stub_bindings)


def _usage_event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "usage",
        "status": "complete",
        "send_id": "h1",
        "call_id": "c1",
        "attempt_id": "a1",
        "turn_id": "t1",
        "sequence_id": "u1",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }
    base.update(overrides)
    return base


def _valid_chain_events() -> tuple[dict[str, object], ...]:
    turn_id, call_id, attempt_id, send_id = "t1", "c1", "a1", "h1"
    return (
        {
            "kind": "planner_turn",
            "phase": "start",
            "turn_id": turn_id,
            "correlation_id": turn_id,
            "sequence_id": "pt-s",
            "monotonic_s": 1.0,
        },
        {
            "kind": "logical_call",
            "phase": "start",
            "turn_id": turn_id,
            "call_id": call_id,
            "correlation_id": call_id,
            "sequence_id": "lc-s",
            "monotonic_s": 1.1,
        },
        {
            "kind": "sdk_attempt",
            "phase": "start",
            "turn_id": turn_id,
            "call_id": call_id,
            "attempt_id": attempt_id,
            "correlation_id": attempt_id,
            "sequence_id": "sdk-s",
            "monotonic_s": 1.2,
        },
        {
            "kind": "http_send",
            "phase": "start",
            "turn_id": turn_id,
            "call_id": call_id,
            "attempt_id": attempt_id,
            "send_id": send_id,
            "correlation_id": send_id,
            "sequence_id": "http-s",
            "monotonic_s": 1.3,
        },
        {
            "kind": "http_send",
            "phase": "end",
            "turn_id": turn_id,
            "call_id": call_id,
            "attempt_id": attempt_id,
            "send_id": send_id,
            "correlation_id": send_id,
            "sequence_id": "http-e",
            "outcome": "success",
            "monotonic_s": 1.4,
        },
        {
            "kind": "sdk_attempt",
            "phase": "end",
            "turn_id": turn_id,
            "call_id": call_id,
            "attempt_id": attempt_id,
            "correlation_id": attempt_id,
            "sequence_id": "sdk-e",
            "monotonic_s": 1.5,
        },
        {
            "kind": "logical_call",
            "phase": "end",
            "turn_id": turn_id,
            "call_id": call_id,
            "correlation_id": call_id,
            "sequence_id": "lc-e",
            "monotonic_s": 1.6,
        },
        {
            "kind": "planner_turn",
            "phase": "end",
            "turn_id": turn_id,
            "correlation_id": turn_id,
            "sequence_id": "pt-e",
            "monotonic_s": 1.7,
        },
        _usage_event(),
    )


def test_http_only_graph_blocked_no_exact_accept() -> None:
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    events = (
        {
            "kind": "http_send",
            "phase": "start",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "s1",
        },
        {
            "kind": "http_send",
            "phase": "end",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "e1",
            "outcome": "success",
        },
        {
            "kind": "usage",
            "status": "complete",
            "send_id": "h1",
            "sequence_id": "u1",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        },
    )
    observation = aggregate_resource_ledger(
        _ledger(
            events=events,
            http_send_attempt_count=1,
            reported_usage_subtotal=usage,
            exact_total_tokens=2,
            incomplete=False,
            closed=True,
        ),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None
    assert any(
        b.startswith(("missing_required_id:", "sdk_attempt_parent_missing:", "usage_without_send:", "logical_call_parent_missing:", "planner_turn_missing:"))
        or "http_send_parent_missing" in b
        for b in observation.blockers
    )


def test_duplicate_paired_phases_same_correlation_blocked() -> None:
    events = (
        {
            "kind": "http_send",
            "phase": "start",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "s1",
        },
        {
            "kind": "http_send",
            "phase": "start",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "s2",
        },
        {
            "kind": "http_send",
            "phase": "end",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "e1",
            "outcome": "success",
        },
        {
            "kind": "http_send",
            "phase": "end",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "e2",
            "outcome": "success",
        },
    )
    observation = aggregate_resource_ledger(
        _ledger(events=events, http_send_attempt_count=2),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert any(b.startswith("duplicate_lifecycle_phase:") for b in observation.blockers)


def test_full_valid_chain_can_accept_exact_total() -> None:
    events = _valid_chain_events()
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    observation = aggregate_resource_ledger(
        _ledger(
            events=events,
            planner_turn_count=1,
            logical_call_count=1,
            sdk_attempt_count=1,
            http_send_attempt_count=1,
            reported_usage_subtotal=usage,
            exact_total_tokens=2,
            incomplete=False,
            closed=True,
        ),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is False
    assert observation.exact_total_tokens == 2


def test_malformed_cache_hit_tokens_blocks_exact() -> None:
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    events = list(_valid_chain_events())
    events[-1] = dict(events[-1])
    events[-1]["cache_hit_tokens"] = "nonsense"
    observation = aggregate_resource_ledger(
        _ledger(
            events=tuple(events),
            planner_turn_count=1,
            logical_call_count=1,
            sdk_attempt_count=1,
            http_send_attempt_count=1,
            reported_usage_subtotal=usage,
            exact_total_tokens=2,
            incomplete=False,
            closed=True,
        ),
        assessment=_open_assessment(),
    )
    assert observation.exact_total_tokens is None
    assert observation.acceptance_blocked is True
    assert "malformed_usage_fields" in observation.blockers


def test_bound_fact_rejects_bool_before_coerce() -> None:
    with pytest.raises(TypeError, match="boolean is not a numeric bound"):
        BoundFact(
            name="x",
            value=True,
            unit="u",
            origin="unknown",
            applicable_path="p",
            proof_digest="a" * 64,
            code_identity="c",
            dependency_identity="d",
            acceptance_reference="r",
        )


def test_fake_input_token_ceiling_blocks_despite_matching_bounds_sha() -> None:

    bounds = _RESOURCE_BOUNDS
    digest = _file_sha256(bounds)
    fact = BoundFact(
        name="input_token_ceiling",
        value=100,
        unit="tokens",
        origin="provider_spec",
        applicable_path="product_deepseek_chat",
        proof_digest=digest,
        code_identity="b" * 64,
        dependency_identity="openai==3.20.0",
        acceptance_reference=bounds,
        scope="admitted",
    )
    candidate = _candidate_with_proof_reference(bounds, digest)
    extension = dict(candidate.resource_extension or {})
    proofs = dict(extension["proofs"])
    proofs["input_token_ceiling"] = fact.model_dump(mode="json")
    extension["proofs"] = proofs
    candidate = candidate.model_copy(update={"resource_extension": extension})
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert result.ready is False
    assert any(
        r.startswith(("proof_fact_unknown:", "proof_fact_unapproved:"))
        for r in result.reasons
    )


def test_label_structured_approval_mismatch_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_read = Path.read_bytes
    body = (real_read(_PROJECT_ROOT / _LABEL_REVIEW)).decode("utf-8")
    body = body.replace(
        '"reviewer": "independent_offline_reviewer"',
        '"reviewer": "forged_reviewer"',
    )
    patched = body.encode("utf-8")
    digest = hashlib.sha256(patched).hexdigest()

    def read_bytes(self: Path) -> bytes:
        if self.name == "LABEL_REVIEW.md":
            return patched
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    candidate = _candidate_with_proof_reference(_RESOURCE_BOUNDS, _file_sha256(_RESOURCE_BOUNDS))
    extension = dict(candidate.resource_extension or {})
    extension["fixture_only"] = False
    extension["label_review_source_path"] = _LABEL_REVIEW
    extension["label_review_source_digest"] = digest
    candidate = candidate.model_copy(
        update={
            "resource_extension": extension,
            "label_review": LabelReviewResult(approved=True, review_status="approved"),
        }
    )
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert result.ready is False
    assert "label_review_content_mismatch" in result.reasons
