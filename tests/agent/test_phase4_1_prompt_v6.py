"""Phase 4.1 coherent planner v6 identity and semantic tests (T196–T197)."""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from typing import Any

import pytest

from signal_diag.agent import planner as planner_mod
from signal_diag.agent import prompts as prompts_mod
from signal_diag.agent.models import PlannerContext
from signal_diag.agent.planner import (
    _SYSTEM_PROMPT,
    PROMPT_VERSION,
    RealLLMPlanner,
    _Phase4V4RealLLMPlanner,
)
from signal_diag.agent.prompts import _S1_PROMPT_V4, _S1_PROMPT_V5
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
_V6_VERSION = "v0.2-s1-planner-6"
_FROZEN_V6_SHA256 = (
    "9be518167ec58f3806ae569e48929c37d1e526ac4ae0463a448dd622ec0f1ef1"
)
_FROZEN_V6_BYTES = 7833

_FORBIDDEN_EVALUATION_FIELDS = {
    "causal_faults",
    "knowledge_policy",
    "sufficient_evidence_sets",
    "observable_conditions",
    "acceptable_outcomes",
    "held_out",
}
_GENERATOR_INPUT_TOKENS = (
    "harmonic_ratios",
    "clip_level",
    "fundamental_amplitude",
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
        run_id="run_phase4_1_prompt_v6",
        user_request="Why distorted?",
        signal_meta=SignalMeta(
            signal_id="sig_phase4_1_v6",
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


def test_t196_v4_and_v5_prompt_bytes_and_hashes_remain_frozen() -> None:
    v4_digest, v4_size = _utf8_sha256(_S1_PROMPT_V4.system_prompt)
    v5_digest, v5_size = _utf8_sha256(_S1_PROMPT_V5.system_prompt)
    assert _S1_PROMPT_V4.version == _FROZEN_V4_VERSION
    assert _S1_PROMPT_V5.version == _FROZEN_V5_VERSION
    assert v4_size == _FROZEN_V4_BYTES
    assert v5_size == _FROZEN_V5_BYTES
    assert v4_digest == _FROZEN_V4_SHA256
    assert v5_digest == _FROZEN_V5_SHA256
    assert _S1_PROMPT_V5.system_prompt.startswith(_S1_PROMPT_V4.system_prompt)
    assert _S1_PROMPT_V5.system_prompt != _S1_PROMPT_V4.system_prompt


def test_t196_v6_prompt_identity_is_coherent_and_not_an_appendix() -> None:
    assert hasattr(prompts_mod, "_S1_PROMPT_V6")
    v6_spec = prompts_mod._S1_PROMPT_V6
    assert v6_spec.version == _V6_VERSION
    v6_text = v6_spec.system_prompt
    v4_text = _S1_PROMPT_V4.system_prompt
    v5_text = _S1_PROMPT_V5.system_prompt
    assert v6_text != v4_text
    assert v6_text != v5_text
    assert not v6_text.startswith(v4_text)
    assert not v6_text.startswith(v5_text)
    digest, size = _utf8_sha256(v6_text)
    assert size == _FROZEN_V6_BYTES
    assert digest == _FROZEN_V6_SHA256
    assert digest == hashlib.sha256(v6_text.encode("utf-8")).hexdigest()
    assert digest not in {_FROZEN_V4_SHA256, _FROZEN_V5_SHA256}


def test_t196_public_planner_selects_v6_and_legacy_planners_keep_identities() -> None:
    assert RealLLMPlanner._prompt_spec.version == _V6_VERSION
    assert PROMPT_VERSION == _V6_VERSION
    assert hasattr(prompts_mod, "_S1_PROMPT_V6")
    assert _SYSTEM_PROMPT == prompts_mod._S1_PROMPT_V6.system_prompt
    assert RealLLMPlanner._prompt_spec is prompts_mod._S1_PROMPT_V6
    assert _Phase4V4RealLLMPlanner._prompt_spec is _S1_PROMPT_V4
    assert hasattr(planner_mod, "_Phase4V5RealLLMPlanner")
    v5_planner_cls = planner_mod._Phase4V5RealLLMPlanner
    assert issubclass(v5_planner_cls, RealLLMPlanner)
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
async def test_t196_public_planner_user_message_identifies_v6_only() -> None:
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
    assert hasattr(prompts_mod, "_S1_PROMPT_V6")
    assert messages[0]["content"] == prompts_mod._S1_PROMPT_V6.system_prompt
    payload = json.loads(messages[1]["content"])
    assert payload["prompt_version"] == _V6_VERSION
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
async def test_t196_private_v4_and_v5_planners_send_historical_identities() -> None:
    v4_client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    v4_planner = _Phase4V4RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=v4_client,
    )
    await v4_planner.decide(_planner_context())
    assert v4_client.chat.completions.last_kwargs is not None
    v4_messages = v4_client.chat.completions.last_kwargs["messages"]
    assert v4_messages[0]["content"] == _S1_PROMPT_V4.system_prompt
    assert json.loads(v4_messages[1]["content"])["prompt_version"] == _FROZEN_V4_VERSION

    assert hasattr(planner_mod, "_Phase4V5RealLLMPlanner")
    v5_client = _FakeClient(json.dumps(_valid_call_tool_payload()))
    v5_planner = planner_mod._Phase4V5RealLLMPlanner(
        provider="deepseek",
        api_key="test-key",
        model="deepseek-v4-flash",
        client=v5_client,
    )
    await v5_planner.decide(_planner_context())
    assert v5_client.chat.completions.last_kwargs is not None
    v5_messages = v5_client.chat.completions.last_kwargs["messages"]
    assert v5_messages[0]["content"] == _S1_PROMPT_V5.system_prompt
    assert json.loads(v5_messages[1]["content"])["prompt_version"] == _FROZEN_V5_VERSION
    assert v5_messages[0]["content"] != v4_messages[0]["content"]


def _v6_prompt_text() -> str:
    assert hasattr(prompts_mod, "_S1_PROMPT_V6")
    return prompts_mod._S1_PROMPT_V6.system_prompt


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


def _finish_examples(text: str) -> list[dict[str, Any]]:
    return [
        obj
        for obj in _extract_json_objects(text)
        if obj.get("decision_type") == "finish"
    ]


def _claims_of(example: dict[str, Any]) -> list[dict[str, Any]]:
    claims = example.get("claims")
    if not isinstance(claims, list):
        return []
    return [claim for claim in claims if isinstance(claim, dict)]


def test_t197_v6_policy_keeps_hypotheses_open_without_fixed_pipeline() -> None:
    lowered = _v6_prompt_text().lower()
    required = (
        "keep every still-viable clipping or harmonic hypothesis open",
        "supported, ruled out, or explicitly unobservable",
        "does not eliminate another viable family",
        "no required universal tool order",
        "not a fixed clipping",
        "fft",
        "f0",
        "thd",
        "runtime does not force",
        "illustrative placeholders",
    )
    for meaning in required:
        assert meaning in lowered
    forbidden = (
        "prefer stopping once supported evidence is sufficient",
        "detect_clipping then analyze_harmonic_distortion",
        "clipping → fft → f0 → thd",
        "clipping -> fft -> f0 -> thd",
    )
    for phrase in forbidden:
        assert phrase not in lowered


def test_t197_v6_policy_separates_observed_distortion_from_rule_acceptance() -> None:
    lowered = _v6_prompt_text().lower()
    required = (
        "observed causal distortion and configured rule acceptance are independent",
        "rule pass never erases",
        "no_supported_fault is a final empty-cause-set conclusion",
        "not emitted as an additional cause beside a supported fault",
        "clean negative evidence is supporting context",
        "not an extra no-fault diagnosis",
    )
    for meaning in required:
        assert meaning in lowered
    assert "exceeds the supported threshold" not in lowered


def test_t197_v6_policy_requires_traceable_inconclusive_claims() -> None:
    lowered = _v6_prompt_text().lower()
    required = (
        "inconclusive diagnosis contains a traceable claim",
        "same-run evidence",
        "not_applicable",
        "non-empty limitation",
        "same-run knowledge",
    )
    for meaning in required:
        assert meaning in lowered
    assert "claims may be empty" not in lowered


def test_t197_v6_examples_are_mutually_consistent_with_policy() -> None:
    prompt = _v6_prompt_text()
    finishes = _finish_examples(prompt)
    assert finishes, "v6 must include finish examples"

    clipping_supported = False
    harmonic_boundary = False
    combined = False
    inconclusive = False
    clean_no_fault = False

    for example in finishes:
        claims = _claims_of(example)
        assert claims, "v6 must not copy the empty-claims inconclusive example"
        fault_types = [str(claim.get("fault_type")) for claim in claims]
        outcome = example.get("outcome")

        if outcome == "supported_fault" and fault_types == ["clipping"]:
            claim = claims[0]
            assert claim.get("evidence_refs")
            assert claim.get("rule_refs")
            clipping_supported = True

        if (
            outcome == "supported_fault"
            and fault_types == ["harmonic_distortion"]
        ):
            statement = str(claims[0].get("statement", "")).lower()
            assert "pass" in statement
            assert "exceeds the supported threshold" not in statement
            assert claims[0].get("evidence_refs")
            assert claims[0].get("rule_refs")
            harmonic_boundary = True

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
            combined = True

        if outcome == "inconclusive":
            assert "limitations" in example
            assert example["limitations"]
            claim = claims[0]
            assert claim.get("fault_type") == "inconclusive"
            assert claim.get("evidence_refs")
            assert claim.get("rule_refs")
            assert claim.get("knowledge_refs")
            assert "not_applicable" in prompt.lower()
            inconclusive = True

        if outcome == "no_supported_fault":
            assert fault_types == ["no_supported_fault"]
            statement = str(claims[0].get("statement", "")).lower()
            assert "clipping" in statement
            assert "harmonic" in statement
            assert claims[0].get("evidence_refs")
            clean_no_fault = True

        if outcome == "supported_fault":
            assert "no_supported_fault" not in fault_types

    assert clipping_supported
    assert harmonic_boundary
    assert combined
    assert inconclusive
    assert clean_no_fault

    decision_types = {
        obj.get("decision_type") for obj in _extract_json_objects(prompt)
    }
    assert decision_types >= {
        "call_tool",
        "evaluate_rules",
        "retrieve_knowledge",
        "finish",
    }

    lowered = prompt.lower()
    assert (
        "never send or request raw waveform samples, full fft arrays, "
        "generator truth, expected faults, case policy, or scoring targets"
        in lowered
    )
    for token in _FORBIDDEN_EVALUATION_FIELDS:
        assert token not in lowered
