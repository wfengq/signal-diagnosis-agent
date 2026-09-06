"""T-CX239–T-CX240: v9.10 prompt and product identity."""

from __future__ import annotations

import hashlib

from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_9, _S1_PROMPT_V9_10
from signal_diag.app.composition import build_product_service


def test_t_cx239_v910_is_additive_and_preserves_v99_identity() -> None:
    old_sha = hashlib.sha256(_S1_PROMPT_V9_9.system_prompt.encode()).hexdigest()
    assert _S1_PROMPT_V9_9.version == "v0.3-s1-planner-9.9"
    assert _S1_PROMPT_V9_10.version == "v0.3-s1-planner-9.10"
    assert hashlib.sha256(_S1_PROMPT_V9_9.system_prompt.encode()).hexdigest() == old_sha
    text = _S1_PROMPT_V9_10.system_prompt
    assert "one coherent clipping evidence family" in text
    assert "test_clipping_mechanism=true" in text
    assert "remove the unsupported harmonic_distortion sibling" in text
    assert "Never fall back to ScriptedPlanner" in text


def test_t_cx240_v910_profile_remains_available_after_supersession() -> None:
    service = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    assert service._dependencies.rule_profile_loader.load(
        "profile_s1_contextual_comparison_v9_10"
    ).profile_id == "profile_s1_contextual_comparison_v9_10"
