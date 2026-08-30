"""Phase 4.2 opaque evaluation signal identity (T202)."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent.planner import RealLLMPlanner
from signal_diag.evaluation.dataset import (
    _materialize_case,
    _opaque_evaluation_signal_id,
    load_dataset_manifest,
)
from signal_diag.evaluation.models import (
    BenchmarkConfig,
    DatasetManifest,
    EvaluationCase,
)
from signal_diag.evaluation.runner import (
    _execute_agent_slot,
    _run_agent_slot_with_retries,
    _run_real_benchmark_for_split,
)
from signal_diag.signal.repository import InMemorySignalRepository
from tests.evaluation.conftest import CANONICAL_MANIFEST, PHASE4_1_MANIFEST
from tests.evaluation.test_runner import _adaptive_success_handler, _client_from_handler

PHASE4_2_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1_2.yaml"
)
_OPAQUE_PATTERN = re.compile(r"^sig_eval_[0-9a-f]{24}$")
_STARTED = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
_SEMANTIC_TOKENS = (
    "clipping_strong",
    "invalid_noise",
    "combined",
    "case_v12",
    "held_out",
    "development",
    "clipping",
    "clip",
    "harmonic",
    "clean",
    "combo",
    "noise",
    "fault",
    "held",
)
_FORBIDDEN_OUTBOUND_KEYS = {
    "causal_faults",
    "knowledge_policy",
    "sufficient_evidence_sets",
    "observable_conditions",
    "acceptable_outcomes",
    "acceptable_first_tools",
    "held_out",
    "expected_faults",
    "expected_outcomes",
    "target_metrics",
    "samples",
    "waveform",
    "frequencies_hz",
    "magnitude_db",
}


def _expected_opaque(dataset_id: str, dataset_version: str, case_id: str) -> str:
    raw = f"{dataset_id}\0{dataset_version}\0{case_id}".encode()
    return f"sig_eval_{hashlib.sha256(raw).hexdigest()[:24]}"


def _assert_opaque_id(signal_id: str, *, case_id: str) -> None:
    assert _OPAQUE_PATTERN.fullmatch(signal_id), signal_id
    suffix = signal_id.removeprefix("sig_eval_")
    assert suffix == suffix.lower()
    lowered = signal_id.lower()
    assert case_id.lower() not in lowered
    assert case_id.removeprefix("case_").lower() not in lowered
    for token in _SEMANTIC_TOKENS:
        assert token not in lowered, f"{token!r} leaked into {signal_id}"


def _json_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for nested in value.values():
            keys.update(_json_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_json_keys(item))
    return keys


def _string_blob(value: object) -> str:
    parts: list[str] = []
    if isinstance(value, str):
        parts.append(value)
    elif isinstance(value, dict):
        for key, nested in value.items():
            parts.append(str(key))
            parts.append(_string_blob(nested))
    elif isinstance(value, list):
        for item in value:
            parts.append(_string_blob(item))
    return "\n".join(parts)


def _capture_planner_builder(inner_client: object) -> RealLLMPlanner:
    return RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        client=inner_client,  # type: ignore[arg-type]
    )


def _slot_config(manifest: DatasetManifest) -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_id="bench_t202_opaque_ids",
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        rule_profile_id=manifest.rule_profile_id,
        rule_profile_version=manifest.rule_profile_version,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="v0.2-s1-planner-6",
        prompt_sha256="0" * 64,
        started_at_utc=_STARTED,
        repetitions=1,
        max_infrastructure_retries=0,
        max_concurrency=1,
    )


def test_t202_opaque_id_matches_sha256_and_format() -> None:
    dataset_id = "s1-distortion-synthetic"
    dataset_version = "1.2.0"
    case_id = "case_v12_dev_clipping_strong"
    signal_id = _opaque_evaluation_signal_id(dataset_id, dataset_version, case_id)
    assert signal_id == _expected_opaque(dataset_id, dataset_version, case_id)
    _assert_opaque_id(signal_id, case_id=case_id)


def test_t202_opaque_id_is_stable_and_unique() -> None:
    dataset_id = "s1-distortion-synthetic"
    version = "1.2.0"
    first = _opaque_evaluation_signal_id(dataset_id, version, "case_v12_dev_clipping_01")
    second = _opaque_evaluation_signal_id(dataset_id, version, "case_v12_dev_clipping_01")
    other_case = _opaque_evaluation_signal_id(
        dataset_id, version, "case_v12_dev_invalid_noise_01"
    )
    other_version = _opaque_evaluation_signal_id(
        dataset_id, "1.1.0", "case_v12_dev_clipping_01"
    )
    assert first == second
    assert first != other_case
    assert first != other_version
    _assert_opaque_id(first, case_id="case_v12_dev_clipping_01")
    _assert_opaque_id(other_case, case_id="case_v12_dev_invalid_noise_01")


def test_t202_v12_cases_materialize_opaque_ids_when_injected() -> None:
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    seen: set[str] = set()
    for case in manifest.cases:
        opaque = _opaque_evaluation_signal_id(
            manifest.dataset_id, manifest.version, case.case_id
        )
        _assert_opaque_id(opaque, case_id=case.case_id)
        assert opaque not in seen
        seen.add(opaque)
        record = _materialize_case(
            case,
            InMemorySignalRepository(),
            signal_id=opaque,
        )
        assert record.meta.signal_id == opaque
        stored = InMemorySignalRepository()
        _materialize_case(case, stored, signal_id=opaque)
        assert stored.get(opaque).meta.signal_id == opaque


def test_t202_legacy_materialize_without_signal_id_unchanged() -> None:
    for path in (CANONICAL_MANIFEST, PHASE4_1_MANIFEST):
        manifest = load_dataset_manifest(path)
        for case in manifest.cases:
            record = _materialize_case(case, InMemorySignalRepository())
            assert record.meta.signal_id == (
                f"sig_eval_{case.case_id.removeprefix('case_')}"
            )


def test_t202_real_split_helpers_accept_signal_id_factory() -> None:
    assert "signal_id_factory" in inspect.signature(_execute_agent_slot).parameters
    assert "signal_id_factory" in inspect.signature(
        _run_agent_slot_with_retries
    ).parameters
    assert "signal_id_factory" in inspect.signature(
        _run_real_benchmark_for_split
    ).parameters


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_id", [None, ""])
async def test_t202_factory_invalid_id_does_not_fall_back_to_semantic(
    invalid_id: str | None,
) -> None:
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    case = next(
        item for item in manifest.cases if item.case_id == "case_v12_dev_clipping_01"
    )
    semantic = f"sig_eval_{case.case_id.removeprefix('case_')}"
    client = _client_from_handler(_adaptive_success_handler)

    def factory(_item: EvaluationCase) -> str:
        return invalid_id  # type: ignore[return-value]

    with pytest.raises(ValueError, match="signal_id_factory") as caught:
        await _execute_agent_slot(
            case,
            _slot_config(manifest),
            1,
            client,
            planner_builder=_capture_planner_builder,
            signal_id_factory=factory,
        )
    assert semantic not in str(caught.value)
    calls: list[dict[str, Any]] = client.chat.completions.calls
    for kwargs in calls:
        user_payload = json.loads(kwargs["messages"][1]["content"])
        signal_id = user_payload["planner_context"]["signal_meta"]["signal_id"]
        assert signal_id != semantic
        assert semantic not in signal_id


@pytest.mark.asyncio
async def test_t202_outbound_planner_context_hides_case_semantics() -> None:
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    case = next(item for item in manifest.cases if item.case_id == "case_v12_dev_clipping_01")
    expected = _opaque_evaluation_signal_id(
        manifest.dataset_id, manifest.version, case.case_id
    )
    client = _client_from_handler(_adaptive_success_handler)

    def factory(item: EvaluationCase) -> str:
        return _opaque_evaluation_signal_id(
            manifest.dataset_id, manifest.version, item.case_id
        )

    trace = await _execute_agent_slot(
        case,
        _slot_config(manifest),
        1,
        client,
        planner_builder=_capture_planner_builder,
        signal_id_factory=factory,
    )
    assert trace.case_id == case.case_id
    calls: list[dict[str, Any]] = client.chat.completions.calls
    assert calls
    semantic_remainder = case.case_id.removeprefix("case_")
    for kwargs in calls:
        user_payload = json.loads(kwargs["messages"][1]["content"])
        context = user_payload["planner_context"]
        signal_id = context["signal_meta"]["signal_id"]
        assert signal_id == expected
        _assert_opaque_id(signal_id, case_id=case.case_id)
        keys = {key.lower() for key in _json_keys(user_payload)}
        for forbidden in _FORBIDDEN_OUTBOUND_KEYS:
            assert forbidden not in keys
        blob = _string_blob(user_payload).lower()
        assert case.case_id.lower() not in blob
        assert semantic_remainder.lower() not in blob
        assert case.split.lower() not in blob
        assert case.signal.generator.lower() not in blob
        assert "causal_faults" not in blob
        assert "acceptable_first_tools" not in blob
        assert "sufficient_evidence_sets" not in blob
        assert "target_metrics" not in blob
        assert "samples" not in keys
        assert "waveform" not in keys
        assert "frequencies_hz" not in keys
        assert "magnitude_db" not in keys
