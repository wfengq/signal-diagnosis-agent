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
    assert d038["product_tree_sha256"] == (
        "7dec1d095144ea44468c1d531c7ef0af52b363f684b446291a654404a3be120f"
    )
    assert d038["prompt_sha256"] == oq014["prompt_sha256"]
    assert d038["model_calls"] == 0
    d038_dev2 = next(
        row
        for row in rows
        if row["amendment_id"] == "d038_planner_ablation_protocol_revision_dev_2"
    )
    assert d038_dev2["amendment_kind"] == "append_only_code_identity"
    assert d038_dev2["prior_bridge_current_implementation_sha256"] == (
        d038["current_implementation_sha256"]
    )
    assert d038_dev2["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d038_dev2["product_tree_sha256"] == (
        "18221d0936e667e44c38275bdb0e36e54bf74e4b6c58d6dfc82b607299925de6"
    )
    assert d038_dev2["prompt_sha256"] == oq014["prompt_sha256"]
    assert d038_dev2["model_calls"] == 0
    d038_snapshot = next(
        row
        for row in rows
        if row["amendment_id"]
        == "d038_planner_ablation_dev_2_snapshot_failure_classification"
    )
    assert d038_snapshot["amendment_kind"] == "append_only_code_identity"
    assert d038_snapshot["prior_bridge_current_implementation_sha256"] == (
        d038_dev2["current_implementation_sha256"]
    )
    assert d038_snapshot["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert d038_snapshot["product_tree_sha256"] == (
        "7b9299d22c1a0103f81731624cec9ccc0be05eac6370f5c24ae68f23b19d34b3"
    )
    assert d038_snapshot["prompt_sha256"] == oq014["prompt_sha256"]
    assert d038_snapshot["model_calls"] == 0
    d038_telemetry = next(
        row
        for row in rows
        if row["amendment_id"]
        == "d038_planner_ablation_dev_2_token_transport_telemetry"
    )
    assert d038_telemetry["amendment_kind"] == "append_only_code_identity"
    assert d038_telemetry["prior_bridge_current_implementation_sha256"] == (
        d038_snapshot["current_implementation_sha256"]
    )
    assert d038_telemetry["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d038_telemetry["product_tree_sha256"] == (
        "864d3d8d668bb424fb950529dc94387423abdcca58f38316b1512a1827ca4b1b"
    )
    assert d038_telemetry["prompt_sha256"] == oq014["prompt_sha256"]
    assert d038_telemetry["model_calls"] == 0
    d039 = next(
        row
        for row in rows
        if row["amendment_id"] == "d039_single_file_observed_facts"
    )
    assert d039["amendment_kind"] == "append_only_code_identity"
    assert d039["prior_bridge_current_implementation_sha256"] == (
        d038_telemetry["current_implementation_sha256"]
    )
    assert d039["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d039["product_tree_sha256"] == (
        "4b7a5916e45c7eb72505be0a8c8d4aa7f95216fe8a6c87c22e7bd2253318429c"
    )
    assert d039["prompt_sha256"] == oq014["prompt_sha256"]
    assert d039["model_calls"] == 0
    d040 = next(
        row
        for row in rows
        if row["amendment_id"] == "d040_preseal_sdk_capability_rebind"
    )
    assert d040["amendment_kind"] == "append_only_code_identity"
    assert d040["prior_bridge_current_implementation_sha256"] == (
        d039["current_implementation_sha256"]
    )
    assert d040["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d040["product_tree_sha256"] == (
        "8d35581d9a5217e66ce9734687a533ef72df9a0e597f340ffd4bd57cce8058d0"
    )
    assert d040["prompt_sha256"] == oq014["prompt_sha256"]
    assert d040["model_calls"] == 0
    d039_surfaces = next(
        row
        for row in rows
        if row["amendment_id"] == "d039_observed_facts_web_cli_surfaces"
    )
    assert d039_surfaces["amendment_kind"] == "append_only_code_identity"
    assert d039_surfaces["prior_bridge_current_implementation_sha256"] == (
        d040["current_implementation_sha256"]
    )
    assert d039_surfaces["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d039_surfaces["product_tree_sha256"] == (
        "2ed1ff7ff5868679ad703aa2dda66e182342e083f87ad524c263b1ba87779e00"
    )
    assert d039_surfaces["prompt_sha256"] == oq014["prompt_sha256"]
    assert d039_surfaces["model_calls"] == 0
    d042 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_a"
    )
    assert d042["amendment_kind"] == "append_only_code_identity"
    assert d042["prior_bridge_current_implementation_sha256"] == (
        d039_surfaces["current_implementation_sha256"]
    )
    assert d042["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042["product_tree_sha256"] == (
        "d2ca91ba9971bd4424bd4b0dcdcc21682b6745badf56fcb3b8e54cc29fff816e"
    )
    assert d042["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042["model_calls"] == 0
    d042_phase_b = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_b"
    )
    assert d042_phase_b["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_b["prior_bridge_current_implementation_sha256"] == (
        d042["current_implementation_sha256"]
    )
    assert d042_phase_b["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_b["product_tree_sha256"] == (
        "cda690d560fa71da49ae2021fd0e666d84f026352f050deb066b38c23ac58c64"
    )
    assert d042_phase_b["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_b["model_calls"] == 0
    d042_phase_b_revise = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_b_revise"
    )
    assert d042_phase_b_revise["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_b_revise["prior_bridge_current_implementation_sha256"] == (
        d042_phase_b["current_implementation_sha256"]
    )
    assert d042_phase_b_revise["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_b_revise["product_tree_sha256"] == (
        "ed11899bc5114e9b78bb85f115fabda0706ecb2a99c514a9f6ff7a836bc50703"
    )
    assert d042_phase_b_revise["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_b_revise["model_calls"] == 0
    d042_phase_b_revise2 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_b_revise2"
    )
    assert d042_phase_b_revise2["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_b_revise2["prior_bridge_current_implementation_sha256"] == (
        d042_phase_b_revise["current_implementation_sha256"]
    )
    assert d042_phase_b_revise2["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_b_revise2["product_tree_sha256"] == (
        "ae86adfbb5039b0cfbe8b7e15a2650fbc6a478be315e0e1ce52c35e74c77661e"
    )
    assert d042_phase_b_revise2["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_b_revise2["model_calls"] == 0
    d042_phase_b_revise3 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_b_revise3"
    )
    assert d042_phase_b_revise3["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_b_revise3["prior_bridge_current_implementation_sha256"] == (
        d042_phase_b_revise2["current_implementation_sha256"]
    )
    assert d042_phase_b_revise3["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_b_revise3["product_tree_sha256"] == (
        "572f039d7e962d9906e03a95eb92a4fba64f135cdc490af2acce71f7c6875735"
    )
    assert d042_phase_b_revise3["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_b_revise3["model_calls"] == 0
    d042_phase_b_revise4 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_b_revise4"
    )
    assert d042_phase_b_revise4["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_b_revise4["prior_bridge_current_implementation_sha256"] == (
        d042_phase_b_revise3["current_implementation_sha256"]
    )
    assert d042_phase_b_revise4["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_b_revise4["product_tree_sha256"] == (
        "5f73c757dee9771d6499cd2413ff5751679250e332ffb31332eaca5c43a7208d"
    )
    assert d042_phase_b_revise4["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_b_revise4["model_calls"] == 0
    d042_phase_c_task7 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_c_task7_offline"
    )
    assert d042_phase_c_task7["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_c_task7["prior_bridge_current_implementation_sha256"] == (
        d042_phase_b_revise4["current_implementation_sha256"]
    )
    assert d042_phase_c_task7["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_c_task7["product_tree_sha256"] == (
        "29df07a0c0560e20bf7961a11d97c8cffa8f0ccfdc51713cef47d3376901ba87"
    )
    assert d042_phase_c_task7["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_c_task7["model_calls"] == 0
    d042_phase_c_task7_revise1 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_c_task7_revise1"
    )
    assert d042_phase_c_task7_revise1["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_c_task7_revise1["prior_bridge_current_implementation_sha256"] == (
        d042_phase_c_task7["current_implementation_sha256"]
    )
    assert d042_phase_c_task7_revise1["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_c_task7_revise1["product_tree_sha256"] == (
        "5f9c03ae4e34b73a33ab06f3510bb9a81a19c5c2763b33487eb922ed76ea58e7"
    )
    assert d042_phase_c_task7_revise1["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_c_task7_revise1["model_calls"] == 0
    d042_phase_c_task7_revise1b = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_c_task7_revise1b"
    )
    assert d042_phase_c_task7_revise1b["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_c_task7_revise1b["prior_bridge_current_implementation_sha256"] == (
        d042_phase_c_task7_revise1["current_implementation_sha256"]
    )
    assert d042_phase_c_task7_revise1b["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_c_task7_revise1b["product_tree_sha256"] == (
        contextual_product_tree_sha256()
    )
    assert d042_phase_c_task7_revise1b["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_c_task7_revise1b["model_calls"] == 0
