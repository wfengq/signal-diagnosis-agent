"""T-CX241–T-CX244: v9.10 freeze and historical-seal lifecycle."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from signal_diag.evaluation.contextual.calibration import (
    contextual_implementation_sha256,
    resolve_active_freeze_code_sha256,
)
from signal_diag.evaluation.contextual.campaign import (
    CampaignPreflightError,
    preflight_contextual_validation,
)

REPO = Path(__file__).resolve().parents[3]
DEV = (
    REPO
    / "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1"
)
VAL = (
    REPO
    / "docs/evaluations/v0_3/contextual/validation/"
    "study_v0_3_contextual_validation_1"
)


def test_t_cx241_v910_development_identity_has_recomputed_bridge() -> None:
    rows = json.loads((DEV / "code_identity_amendment.json").read_text("utf-8"))
    current = contextual_implementation_sha256()
    row = next(
        item
        for item in rows
        if item["amendment_id"] == "v9_10_contextual_clipping_recovery"
    )
    assert row["amendment_kind"] == "append_only_behavior_identity"
    assert row["current_implementation_sha256"] != current
    assert row["qualification_recompute_unchanged"] is True
    assert row["calibration_recompute_unchanged_except_code_sha256"] is True
    assert row["selected_threshold_percent_unchanged"] == 5.0
    assert row["model_calls"] == 0
    assert resolve_active_freeze_code_sha256(DEV) == current


def test_t_cx248_observability_amendment_is_preserved_after_supersession() -> None:
    rows = json.loads((DEV / "code_identity_amendment.json").read_text("utf-8"))
    current = contextual_implementation_sha256()
    row = next(
        item
        for item in rows
        if item["amendment_id"] == "v9_10_evaluation_failure_observability"
    )
    assert row["amendment_kind"] == "append_only_evaluation_identity"
    assert row["current_implementation_sha256"] == (
        "83302bfec62893fcd373a2b0a23b239cfccc3ce9f0e347f7d0606555cab22a95"
    )
    assert row["current_implementation_sha256"] != current
    assert row["qualification_recompute_unchanged"] is True
    assert row["calibration_recompute_unchanged"] is True
    assert row["selected_threshold_percent_unchanged"] == 5.0
    assert row["model_calls"] == 0


def test_t_cx249_post_assemble_amendment_matches_current_harness() -> None:
    rows = json.loads((DEV / "code_identity_amendment.json").read_text("utf-8"))
    current = contextual_implementation_sha256()
    row = next(
        item
        for item in rows
        if item["amendment_id"]
        == "v9_10_evaluation_harness_post_assemble_fix"
    )
    assert row["amendment_kind"] == "append_only_evaluation_identity"
    assert row["prior_bridge_current_implementation_sha256"] == (
        "83302bfec62893fcd373a2b0a23b239cfccc3ce9f0e347f7d0606555cab22a95"
    )
    assert row["current_implementation_sha256"] == (
        "1dfc498e30bb5139eef2f8340aad2e2f3ea2aef5ceb51a633e040bf736065d42"
    )
    assert row["current_implementation_sha256"] != current
    assert row["qualification_recompute_unchanged"] is True
    assert row["calibration_recompute_unchanged"] is True
    assert row["selected_threshold_percent_unchanged"] == 5.0
    assert row["amendment_creation_model_calls"] == 0
    reseal = next(
        item
        for item in rows
        if item["amendment_id"] == "v9_11_validation_reseal_campaign_rebind"
    )
    assert reseal["amendment_kind"] == "append_only_evaluation_identity"
    assert reseal["prior_bridge_current_implementation_sha256"] == (
        "1dfc498e30bb5139eef2f8340aad2e2f3ea2aef5ceb51a633e040bf736065d42"
    )
    assert reseal["current_implementation_sha256"] != current
    correction = next(
        item
        for item in rows
            if item["amendment_id"] == "contextual_scoring_reconstruction_boundary_v2"
    )
    assert correction["amendment_kind"] == "append_only_evaluation_identity"
    assert correction["prior_bridge_current_implementation_sha256"] == (
        "3bc9a67461862e77b7544ae8dd52745d8ab94d68a34b65c03c7d2be8705671c1"
    )
    assert correction["current_implementation_sha256"] == (
        "799ee09e0a02ba39bf65596399f36de18c9d6b90c8aea7c919817f7cbbd91f72"
    )
    assert correction["current_implementation_sha256"] != current
    assert correction["model_calls"] == 0
    oq014 = next(
        item
        for item in rows
        if item["amendment_id"] == "oq014_option_c_single_signal_flat_top_clipping"
    )
    assert oq014["amendment_kind"] == "append_only_behavior_identity"
    assert oq014["prior_bridge_current_implementation_sha256"] == (
        correction["current_implementation_sha256"]
    )
    assert oq014["current_implementation_sha256"] == current
    assert oq014["model_calls"] == 0
    assert reseal["qualification_recompute_unchanged"] is True
    assert reseal["calibration_recompute_unchanged"] is True
    assert reseal["selected_threshold_percent_unchanged"] == 5.0
    assert reseal["amendment_creation_model_calls"] == 0
    assert reseal["validation_passed"] is False
    assert resolve_active_freeze_code_sha256(DEV) == current


def test_t_cx242_v99_v3_is_historical_with_truthful_execution_counts() -> None:
    record = json.loads(
        (VAL / "VALIDATION_SEAL_SUPERSESSION.json").read_text("utf-8")
    )
    historical = record["v9_9_executed_seal"]
    assert historical["directory"] == "validation_seal_v3"
    assert historical["status"] == "historical_infrastructure_stopped"
    assert historical["original_terminal_slots"] == 47
    assert historical["original_planned_slots"] == 60
    assert historical["diagnostic_continuation_slots"] == 13
    assert historical["one_shot_validation_complete"] is False
    assert historical["validation_passed"] is False
    active = record["active_seal"]
    assert active["directory"] == "validation_seal_v4"
    assert active["status"] == "active_model_not_run"
    assert active["model_calls"] == 0
    assert active["validation_passed"] is False
    assert record["authorization_boundary"]["real_model_run_authorized"] is False


def test_t_cx243_preflight_rejects_historical_v3_before_credentials() -> None:
    output = VAL / "__t_cx243_must_not_exist__"
    assert not output.exists()
    with pytest.raises(CampaignPreflightError, match="validation_seal_v4"):
        preflight_contextual_validation(
            study_dir=VAL,
            seal_dir=VAL / "validation_seal_v3",
            output=output,
            environ={},
        )
    assert not output.exists()


def test_t_cx244_lifecycle_ids_are_registered_once() -> None:
    text = (REPO / "docs/TEST_PLAN_V0_3_CONTEXTUAL.md").read_text("utf-8")
    ids = re.findall(r"^\| (T-CX\d+) \|", text, flags=re.MULTILINE)
    for number in range(241, 245):
        assert ids.count(f"T-CX{number}") == 1

    for number in range(248, 250):
        assert ids.count(f"T-CX{number}") == 1
