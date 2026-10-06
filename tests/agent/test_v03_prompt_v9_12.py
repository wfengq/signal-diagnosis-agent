"""T-CX391: v9.12 prefixes the current v9.11 text and is not the product default."""

from __future__ import annotations

import hashlib

from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_11, _S1_PROMPT_V9_12

_V9_11_SHA256 = "b4c279dfcbee2d5c22f7eb6d5b4f211555da95bbeb2e2867b68a3f1d11681ca0"
_V9_12_SHA256 = "a90ffd1846a478f9117e61c374645eac1739ee57c5f033515fe5977269e83d1c"


def test_t_cx391_v912_prefixes_current_v911_and_registers_hash() -> None:
    assert hashlib.sha256(_S1_PROMPT_V9_11.system_prompt.encode()).hexdigest() == _V9_11_SHA256
    assert _S1_PROMPT_V9_12.system_prompt.startswith(_S1_PROMPT_V9_11.system_prompt)
    assert _S1_PROMPT_V9_12.version == "v0.3-s1-planner-9.12"
    assert _S1_PROMPT_V9_12.system_prompt != _S1_PROMPT_V9_11.system_prompt
    extra = _S1_PROMPT_V9_12.system_prompt.removeprefix(_S1_PROMPT_V9_11.system_prompt)
    assert "time_range" in extra
    assert "channel" in extra
    assert "segment" in extra.lower()
    assert "whole file" in extra.lower()
    digest = hashlib.sha256(_S1_PROMPT_V9_12.system_prompt.encode()).hexdigest()
    assert digest == _V9_12_SHA256


def test_t_cx391_product_default_stays_v911() -> None:
    assert PROMPT_VERSION == "v0.3-s1-planner-9.11"
    assert RealLLMPlanner._prompt_spec is _S1_PROMPT_V9_11
    assert RealLLMPlanner._prompt_spec is not _S1_PROMPT_V9_12
