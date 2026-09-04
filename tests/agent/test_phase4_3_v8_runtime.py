"""Phase 4.3 planner v8 product-boundary runtime tests (T211, T212)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent import prompts as prompts_mod
from signal_diag.agent.models import AgentRunResult, CallToolDecision
from signal_diag.agent.planner import _Phase4V8RealLLMPlanner
from signal_diag.agent.runtime import DistortionDiagnosisRuntime
from signal_diag.evaluation.dataset import (
    _materialize_case,
    _opaque_evaluation_signal_id,
    load_dataset_manifest,
)
from signal_diag.evaluation.recording import RecordingPlanner
from signal_diag.knowledge.index import KnowledgeIndex
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import generate_combined_distortion, generate_sine
from signal_diag.signal.factory import build_signal_record
from signal_diag.signal.repository import InMemorySignalRepository
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
CORPUS_PATH = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"
PHASE4_2_MANIFEST = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1_2.yaml"
)
_V8_VERSION = "v0.2-s1-planner-8"
_OPAQUE_SIGNAL_ID = re.compile(r"^sig_eval_[0-9a-f]{24}$")
_S1_FAMILY_TOOLS = frozenset({"detect_clipping", "analyze_harmonic_distortion"})
_BROAD_HYPOTHESES = ("clipping", "harmonic_distortion")
_HIDDEN_EVALUATION_FIXTURE = {
    "case_id": "SENTINEL_CASE_ZXQ7B_LEAK",
    "category": "SENTINEL_CATEGORY_QK9M",
    "split": "SENTINEL_SPLIT_HELD_OUT",
    "generator": "SENTINEL_GENERATOR_TRUTH",
    "causal_faults": ("SENTINEL_CAUSAL_FAULT",),
    "knowledge_policy": "SENTINEL_KNOWLEDGE_POLICY",
    "acceptable_first_tools": ("SENTINEL_ACCEPTABLE_TOOL",),
    "sufficient_evidence_sets": ("SENTINEL_SUFFICIENT_SET",),
    "observable_conditions": ("SENTINEL_OBSERVABLE_CONDITION",),
    "target_metrics": {"SENTINEL_TARGET_BAND": 0.99},
    "dataset_id": "SENTINEL_MANIFEST_DATASET",
    "dataset_version": "SENTINEL_MANIFEST_VERSION",
}
_FORBIDDEN_EVALUATION_KEYS = {
    "case_id",
    "category",
    "split",
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
    "dataset_id",
    "generator",
    "clip_level",
    "harmonic_ratios",
    "fundamental_amplitude",
}
_FFT_KEYS = frozenset({"frequencies_hz", "magnitude_db"})
_GENERATOR_INPUT_TOKENS = (
    "harmonic_ratios",
    "clip_level",
    "fundamental_amplitude",
)
_CASE_ID_PATTERN = re.compile(r"case_v1[12]_")
_FORBIDDEN_VALUE_TOKENS = (
    "case_v12_",
    "case_v11_",
    "clipping_strong",
    "invalid_noise",
    "combined_01",
    "combined_distortion",
    "clipped_sine",
    "harmonic_sine",
    "white_noise",
    "acceptable_first_tools",
    "sufficient_evidence_sets",
    "causal_faults",
    "s1-distortion-synthetic",
    "SENTINEL_CASE_ZXQ7B_LEAK",
    "SENTINEL_CATEGORY_QK9M",
    "SENTINEL_SPLIT_HELD_OUT",
    "SENTINEL_GENERATOR_TRUTH",
    "SENTINEL_CAUSAL_FAULT",
    "SENTINEL_KNOWLEDGE_POLICY",
    "SENTINEL_ACCEPTABLE_TOOL",
    "SENTINEL_SUFFICIENT_SET",
    "SENTINEL_OBSERVABLE_CONDITION",
    "SENTINEL_TARGET_BAND",
    "SENTINEL_MANIFEST_DATASET",
    "SENTINEL_MANIFEST_VERSION",
)
_SEMANTIC_SIGNAL_TOKENS = (
    "case_v12",
    "case_v11",
    "clipping",
    "harmonic",
    "combined",
    "combo",
    "noise",
    "clean",
    "fault",
    "held",
    "development",
    "invalid",
    "sentinel",
)


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _V8PolicyFakeCompletions:
    """Observation-driven fake that returns exactly one JSON decision per create()."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        context = json.loads(kwargs["messages"][1]["content"])["planner_context"]
        payload = _v8_policy_decision(context)
        return _FakeResponse([_FakeChoice(_FakeMessage(json.dumps(payload)))])


@dataclass
class _FakeChat:
    completions: _V8PolicyFakeCompletions


@dataclass
class _FakeClient:
    chat: _FakeChat


def _v8_client() -> _FakeClient:
    return _FakeClient(_FakeChat(_V8PolicyFakeCompletions()))


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


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found: list[str] = []
        for nested in value.values():
            found.extend(_string_values(nested))
        return found
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            found.extend(_string_values(item))
        return found
    return []


def _has_long_numeric_array(value: object, *, min_len: int = 32) -> bool:
    if isinstance(value, list):
        if len(value) >= min_len and all(isinstance(item, (int, float)) for item in value):
            return True
        return any(_has_long_numeric_array(item, min_len=min_len) for item in value)
    if isinstance(value, dict):
        return any(_has_long_numeric_array(item, min_len=min_len) for item in value.values())
    return False


def _looks_unstable_or_nonperiodic(user_request: str) -> bool:
    lowered = user_request.lower()
    return (
        ("unstable" in lowered and "pitch" in lowered)
        or "non-periodic" in lowered
        or "not periodic" in lowered
        or "does not sound periodic" in lowered
        or "does not stay periodic" in lowered
    )


def _looks_clipping_symptom(user_request: str) -> bool:
    lowered = user_request.lower()
    return any(token in lowered for token in ("flatten", "ceiling", "crest", "limited"))


def _looks_overtone_symptom(user_request: str) -> bool:
    lowered = user_request.lower()
    return "overtone" in lowered or "tonal" in lowered


def _first_tool_from_visible_request(user_request: str) -> str:
    if _looks_clipping_symptom(user_request):
        return "detect_clipping"
    if _looks_overtone_symptom(user_request):
        return "analyze_harmonic_distortion"
    if _looks_unstable_or_nonperiodic(user_request):
        return "estimate_fundamental"
    return "detect_clipping"


def _initial_assessment(user_request: str) -> dict[str, Any]:
    if _looks_overtone_symptom(user_request) or _looks_unstable_or_nonperiodic(
        user_request
    ):
        hypotheses = ["harmonic_distortion"]
        objective = (
            "Determine whether harmonic distortion explains the observed signal."
        )
    else:
        hypotheses = list(_BROAD_HYPOTHESES)
        objective = (
            "Determine whether clipping or harmonic distortion explains the signal."
        )
    return {
        "task_type": "distortion_analysis",
        "objective": objective,
        "hypotheses": hypotheses,
    }


def _has_invalid_harmonic(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("validity") == "not_applicable"
        for item in evidence
    )


def _flatten_evaluations(context: dict[str, Any]) -> list[dict[str, Any]]:
    batches = list(context.get("rule_evaluation_batches") or [])
    return [item for batch in batches for item in batch.get("evaluations", [])]


def _ids_for_tool(evidence: list[dict[str, Any]], tool_name: str) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("source_tool") == tool_name
    ]


def _valid_ids_for_tool(evidence: list[dict[str, Any]], tool_name: str) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("source_tool") == tool_name and item.get("validity") == "valid"
    ]


def _invalid_harmonic_ids(evidence: list[dict[str, Any]]) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("validity") == "not_applicable"
    ]


def _order2_ids(evidence: list[dict[str, Any]]) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("metric") == "harmonic_order_2_relative_amplitude"
        and item.get("validity") == "valid"
        and isinstance(item.get("value"), (int, float))
    ]


def _clipping_detected(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "detect_clipping"
        and item.get("metric") == "clipping_detected"
        and item.get("value") is True
        for item in evidence
    )


def _needed_family_tools(hypotheses: list[str]) -> set[str]:
    needed: set[str] = set()
    if "clipping" in hypotheses:
        needed.add("detect_clipping")
    if "harmonic_distortion" in hypotheses:
        needed.add("analyze_harmonic_distortion")
    return needed


def _call_tool_payload(
    tool_name: str,
    *,
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision_type": "call_tool",
        "call": {"tool_name": tool_name, "args": {}},
        "purpose": f"collect {tool_name} evidence from the current request",
    }
    if assessment is not None:
        payload["task_assessment"] = assessment
    return payload



def _ids_for_metric(evidence: list[dict[str, Any]], metric: str, value: object | None = None) -> list[str]:
    ids: list[str] = []
    for item in evidence:
        if item.get("metric") != metric:
            continue
        if value is not None and item.get("value") != value:
            continue
        ids.append(item["evidence_id"])
    return ids

def _v8_finish(context: dict[str, Any]) -> dict[str, Any]:
    evidence = list(context.get("evidence") or [])
    evaluations = _flatten_evaluations(context)
    retrievals = list(context.get("knowledge_retrievals") or [])
    user_request = str(context.get("user_request") or "")
    matched_knowledge = [
        item["retrieval_id"] for item in retrievals if item.get("matches")
    ]
    na_rule_ids = [
        item["evaluation_id"]
        for item in evaluations
        if item.get("judgment") == "not_applicable"
    ]
    clip_ids = _ids_for_tool(evidence, "detect_clipping")
    harm_valid_ids = _valid_ids_for_tool(evidence, "analyze_harmonic_distortion")
    order2_ids = _order2_ids(evidence)
    clip_fail = [
        item
        for item in evaluations
        if item.get("judgment") == "fail"
        and (
            "clip" in item.get("rule_id", "")
            or "flat_top" in item.get("rule_id", "")
        )
    ]
    thd_evals = [
        item for item in evaluations if item.get("rule_id") == "rule_thd_acceptable"
    ]
    harmonic_valid_evals = [
        item
        for item in evaluations
        if item.get("rule_id") == "rule_harmonic_analysis_valid"
    ]
    thd_fail = any(item.get("judgment") == "fail" for item in thd_evals)
    thd_present = any(
        item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("metric") == "thd_percent"
        and item.get("validity") == "valid"
        for item in evidence
    )
    clipping_present = (_clipping_detected(evidence) or bool(clip_fail)) and bool(
        _ids_for_metric(evidence, "clipping_mechanism", True)
    )
    overtone_request = _looks_overtone_symptom(user_request)

    if _has_invalid_harmonic(evidence):
        return {
            "decision_type": "finish",
            "outcome": "inconclusive",
            "claims": [
                {
                    "claim_id": "claim_inconclusive",
                    "fault_type": "inconclusive",
                    "statement": (
                        "Harmonic analysis is not applicable; no numeric THD "
                        "was fabricated."
                    ),
                    "evidence_refs": _invalid_harmonic_ids(evidence),
                    "rule_refs": na_rule_ids,
                    "knowledge_refs": matched_knowledge,
                }
            ],
            "confidence_label": "low",
            "limitations": [
                "Harmonic analysis is invalid or not applicable on this signal."
            ],
        }

    claims: list[dict[str, Any]] = []
    if clipping_present:
        claims.append(
            {
                "claim_id": "claim_clip",
                "fault_type": "clipping",
                "statement": "Clipping evidence supports a clipping diagnosis.",
                "evidence_refs": clip_ids + _ids_for_metric(evidence, "clipping_mechanism", True),
                "rule_refs": [item["evaluation_id"] for item in clip_fail],
            }
        )
    independent_harmonic = (
        thd_fail
        or (bool(order2_ids) and clipping_present)
        or (overtone_request and thd_present and not clipping_present)
    ) and bool(_ids_for_metric(evidence, "series_kind", "even_order_present"))
    if independent_harmonic:
        harm_rule_ids = [
            item["evaluation_id"] for item in thd_evals + harmonic_valid_evals
        ]
        harm_refs = list(harm_valid_ids)
        for evidence_id in order2_ids:
            if evidence_id not in harm_refs:
                harm_refs.append(evidence_id)
        statement = (
            "Harmonic distortion is present in the deterministic Evidence."
        )
        if any(item.get("judgment") == "pass" for item in thd_evals) and not thd_fail:
            statement = (
                "Harmonic distortion is present in the Evidence; the configured "
                "rule evaluation is PASS and does not erase that observation."
            )
        claims.append(
            {
                "claim_id": "claim_harm",
                "fault_type": "harmonic_distortion",
                "statement": statement,
                "evidence_refs": harm_refs + _ids_for_metric(evidence, "series_kind", "even_order_present"),
                "rule_refs": harm_rule_ids,
            }
        )
    if claims:
        return {
            "decision_type": "finish",
            "outcome": "supported_fault",
            "claims": claims,
            "confidence_label": "high",
        }
    return {
        "decision_type": "finish",
        "outcome": "no_supported_fault",
        "claims": [
            {
                "claim_id": "claim_clean",
                "fault_type": "no_supported_fault",
                "statement": (
                    "Clipping and harmonic distortion are both ruled out by "
                    "sufficient Evidence; the supported cause set is empty."
                ),
                "evidence_refs": [item["evidence_id"] for item in evidence],
                "rule_refs": [item["evaluation_id"] for item in evaluations],
            }
        ],
        "confidence_label": "high",
    }


def _v8_policy_decision(context: dict[str, Any]) -> dict[str, Any]:
    observations = list(context.get("observations") or [])
    evidence = list(context.get("evidence") or [])
    batches = list(context.get("rule_evaluation_batches") or [])
    retrievals = list(context.get("knowledge_retrievals") or [])
    observed_tools = {item.get("tool_name") for item in observations}
    user_request = str(context.get("user_request") or "")
    assessment = context.get("task_assessment")
    if not observations:
        chosen = _first_tool_from_visible_request(user_request)
        return _call_tool_payload(chosen, assessment=_initial_assessment(user_request))
    hypotheses = list((assessment or {}).get("hypotheses") or [])
    missing_family = _needed_family_tools(hypotheses) - observed_tools
    if missing_family:
        return _call_tool_payload(min(missing_family), assessment=None)
    if evidence and not batches:
        return {
            "decision_type": "evaluate_rules",
            "profile_id": "profile_s1_distortion",
            "evidence_refs": [item["evidence_id"] for item in evidence],
            "purpose": "evaluate current S1 evidence under the configured profile",
        }
    if _has_invalid_harmonic(evidence) and not retrievals:
        return {
            "decision_type": "retrieve_knowledge",
            "query_text": "inconclusive harmonic analysis",
            "tags": ["inconclusive"],
            "purpose": "explain invalid or not applicable harmonic measurement",
        }
    return _v8_finish(context)


def _assert_no_leakage(calls: list[dict[str, Any]]) -> None:
    assert calls
    for kwargs in calls:
        messages = kwargs["messages"]
        assert len(messages) >= 2
        user_payload = json.loads(messages[1]["content"])
        blob = json.dumps(user_payload)
        assert _CASE_ID_PATTERN.search(blob) is None
        lowered_blob = blob.lower()
        for token in _GENERATOR_INPUT_TOKENS:
            assert token not in lowered_blob
        keys = _json_keys(user_payload)
        lowered_keys = {key.lower() for key in keys}
        for token in _FORBIDDEN_EVALUATION_KEYS:
            assert token not in lowered_keys
        for token in _FFT_KEYS:
            assert token not in keys
        assert "samples" not in keys
        assert "waveform" not in lowered_keys
        assert not _has_long_numeric_array(user_payload)
        for token in _FORBIDDEN_VALUE_TOKENS:
            assert token not in lowered_blob
        signal_id = user_payload["planner_context"]["signal_meta"]["signal_id"]
        lowered_id = signal_id.lower()
        for token in _SEMANTIC_SIGNAL_TOKENS:
            assert token not in lowered_id
        for value in _string_values(user_payload):
            lowered_value = value.lower()
            assert _CASE_ID_PATTERN.search(value) is None
            for token in _FORBIDDEN_VALUE_TOKENS:
                assert token not in lowered_value


def _assert_same_run_refs(result: AgentRunResult) -> None:
    assert result.diagnosis is not None
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        evaluation.evaluation_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    matched_knowledge_ids = {
        item.retrieval_id
        for item in result.knowledge_retrievals
        if item.matches
    }
    empty_knowledge_ids = knowledge_ids - matched_knowledge_ids
    for claim in result.diagnosis.claims:
        assert set(claim.evidence_refs) <= evidence_ids
        assert set(claim.rule_refs) <= rule_ids
        assert set(claim.knowledge_refs) <= knowledge_ids
        assert set(claim.knowledge_refs).isdisjoint(empty_knowledge_ids)
        if claim.fault_type != "inconclusive":
            assert claim.evidence_refs


def _assert_runtime_does_not_force_actions(
    result: AgentRunResult,
    recording: RecordingPlanner,
) -> None:
    planned_tools = [
        record.decision.call.tool_name
        for record in recording.records
        if isinstance(record.decision, CallToolDecision)
    ]
    observed_tools = [observation.tool_name for observation in result.observations]
    assert observed_tools == planned_tools
    planned_kinds = [
        getattr(record.decision, "decision_type", None)
        for record in recording.records
        if record.decision is not None
    ]
    assert planned_kinds
    assert "finish" in planned_kinds


def _decision_path(recording: RecordingPlanner) -> tuple[str, ...]:
    path: list[str] = []
    for record in recording.records:
        if record.decision is None:
            continue
        kind = getattr(record.decision, "decision_type", None)
        if kind == "call_tool":
            path.append(f"call_tool:{record.decision.call.tool_name}")
        elif kind is not None:
            path.append(str(kind))
    return tuple(path)



def _full_scale_combined_case():
    return generate_combined_distortion(
        fundamental_hz=168.0,
        harmonic_ratios={2: 0.18},
        clip_level=1.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=1.2,
    )


def _v12_store(
    repository: InMemorySignalRepository,
    case_id: str,
) -> tuple[str, str]:
    manifest = load_dataset_manifest(PHASE4_2_MANIFEST)
    case = next(item for item in manifest.cases if item.case_id == case_id)
    assert case.split == "development"
    signal_id = _opaque_evaluation_signal_id(
        manifest.dataset_id,
        manifest.version,
        case.case_id,
    )
    _materialize_case(case, repository, signal_id=signal_id)
    assert _OPAQUE_SIGNAL_ID.fullmatch(signal_id)
    return signal_id, case.user_request


def _store_sine_under_id(
    repository: InMemorySignalRepository,
    signal_id: str,
) -> None:
    generated = generate_sine(
        frequency_hz=172.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.48,
    )
    record = build_signal_record(
        generated.record.samples,
        sample_rate_hz=generated.record.meta.sample_rate_hz,
        source_type="generated",
        signal_id=signal_id,
    )
    repository.put(record)


async def _run_v8_product_path(
    repository: InMemorySignalRepository,
    signal_id: str,
    client: _FakeClient,
    user_request: str,
) -> tuple[AgentRunResult, RecordingPlanner]:
    planner = _Phase4V8RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    assert type(planner) is _Phase4V8RealLLMPlanner
    recording = RecordingPlanner(planner)
    runtime = DistortionDiagnosisRuntime(
        repository=repository,
        tool_service=SignalToolService(repository),
        planner=recording,
        rule_engine=RuleEngine(),
        rule_profile_loader=YamlRuleProfileLoader(
            {"profile_s1_distortion": PROFILE_PATH}
        ),
        knowledge_index=KnowledgeIndex(CORPUS_PATH),
    )
    result = await runtime.run(signal_id=signal_id, user_request=user_request)
    calls = client.chat.completions.calls
    assert calls
    first_system = calls[0]["messages"][0]["content"]
    assert first_system == prompts_mod._S1_PROMPT_V8.system_prompt
    for kwargs in calls:
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["prompt_version"] == _V8_VERSION
        assert kwargs["messages"][0]["content"] == prompts_mod._S1_PROMPT_V8.system_prompt
        assert payload["planner_context"]["signal_meta"]["signal_id"] == signal_id
        assert payload["planner_context"]["user_request"] == user_request
    _assert_no_leakage(calls)
    _assert_same_run_refs(result)
    _assert_runtime_does_not_force_actions(result, recording)
    return result, recording


def _causal_fault_types(result: AgentRunResult) -> list[str]:
    assert result.diagnosis is not None
    return [claim.fault_type for claim in result.diagnosis.claims]


def _tool_names(result: AgentRunResult) -> tuple[str, ...]:
    return tuple(observation.tool_name for observation in result.observations)


def _dsp_family_tools(result: AgentRunResult) -> tuple[str, ...]:
    return tuple(
        observation.tool_name
        for observation in result.observations
        if observation.tool_name in _S1_FAMILY_TOOLS
    )


def _decision_kinds(recording: RecordingPlanner) -> list[str]:
    return [
        getattr(record.decision, "decision_type", None)
        for record in recording.records
        if record.decision is not None
    ]


@pytest.fixture(autouse=True)
def _no_deepseek_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


@pytest.mark.asyncio
async def test_t211_outbound_json_omits_hidden_evaluation_sentinels(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = _opaque_evaluation_signal_id(
        str(_HIDDEN_EVALUATION_FIXTURE["dataset_id"]),
        str(_HIDDEN_EVALUATION_FIXTURE["dataset_version"]),
        str(_HIDDEN_EVALUATION_FIXTURE["case_id"]),
    )
    assert _OPAQUE_SIGNAL_ID.fullmatch(signal_id)
    assert str(_HIDDEN_EVALUATION_FIXTURE["case_id"]) not in signal_id
    _store_sine_under_id(repository, signal_id)
    user_request = "Please inspect this recording for any plausible S1 distortion causes."
    client = _v8_client()
    result, _recording = await _run_v8_product_path(
        repository, signal_id, client, user_request
    )
    assert result.diagnosis is not None
    hidden_blob = json.dumps(_HIDDEN_EVALUATION_FIXTURE)
    for kwargs in client.chat.completions.calls:
        outbound = json.dumps(kwargs["messages"])
        assert hidden_blob not in outbound
        for sentinel in _string_values(_HIDDEN_EVALUATION_FIXTURE):
            assert sentinel not in outbound
        payload = json.loads(kwargs["messages"][1]["content"])
        keys = {key.lower() for key in _json_keys(payload)}
        for forbidden in _FORBIDDEN_EVALUATION_KEYS:
            assert forbidden not in keys


@pytest.mark.asyncio
async def test_t211_opaque_signal_id_does_not_change_decision_path(
    repository: InMemorySignalRepository,
) -> None:
    first_id = _opaque_evaluation_signal_id(
        "s1-distortion-synthetic",
        "1.2.0",
        "SENTINEL_CASE_ZXQ7B_LEAK",
    )
    second_id = _opaque_evaluation_signal_id(
        "s1-distortion-synthetic",
        "1.2.0",
        "SENTINEL_CASE_OTHER_OPAQUE",
    )
    assert first_id != second_id
    assert _OPAQUE_SIGNAL_ID.fullmatch(first_id)
    assert _OPAQUE_SIGNAL_ID.fullmatch(second_id)
    _store_sine_under_id(repository, first_id)
    _store_sine_under_id(repository, second_id)
    user_request = "Please inspect this recording for any plausible S1 distortion causes."
    first_client = _v8_client()
    second_client = _v8_client()
    _first_result, first_recording = await _run_v8_product_path(
        repository, first_id, first_client, user_request
    )
    _second_result, second_recording = await _run_v8_product_path(
        repository, second_id, second_client, user_request
    )
    assert _decision_path(first_recording) == _decision_path(second_recording)
    assert _decision_path(first_recording)
    for kwargs in first_client.chat.completions.calls:
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["planner_context"]["signal_meta"]["signal_id"] == first_id
        assert "SENTINEL_CASE_ZXQ7B_LEAK" not in json.dumps(payload)
    for kwargs in second_client.chat.completions.calls:
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["planner_context"]["signal_meta"]["signal_id"] == second_id
        assert "SENTINEL_CASE_OTHER_OPAQUE" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_t212_clean_broad_collects_clipping_and_harmonic_then_no_fault(
    repository: InMemorySignalRepository,
) -> None:
    signal_id, user_request = _v12_store(repository, "case_v12_dev_clean_01")
    result, recording = await _run_v8_product_path(
        repository, signal_id, _v8_client(), user_request
    )
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "no_supported_fault"
    family = _dsp_family_tools(result)
    assert set(family) == _S1_FAMILY_TOOLS
    assert family[0] in _S1_FAMILY_TOOLS
    assert "analyze_spectrum" not in _tool_names(result)
    assert "estimate_fundamental" not in _tool_names(result)
    assert not result.knowledge_retrievals
    assert _causal_fault_types(result) == ["no_supported_fault"]
    kinds = _decision_kinds(recording)
    assert kinds.index("evaluate_rules") < kinds.index("finish")
    assert "retrieve_knowledge" not in kinds


@pytest.mark.asyncio
async def test_t212_harmonic_specific_starts_with_harmonic_and_finishes(
    repository: InMemorySignalRepository,
) -> None:
    signal_id, user_request = _v12_store(repository, "case_v12_dev_harmonic_01")
    result, recording = await _run_v8_product_path(
        repository, signal_id, _v8_client(), user_request
    )
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    tools = _tool_names(result)
    assert tools[0] == "analyze_harmonic_distortion"
    assert "detect_clipping" not in tools
    assert "analyze_spectrum" not in tools
    assert "estimate_fundamental" not in tools
    assert not result.knowledge_retrievals
    assert _causal_fault_types(result) == ["harmonic_distortion"]
    harm_claim = result.diagnosis.claims[0]
    assert harm_claim.evidence_refs
    assert harm_claim.rule_refs
    kinds = _decision_kinds(recording)
    assert kinds.index("evaluate_rules") < kinds.index("finish")
    assert "retrieve_knowledge" not in kinds


@pytest.mark.asyncio
async def test_t212_combined_broad_does_not_finish_after_clipping(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _full_scale_combined_case())
    result, recording = await _run_v8_product_path(
        repository,
        signal_id,
        _v8_client(),
        "Please inspect this recording for any plausible S1 distortion causes.",
    )
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    family = _dsp_family_tools(result)
    assert set(family) == _S1_FAMILY_TOOLS
    assert family[0] in _S1_FAMILY_TOOLS
    assert "analyze_spectrum" not in _tool_names(result)
    assert "estimate_fundamental" not in _tool_names(result)
    finish_index = _decision_kinds(recording).index("finish")
    finish_context = recording.records[finish_index].context
    finish_tools = {item.tool_name for item in finish_context.observations}
    assert _S1_FAMILY_TOOLS <= finish_tools
    faults = set(_causal_fault_types(result))
    assert faults == {"clipping", "harmonic_distortion"}
    clip_claim = next(
        claim for claim in result.diagnosis.claims if claim.fault_type == "clipping"
    )
    harm_claim = next(
        claim
        for claim in result.diagnosis.claims
        if claim.fault_type == "harmonic_distortion"
    )
    assert clip_claim.evidence_refs
    assert harm_claim.evidence_refs
    assert set(clip_claim.evidence_refs).isdisjoint(set(harm_claim.evidence_refs))
    assert clip_claim.rule_refs
    assert harm_claim.rule_refs
    order2_ids = {
        item.evidence_id
        for item in result.evidence
        if item.metric == "harmonic_order_2_relative_amplitude"
        and item.validity == "valid"
    }
    assert order2_ids
    assert order2_ids <= set(harm_claim.evidence_refs)
    kinds = _decision_kinds(recording)
    first_tool = next(
        record.decision.call.tool_name
        for record in recording.records
        if isinstance(record.decision, CallToolDecision)
    )
    if first_tool == "detect_clipping":
        clip_index = next(
            index
            for index, name in enumerate(_tool_names(result))
            if name == "detect_clipping"
        )
        harm_index = next(
            index
            for index, name in enumerate(_tool_names(result))
            if name == "analyze_harmonic_distortion"
        )
        assert clip_index < harm_index
        assert kinds.index("finish") > kinds.index("evaluate_rules")


@pytest.mark.asyncio
async def test_t212_noise_acquires_invalid_harmonic_then_knowledge(
    repository: InMemorySignalRepository,
) -> None:
    signal_id, user_request = _v12_store(repository, "case_v12_dev_noise_01")
    result, recording = await _run_v8_product_path(
        repository, signal_id, _v8_client(), user_request
    )
    assert result.status == "inconclusive"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.limitations
    tools = _tool_names(result)
    assert tools[0] in {"estimate_fundamental", "analyze_harmonic_distortion"}
    assert "analyze_harmonic_distortion" in tools
    assert "detect_clipping" not in tools
    assert "analyze_spectrum" not in tools
    assert any(
        item.source_tool == "analyze_harmonic_distortion"
        and item.validity == "not_applicable"
        for item in result.evidence
    )
    assert result.knowledge_retrievals
    assert result.knowledge_retrievals[0].matches
    claims = result.diagnosis.claims
    assert len(claims) == 1
    claim = claims[0]
    assert claim.fault_type == "inconclusive"
    assert claim.evidence_refs
    assert claim.knowledge_refs
    assert claim.rule_refs
    cited_rules = [
        evaluation
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
        if evaluation.evaluation_id in claim.rule_refs
    ]
    assert cited_rules
    assert any(item.judgment == "not_applicable" for item in cited_rules)
    assert all(
        next(item for item in result.evidence if item.evidence_id == ref).validity
        == "not_applicable"
        for ref in claim.evidence_refs
        if next(item for item in result.evidence if item.evidence_id == ref).source_tool
        == "analyze_harmonic_distortion"
    )
    kinds = _decision_kinds(recording)
    assert kinds.index("evaluate_rules") < kinds.index("retrieve_knowledge")
    assert kinds.index("retrieve_knowledge") < kinds.index("finish")
