"""T-CX394–T-CX396: simulated user, scoring, and call caps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from signal_diag.agent.intake import ContextDraft
from signal_diag.evaluation.agent_increment.budget import (
    DEV_STAGE_CAP,
    HELD_OUT_STAGE_CAP,
    PER_CASE_CAP,
    CallCapStop,
    CallLedger,
)
from signal_diag.evaluation.agent_increment.campaign import (
    WriteOnceError,
    dry_run_summary,
    write_report,
)
from signal_diag.evaluation.agent_increment.models import ArmOutcome
from signal_diag.evaluation.agent_increment.scoring import score_family
from signal_diag.evaluation.agent_increment.simulated_user import (
    confirm_proposed_fields,
)


def _draft(**overrides: object) -> ContextDraft:
    payload: dict[str, object] = {
        "mode": "single_signal",
        "nominal_fundamental_hz": None,
        "reference_file": None,
        "stimulus_kind": None,
        "missing_fields": (),
        "questions": (),
    }
    payload.update(overrides)
    return ContextDraft.model_validate(payload)


def test_t_cx394_simulated_user_does_not_fill_unasked_fields() -> None:
    truth = _draft(
        mode="nominal_single_tone",
        nominal_fundamental_hz=1000.0,
        stimulus_kind="single_tone",
    )
    silent = confirm_proposed_fields(_draft(), truth)
    assert silent.confirmed.nominal_fundamental_hz is None
    assert silent.confirmed.stimulus_kind is None
    assert silent.confirmed.mode == "nominal_single_tone"
    assert silent.correction_count == 1
    asked = confirm_proposed_fields(
        _draft(questions=("nominal_fundamental_hz",)),
        truth,
    )
    assert asked.confirmed.nominal_fundamental_hz == 1000.0
    assert asked.confirmed.stimulus_kind is None
    assert asked.correction_count == 1
    wrong = confirm_proposed_fields(_draft(nominal_fundamental_hz=440.0), truth)
    assert wrong.confirmed.nominal_fundamental_hz == 1000.0
    assert wrong.correction_count == 2


def _rows(agent_correct: int, strong_correct: int, *, unsupported: int = 0) -> list[ArmOutcome]:
    rows: list[ArmOutcome] = []
    for index in range(24):
        for arm, correct_n in (
            ("agent", agent_correct),
            ("strong_fixed", strong_correct),
            ("weak_fixed", 0),
        ):
            rows.append(
                ArmOutcome(
                    case_id=f"c{index}",
                    family="T1",
                    arm=arm,  # type: ignore[arg-type]
                    conclusion_correct=index < correct_n,
                    unsupported_positive=arm == "agent" and index < unsupported,
                    evidence_traceable=True,
                    context_fields_correct=2,
                    context_fields_graded=2,
                    correction_count=1 if arm == "agent" else 0,
                    localization_correct=None,
                    tool_calls=0,
                )
            )
    return rows


def test_t_cx395_increment_labels_match_the_pass_line() -> None:
    measurable = score_family(_rows(10, 7))
    assert measurable.increment == 3
    assert measurable.increment_label == "measurable_increment"
    assert measurable.safety_hard_pass is True
    assert measurable.evidence_traceability == 1.0
    assert measurable.unsupported_positive_count == 0
    assert measurable.t1_field_accuracy == 1.0
    assert measurable.t1_correction_count == 24
    quiet = score_family(_rows(8, 7))
    assert quiet.increment == 1
    assert quiet.increment_label == "no_significant_increment"
    negative = score_family(_rows(4, 6))
    assert negative.increment == -2
    assert negative.increment_label == "negative"
    unsafe = score_family(_rows(10, 7, unsupported=1))
    assert unsafe.safety_hard_pass is False
    assert unsafe.unsupported_positive_count == 1


def test_t_cx396_caps_stop_and_write_once(tmp_path: Path) -> None:
    assert PER_CASE_CAP == 21
    assert DEV_STAGE_CAP == 1500
    assert HELD_OUT_STAGE_CAP == 1008
    ledger = CallLedger(stage_cap=1500, output_dir=tmp_path)
    for _ in range(21):
        ledger.reserve("case-1")
    with pytest.raises(CallCapStop):
        ledger.reserve("case-1")
    stop = json.loads((tmp_path / "stop_record.json").read_text(encoding="utf-8"))
    assert stop["reason"] == "per_case_cap"
    assert stop["case_id"] == "case-1"
    assert stop["per_case_cap"] == 21
    stage = CallLedger(stage_cap=2, output_dir=tmp_path / "stage")
    stage.reserve("a")
    stage.reserve("b")
    with pytest.raises(CallCapStop):
        stage.reserve("c")
    stage_stop = json.loads((tmp_path / "stage" / "stop_record.json").read_text(encoding="utf-8"))
    assert stage_stop["reason"] == "stage_cap"
    report = tmp_path / "run"
    write_report(report, {"study_id": "study_s1_agent_increment_1", "ok": True})
    with pytest.raises(WriteOnceError):
        write_report(report, {"study_id": "study_s1_agent_increment_1", "ok": False})
    summary = dry_run_summary(case_count=24, stage_cap=DEV_STAGE_CAP)
    assert summary["cases"] == 24
    assert summary["arms"] == ["agent", "strong_fixed", "weak_fixed"]
    assert summary["max_calls"] == 504
    held = dry_run_summary(case_count=48, stage_cap=HELD_OUT_STAGE_CAP)
    assert held["max_calls"] == 1008
