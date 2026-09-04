"""T-CX076–T-CX085: freeze and wire v0.3-s1-planner-9.5."""

from __future__ import annotations

import hashlib
import re

from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_4, _S1_PROMPT_V9_5
from signal_diag.app.composition import build_product_service

_FROZEN_V94_SHA256 = (
    "a29c9cda17bd4bf1d922880610609e32f0670b3eecb984a1e3afa16671e806af"
)
_FROZEN_V95_SHA256 = (
    "a4f4d260adb45a2af088961c77586b08d8279cd1bc4f3780474c3b0a6bd7cb02"
)

_NUMERIC_THRESHOLD_PATTERN = re.compile(
    r"\b(\d+\.?\d*)\s*%\s*(THD|thd)|h2\s*/\s*h3|1\.0\s*%|5\.0\s*%",
    re.IGNORECASE,
)


def test_t_cx076_prompt_version_is_v9_5() -> None:
    assert PROMPT_VERSION == "v0.3-s1-planner-9.5"
    assert _S1_PROMPT_V9_5.version == "v0.3-s1-planner-9.5"
    assert RealLLMPlanner._prompt_spec.version == "v0.3-s1-planner-9.5"


def test_t_cx077_v9_5_sha_is_frozen() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_5.system_prompt.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V95_SHA256


def test_t_cx078_v9_4_sha_remains_frozen() -> None:
    digest = hashlib.sha256(_S1_PROMPT_V9_4.system_prompt.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V94_SHA256
    assert _S1_PROMPT_V9_4.version == "v0.3-s1-planner-9.4"


def test_t_cx079_mode_semantics_present() -> None:
    text = _S1_PROMPT_V9_5.system_prompt
    assert "paired_reference" in text
    assert "analyze_contextual_distortion" in text
    assert "harmonic-growth" in text or "harmonic growth" in text
    assert "nominal_single_tone" in text
    assert "single_signal" in text
    assert "do not silently downgrade mode" in text.lower()


def test_t_cx080_clipping_independence_preserved() -> None:
    text = _S1_PROMPT_V9_5.system_prompt.lower()
    assert "clipping_mechanism" in text
    assert "substantial clipping" in text
    assert "independent" in text


def test_t_cx081_no_numeric_thresholds_in_prompt_prose() -> None:
    assert _NUMERIC_THRESHOLD_PATTERN.search(_S1_PROMPT_V9_5.system_prompt) is None


def test_t_cx082_no_hidden_injection_provenance() -> None:
    text = _S1_PROMPT_V9_5.system_prompt.lower()
    assert "injection_mechanism" not in text
    assert "true injection provenance" not in text


def test_t_cx083_product_composition_wires_v9_5_and_contextual_policy() -> None:
    service = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    identity = service._dependencies.planner_identity
    assert identity.prompt_version == "v0.3-s1-planner-9.5"
    assert identity.phase4_certified_default is False
    assert service._dependencies.causal_policy_version == "v9_5_contextual"
    planner = service._dependencies.planner_factory()
    assert isinstance(planner, RealLLMPlanner)
    assert planner.prompt_version == "v0.3-s1-planner-9.5"


def test_t_cx084_composition_source_has_no_scripted_fallback() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "signal_diag"
        / "app"
        / "composition.py"
    ).read_text(encoding="utf-8")
    assert "ScriptedPlanner" not in source


def test_t_cx085_v9_5_differs_from_v9_4_bytes() -> None:
    assert _S1_PROMPT_V9_5.system_prompt != _S1_PROMPT_V9_4.system_prompt
    assert _FROZEN_V95_SHA256 != _FROZEN_V94_SHA256
