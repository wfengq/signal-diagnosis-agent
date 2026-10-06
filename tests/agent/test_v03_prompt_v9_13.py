"""T-CX406: v9.13 replaces the v9.12 segment guidance; v9.11 and v9.12 stay pinned."""

from __future__ import annotations

import hashlib

from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.prompts_v03 import (
    _S1_PROMPT_V9_11,
    _S1_PROMPT_V9_12,
    _S1_PROMPT_V9_13,
)

_V9_12_SHA256 = "a90ffd1846a478f9117e61c374645eac1739ee57c5f033515fe5977269e83d1c"


def test_t_cx406_v913_prefixes_v911_and_leaves_v912_unchanged() -> None:
    assert _S1_PROMPT_V9_13.version == "v0.3-s1-planner-9.13"
    assert _S1_PROMPT_V9_13.system_prompt.startswith(_S1_PROMPT_V9_11.system_prompt)
    v912 = hashlib.sha256(_S1_PROMPT_V9_12.system_prompt.encode()).hexdigest()
    assert v912 == _V9_12_SHA256
    assert not _S1_PROMPT_V9_13.system_prompt.startswith(_S1_PROMPT_V9_12.system_prompt)


def test_t_cx406_guidance_plans_channel_and_window_calls() -> None:
    extra = _S1_PROMPT_V9_13.system_prompt.removeprefix(_S1_PROMPT_V9_11.system_prompt)
    lowered = extra.lower()
    # D1 rounds 1-2: the planner stopped after two whole-file calls on every T2 case.
    for needle in (
        "signal_meta.duration_s",
        "signal_meta.channels",
        "remaining_tool_calls",
        "left",
        "right",
        "time_range",
        "window",
        "valid=false",
    ):
        assert needle in lowered, needle
    assert "never gives a location" in lowered
    assert "fundamental frequency" in lowered  # must not be invented
    assert "threshold" in lowered


def test_t_cx406_product_default_stays_v911() -> None:
    assert PROMPT_VERSION == "v0.3-s1-planner-9.11"
    assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V9_11
