"""Phase 4.2 planner v7 product-boundary runtime tests (T206)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from signal_diag.agent import prompts as prompts_mod
from signal_diag.agent.models import AgentRunResult, CallToolDecision
from signal_diag.agent.planner import RealLLMPlanner, _Phase4V7RealLLMPlanner
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
from signal_diag.signal import (
    generate_clipped_sine,
    generate_combined_distortion,
    generate_harmonic_sine,
)
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
_V7_VERSION = "v0.2-s1-planner-7"
_OPAQUE_SIGNAL_ID = re.compile(r"^sig_eval_[0-9a-f]{24}$")
_S1_DSP_TOOLS = frozenset({"detect_clipping", "analyze_harmonic_distortion"})
_ASSESSMENT = {
    "task_type": "distortion_analysis",
    "objective": "Determine whether clipping or harmonic distortion explains the signal.",
    "hypotheses": ["clipping", "harmonic_distortion"],
}
_FORBIDDEN_EVALUATION_FIELDS = {
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
}
_GENERATOR_INPUT_TOKENS = (
    "harmonic_ratios",
    "clip_level",
    "fundamental_amplitude",
)
_FFT_KEYS = frozenset({"frequencies_hz", "magnitude_db"})
_CASE_ID_PATTERN = re.compile(r"case_v1[12]_")
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
)
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


class _V7PolicyFakeCompletions:
    """Observation-driven fake that returns exactly one JSON decision per create()."""

    def __init__(
        self,
        *,
        first_tool: str,
        collect_other_family: bool = False,
        knowledge_tags: tuple[str, ...] = ("inconclusive",),
        knowledge_query: str = "inconclusive harmonic analysis",
    ) -> None:
        self._first_tool = first_tool
        self._collect_other_family = collect_other_family
        self._knowledge_tags = knowledge_tags
        self._knowledge_query = knowledge_query
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        context = json.loads(kwargs["messages"][1]["content"])["planner_context"]
        payload = _v7_policy_decision(
            context,
            first_tool=self._first_tool,
            collect_other_family=self._collect_other_family,
            knowledge_tags=self._knowledge_tags,
            knowledge_query=self._knowledge_query,
        )
        return _FakeResponse([_FakeChoice(_FakeMessage(json.dumps(payload)))])


@dataclass
class _FakeChat:
    completions: _V7PolicyFakeCompletions


@dataclass
class _FakeClient:
    chat: _FakeChat


def _v7_client(
    *,
    first_tool: str,
    collect_other_family: bool = False,
    knowledge_tags: tuple[str, ...] = ("inconclusive",),
    knowledge_query: str = "inconclusive harmonic analysis",
) -> _FakeClient:
    completions = _V7PolicyFakeCompletions(
        first_tool=first_tool,
        collect_other_family=collect_other_family,
        knowledge_tags=knowledge_tags,
        knowledge_query=knowledge_query,
    )
    return _FakeClient(_FakeChat(completions))


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


def _first_tool_from_visible_request(user_request: str, configured: str) -> str:
    if _looks_clipping_symptom(user_request):
        return "detect_clipping"
    if _looks_overtone_symptom(user_request):
        return "analyze_harmonic_distortion"
    if _looks_unstable_or_nonperiodic(user_request):
        if configured in {"estimate_fundamental", "analyze_harmonic_distortion"}:
            return configured
        return "estimate_fundamental"
    return configured


def _has_invalid_harmonic(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "analyze_harmonic_distortion"
        and item.get("validity") == "not_applicable"
        for item in evidence
    )


def _has_unvoiced_fundamental(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "estimate_fundamental"
        and item.get("metric") == "voiced"
        and item.get("value") is False
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


def _invalid_or_na_ids(evidence: list[dict[str, Any]], tool_name: str) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("source_tool") == tool_name
        and (
            item.get("validity") == "not_applicable"
            or (
                tool_name == "estimate_fundamental"
                and item.get("metric") == "voiced"
                and item.get("value") is False
            )
            or tool_name == "estimate_fundamental"
        )
    ]


def _valid_thd_values(evidence: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for item in evidence:
        if (
            item.get("source_tool") == "analyze_harmonic_distortion"
            and item.get("metric") == "thd_percent"
            and item.get("validity") == "valid"
            and isinstance(item.get("value"), (int, float))
        ):
            values.append(float(item["value"]))
    return values


def _clipping_detected(evidence: list[dict[str, Any]]) -> bool:
    return any(
        item.get("source_tool") == "detect_clipping"
        and item.get("metric") == "clipping_detected"
        and item.get("value") is True
        for item in evidence
    )


def _order2_ids(evidence: list[dict[str, Any]]) -> list[str]:
    return [
        item["evidence_id"]
        for item in evidence
        if item.get("metric") == "harmonic_order_2_relative_amplitude"
        and item.get("validity") == "valid"
        and isinstance(item.get("value"), (int, float))
    ]


def _odd_order_present(evidence: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(item.get("metric"), str)
        and re.fullmatch(r"harmonic_order_\d+_relative_amplitude", item["metric"])
        and int(item["metric"].split("_")[2]) % 2 == 1
        and item.get("validity") == "valid"
        for item in evidence
    )


def _call_tool_payload(tool_name: str, *, first: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision_type": "call_tool",
        "call": {"tool_name": tool_name, "args": {}},
        "purpose": f"collect {tool_name} evidence from the current request",
    }
    if first:
        payload["task_assessment"] = _ASSESSMENT
    return payload


def _inconclusive_finish(
    *,
    evidence_ids: list[str],
    rule_ids: list[str],
    knowledge_ids: list[str],
    statement: str,
    limitation: str,
) -> dict[str, Any]:
    return {
        "decision_type": "finish",
        "outcome": "inconclusive",
        "claims": [
            {
                "claim_id": "claim_inconclusive",
                "fault_type": "inconclusive",
                "statement": statement,
                "evidence_refs": evidence_ids,
                "rule_refs": rule_ids,
                "knowledge_refs": knowledge_ids,
            }
        ],
        "confidence_label": "low",
        "limitations": [limitation],
    }



def _ids_for_metric(evidence: list[dict[str, Any]], metric: str, value: object | None = None) -> list[str]:
    ids: list[str] = []
    for item in evidence:
        if item.get("metric") != metric:
            continue
        if value is not None and item.get("value") != value:
            continue
        ids.append(item["evidence_id"])
    return ids

def _v7_finish(context: dict[str, Any]) -> dict[str, Any]:
    evidence = list(context.get("evidence") or [])
    evaluations = _flatten_evaluations(context)
    retrievals = list(context.get("knowledge_retrievals") or [])
    matched_knowledge = [
        item["retrieval_id"] for item in retrievals if item.get("matches")
    ]
    na_or_applicable = [
        item["evaluation_id"]
        for item in evaluations
        if item.get("judgment") in {"not_applicable", "fail", "pass"}
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
    thd_present = bool(_valid_thd_values(evidence))
    thd_pass = any(item.get("judgment") == "pass" for item in thd_evals)
    clipping_present = (_clipping_detected(evidence) or bool(clip_fail)) and bool(
        _ids_for_metric(evidence, "clipping_mechanism", True)
    )

    if _has_invalid_harmonic(evidence):
        return _inconclusive_finish(
            evidence_ids=_invalid_or_na_ids(evidence, "analyze_harmonic_distortion"),
            rule_ids=na_or_applicable,
            knowledge_ids=matched_knowledge,
            statement=(
                "Harmonic analysis is not applicable; no numeric THD was "
                "fabricated."
            ),
            limitation="Harmonic analysis is invalid or not applicable on this signal.",
        )

    if _has_unvoiced_fundamental(evidence):
        return _inconclusive_finish(
            evidence_ids=_ids_for_tool(evidence, "estimate_fundamental"),
            rule_ids=na_or_applicable,
            knowledge_ids=matched_knowledge,
            statement=(
                "The fundamental estimate is unvoiced, so harmonic distortion "
                "cannot be established."
            ),
            limitation="Fundamental frequency estimate is unvoiced or unreliable.",
        )

    claims: list[dict[str, Any]] = []
    if clipping_present:
        statement = "Clipping evidence supports a clipping diagnosis."
        if _odd_order_present(evidence) and not order2_ids:
            statement = (
                "Clipping is present in the live Evidence. Odd-order harmonics "
                "are the expected clipping-induced pattern and are not by "
                "themselves an independent harmonic_distortion claim."
            )
        claims.append(
            {
                "claim_id": "claim_clip",
                "fault_type": "clipping",
                "statement": statement,
                "evidence_refs": clip_ids + _ids_for_metric(evidence, "clipping_mechanism", True),
                "rule_refs": [item["evaluation_id"] for item in clip_fail],
            }
        )
    independent_harmonic = (bool(order2_ids) or (thd_present and not clipping_present)) and bool(
        _ids_for_metric(evidence, "series_kind", "even_order_present")
    )
    if independent_harmonic:
        harm_rule_ids = [
            item["evaluation_id"] for item in thd_evals + harmonic_valid_evals
        ]
        statement = (
            "Harmonic distortion is present in the deterministic Evidence, while "
            "the observed THD still satisfies the configured 5% demonstration "
            "limit (rule PASS)."
            if thd_pass
            else "A reportable even-order (order-2) component supports an independent harmonic_distortion claim."
        )
        if thd_pass and not clipping_present:
            statement = (
                "Harmonic distortion is present in the Evidence; the configured "
                "rule evaluation is PASS and does not erase that observation."
            )
        harm_refs = list(harm_valid_ids)
        if order2_ids:
            for evidence_id in order2_ids:
                if evidence_id not in harm_refs:
                    harm_refs.append(evidence_id)
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
        finish: dict[str, Any] = {
            "decision_type": "finish",
            "outcome": "supported_fault",
            "claims": claims,
            "confidence_label": "high",
        }
        if clipping_present and _odd_order_present(evidence) and not order2_ids:
            finish["limitations"] = [
                (
                    "Odd-order harmonic components are treated as a clipping-induced "
                    "pattern, not a separate harmonic_distortion fault."
                )
            ]
        return finish
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


def _v7_policy_decision(
    context: dict[str, Any],
    *,
    first_tool: str,
    collect_other_family: bool,
    knowledge_tags: tuple[str, ...],
    knowledge_query: str,
) -> dict[str, Any]:
    observations = list(context.get("observations") or [])
    evidence = list(context.get("evidence") or [])
    batches = list(context.get("rule_evaluation_batches") or [])
    retrievals = list(context.get("knowledge_retrievals") or [])
    observed_tools = {item.get("tool_name") for item in observations}
    user_request = str(context.get("user_request") or "")
    if not observations:
        chosen = _first_tool_from_visible_request(user_request, first_tool)
        return _call_tool_payload(chosen, first=True)
    if collect_other_family:
        remaining = _S1_DSP_TOOLS - observed_tools
        if remaining:
            return _call_tool_payload(min(remaining), first=False)
    if evidence and not batches:
        return {
            "decision_type": "evaluate_rules",
            "profile_id": "profile_s1_distortion",
            "evidence_refs": [item["evidence_id"] for item in evidence],
            "purpose": "evaluate current S1 evidence under the configured profile",
        }
    needs_knowledge = (
        _has_invalid_harmonic(evidence) or _has_unvoiced_fundamental(evidence)
    ) and not retrievals
    if needs_knowledge:
        return {
            "decision_type": "retrieve_knowledge",
            "query_text": knowledge_query,
            "tags": list(knowledge_tags),
            "purpose": "explain invalid, unvoiced, or not applicable measurement",
        }
    return _v7_finish(context)


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
        for token in _FORBIDDEN_EVALUATION_FIELDS:
            assert token not in lowered_blob
        for token in _FORBIDDEN_VALUE_TOKENS:
            assert token not in lowered_blob
        keys = _json_keys(user_payload)
        lowered_keys = {key.lower() for key in keys}
        assert "samples" not in keys
        assert "waveform" not in lowered_keys
        for token in _FFT_KEYS:
            assert token not in keys
        assert not _has_long_numeric_array(user_payload)
        signal_id = user_payload["planner_context"]["signal_meta"]["signal_id"]
        lowered_id = signal_id.lower()
        for token in _SEMANTIC_SIGNAL_TOKENS:
            assert token not in lowered_id
        for value in _string_values(user_payload["planner_context"]):
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


def _assert_no_unrelated_evidence(result: AgentRunResult) -> None:
    assert result.diagnosis is not None
    by_tool = {
        item.evidence_id: item.source_tool for item in result.evidence
    }
    for claim in result.diagnosis.claims:
        cited_tools = {by_tool[ref] for ref in claim.evidence_refs if ref in by_tool}
        if claim.fault_type == "clipping":
            assert cited_tools <= {"detect_clipping"}
        elif claim.fault_type == "harmonic_distortion":
            assert cited_tools <= {"analyze_harmonic_distortion"}
        elif claim.fault_type == "inconclusive":
            assert cited_tools <= {
                "analyze_harmonic_distortion",
                "estimate_fundamental",
            }
            for ref in claim.evidence_refs:
                item = next(ev for ev in result.evidence if ev.evidence_id == ref)
                if item.source_tool == "analyze_harmonic_distortion":
                    assert item.validity == "not_applicable"
                if item.source_tool == "estimate_fundamental":
                    assert item.source_tool == "estimate_fundamental"



def _full_scale_clipped_case():
    return generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=1.2,
        clip_level=1.0,
    )


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


def _boundary_harmonic_case():
    return generate_harmonic_sine(
        fundamental_hz=200.0,
        harmonic_ratios={2: 0.04999999},
        sample_rate_hz=48_000,
        duration_s=2.0,
        fundamental_amplitude=0.48,
    )


async def _run_v7_product_path(
    repository: InMemorySignalRepository,
    signal_id: str,
    client: _FakeClient,
    user_request: str,
) -> tuple[AgentRunResult, RecordingPlanner]:
    planner = _Phase4V7RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    assert type(planner) is _Phase4V7RealLLMPlanner
    assert isinstance(planner, RealLLMPlanner)
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
    assert first_system == prompts_mod._S1_PROMPT_V7.system_prompt
    for kwargs in calls:
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["prompt_version"] == _V7_VERSION
        assert kwargs["messages"][0]["content"] == prompts_mod._S1_PROMPT_V7.system_prompt
        assert payload["planner_context"]["signal_meta"]["signal_id"] == signal_id
        assert payload["planner_context"]["user_request"] == user_request
    _assert_no_leakage(calls)
    _assert_same_run_refs(result)
    _assert_runtime_does_not_force_actions(result, recording)
    _assert_no_unrelated_evidence(result)
    return result, recording


def _rule_judgments(result: AgentRunResult) -> dict[str, str]:
    return {
        evaluation.rule_id: evaluation.judgment
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }


def _causal_fault_types(result: AgentRunResult) -> list[str]:
    assert result.diagnosis is not None
    return [claim.fault_type for claim in result.diagnosis.claims]


def _tool_names(result: AgentRunResult) -> tuple[str, ...]:
    return tuple(observation.tool_name for observation in result.observations)


def _dsp_tool_names(result: AgentRunResult) -> tuple[str, ...]:
    return tuple(
        observation.tool_name
        for observation in result.observations
        if observation.tool_name in _S1_DSP_TOOLS
    )


@pytest.fixture(autouse=True)
def _no_deepseek_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


@pytest.mark.asyncio
async def test_t206_invalid_harmonic_is_pure_inconclusive(
    repository: InMemorySignalRepository,
) -> None:
    signal_id, user_request = _v12_store(repository, "case_v12_dev_noise_01")
    client = _v7_client(first_tool="analyze_harmonic_distortion")
    result, recording = await _run_v7_product_path(
        repository, signal_id, client, user_request
    )
    assert result.status == "inconclusive"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.limitations
    assert _tool_names(result)[0] == "analyze_harmonic_distortion"
    assert "estimate_fundamental" not in _tool_names(result)
    assert any(item.validity == "not_applicable" for item in result.evidence)
    assert result.knowledge_retrievals
    assert result.knowledge_retrievals[0].matches
    claims = result.diagnosis.claims
    assert claims
    assert all(claim.fault_type == "inconclusive" for claim in claims)
    assert "no_supported_fault" not in _causal_fault_types(result)
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    for claim in claims:
        assert claim.evidence_refs
        assert claim.knowledge_refs
        assert set(claim.knowledge_refs) <= knowledge_ids
        assert claim.rule_refs
        assert all(
            next(item for item in result.evidence if item.evidence_id == ref).validity
            == "not_applicable"
            for ref in claim.evidence_refs
        )
    kinds = [
        getattr(record.decision, "decision_type", None)
        for record in recording.records
        if record.decision is not None
    ]
    assert kinds.index("evaluate_rules") < kinds.index("retrieve_knowledge")
    assert kinds.index("retrieve_knowledge") < kinds.index("finish")


@pytest.mark.asyncio
async def test_t206_unvoiced_fundamental_is_pure_inconclusive(
    repository: InMemorySignalRepository,
) -> None:
    signal_id, user_request = _v12_store(repository, "case_v12_dev_noise_01")
    client = _v7_client(
        first_tool="estimate_fundamental",
        knowledge_query="unvoiced fundamental invalid pitch",
    )
    result, recording = await _run_v7_product_path(
        repository, signal_id, client, user_request
    )
    assert result.status == "inconclusive"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "inconclusive"
    assert result.diagnosis.limitations
    assert _tool_names(result)[0] == "estimate_fundamental"
    assert "analyze_harmonic_distortion" not in _tool_names(result)
    assert any(
        item.source_tool == "estimate_fundamental"
        and item.metric == "voiced"
        and item.value is False
        for item in result.evidence
    )
    assert result.knowledge_retrievals
    assert result.knowledge_retrievals[0].matches
    claims = result.diagnosis.claims
    assert claims
    assert all(claim.fault_type == "inconclusive" for claim in claims)
    assert "no_supported_fault" not in _causal_fault_types(result)
    knowledge_ids = {item.retrieval_id for item in result.knowledge_retrievals}
    for claim in claims:
        assert claim.evidence_refs
        assert claim.knowledge_refs
        assert set(claim.knowledge_refs) <= knowledge_ids
        assert claim.rule_refs
        assert all(
            next(item for item in result.evidence if item.evidence_id == ref).source_tool
            == "estimate_fundamental"
            for ref in claim.evidence_refs
        )
    kinds = [
        getattr(record.decision, "decision_type", None)
        for record in recording.records
        if record.decision is not None
    ]
    assert kinds.index("evaluate_rules") < kinds.index("retrieve_knowledge")
    assert kinds.index("retrieve_knowledge") < kinds.index("finish")


@pytest.mark.asyncio
async def test_t206_clipping_only_odd_harmonics_are_not_independent_fault(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _full_scale_clipped_case())
    client = _v7_client(first_tool="detect_clipping", collect_other_family=True)
    result, recording = await _run_v7_product_path(
        repository,
        signal_id,
        client,
        "The peaks look flattened and the amplitude seems to hit a ceiling.",
    )
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert _dsp_tool_names(result)[0] == "detect_clipping"
    assert "analyze_harmonic_distortion" in _dsp_tool_names(result)
    assert "estimate_fundamental" not in _tool_names(result)
    faults = set(_causal_fault_types(result))
    assert faults == {"clipping"}
    assert "harmonic_distortion" not in faults
    assert "no_supported_fault" not in faults
    odd_metrics = [
        item.metric
        for item in result.evidence
        if item.metric.startswith("harmonic_order_")
        and int(item.metric.split("_")[2]) % 2 == 1
    ]
    assert odd_metrics
    assert not any(
        item.metric == "harmonic_order_2_relative_amplitude" for item in result.evidence
    )
    clip_claim = next(
        claim for claim in result.diagnosis.claims if claim.fault_type == "clipping"
    )
    explanation = (
        clip_claim.statement + " " + " ".join(result.diagnosis.limitations)
    ).lower()
    assert "odd" in explanation
    assert clip_claim.evidence_refs
    assert clip_claim.rule_refs
    finish_records = [
        record
        for record in recording.records
        if record.decision is not None
        and getattr(record.decision, "decision_type", None) == "finish"
    ]
    assert finish_records
    finish_tools = {
        observation.tool_name
        for observation in finish_records[0].context.observations
        if observation.tool_name in _S1_DSP_TOOLS
    }
    assert finish_tools == _S1_DSP_TOOLS


@pytest.mark.asyncio
async def test_t206_combined_even_order_has_separate_same_run_claims(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _full_scale_combined_case())
    client = _v7_client(first_tool="detect_clipping", collect_other_family=True)
    result, recording = await _run_v7_product_path(
        repository,
        signal_id,
        client,
        "Please inspect this recording for any plausible S1 distortion causes.",
    )
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    dsp_tools = _dsp_tool_names(result)
    assert dsp_tools[0] == "detect_clipping"
    assert "analyze_harmonic_distortion" in dsp_tools
    finish_records = [
        record
        for record in recording.records
        if record.decision is not None
        and getattr(record.decision, "decision_type", None) == "finish"
    ]
    assert finish_records
    finish_tools = {
        observation.tool_name
        for observation in finish_records[0].context.observations
        if observation.tool_name in _S1_DSP_TOOLS
    }
    assert finish_tools == _S1_DSP_TOOLS
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


@pytest.mark.asyncio
async def test_t206_boundary_harmonic_pass_still_supports_harmonic(
    repository: InMemorySignalRepository,
) -> None:
    signal_id = store_synthetic_case(repository, _boundary_harmonic_case())
    user_request = "I hear extra tonal overtones sitting on the original tone."
    client = _v7_client(first_tool="analyze_harmonic_distortion")
    result, _recording = await _run_v7_product_path(
        repository, signal_id, client, user_request
    )
    assert result.status == "success"
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == "supported_fault"
    assert _tool_names(result)[0] == "analyze_harmonic_distortion"
    assert "harmonic_distortion" in _causal_fault_types(result)
    assert "no_supported_fault" not in _causal_fault_types(result)
    judgments = _rule_judgments(result)
    assert judgments["rule_thd_acceptable"] == "pass"
    thd_values = [
        float(item.value)
        for item in result.evidence
        if item.metric == "thd_percent" and item.validity == "valid"
    ]
    assert thd_values
    assert 4.999 <= thd_values[0] <= 5.001
    harm_claims = [
        claim
        for claim in result.diagnosis.claims
        if claim.fault_type == "harmonic_distortion"
    ]
    assert harm_claims
    statement = harm_claims[0].statement.lower()
    assert "pass" in statement
    assert "configured" in statement
    assert harm_claims[0].rule_refs
    assert harm_claims[0].evidence_refs
