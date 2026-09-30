"""T-CX250 and T-CX254: v9.11 prompt and product identity."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from signal_diag.agent import prompts_v03
from signal_diag.agent.planner import PROMPT_VERSION, RealLLMPlanner
from signal_diag.agent.prompts_v03 import _S1_PROMPT_V9_10
from signal_diag.app.composition import build_product_service
from signal_diag.evaluation.contextual.calibration import (
    contextual_implementation_sha256,
    contextual_product_tree_sha256,
    resolve_active_freeze_code_sha256,
)


def test_t_cx250_v911_preserves_v910_prompt_and_registers_ids_once() -> None:
    assert _S1_PROMPT_V9_10.version == "v0.3-s1-planner-9.10"
    assert hashlib.sha256(_S1_PROMPT_V9_10.system_prompt.encode()).hexdigest() == (
        "2c9a8777362d35051e3e0642f930e87eeaffe14aea045abefb8139fd182bca3c"
    )
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    ids = re.findall(r"^\| (T-CX\d+) \|", text, flags=re.MULTILINE)
    for number in range(250, 256):
        assert ids.count(f"T-CX{number}") == 1


def test_t_cx254_v911_prompt_explains_mode_aware_complete_recovery() -> None:
    spec = getattr(prompts_v03, "_S1_PROMPT_V9_11", None)
    assert spec is not None
    assert spec.version == "v0.3-s1-planner-9.11"
    text = spec.system_prompt
    assert "single_signal" in text
    assert "flat_top_detected=true" in text
    assert "clipping_mechanism=false" in text
    assert "paired_reference" in text
    assert "nominal_single_tone" in text
    assert "test_clipping_mechanism=false" in text
    assert "every listed deficit together" in text
    assert "Never fall back to ScriptedPlanner" in text
    assert (
        "no_supported_fault checklist: cite same-run clipping_mechanism=false "
        "Evidence."
    ) not in text


def test_t_cx254_product_wires_v911_without_profile_or_threshold_change() -> None:
    spec = getattr(prompts_v03, "_S1_PROMPT_V9_11", None)
    assert spec is not None
    assert PROMPT_VERSION == "v0.3-s1-planner-9.11"
    assert RealLLMPlanner._prompt_spec is spec
    service = build_product_service(environ={"DEEPSEEK_API_KEY": "sk-test"})
    assert service._dependencies.causal_policy_version == (
        "v9_11_mode_aware_no_fault_recovery"
    )
    profile = service._dependencies.rule_profile_loader.load(
        "profile_s1_contextual_comparison_v9_10"
    )
    assert profile.version == "1.0.0"
    by_id = {rule.rule_id: rule for rule in profile.rules}
    assert by_id["rule_test_clipping_ratio_acceptable"].threshold == 0.01


def test_t_cx254_v911_behavior_identity_is_preserved_and_active_bridge_matches() -> None:
    root = Path(__file__).resolve().parents[2]
    path = (
        root
        / "docs/evaluations/v0_3/contextual/development/"
        "study_v0_3_contextual_dev_1/code_identity_amendment.json"
    )
    rows = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        row
        for row in rows
        if row["amendment_id"] == "v9_11_mode_aware_no_fault_recovery"
    ]
    assert len(matches) == 1
    row = matches[0]
    assert row["current_implementation_sha256"] == (
        "1dfc498e30bb5139eef2f8340aad2e2f3ea2aef5ceb51a633e040bf736065d42"
    )
    assert row["product_tree_sha256"] == (
        "626824f6bd2c4c04da566d77914648f2e2d629241d910cb56bcd086bd279c799"
    )
    assert row["prompt_sha256"] == (
        "ecd10554beef79afcf505bf788509f660eb933eaef72ed89693514009fe1134b"
    )
    assert resolve_active_freeze_code_sha256(path.parent) == (
        contextual_implementation_sha256()
    )
    oq014 = next(
        row
        for row in rows
        if row["amendment_id"] == "oq014_option_c_single_signal_flat_top_clipping"
    )
    assert oq014["amendment_kind"] == "append_only_behavior_identity"
    assert oq014["prior_bridge_current_implementation_sha256"] == (
        "799ee09e0a02ba39bf65596399f36de18c9d6b90c8aea7c919817f7cbbd91f72"
    )
    assert oq014["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert oq014["product_tree_sha256"] == (
        "7eef19bbe41a4fa896199d9995261ac5897b6531482607caf2587a3c895240f9"
    )
    assert oq014["prompt_sha256"] == hashlib.sha256(
        prompts_v03._S1_PROMPT_V9_11.system_prompt.encode()
    ).hexdigest()
    d037 = next(
        row
        for row in rows
        if row["amendment_id"] == "d037_single_file_context_guidance"
    )
    assert d037["amendment_kind"] == "append_only_code_identity"
    assert d037["prior_bridge_current_implementation_sha256"] == (
        oq014["current_implementation_sha256"]
    )
    assert d037["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d037["product_tree_sha256"] == (
        "0a575a0cfb8b4eba649dab88ba40625f32b0d51be48437594d852f15dd4287ca"
    )
    assert d037["prompt_sha256"] == oq014["prompt_sha256"]
    assert d037["model_calls"] == 0
    d038 = next(
        row
        for row in rows
        if row["amendment_id"] == "d038_planner_ablation_wave2_harness"
    )
    assert d038["amendment_kind"] == "append_only_code_identity"
    assert d038["prior_bridge_current_implementation_sha256"] == (
        d037["current_implementation_sha256"]
    )
    assert d038["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d038["product_tree_sha256"] == contextual_product_tree_sha256()
    assert d038["prompt_sha256"] == oq014["prompt_sha256"]
    assert d038["model_calls"] == 0
