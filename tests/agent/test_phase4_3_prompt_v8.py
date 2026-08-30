"""Phase 4.3 coherent planner v8 identity and policy tests (T209, T210)."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from signal_diag.agent import planner as planner_mod
from signal_diag.agent import prompts as prompts_mod
from signal_diag.agent.models import AgentDecision, PlannerContext
from signal_diag.agent.planner import (
    _SYSTEM_PROMPT,
    PROMPT_VERSION,
    RealLLMPlanner,
    _Phase4V4RealLLMPlanner,
    _Phase4V7RealLLMPlanner,
)
from signal_diag.agent.prompts import (
    _S1_PROMPT_V4,
    _S1_PROMPT_V5,
    _S1_PROMPT_V8,
)
from signal_diag.signal.models import SignalMeta
from signal_diag.tools.registry import get_tool_descriptors

_FROZEN_V4_VERSION = "v0.2-s1-planner-4"
_FROZEN_V4_SHA256 = (
    "ec87b20e3b0900ed9df9713a3c84ab0eeb920cd361b7fa494b3f601c43cc39b4"
)
_FROZEN_V4_BYTES = 4519
_FROZEN_V5_VERSION = "v0.2-s1-planner-5"
_FROZEN_V5_SHA256 = (
    "134e80a308977b11f13038d45f9ba938325ed4afeb67f6a6e1c835766144f78b"
)
_FROZEN_V5_BYTES = 5514
_FROZEN_V6_VERSION = "v0.2-s1-planner-6"
_FROZEN_V6_SHA256 = (
    "9be518167ec58f3806ae569e48929c37d1e526ac4ae0463a448dd622ec0f1ef1"
)
_FROZEN_V6_BYTES = 7833
_FROZEN_V7_VERSION = "v0.2-s1-planner-7"
_FROZEN_V7_SHA256 = (
    "008b0fee78a83ada11140b42596d0f0e1abed27e641d5107e53ba759db6bc82a"
)
_FROZEN_V7_BYTES = 9386
_V8_VERSION = "v0.2-s1-planner-8"
_FROZEN_V8_SHA256 = (
    "bf5355ef514574bd2ec4dfda0b3afd2e9810d6031fd1bb9fc13c54fc9fcb8b7e"
)
_FROZEN_V8_BYTES = 12275

_AGENT_DECISION_ADAPTER: TypeAdapter[AgentDecision] = TypeAdapter(AgentDecision)

_FORBIDDEN_EVALUATION_FIELDS = {
    "causal_faults",
    "knowledge_policy",
    "sufficient_evidence_sets",
    "observable_conditions",
    "acceptable_outcomes",
    "acceptable_first_tools",
    "held_out",
}
_FORBIDDEN_IDENTITY_TOKENS = (
    "s1-distortion-synthetic",
    "1.2.0",
    "1.1.0",
    "bench_phase4",
    "bench_official",
    "phase4.2",
    "phase4.3",
    "combined_01",
    "clipping_strong",
    "invalid_noise",
    "sig_eval_",
    "case_v12",
    "case_v11",
)
_GENERATOR_INPUT_TOKENS = (
    "harmonic_ratios",
    "clip_level",
    "fundamental_amplitude",
)
_PLACEHOLDER_ID_RE = re.compile(
    r"^(?:claim_[a-z0-9_]+|ev_[a-z0-9_]+_001|ruleval_[a-z0-9_]+_001|know_001)$"
)
_LIVE_LOOKING_ID_RE = re.compile(
    r"\b(?:ev|ruleval|know)_[0-9a-f]{8,}\b",
    re.IGNORECASE,
)


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


def _planner_context() -> PlannerContext:
    return PlannerContext(
        run_id="run_phase4_3_prompt_v8",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_phase4_3_v8",
            source_type="generated",
            sample_rate_hz=48_000,
            channels=1,
            num_samples=96_000,
            duration_s=2.0,
            original_dtype="float32",
        ),
        task_assessment=None,
        observations=(),
        evidence=(),
        tool_history=(),
        available_tools=get_tool_descriptors(),
        remaining_tool_calls=8,
        remaining_planner_retries=2,
        no_progress_count=0,
    )


def _valid_call_tool_payload() -> dict[str, object]:
    return {
        "decision_type": "call_tool",
        "task_assessment": {
            "task_type": "distortion_analysis",
            "objective": "inspect clipping",
        },
        "call": {
            "tool_name": "detect_clipping",
            "args": {},
        },
        "purpose": "check clipping evidence",
    }


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _FakeCompletions:
    def __init__(self, content: str | None) -> None:
        self._content = content
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_kwargs = kwargs
        return _FakeResponse([_FakeChoice(_FakeMessage(self._content))])


class _FakeChat:
    def __init__(self, content: str | None) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str | None) -> None:
        self.chat = _FakeChat(content)


def _utf8_sha256(text: str) -> tuple[str, int]:
    encoded = text.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def _v8_prompt_text() -> str:
    return _S1_PROMPT_V8.system_prompt


def _extract_json_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            break
        try:
            parsed, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(parsed, dict):
            objects.append(parsed)
        index = end
    return objects


def _decision_examples(text: str) -> list[dict[str, Any]]:
    return [
        obj
        for obj in _extract_json_objects(text)
        if obj.get("decision_type")
        in {"call_tool", "evaluate_rules", "retrieve_knowledge", "finish"}
    ]


def _finish_examples(text: str) -> list[dict[str, Any]]:
    return [
        obj for obj in _decision_examples(text) if obj.get("decision_type") == "finish"
    ]


def _call_tool_examples(text: str) -> list[dict[str, Any]]:
    return [
        obj
        for obj in _decision_examples(text)
        if obj.get("decision_type") == "call_tool"
    ]


def _claims_of(example: dict[str, Any]) -> list[dict[str, Any]]:
    claims = example.get("claims")
    if not isinstance(claims, list):
        return []
    return [claim for claim in claims if isinstance(claim, dict)]


def _walk_strings(value: object) -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {
                "claim_id",
                "evidence_refs",
                "rule_refs",
                "knowledge_refs",
            }:
                found.append((str(key), nested))
            found.extend(_walk_strings(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_strings(item))
    return found


def test_t209_v4_v5_v6_v7_prompt_bytes_and_hashes_remain_frozen() -> None:
    v4_digest, v4_size = _utf8_sha256(_S1_PROMPT_V4.system_prompt)
    v5_digest, v5_size = _utf8_sha256(_S1_PROMPT_V5.system_prompt)
    assert hasattr(prompts_mod, "_S1_PROMPT_V6")
    v6_digest, v6_size = _utf8_sha256(prompts_mod._S1_PROMPT_V6.system_prompt)
    assert hasattr(prompts_mod, "_S1_PROMPT_V7")
    v7_digest, v7_size = _utf8_sha256(prompts_mod._S1_PROMPT_V7.system_prompt)
    assert _S1_PROMPT_V4.version == _FROZEN_V4_VERSION
    assert _S1_PROMPT_V5.version == _FROZEN_V5_VERSION
    assert prompts_mod._S1_PROMPT_V6.version == _FROZEN_V6_VERSION
    assert prompts_mod._S1_PROMPT_V7.version == _FROZEN_V7_VERSION
    assert v4_size == _FROZEN_V4_BYTES
    assert v5_size == _FROZEN_V5_BYTES
    assert v6_size == _FROZEN_V6_BYTES
    assert v7_size == _FROZEN_V7_BYTES
    assert v4_digest == _FROZEN_V4_SHA256
    assert v5_digest == _FROZEN_V5_SHA256
    assert v6_digest == _FROZEN_V6_SHA256
    assert v7_digest == _FROZEN_V7_SHA256
    assert _S1_PROMPT_V5.system_prompt.startswith(_S1_PROMPT_V4.system_prompt)
    assert not prompts_mod._S1_PROMPT_V6.system_prompt.startswith(
        _S1_PROMPT_V4.system_prompt
    )
    assert not prompts_mod._S1_PROMPT_V7.system_prompt.startswith(
        prompts_mod._S1_PROMPT_V6.system_prompt
    )


def test_t209_v8_prompt_identity_is_coherent_and_not_an_appendix() -> None:
    v8_spec = _S1_PROMPT_V8
    assert v8_spec.version == _V8_VERSION
    v8_text = v8_spec.system_prompt
    v4_text = _S1_PROMPT_V4.system_prompt
    v5_text = _S1_PROMPT_V5.system_prompt
    v6_text = prompts_mod._S1_PROMPT_V6.system_prompt
    v7_text = prompts_mod._S1_PROMPT_V7.system_prompt
    assert v8_text != v4_text
    assert v8_text != v5_text
    assert v8_text != v6_text
    assert v8_text != v7_text
    assert not v8_text.startswith(v4_text)
    assert not v8_text.startswith(v5_text)
    assert not v8_text.startswith(v6_text)
    assert not v8_text.startswith(v7_text)
    assert not v8_text.endswith(v7_text)
    assert v7_text.rstrip() not in v8_text
    assert "phase 4.1 observation-driven decision policy" not in v8_text.lower()
    assert "phase 4.2" not in v8_text.lower()
    assert "phase 4.3" not in v8_text.lower()
    digest, size = _utf8_sha256(v8_text)
    assert size == _FROZEN_V8_BYTES
    assert digest == _FROZEN_V8_SHA256
    assert digest == hashlib.sha256(v8_text.encode("utf-8")).hexdigest()
    assert digest not in {
        _FROZEN_V4_SHA256,
        _FROZEN_V5_SHA256,
        _FROZEN_V6_SHA256,
        _FROZEN_V7_SHA256,
    }


def test_t209_public_planner_selects_v8_and_private_v7_keeps_frozen_v7() -> None:
    assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V8
    assert RealLLMPlanner._prompt_spec.version == _V8_VERSION
    assert PROMPT_VERSION == _V8_VERSION
    assert _SYSTEM_PROMPT == _S1_PROMPT_V8.system_prompt
    assert _Phase4V7RealLLMPlanner._prompt_spec is prompts_mod._S1_PROMPT_V7
    assert _Phase4V7RealLLMPlanner._prompt_spec.version == _FROZEN_V7_VERSION
    v7_digest, v7_size = _utf8_sha256(_Phase4V7RealLLMPlanner._prompt_spec.system_prompt)
    assert v7_digest == _FROZEN_V7_SHA256
    assert v7_size == _FROZEN_V7_BYTES
    assert issubclass(_Phase4V7RealLLMPlanner, RealLLMPlanner)
    assert hasattr(planner_mod, "_Phase4V6RealLLMPlanner")
    v6_planner_cls = planner_mod._Phase4V6RealLLMPlanner
    assert v6_planner_cls._prompt_spec is prompts_mod._S1_PROMPT_V6
    assert v6_planner_cls._prompt_spec.version == _FROZEN_V6_VERSION
    assert _Phase4V4RealLLMPlanner._prompt_spec is _S1_PROMPT_V4
    assert hasattr(planner_mod, "_Phase4V5RealLLMPlanner")
    v5_planner_cls = planner_mod._Phase4V5RealLLMPlanner
    assert v5_planner_cls._prompt_spec is _S1_PROMPT_V5
    assert v5_planner_cls._prompt_spec.version == _FROZEN_V5_VERSION
    signature = inspect.signature(RealLLMPlanner.__init__)
    assert list(signature.parameters) == [
        "self",
        "provider",
        "api_key",
        "base_url",
        "model",
        "client",
    ]


@pytest.mark.asyncio
async def test_t209_public_planner_user_message_identifies_v8_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    planner = RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    await planner.decide(_planner_context())
    assert client.chat.completions.last_kwargs is not None
    messages = client.chat.completions.last_kwargs["messages"]
    assert messages[0]["content"] == _S1_PROMPT_V8.system_prompt
    payload = json.loads(messages[1]["content"])
    assert payload["prompt_version"] == _V8_VERSION
    assert set(payload) == {"prompt_version", "planner_context"}
    keys = _json_keys(payload)
    assert "samples" not in keys
    assert "frequencies_hz" not in keys
    for token in _GENERATOR_INPUT_TOKENS:
        assert token not in keys
    lowered_keys = {key.lower() for key in keys}
    for token in _FORBIDDEN_EVALUATION_FIELDS:
        assert token not in lowered_keys
    lowered = messages[1]["content"].lower()
    for token in _FORBIDDEN_EVALUATION_FIELDS:
        assert token not in lowered


@pytest.mark.asyncio
async def test_t209_private_v7_planner_sends_frozen_v7_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    planner = _Phase4V7RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
    )
    await planner.decide(_planner_context())
    assert client.chat.completions.last_kwargs is not None
    messages = client.chat.completions.last_kwargs["messages"]
    assert messages[0]["content"] == prompts_mod._S1_PROMPT_V7.system_prompt
    assert json.loads(messages[1]["content"])["prompt_version"] == _FROZEN_V7_VERSION
    digest, size = _utf8_sha256(messages[0]["content"])
    assert digest == _FROZEN_V7_SHA256
    assert size == _FROZEN_V7_BYTES


def test_t210_v8_policy_requires_viable_hypotheses_and_opaque_signal_id() -> None:
    lowered = _v8_prompt_text().lower()
    required = (
        "keep task_assessment.hypotheses equal to the still-viable requested s1 causes",
        "a positive result for one cause does not close another viable cause",
        "never infer behavior from signal_id; it is an opaque repository key",
        (
            "finish only after every viable hypothesis is supported, ruled out, or "
            "explicitly unobservable with a traceable limitation"
        ),
        "choose the shortest informative tool from visible symptoms and observations",
        "runtime does not force",
        "no required universal tool order",
        "not a fixed clipping",
        "fft",
        "f0",
        "thd",
        "illustrative placeholders",
    )
    for meaning in required:
        assert meaning in lowered
    forbidden = (
        "detect_clipping then analyze_harmonic_distortion",
        "clipping → fft → f0 → thd",
        "clipping -> fft -> f0 -> thd",
    )
    for phrase in forbidden:
        assert phrase not in lowered


def test_t210_v8_policy_allows_direct_harmonic_and_minimal_tools() -> None:
    lowered = _v8_prompt_text().lower()
    required = (
        "analyze_harmonic_distortion does not require spectrum or standalone f0 first",
        "flattened peaks",
        "amplitude ceiling",
        "overtones",
        "harmonic coloration",
        "unstable pitch",
        "non-periodic",
        "once all viable hypotheses close",
        "not another unrelated tool",
        "do not call tools to decorate",
        "do not repeat a rule batch",
    )
    for meaning in required:
        assert meaning in lowered
    assert "spectrum or standalone f0 is not a prerequisite" in lowered or (
        "does not require spectrum or standalone f0 first" in lowered
    )


def test_t210_v8_policy_keeps_dual_truth_and_combined_order2_independence() -> None:
    lowered = _v8_prompt_text().lower()
    required = (
        "observed causal distortion and configured rule acceptance are independent",
        "rule pass never erases",
        "no_supported_fault is a final empty-cause-set conclusion",
        "not emitted as an additional cause beside a supported fault",
        "odd-order pattern expected from symmetric clipping",
        "not by itself an independent harmonic",
        "reportable even-order",
        "order-2",
        "do not generalize the symmetric-synthetic assumption",
        "pure inconclusive",
        "same-run evidence",
        "not_applicable",
        "non-empty limitation",
        "same-run knowledge",
    )
    for meaning in required:
        assert meaning in lowered
    assert "exceeds the supported threshold" not in lowered
    assert "claims may be empty" not in lowered


def test_t210_v8_prompt_rejects_evaluation_identity_and_live_looking_ids() -> None:
    prompt = _v8_prompt_text()
    lowered = prompt.lower()
    for token in _FORBIDDEN_EVALUATION_FIELDS:
        assert token not in lowered
    for token in _FORBIDDEN_IDENTITY_TOKENS:
        assert token not in lowered
    assert _LIVE_LOOKING_ID_RE.search(prompt) is None
    assert re.search(r"\b\d+(\.\d+)?\s*%", prompt) is None
    placeholder_ids: list[str] = []
    for obj in _extract_json_objects(prompt):
        for key, value in _walk_strings(obj):
            if key in {
                "claim_id",
                "evidence_refs",
                "rule_refs",
                "knowledge_refs",
            } or str(key).endswith("_refs"):
                if isinstance(value, str):
                    placeholder_ids.append(value)
                elif isinstance(value, list):
                    placeholder_ids.extend(str(item) for item in value)
            if key == "claim_id":
                placeholder_ids.append(str(value))
    assert placeholder_ids
    for item in placeholder_ids:
        if isinstance(item, str) and item:
            assert _PLACEHOLDER_ID_RE.match(item), item


def test_t210_v8_examples_validate_and_cover_four_representative_paths() -> None:
    prompt = _v8_prompt_text()
    examples = _decision_examples(prompt)
    assert examples, "v8 must include JSON decision examples"
    for example in examples:
        try:
            _AGENT_DECISION_ADAPTER.validate_python(example)
        except ValidationError as error:
            raise AssertionError(f"v8 example failed structural validation: {example}") from error

    call_tools = _call_tool_examples(prompt)
    finishes = _finish_examples(prompt)
    assert call_tools
    assert finishes

    broad_initial = False
    harmonic_first = False
    continue_after_clipping = False
    for example in call_tools:
        assessment = example.get("task_assessment") or {}
        hypotheses = assessment.get("hypotheses")
        objective = str(assessment.get("objective", "")).lower()
        tool_name = str((example.get("call") or {}).get("tool_name", ""))
        purpose = str(example.get("purpose", "")).lower()
        if isinstance(hypotheses, list) and not hypotheses:
            assert "clipping" not in objective or "harmonic" not in objective, (
                "broad initial assessment must not use an empty hypothesis list"
            )
        if (
            isinstance(hypotheses, list)
            and hypotheses == ["clipping", "harmonic_distortion"]
            and tool_name in {"detect_clipping", "analyze_harmonic_distortion"}
        ):
            broad_initial = True
        if tool_name == "analyze_harmonic_distortion" and (
            "first" in purpose or hypotheses == ["harmonic_distortion"]
        ):
            harmonic_first = True
        if tool_name == "analyze_harmonic_distortion" and (
            "clipping is supported" in purpose or "remains viable" in purpose
        ):
            continue_after_clipping = True
        assert tool_name != "analyze_spectrum"
        assert "mandatory" not in purpose
        assert "prerequisite" not in purpose or "not a prerequisite" in purpose

    assert broad_initial
    assert harmonic_first
    assert continue_after_clipping

    clipping_only_finish = False
    harmonic_only = False
    combined = False
    inconclusive = False
    clean_no_fault = False
    for example in finishes:
        claims = _claims_of(example)
        assert claims, "v8 must not copy the empty-claims inconclusive example"
        fault_types = [str(claim.get("fault_type")) for claim in claims]
        outcome = example.get("outcome")
        assessment = example.get("task_assessment") or {}
        remaining = assessment.get("hypotheses") if isinstance(assessment, dict) else None

        if outcome == "supported_fault" and fault_types == ["clipping"]:
            clipping_only_finish = True
            if isinstance(remaining, list):
                assert "harmonic_distortion" not in remaining

        if outcome == "supported_fault" and fault_types == ["harmonic_distortion"]:
            statement = str(claims[0].get("statement", "")).lower()
            assert "pass" in statement or "harmonic" in statement
            assert "exceeds the supported threshold" not in statement
            assert claims[0].get("evidence_refs")
            assert claims[0].get("rule_refs")
            assert not claims[0].get("knowledge_refs")
            harmonic_only = True

        if (
            outcome == "supported_fault"
            and "clipping" in fault_types
            and "harmonic_distortion" in fault_types
        ):
            assert "no_supported_fault" not in fault_types
            clip_claim = next(
                claim for claim in claims if claim.get("fault_type") == "clipping"
            )
            harm_claim = next(
                claim
                for claim in claims
                if claim.get("fault_type") == "harmonic_distortion"
            )
            assert clip_claim.get("evidence_refs")
            assert harm_claim.get("evidence_refs")
            assert set(clip_claim["evidence_refs"]) != set(harm_claim["evidence_refs"])
            harm_statement = str(harm_claim.get("statement", "")).lower()
            assert "even-order" in harm_statement or "order-2" in harm_statement
            combined = True

        if outcome == "inconclusive":
            assert "limitations" in example
            assert example["limitations"]
            assert "no_supported_fault" not in fault_types
            assert fault_types == ["inconclusive"]
            claim = claims[0]
            assert claim.get("evidence_refs")
            assert claim.get("rule_refs")
            assert claim.get("knowledge_refs")
            mixed = " ".join(
                str(ref) for claim in claims for ref in claim.get("evidence_refs", ())
            )
            assert "ev_clip_" not in mixed
            inconclusive = True

        if outcome == "no_supported_fault":
            assert fault_types == ["no_supported_fault"]
            statement = str(claims[0].get("statement", "")).lower()
            assert "clipping" in statement
            assert "harmonic" in statement
            refs = claims[0].get("evidence_refs") or []
            assert len(refs) >= 2
            assert not claims[0].get("knowledge_refs")
            clean_no_fault = True

        if outcome == "supported_fault":
            assert "no_supported_fault" not in fault_types

    assert not clipping_only_finish, (
        "v8 must not finish a broad combined request after clipping only"
    )
    assert harmonic_only
    assert combined
    assert inconclusive
    assert clean_no_fault

    decision_types = {obj.get("decision_type") for obj in examples}
    assert decision_types >= {
        "call_tool",
        "evaluate_rules",
        "retrieve_knowledge",
        "finish",
    }

    lowered = prompt.lower()
    assert (
        "never send or request raw waveform samples, full fft arrays, "
        "generator truth, expected faults, case policy, acceptable tools, "
        "sufficient evidence sets, causal faults, split, or scoring targets"
        in lowered
    )
    assert "clean broad" in lowered
    assert "harmonic-specific" in lowered
    assert "combined broad" in lowered
    assert "invalid/noise" in lowered or "invalid/noise request" in lowered
    assert "do not call spectrum or standalone f0 by default" in lowered
    assert "do not retrieve knowledge" in lowered
    assert "do not add clipping, spectrum, or standalone f0" in lowered
    assert "does not permit early finish" in lowered
    assert "do not detour through clipping or spectrum" in lowered
