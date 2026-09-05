"""T-CX181–T-CX183: freeze v0.3-s1-planner-9.7 identity."""

from __future__ import annotations

import hashlib
import re

from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_6, _S1_PROMPT_V9_7

_FROZEN_V96_SHA256 = (
    "b9ed17debf9bfd2f086ee0eaa178d83370630a0530ebd02336769e416be1b5eb"
)
_FROZEN_V97_SHA256 = (
    "fc50d82fc7b5701388f5d35c7f50a157ed1c88f050e6057cd8f11caf280b982a"
)

_NUMERIC_THRESHOLD_PATTERN = re.compile(
    r"\b(\d+\.?\d*)\s*%\s*(THD|thd)|h2\s*/\s*h3|1\.0\s*%|5\.0\s*%",
    re.IGNORECASE,
)


def test_t_cx181_v97_removes_positive_manual_rule_instructions() -> None:
    text = _S1_PROMPT_V9_7.system_prompt
    assert '"decision_type": "evaluate_rules"' not in text
    assert '"call_tool", "evaluate_rules"' not in text
    assert "Use profile_s1_distortion for configured S1" not in text
    assert "rule batches are created automatically" in text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V97_SHA256
    frozen_v96 = hashlib.sha256(_S1_PROMPT_V9_6.system_prompt.encode("utf-8")).hexdigest()
    assert frozen_v96 == _FROZEN_V96_SHA256


def test_t_cx182_v97_retains_finish_and_safety_semantics() -> None:
    text = _S1_PROMPT_V9_7.system_prompt.lower()
    for phrase in (
        "paired_reference",
        "nominal_single_tone",
        "analyze_contextual_distortion",
        "clipping_mechanism=false",
        "natural",
        "combined",
        "independent",
        "no_supported_fault",
        "scriptedplanner",
    ):
        assert phrase in text
    assert _NUMERIC_THRESHOLD_PATTERN.search(text) is None


def test_t_cx183_v97_prompt_identity_remains_available() -> None:
    assert _S1_PROMPT_V9_7.version == "v0.3-s1-planner-9.7"
    digest = hashlib.sha256(_S1_PROMPT_V9_7.system_prompt.encode("utf-8")).hexdigest()
    assert digest == _FROZEN_V97_SHA256
    # Active product wiring advanced to v9.8 (T-CX190); v9.7 remains frozen.
