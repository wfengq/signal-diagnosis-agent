"""T-CX503–T-CX508: multi-round test sessions, rule policy and sandbox (D060). No network."""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from signal_diag.app.session_eval import (
    load_cases,
    oracle_onset,
    run,
    run_session,
    score,
)
from signal_diag.app.test_session import (
    START,
    AskUser,
    Finish,
    LevelObservation,
    ProposeTest,
    SessionRejected,
    SessionRound,
    SessionState,
    apply_action,
    apply_answer,
    level_label,
    new_session,
    parse_level_label,
    resolution,
    rule_next_action,
    summary_lines,
    validate_action,
)


def _obs(level: float, outcome: str, *, round_index: int = 0, faults: tuple[str, ...] = (), failed: tuple[str, ...] = (), fix: str | None = None) -> LevelObservation:
    return LevelObservation(
        ref=f"swrun_r{round_index}:{level_label(level)}",
        round_index=round_index,
        level_db=level,
        outcome=outcome,  # type: ignore[arg-type]
        fault_types=faults or (("harmonic_distortion",) if outcome == "supported_fault" else ()),
        failed_validity=failed,
        fix_applied=fix,  # type: ignore[arg-type]
    )


def _state(*rounds: tuple[ProposeTest, tuple[LevelObservation, ...]], answers: dict | None = None, **kwargs: object) -> SessionState:
    state = new_session(answers=answers, **kwargs)  # type: ignore[arg-type]
    built = tuple(
        SessionRound(index=i, action=action, run_id=f"swrun_r{i}", observations=obs)
        for i, (action, obs) in enumerate(rounds)
    )
    return state.model_copy(update={"rounds": built})


def _round(levels: tuple[float, ...], outcomes: tuple[str, ...], *, index: int = 0, fix: str | None = None, **obs_kwargs: object) -> tuple[ProposeTest, tuple[LevelObservation, ...]]:
    action = ProposeTest(levels_db=levels, fix=fix, reason_refs=(START,))  # type: ignore[arg-type]
    return action, tuple(_obs(level, outcome, round_index=index, fix=fix, **obs_kwargs) for level, outcome in zip(levels, outcomes, strict=True))  # type: ignore[arg-type]


def test_t_cx503_labels_answers_and_new_session() -> None:
    assert [level_label(x) for x in (-12.0, 0.0, 3.0)] == ["-12 dB", "0 dB", "+3 dB"]
    assert parse_level_label("+3 dB") == 3.0 and parse_level_label("loud") is None
    state = new_session(answers={"max_level_db": 6, "can_retest": True}, seed="x")
    assert state.session_id.startswith("sess_") and state.answers["max_level_db"] == 6.0
    assert new_session(seed="x") .session_id == new_session(seed="x").session_id
    for field, value in (("max_level_db", 4), ("max_level_db", 30), ("can_retest", "yes"), ("connection", "wifi"), ("colour", 1)):
        with pytest.raises(SessionRejected):
            apply_answer(state, field, value)  # type: ignore[arg-type]
    assert apply_answer(state, "connection", "acoustic_mic").connection == "acoustic_mic"
    with pytest.raises(SessionRejected):
        new_session(sample_rate_hz=22_050)
    with pytest.raises(SessionRejected):
        new_session(max_rounds=9)


def _rejected(action: ProposeTest | AskUser | Finish, state: SessionState, check: str) -> None:
    with pytest.raises(SessionRejected) as caught:
        validate_action(action, state)
    assert caught.value.check == check, caught.value


def test_t_cx504_validator_rejects_each_violation() -> None:
    fresh = new_session()
    validate_action(ProposeTest(levels_db=(-12.0, -6.0, 0.0), reason_refs=(START,)), fresh)
    _rejected(ProposeTest(levels_db=(-12.0, -7.0), reason_refs=(START,)), fresh, "levels")
    _rejected(ProposeTest(levels_db=(-6.0, -12.0), reason_refs=(START,)), fresh, "levels")
    _rejected(ProposeTest(levels_db=(-9.0, -6.0, -3.0, 0.0), reason_refs=(START,)), fresh, "levels")
    _rejected(ProposeTest(levels_db=(3.0,), reason_refs=(START,)), fresh, "levels")
    _rejected(ProposeTest(levels_db=(-6.0,), reason_refs=("swrun_x:-6 dB",)), fresh, "citation")
    _rejected(ProposeTest(levels_db=(-6.0,), fix="use_one_clock", reason_refs=(START,)), fresh, "fix")
    _rejected(Finish(status="resolved"), fresh, "finish")
    _rejected(Finish(status="budget_exhausted"), fresh, "finish")
    _rejected(Finish(status="blocked_by_user"), fresh, "finish")
    _rejected(Finish(status="measurement_failed"), fresh, "finish")

    one = _state(_round((-12.0, -6.0, 0.0), ("no_supported_fault", "supported_fault", "supported_fault")))
    ref = one.rounds[0].observations[0].ref
    validate_action(ProposeTest(levels_db=(-9.0,), reason_refs=(ref,)), one)
    _rejected(ProposeTest(levels_db=(-24.0,), reason_refs=(ref,)), one, "levels")
    _rejected(ProposeTest(levels_db=(-12.0, -6.0, 0.0), reason_refs=(ref,)), one, "repeat")
    _rejected(ProposeTest(levels_db=(-9.0,), reason_refs=(START,)), one, "citation")
    validate_action(AskUser(field="max_level_db", question="?"), one)
    asked = apply_action(one, AskUser(field="max_level_db", question="?"))
    _rejected(AskUser(field="max_level_db", question="?"), asked, "ask")

    full = _state(*[_round((-12.0,), ("no_supported_fault",), index=i) for i in range(1)], max_rounds=1)
    _rejected(ProposeTest(levels_db=(-9.0,), reason_refs=(full.rounds[0].observations[0].ref,)), full, "budget")
    no_retest = new_session(answers={"can_retest": False})
    _rejected(ProposeTest(levels_db=(-6.0,), reason_refs=(START,)), no_retest, "precondition")
    validate_action(Finish(status="blocked_by_user"), no_retest)
    pending = apply_action(fresh, ProposeTest(levels_db=(-6.0,), reason_refs=(START,)))
    _rejected(AskUser(field="can_retest", question="?"), pending, "state")
    done = apply_action(no_retest, Finish(status="blocked_by_user"))
    _rejected(AskUser(field="max_level_db", question="?"), done, "state")


def test_t_cx505_resolution_criteria() -> None:
    gap = _state(_round((-12.0, -6.0, 0.0), ("no_supported_fault", "supported_fault", "supported_fault")))
    assert resolution(gap).onset_db == -6.0 and not resolution(gap).resolved
    closed = _state(
        _round((-12.0, -6.0, 0.0), ("no_supported_fault", "supported_fault", "supported_fault")),
        _round((-9.0,), ("no_supported_fault",), index=1),
    )
    assert resolution(closed).resolved and resolution(closed).highest_clean_db == -9.0
    clean = _state(_round((-12.0, -6.0, 0.0), ("no_supported_fault",) * 3))
    assert not resolution(clean).resolved
    assert resolution(apply_answer(clean, "max_level_db", 0.0)).resolved
    assert not resolution(apply_answer(clean, "max_level_db", 6.0)).resolved
    clipped = _state(_round((-12.0, -6.0), ("no_supported_fault", "supported_fault"), faults=("clipping",)))
    assert resolution(clipped).onset_db is None
    settled = apply_answer(clipped, "recorder_gain_adjustable", False)
    assert resolution(settled).onset_db == -6.0
    invalid = _state(_round((-6.0,), ("inconclusive",), failed=("rule_sweep_snr_acceptable",)))
    assert resolution(invalid).onset_db is None and not resolution(invalid).resolved
    floor = _state(_round((-36.0,), ("supported_fault",)))
    assert resolution(floor).resolved
    assert resolution(new_session(start_outcome="supported_fault")).resolved


def test_t_cx506_rule_policy_steps() -> None:
    assert rule_next_action(new_session()) == ProposeTest(levels_db=(-12.0, -6.0, 0.0), reason_refs=(START,))
    assert rule_next_action(new_session(answers={"max_level_db": -9.0})).levels_db == (-12.0,)
    assert rule_next_action(new_session(start_outcome="inconclusive")) == AskUser(field="can_retest", question=rule_next_action(new_session(start_outcome="inconclusive")).question)  # type: ignore[union-attr]
    assert rule_next_action(new_session(start_outcome="no_supported_fault")) == Finish(status="resolved")
    assert rule_next_action(new_session(answers={"can_retest": False})) == Finish(status="blocked_by_user")

    noisy = _state(_round((-12.0, -6.0), ("inconclusive",) * 2, failed=("rule_sweep_snr_acceptable", "rule_sweep_drift_acceptable")))
    first = rule_next_action(noisy)
    assert isinstance(first, ProposeTest) and first.fix == "use_one_clock" and first.levels_db == (-12.0, -6.0)
    gap = _state(_round((-12.0, -6.0, 0.0), ("no_supported_fault", "supported_fault", "supported_fault")))
    step = rule_next_action(gap)
    assert isinstance(step, ProposeTest) and step.levels_db == (-9.0,) and step.fix is None
    wide = _state(_round((-24.0, 0.0), ("no_supported_fault", "supported_fault")))
    assert rule_next_action(wide).levels_db == (-21.0, -12.0, -3.0)  # type: ignore[union-attr]
    low = _state(_round((-12.0, -6.0, 0.0), ("supported_fault",) * 3))
    assert rule_next_action(low).levels_db == (-21.0, -18.0, -15.0)  # type: ignore[union-attr]
    clipped = _state(_round((-12.0, -6.0), ("no_supported_fault", "supported_fault"), faults=("clipping",)))
    assert rule_next_action(clipped) == AskUser(field="recorder_gain_adjustable", question=rule_next_action(clipped).question)  # type: ignore[union-attr]
    yes = rule_next_action(apply_answer(clipped, "recorder_gain_adjustable", True))
    assert isinstance(yes, ProposeTest) and yes.fix == "check_recorder_gain"
    clean = _state(_round((-12.0, -6.0, 0.0), ("no_supported_fault",) * 3))
    assert isinstance(rule_next_action(clean), AskUser)
    up = rule_next_action(apply_answer(clean, "max_level_db", 6.0))
    assert isinstance(up, ProposeTest) and up.levels_db == (3.0, 6.0)
    budget = _state(_round((-12.0, -6.0, 0.0), ("no_supported_fault", "supported_fault", "supported_fault")), max_rounds=1)
    assert rule_next_action(budget) == Finish(status="budget_exhausted")
    for state in (noisy, gap, wide, low, clean, budget):
        action = rule_next_action(state)
        validate_action(action, state)


def test_t_cx507_sandbox_runs_whole_sessions() -> None:
    cases = {case["case_id"]: case for case in load_cases("dev")}
    assert oracle_onset({"case_id": "probe", "device": {"kind": "hard_clip", "ceiling": 0.2}, "user": {"max_level_db": -6.0}}) == -6.0
    for case_id in ("s01", "s14", "s20", "s29"):
        state, log = run_session(cases[case_id])
        row = score(cases[case_id], state)
        assert row["correct"], row
        assert log[-1]["action"]["kind"] == "finish"
        assert summary_lines(state)[-1].endswith(row["status"])


def test_t_cx508_scenarios_and_harness(tmp_path: Path) -> None:
    cases = load_cases("dev")
    assert len(cases) == 30 and len({case["case_id"] for case in cases}) == 30
    tags = collections.Counter(tag for case in cases for tag in case["tags"])
    for tag in ("bracket", "clean", "noise", "drift", "recorder", "truncate", "wrong_stimulus", "start", "blocked", "budget"):
        assert tags[tag] >= 1, tag
    statuses = {case["expected"]["status"] for case in cases}
    assert statuses == {"resolved", "blocked_by_user", "budget_exhausted"}
    summary = run(tmp_path, case_ids=["s02", "s27"])
    assert summary["cases"] == 2 and summary["final_correct"] == 1.0 and summary["model_calls"] == 0
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert {row["case_id"] for row in rows} == {"s02", "s27"} and all(row["steps"] for row in rows[:1])
    for name in ("results.jsonl", "summary.json"):
        assert all(line == line.rstrip() for line in (tmp_path / name).read_text(encoding="utf-8").splitlines())
