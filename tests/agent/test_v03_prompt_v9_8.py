"""T-CX189–T-CX190: freeze and wire v0.3-s1-planner-9.8."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_7, _S1_PROMPT_V9_8
from signal_diag.app.composition import build_product_service

_FROZEN_V97_SHA256 = (
    "fc50d82fc7b5701388f5d35c7f50a157ed1c88f050e6057cd8f11caf280b982a"
)
_FROZEN_V98_SHA256 = (
    "6d7e18dae4bc1b7e19e3430a9266e7d2c10496df194d3571390df025c6f7bf41"
)

_NUMERIC_THRESHOLD_PATTERN = re.compile(
    r"\b(\d+\.?\d*)\s*%\s*(THD|thd)|h2\s*/\s*h3|1\.0\s*%|5\.0\s*%",
    re.IGNORECASE,
)


def test_t_cx189_v98_prompt_freezes_recovery_and_preserves_v97() -> None:
    frozen_v97 = hashlib.sha256(_S1_PROMPT_V9_7.system_prompt.encode("utf-8")).hexdigest()
    assert frozen_v97 == _FROZEN_V97_SHA256
    text = _S1_PROMPT_V9_8.system_prompt
    assert _S1_PROMPT_V9_8.version == "v0.3-s1-planner-9.8"
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == _FROZEN_V98_SHA256
    assert "v0.3-s1-planner-9.8" in text
    assert "together" in text.lower()
    assert "test_thd_percent" in text
    assert "even_order_present" in text
    assert "Never fall back to ScriptedPlanner" in text
    assert '"decision_type": "evaluate_rules"' not in text
    assert _NUMERIC_THRESHOLD_PATTERN.search(text) is None


def test_t_cx190_product_wires_v98_identity() -> None:
    assert PROMPT_VERSION == "v0.3-s1-planner-9.8"
    assert RealLLMPlanner._prompt_spec.version == "v0.3-s1-planner-9.8"
    service = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    assert service._dependencies.causal_policy_version == (
        "v9_8_claim_reference_recovery"
    )
    assert isinstance(service._dependencies.planner_factory(), RealLLMPlanner)
    identity = service._dependencies.planner_identity
    assert identity.prompt_version == "v0.3-s1-planner-9.8"
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "signal_diag"
        / "app"
        / "composition.py"
    ).read_text(encoding="utf-8")
    assert "ScriptedPlanner" not in source
