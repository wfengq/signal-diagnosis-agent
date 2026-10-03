"""Codex revise round 4: graph ancestry, duplicate usage, proof/label binding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from signal_diag.evaluation.planner_ablation.v2.models import LabelReviewResult
from signal_diag.evaluation.planner_ablation.v2.resource_models import ReportedUsage
from signal_diag.evaluation.planner_ablation.v2.resource_telemetry import (
    aggregate_resource_ledger,
)
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    _normalized_label_approval,
    validate_resource_candidate,
)
from tests.evaluation.planner_ablation.v2.test_codex_revise_round2 import (
    _RESOURCE_BOUNDS,
    _ledger,
    _open_assessment,
)
from tests.evaluation.planner_ablation.v2.test_codex_revise_round3 import (
    _valid_chain_events,
)
from tests.evaluation.planner_ablation.v2.test_resource_candidate import (
    _candidate_with_proof_reference,
    _file_sha256,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _allow_dirty_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    from signal_diag.evaluation.planner_ablation.v2 import sealing

    def _stub_bindings(repository_root: Path):
        return sealing.CodeBindingsV2(
            implementation_commit="0" * 40,
            aggregate_code_identity="b" * 64,
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


def test_missing_sequence_id_and_monotonic_blocked() -> None:
    events = (
        {
            "kind": "http_send",
            "phase": "start",
            "correlation_id": "h1",
            "send_id": "h1",
            "sequence_id": "s1",
            "monotonic_s": 1.0,
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
            "completion_tokens": 0,
            "total_tokens": 1,
        },
    )
    observation = aggregate_resource_ledger(
        _ledger(events=events, http_send_attempt_count=1),
        assessment=_open_assessment(),
    )
    assert observation.acceptance_blocked is True
    assert "missing_required_monotonic:http_send" in observation.blockers
    assert "missing_required_monotonic:usage" in observation.blockers


def test_lifecycle_self_end_before_start_blocked() -> None:
    events = (
        {
            "kind": "planner_turn",
            "phase": "start",
            "correlation_id": "t1",
            "turn_id": "t1",
            "sequence_id": "pt-s",
            "monotonic_s": 5.0,
        },
        {
            "kind": "planner_turn",
            "phase": "end",
            "correlation_id": "t1",
            "turn_id": "t1",
            "sequence_id": "pt-e",
            "monotonic_s": 4.0,
        },
    )
    observation = aggregate_resource_ledger(
        _ledger(events=events, planner_turn_count=1),
        assessment=_open_assessment(),
    )
    assert any(
        b == "event_graph_temporal:planner_turn:t1:end_before_start"
        for b in observation.blockers
    )


def test_wrong_http_ancestry_mismatch_blocked() -> None:
    turn_id, call_id, attempt_id, send_id = "t1", "c1", "a1", "h1"
    events = (
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
            "turn_id": "nonexistent",
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
            "turn_id": "nonexistent",
            "call_id": call_id,
            "attempt_id": attempt_id,
            "send_id": send_id,
            "correlation_id": send_id,
            "sequence_id": "http-e",
            "outcome": "success",
            "monotonic_s": 1.4,
        },
    )
    observation = aggregate_resource_ledger(
        _ledger(events=events, http_send_attempt_count=1),
        assessment=_open_assessment(),
    )
    assert f"http_send_ancestry_mismatch:{send_id}" in observation.blockers


def test_duplicate_usage_for_same_send_blocks_exact() -> None:
    events = list(_valid_chain_events())
    events.append(
        {
            "kind": "usage",
            "status": "complete",
            "send_id": "h1",
            "call_id": "c1",
            "attempt_id": "a1",
            "turn_id": "t1",
            "sequence_id": "u2",
            "monotonic_s": 1.85,
            "prompt_tokens": 9,
            "completion_tokens": 9,
            "total_tokens": 18,
        }
    )
    usage = ReportedUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
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
    assert "duplicate_usage_for_send:h1" in observation.blockers
    assert observation.acceptance_blocked is True
    assert observation.exact_total_tokens is None


def test_sparse_approved_proof_record_fails_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bounds = _PROJECT_ROOT / _RESOURCE_BOUNDS
    text = bounds.read_text(encoding="utf-8")
    sparse_name = "planner_turn_ceiling"
    payload = json.loads(text.split("```json")[1].split("```")[0].strip())
    for fact in payload["facts"]:
        if fact.get("name") == sparse_name:
            fact.clear()
            fact.update({"name": sparse_name, "status": "approved"})
    patched = (
        text.split("```json")[0]
        + "```json\n"
        + json.dumps(payload, indent=2)
        + "\n```\n"
    )
    digest = hashlib.sha256(patched.encode("utf-8")).hexdigest()
    from signal_diag.evaluation.planner_ablation.v2 import sealing

    bounds_path = bounds

    def read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == bounds_path:
            return patched
        return Path.read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", read_text)

    def patched_sha256(path: Path) -> str:
        if path == bounds_path:
            return digest
        return sealing._sha256_file(path)

    monkeypatch.setattr(sealing, "_sha256_file", patched_sha256)
    candidate = _candidate_with_proof_reference(_RESOURCE_BOUNDS, digest)
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert f"proof_fact_incomplete_record:{sparse_name}" in result.reasons


def test_proof_fact_code_identity_not_applicable() -> None:
    candidate = _candidate_with_proof_reference(
        _RESOURCE_BOUNDS, _file_sha256(_RESOURCE_BOUNDS)
    )
    extension = dict(candidate.resource_extension or {})
    extension["code_identity"] = "c" * 64
    candidate = candidate.model_copy(update={"resource_extension": extension})
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert "proof_fact_code_identity_not_applicable:planner_turn_ceiling" in result.reasons


def test_string_approved_false_not_treated_as_true() -> None:
    normalized = _normalized_label_approval({"approved": "false", "schema": "x"})
    assert normalized["approved"] is False


def test_label_review_approved_not_bool_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_read = Path.read_bytes
    label_path = (
        _PROJECT_ROOT
        / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2/LABEL_REVIEW.md"
    )
    label_body = label_path.read_text(encoding="utf-8")
    label_body = label_body.replace('"approved": true', '"approved": "false"')
    patched_label = label_body.encode("utf-8")
    label_digest = hashlib.sha256(patched_label).hexdigest()

    def read_bytes(self: Path) -> bytes:
        if self.name == "LABEL_REVIEW.md":
            return patched_label
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    candidate = _candidate_with_proof_reference(_RESOURCE_BOUNDS, _file_sha256(_RESOURCE_BOUNDS))
    extension = dict(candidate.resource_extension or {})
    extension["fixture_only"] = False
    extension["label_review_source_path"] = (
        "docs/evaluations/v0_3/planner_ablation/"
        "study_s1_planner_ablation_dev_2/LABEL_REVIEW.md"
    )
    extension["label_review_source_digest"] = label_digest
    candidate = candidate.model_copy(
        update={
            "resource_extension": extension,
            "label_review": LabelReviewResult(approved=True, review_status="approved"),
        }
    )
    result = validate_resource_candidate(candidate, repository_root=_PROJECT_ROOT)
    assert "label_review_approved_not_bool" in result.reasons


def test_valid_full_chain_with_times_still_accepts_exact() -> None:
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
