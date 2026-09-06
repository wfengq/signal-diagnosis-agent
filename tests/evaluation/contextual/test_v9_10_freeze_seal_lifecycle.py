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
    assert row["current_implementation_sha256"] == current
    assert row["qualification_recompute_unchanged"] is True
    assert row["calibration_recompute_unchanged_except_code_sha256"] is True
    assert row["selected_threshold_percent_unchanged"] == 5.0
    assert row["model_calls"] == 0
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
    assert record["active_seal"]["directory"] is None
    assert record["active_seal"]["status"] == (
        "none_pending_v9_10_development_confirmation"
    )


def test_t_cx243_preflight_rejects_historical_v3_before_credentials() -> None:
    output = VAL / "__t_cx243_must_not_exist__"
    assert not output.exists()
    with pytest.raises(CampaignPreflightError, match="historical.*not active"):
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
