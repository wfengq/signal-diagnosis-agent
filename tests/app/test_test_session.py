"""T-CX503–T-CX512: multi-round test sessions, rule policy and sandbox (D060). No network."""

from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

from signal_diag.app.session_eval import (
    load_cases,
    oracle_onset,
    render,
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
    _rejected(ProposeTest(levels_db=(-9.0,), reason_refs=(ref,)), asked, "state")
    answered = apply_answer(asked, "max_level_db", 0.0)
    assert answered.open_ask is None
    _rejected(AskUser(field="max_level_db", question="?"), answered, "ask")

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


async def _upload(client: object, case: dict, levels: list[float]) -> str:
    files = {
        f"recording_{index}": (f"{index}.wav", render(case, level, frozenset()), "audio/wav")
        for index, level in enumerate(levels, 1)
    }
    data = {"metadata": json.dumps({"levels": [level_label(level) for level in levels]})}
    response = await client.post("/api/v1/sweep-runs", files=files, data=data)  # type: ignore[attr-defined]
    return str(response.json()["run_id"])


@pytest.mark.asyncio
async def test_t_cx509_api_session_flow() -> None:
    from signal_diag.app.api import create_app
    from signal_diag.app.engine_service import build_engine_service
    from tests.app.test_api import _client

    case = next(c for c in load_cases("dev") if c["case_id"] == "s01")
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        view = (await client.post("/api/v1/test-sessions", json={})).json()
        session_id = view["session"]["session_id"]
        assert view["next"]["kind"] == "propose_test" and view["next"]["level_labels"] == ["-12 dB", "-6 dB", "0 dB"]
        assert view["model_calls"] == 0 and view["rounds_left"] == 4
        run_id = await _upload(client, case, [-12.0, -6.0, 0.0])
        view = (await client.post(f"/api/v1/test-sessions/{session_id}/runs", json={"run_id": run_id})).json()
        assert view["next"]["level_labels"] == ["-9 dB"] and view["resolution"]["onset_db"] == -6.0
        wrong = await _upload(client, case, [-12.0])
        rejected = await client.post(f"/api/v1/test-sessions/{session_id}/runs", json={"run_id": wrong})
        assert rejected.status_code == 422
        run_id = await _upload(client, case, [-9.0])
        view = (await client.post(f"/api/v1/test-sessions/{session_id}/runs", json={"run_id": run_id})).json()
        assert view["next"] == {"kind": "finish", "status": "resolved"}
        assert (await client.get(f"/api/v1/test-sessions/{session_id}")).json()["next"]["kind"] == "finish"

        asked = (await client.post("/api/v1/test-sessions", json={"start_outcome": "inconclusive"})).json()
        assert asked["next"]["kind"] == "ask_user" and asked["next"]["field"] == "can_retest"
        sid = asked["session"]["session_id"]
        bad = await client.post(f"/api/v1/test-sessions/{sid}/answers", json={"field": "can_retest", "value": "maybe"})
        assert bad.status_code == 422
        done = (await client.post(f"/api/v1/test-sessions/{sid}/answers", json={"field": "can_retest", "value": False})).json()
        assert done["next"] == {"kind": "finish", "status": "blocked_by_user"}
        assert (await client.get("/api/v1/test-sessions/sess_missing")).status_code == 404
        assert (await client.post("/api/v1/test-sessions", json={"max_rounds": 9})).status_code == 422
        plan = (await client.post("/api/v1/test-plans/confirm", json={"plan_id": "existing_recording", "source": "questionnaire"})).json()
        assert (await client.post("/api/v1/test-sessions", json={"plan_key": plan["plan_key"]})).status_code == 422


def test_t_cx510_cli_session_simulate(capsys: pytest.CaptureFixture[str]) -> None:
    from signal_diag.app.cli import main

    assert main(["session", "simulate", "s29"]) == 0
    out = capsys.readouterr().out
    assert "ask can_retest -> False" in out and "finish blocked_by_user" in out and "correct: True" in out
    assert main(["session", "simulate", "s27", "--output", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["score"]["correct"] is True
    assert main(["session", "simulate", "nope"]) == 2


@pytest.mark.asyncio
async def test_t_cx511_web_ui_wiring() -> None:
    from signal_diag.app.api import create_app
    from signal_diag.app.engine_service import build_engine_service
    from tests.app.test_api import _client

    static = Path(__file__).resolve().parents[2] / "src" / "signal_diag" / "app" / "static"
    script = (static / "session.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "textContent" in script
    assert "/api/v1/test-sessions" in script and "SignalSession" in script
    page = (static / "sweep.html").read_text(encoding="utf-8")
    assert 'id="session-start"' in page and 'src="/static/session.js"' in page
    assert "SignalSession.linkRun" in (static / "sweep.js").read_text(encoding="utf-8")
    app = create_app(service=build_engine_service(environ={}))
    async with _client(app=app) as client:
        served = await client.get("/static/session.js")
        assert served.status_code == 200 and served.headers["content-type"].startswith("text/javascript")


def test_t_cx512_heldout_set_is_frozen_and_the_recorded_acceptance_holds() -> None:
    import hashlib

    from signal_diag.app.test_session import RULE_POLICY_VERSION

    root = Path(__file__).resolve().parents[2]
    frozen = root / "docs" / "evaluations" / "v0_3" / "session" / "heldout" / "session_cases_heldout.json"
    asset = root / "src" / "signal_diag" / "evaluation" / "assets" / "session_cases_heldout.json"
    digest = "669ee1098562a624942076d9c0341eabd83c436bd2bfb31200f20d48a2620ba9"
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == digest
    cases = load_cases("heldout")
    assert len(cases) == 20 and not {c["case_id"] for c in cases} & {c["case_id"] for c in load_cases("dev")}
    recorded = json.loads((root / "docs" / "evaluations" / "v0_3" / "session" / "rule_heldout" / "summary.json").read_text())
    assert recorded["policy"] == RULE_POLICY_VERSION and recorded["case_set"] == "heldout"
    assert recorded["cases"] == 20 and recorded["final_correct"] >= 0.9 and recorded["model_calls"] == 0
    by_id = {case["case_id"]: case for case in cases}
    for case_id in ("h04", "h12", "h20"):
        state, _ = run_session(by_id[case_id])
        assert score(by_id[case_id], state)["correct"], case_id
