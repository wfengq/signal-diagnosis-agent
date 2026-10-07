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
        "27849cc6f09d56d1d929d7dd0b83cd369b2ca6846db61788287bedc391626d2b"
    )
    assert d042_phase_c_task7_revise1b["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_c_task7_revise1b["model_calls"] == 0
    d042_phase_c_task8 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_c_task8_offline"
    )
    assert d042_phase_c_task8["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_c_task8["prior_bridge_current_implementation_sha256"] == (
        d042_phase_c_task7_revise1b["current_implementation_sha256"]
    )
    assert d042_phase_c_task8["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_c_task8["product_tree_sha256"] == (
        "e45c301db1944c425eaae0ab0671ea1bfa100b4b3d6f4ca51c5073e2af1dbcf3"
    )
    assert d042_phase_c_task8["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_c_task8["model_calls"] == 0
    d042_phase_c_task8_revise1 = next(
        row
        for row in rows
        if row["amendment_id"] == "d042_regression_workbench_phase_c_task8_revise1"
    )
    assert d042_phase_c_task8_revise1["amendment_kind"] == "append_only_code_identity"
    assert d042_phase_c_task8_revise1["prior_bridge_current_implementation_sha256"] == (
        d042_phase_c_task8["current_implementation_sha256"]
    )
    assert d042_phase_c_task8_revise1["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d042_phase_c_task8_revise1["product_tree_sha256"] == (
        "e45c301db1944c425eaae0ab0671ea1bfa100b4b3d6f4ca51c5073e2af1dbcf3"
    )
    assert d042_phase_c_task8_revise1["prompt_sha256"] == oq014["prompt_sha256"]
    assert d042_phase_c_task8_revise1["model_calls"] == 0
    d043 = next(
        row
        for row in rows
        if row["amendment_id"] == "d043_regression_full_scale_check_impl"
    )
    assert d043["amendment_kind"] == "append_only_code_identity"
    assert d043["prior_bridge_current_implementation_sha256"] == (
        d042_phase_c_task8_revise1["current_implementation_sha256"]
    )
    assert d043["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d043["product_tree_sha256"] == (
        "380a9585e301db9bf3e09c2969b3cfc7c668601c2f999f23e3c07b3a014fce7e"
    )
    assert d043["prompt_sha256"] == oq014["prompt_sha256"]
    assert d043["model_calls"] == 0
    d043_task9a = next(
        row
        for row in rows
        if row["amendment_id"] == "d043_regression_full_scale_check_task9a"
    )
    assert d043_task9a["amendment_kind"] == "append_only_code_identity"
    assert d043_task9a["prior_bridge_current_implementation_sha256"] == (
        d043["current_implementation_sha256"]
    )
    assert d043_task9a["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d043_task9a["product_tree_sha256"] == (
        "48779c0fbbdd0b621f2944386d05c67a4433990f8382e76368b68d1265f94dad"
    )
    assert d043_task9a["prompt_sha256"] == oq014["prompt_sha256"]
    assert d043_task9a["model_calls"] == 0
    d043_task9 = next(
        row
        for row in rows
        if row["amendment_id"] == "d043_regression_full_scale_check_task9"
    )
    assert d043_task9["amendment_kind"] == "append_only_code_identity"
    assert d043_task9["prior_bridge_current_implementation_sha256"] == (
        d043_task9a["current_implementation_sha256"]
    )
    assert d043_task9["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d043_task9["product_tree_sha256"] == (
        "1bbf7378ebd58e72b70a90f75dfd845aef88138cf7eb346708ac42f11aa2226a"
    )
    assert d043_task9["prompt_sha256"] == oq014["prompt_sha256"]
    assert d043_task9["model_calls"] == 0
    d044_oq021 = next(
        row for row in rows if row["amendment_id"] == "d044_oq021_floor_identity"
    )
    assert d044_oq021["amendment_kind"] == "append_only_code_identity"
    assert d044_oq021["prior_bridge_current_implementation_sha256"] == (
        d043_task9["current_implementation_sha256"]
    )
    assert d044_oq021["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d044_oq021["product_tree_sha256"] == (
        "b5c73b90e45a88cb84dc62b3588467198be3ad84aff86175e3d62c678d9d9944"
    )
    assert d044_oq021["prompt_sha256"] == oq014["prompt_sha256"]
    assert d044_oq021["model_calls"] == 0
    d044_floor = next(
        row
        for row in rows
        if row["amendment_id"] == "d044_full_scale_floor_registration"
    )
    assert d044_floor["amendment_kind"] == "append_only_code_identity"
    assert d044_floor["prior_bridge_current_implementation_sha256"] == (
        d044_oq021["current_implementation_sha256"]
    )
    assert d044_floor["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d044_floor["product_tree_sha256"] == (
        "38f1fa27b8292417cfc5a33521c4876c4dbab17974d305f5a8820c8212e7dee2"
    )
    assert d044_floor["prompt_sha256"] == oq014["prompt_sha256"]
    assert d044_floor["model_calls"] == 0
    d044_ruff = next(
        row
        for row in rows
        if row["amendment_id"] == "d044_floor_yaml_loader_ruff_try004"
    )
    assert d044_ruff["amendment_kind"] == "append_only_code_identity"
    assert d044_ruff["prior_bridge_current_implementation_sha256"] == (
        d044_floor["current_implementation_sha256"]
    )
    assert d044_ruff["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert d044_ruff["product_tree_sha256"] == (
        "38400c7ddbede4e6504a8cb5a8c809cd80ffc5b05265f79cbb487df7f3e1a316"
    )
    assert d044_ruff["prompt_sha256"] == oq014["prompt_sha256"]
    assert d044_ruff["model_calls"] == 0
    d045 = next(
        row for row in rows if row["amendment_id"] == "d045_s1_agent_increment_offline"
    )
    assert d045["amendment_kind"] == "append_only_code_identity"
    assert d045["prior_bridge_current_implementation_sha256"] == (
        d044_ruff["current_implementation_sha256"]
    )
    assert d045["current_implementation_sha256"] == contextual_implementation_sha256()
    assert d045["product_tree_sha256"] == (
        "fe8541422fd5f4728995c8854069bb8c0646a7d26e22401bae70fe2a257a80f0"
    )
    assert d045["prompt_sha256"] == oq014["prompt_sha256"]
    assert d045["prompt_version"] == "v0.3-s1-planner-9.11"
    assert d045["model_calls"] == 0
    merged = next(
        row for row in rows if row["amendment_id"] == "d045_merge_d044_product_tree"
    )
    assert merged["amendment_kind"] == "append_only_code_identity"
    assert merged["prior_bridge_current_implementation_sha256"] == (
        d045["current_implementation_sha256"]
    )
    assert merged["current_implementation_sha256"] == contextual_implementation_sha256()
    assert merged["product_tree_sha256"] == (
        "e3e25904b41ca09e5387db121ba97d79f3492ee123c4d5d041c661ee3ec317ab"
    )
    assert merged["prompt_sha256"] == oq014["prompt_sha256"]
    assert merged["prompt_version"] == "v0.3-s1-planner-9.11"
    assert merged["model_calls"] == 0
    draft_metric = next(
        row for row in rows if row["amendment_id"] == "d045_t1_draft_metric"
    )
    assert draft_metric["amendment_kind"] == "append_only_code_identity"
    assert draft_metric["prior_bridge_current_implementation_sha256"] == (
        merged["current_implementation_sha256"]
    )
    assert draft_metric["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert draft_metric["product_tree_sha256"] == (
        "423dd7f0d5481ca84083647caf93d976a76e7ac18e44d9e9f176620730319231"
    )
    assert draft_metric["prompt_sha256"] == oq014["prompt_sha256"]
    assert draft_metric["prompt_version"] == "v0.3-s1-planner-9.11"
    assert draft_metric["model_calls"] == 0
    intake_fix = next(
        row for row in rows if row["amendment_id"] == "d045_d1_intake_request_settings"
    )
    assert intake_fix["amendment_kind"] == "append_only_code_identity"
    assert intake_fix["prior_bridge_current_implementation_sha256"] == (
        draft_metric["current_implementation_sha256"]
    )
    assert intake_fix["current_implementation_sha256"] == (
        contextual_implementation_sha256()
    )
    assert intake_fix["product_tree_sha256"] == (
        "80b9fefaacef45acc849e00c4d21409a0724b30f17f34b38ec930ac6d86e4bf0"
    )
    assert intake_fix["prompt_sha256"] == oq014["prompt_sha256"]
    assert intake_fix["prompt_version"] == "v0.3-s1-planner-9.11"
    assert intake_fix["model_calls"] == 0
    round3 = next(
        row for row in rows if row["amendment_id"] == "d045_d1_r3_intake_1_1_planner_9_13"
    )
    assert round3["amendment_kind"] == "append_only_code_identity"
    assert round3["prior_bridge_current_implementation_sha256"] == (
        intake_fix["current_implementation_sha256"]
    )
    assert round3["current_implementation_sha256"] == contextual_implementation_sha256()
    assert round3["product_tree_sha256"] == (
        "b0312749eee2b39adf0a5d2dc8d1e7db8380cad7b143521aead72edda12811c0"
    )
    assert round3["prompt_sha256"] == oq014["prompt_sha256"]
    assert round3["prompt_version"] == "v0.3-s1-planner-9.11"
    assert round3["model_calls"] == 0
    round4 = next(row for row in rows if row["amendment_id"] == "d045_d1_r4_planner_9_14")
    assert round4["amendment_kind"] == "append_only_code_identity"
    assert round4["prior_bridge_current_implementation_sha256"] == (
        round3["current_implementation_sha256"]
    )
    assert round4["current_implementation_sha256"] == contextual_implementation_sha256()
    assert round4["product_tree_sha256"] == (
        "d3f4ba5fc993febbdda2fe2297ac2f81a8e41aa314be20386d250e79316db04f"
    )
    assert round4["prompt_sha256"] == oq014["prompt_sha256"]
    assert round4["prompt_version"] == "v0.3-s1-planner-9.11"
    assert round4["model_calls"] == 0
    round5 = next(row for row in rows if row["amendment_id"] == "d045_d1_r5_planner_9_15")
    assert round5["amendment_kind"] == "append_only_code_identity"
    assert round5["prior_bridge_current_implementation_sha256"] == (
        round4["current_implementation_sha256"]
    )
    assert round5["current_implementation_sha256"] == contextual_implementation_sha256()
    assert round5["product_tree_sha256"] == (
        "99719634ec30a2495fc613b8edfa5d65f34b0f4c932430065dab8d311314b1e6"
    )
    assert round5["prompt_sha256"] == oq014["prompt_sha256"]
    assert round5["prompt_version"] == "v0.3-s1-planner-9.11"
    assert round5["model_calls"] == 0
    intake_flow = next(row for row in rows if row["amendment_id"] == "d047_intake_product_flow")
    assert intake_flow["amendment_kind"] == "append_only_code_identity"
    assert intake_flow["prior_bridge_current_implementation_sha256"] == (
        round5["current_implementation_sha256"]
    )
    assert intake_flow["current_implementation_sha256"] == contextual_implementation_sha256()
    assert intake_flow["product_tree_sha256"] == (
        "e6ecf9fb2f9806ecd9d628e6bae0f71fb6e7349be16e5f4ae3153fd7d8da4dde"
    )
    assert intake_flow["prompt_sha256"] == oq014["prompt_sha256"]
    assert intake_flow["prompt_version"] == "v0.3-s1-planner-9.11"
    assert intake_flow["model_calls"] == 0
    dispatch = next(row for row in rows if row["amendment_id"] == "d048_sdk_dispatch_identity")
    assert dispatch["amendment_kind"] == "append_only_code_identity"
    assert dispatch["prior_bridge_current_implementation_sha256"] == (
        intake_flow["current_implementation_sha256"]
    )
    assert dispatch["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert dispatch["product_tree_sha256"] == (
        "3b2939961f2d1dab12a1b24ca8facc950fdacd43f2c09d43f4cf115560f5e16a"
    )
    assert dispatch["prompt_sha256"] == oq014["prompt_sha256"]
    assert dispatch["prompt_version"] == "v0.3-s1-planner-9.11"
    assert dispatch["model_calls"] == 0
    f0_guard = next(row for row in rows if row["amendment_id"] == "d049_f0_subharmonic_guard")
    assert f0_guard["amendment_kind"] == "append_only_code_identity"
    assert f0_guard["prior_bridge_current_implementation_sha256"] == (
        dispatch["current_implementation_sha256"]
    )
    assert f0_guard["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert f0_guard["product_tree_sha256"] == (
        "2d95a585786880f99e212547883e899018df52a395899888f816ee0c5601fd19"
    )
    assert f0_guard["prompt_sha256"] == oq014["prompt_sha256"]
    assert f0_guard["prompt_version"] == "v0.3-s1-planner-9.11"
    assert f0_guard["model_calls"] == 0
    localization = next(row for row in rows if row["amendment_id"] == "d050_fault_localization")
    assert localization["amendment_kind"] == "append_only_code_identity"
    assert localization["prior_bridge_current_implementation_sha256"] == (
        f0_guard["current_implementation_sha256"]
    )
    assert localization["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert localization["product_tree_sha256"] == (
        "7a46fedcaaacf7204fe7a88218b0cc5b098e14a4ab1e2c0abda26b3e1d83c6af"
    )
    assert localization["prompt_sha256"] == oq014["prompt_sha256"]
    assert localization["prompt_version"] == "v0.3-s1-planner-9.11"
    assert localization["model_calls"] == 0
    paired = next(
        row for row in rows if row["amendment_id"] == "d051_paired_reference_localization"
    )
    assert paired["amendment_kind"] == "append_only_code_identity"
    assert paired["prior_bridge_current_implementation_sha256"] == (
        localization["current_implementation_sha256"]
    )
    assert paired["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert paired["product_tree_sha256"] == (
        "ba59f0c17cd72c9e0c3d49a8887c73ad1f33755d60b62bd77b0f12f8fdd9fde9"
    )
    assert paired["prompt_sha256"] == oq014["prompt_sha256"]
    assert paired["prompt_version"] == "v0.3-s1-planner-9.11"
    assert paired["model_calls"] == 0
    withholding = next(
        row for row in rows if row["amendment_id"] == "d051_paired_harmonic_withholding"
    )
    assert withholding["amendment_kind"] == "append_only_code_identity"
    assert withholding["prior_bridge_current_implementation_sha256"] == (
        paired["current_implementation_sha256"]
    )
    assert withholding["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert withholding["product_tree_sha256"] == (
        "46ca2e37483f34cd3daf01679b38d3a3f8587faca4145b25f09b1d9803fb6e27"
    )
    assert withholding["prompt_sha256"] == oq014["prompt_sha256"]
    assert withholding["prompt_version"] == "v0.3-s1-planner-9.11"
    assert withholding["model_calls"] == 0
    engine = next(
        row for row in rows if row["amendment_id"] == "d053_deterministic_engine_default"
    )
    assert engine["amendment_kind"] == "append_only_code_identity"
    assert engine["prior_bridge_current_implementation_sha256"] == (
        withholding["current_implementation_sha256"]
    )
    assert engine["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert engine["product_tree_sha256"] == (
        "f48d52fc37fc0ac01761aec20fe9e44ebba24b2cbbfd6e5e976bca800e06e9e8"
    )
    assert engine["prompt_sha256"] == oq014["prompt_sha256"]
    assert engine["prompt_version"] == "v0.3-s1-planner-9.11"
    assert engine["model_calls"] == 0
    sweep = next(row for row in rows if row["amendment_id"] == "d054_sweep_stimulus_test")
    assert sweep["amendment_kind"] == "append_only_code_identity"
    assert sweep["prior_bridge_current_implementation_sha256"] == (
        engine["current_implementation_sha256"]
    )
    assert sweep["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert sweep["product_tree_sha256"] == (
        "a48f8af30666ef0516f3776fe89ae3521fc097b1911e94f5867098dfc49a8f5c"
    )
    assert sweep["prompt_sha256"] == oq014["prompt_sha256"]
    assert sweep["prompt_version"] == "v0.3-s1-planner-9.11"
    assert sweep["model_calls"] == 0
    analysis = next(row for row in rows if row["amendment_id"] == "d054_sweep_analysis_1_1")
    assert analysis["amendment_kind"] == "append_only_code_identity"
    assert analysis["prior_bridge_current_implementation_sha256"] == (
        sweep["current_implementation_sha256"]
    )
    assert analysis["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert analysis["product_tree_sha256"] == (
        "29b81e34c7c9cc0c3b6e4cecde770176bd1edde959d5ec11e062274d6dd45dcd"
    )
    assert analysis["prompt_sha256"] == oq014["prompt_sha256"]
    assert analysis["prompt_version"] == "v0.3-s1-planner-9.11"
    assert analysis["model_calls"] == 0
    explanation = next(row for row in rows if row["amendment_id"] == "d055_explanation_layer")
    assert explanation["amendment_kind"] == "append_only_code_identity"
    assert explanation["prior_bridge_current_implementation_sha256"] == (
        analysis["current_implementation_sha256"]
    )
    assert explanation["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert explanation["product_tree_sha256"] == (
        "353f7a9adc6a0e53883b3dc87e9b3d96746119d7e6b9b15d0f8372c8f3c914e5"
    )
    assert explanation["prompt_sha256"] == oq014["prompt_sha256"]
    assert explanation["prompt_version"] == "v0.3-s1-planner-9.11"
    assert explanation["model_calls"] == 0
    known = next(row for row in rows if row["amendment_id"] == "d056_known_sweep_analysis")
    assert known["amendment_kind"] == "append_only_code_identity"
    assert known["prior_bridge_current_implementation_sha256"] == (
        explanation["current_implementation_sha256"]
    )
    assert known["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert known["product_tree_sha256"] == (
        "e5f555d774f25c38aed376b329d096b7537a6a1bc329ae7b3dd44d3d5bae9933"
    )
    assert known["prompt_sha256"] == oq014["prompt_sha256"]
    assert known["prompt_version"] == "v0.3-s1-planner-9.11"
    assert known["model_calls"] == 0
    guide = next(row for row in rows if row["amendment_id"] == "d057_test_guide")
    assert guide["amendment_kind"] == "append_only_code_identity"
    assert guide["prior_bridge_current_implementation_sha256"] == (
        known["current_implementation_sha256"]
    )
    assert guide["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert guide["product_tree_sha256"] == (
        "43d06b5e93275ce77220d22b653582ff2e7ec11e497f06652975cd2eaa0f6573"
    )
    assert guide["prompt_sha256"] == oq014["prompt_sha256"]
    assert guide["prompt_version"] == "v0.3-s1-planner-9.11"
    assert guide["model_calls"] == 0
    wording = next(row for row in rows if row["amendment_id"] == "d058_explain_wording_check")
    assert wording["amendment_kind"] == "append_only_code_identity"
    assert wording["prior_bridge_current_implementation_sha256"] == (
        guide["current_implementation_sha256"]
    )
    assert wording["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert wording["product_tree_sha256"] == (
        "8b7a297666111d8147d04ccdbf8f2e24b331e20cb83cb36c3751b39159a49c23"
    )
    assert wording["prompt_sha256"] == oq014["prompt_sha256"]
    assert wording["prompt_version"] == "v0.3-s1-planner-9.11"
    assert wording["model_calls"] == 0
    review = next(row for row in rows if row["amendment_id"] == "d058_review_whitespace")
    assert review["amendment_kind"] == "append_only_code_identity"
    assert review["prior_bridge_current_implementation_sha256"] == (
        wording["current_implementation_sha256"]
    )
    assert review["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert review["product_tree_sha256"] == (
        "49d64aec8227122cb05d9a1e43fa113f94dde155fc0b6b08f258b4422075d138"
    )
    assert review["prompt_sha256"] == oq014["prompt_sha256"]
    assert review["prompt_version"] == "v0.3-s1-planner-9.11"
    assert review["model_calls"] == 0
    guide_11 = next(row for row in rows if row["amendment_id"] == "d059_guide_prompt_1_1")
    assert guide_11["amendment_kind"] == "append_only_code_identity"
    assert guide_11["prior_bridge_current_implementation_sha256"] == (
        review["current_implementation_sha256"]
    )
    assert guide_11["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert guide_11["product_tree_sha256"] == (
        "a27de110719e2ca24f8588980779eb5dd63df05be332a56ac810879b6b844f37"
    )
    assert guide_11["prompt_sha256"] == oq014["prompt_sha256"]
    assert guide_11["prompt_version"] == "v0.3-s1-planner-9.11"
    assert guide_11["model_calls"] == 0
    sessions = next(row for row in rows if row["amendment_id"] == "d060_test_sessions_phase_a")
    assert sessions["amendment_kind"] == "append_only_code_identity"
    assert sessions["prior_bridge_current_implementation_sha256"] == (
        guide_11["current_implementation_sha256"]
    )
    assert sessions["current_implementation_sha256"] == (
        "9939842ca31ce0638d3ad985f418dbce80b6065b63ebbdb6daba9515ca1d67e3"
    )
    assert sessions["product_tree_sha256"] == (
        "335951ed11aeddf1953c4a5ec91703ac8da99bd2a051efa9df6b13e6dd5d1ad7"
    )
    assert sessions["prompt_sha256"] == oq014["prompt_sha256"]
    assert sessions["prompt_version"] == "v0.3-s1-planner-9.11"
    assert sessions["model_calls"] == 0
    qa = next(row for row in rows if row["amendment_id"] == "d060_result_qa_phase_c")
    assert qa["amendment_kind"] == "append_only_code_identity"
    assert qa["prior_bridge_current_implementation_sha256"] == (
        sessions["current_implementation_sha256"]
    )
    assert qa["current_implementation_sha256"] == contextual_implementation_sha256()
    assert qa["product_tree_sha256"] == contextual_product_tree_sha256()
    assert qa["prompt_sha256"] == oq014["prompt_sha256"]
    assert qa["prompt_version"] == "v0.3-s1-planner-9.11"
    assert qa["model_calls"] == 0
