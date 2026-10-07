"""Multi-round test sessions (D060, §32): actions, validation, rule policy.

A session strings sweep tests together. Each round's result comes from the
deterministic sweep engine (§29); the next step is one of three actions
(propose a test, ask the user, finish), chosen by a policy and checked by
``validate_action``. The rule policy here needs no model; it is the default
and the baseline a model policy must beat (D060 3A). Whether a session is
resolved is decided only by ``resolution`` from engine results.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from signal_diag.app.sweep import SweepDiagnosis
from signal_diag.app.test_plan import CONNECTIONS, DEFAULT_RATE, SWEEP_RATES

SESSION_VERSION = "test-session-1.0"
RULE_POLICY_VERSION = "session-rules-1.0"
GRID_STEP_DB = 3.0
MIN_LEVEL_DB = -36.0
MAX_LEVEL_LIMIT_DB = 12.0
DEFAULT_MAX_LEVEL_DB = 0.0
DEFAULT_LEVELS_DB = (-12.0, -6.0, 0.0)
MAX_LEVELS_PER_TEST = 3
# A new level may lie at most this far outside the levels already tested.
REACH_DB = 3 * GRID_STEP_DB
DEFAULT_MAX_ROUNDS = 4
MAX_ROUNDS_LIMIT = 6
START = "session_start"

FixCode = Literal[
    "record_whole_stimulus",
    "check_stimulus_file",
    "use_one_clock",
    "rerecord_quieter",
    "check_recorder_gain",
]
# Validity rule -> the fix that addresses it, in the order they are tried.
VALIDITY_FIXES: tuple[tuple[str, FixCode], ...] = (
    ("rule_sweep_analysis_valid", "record_whole_stimulus"),
    ("rule_sweep_alignment_acceptable", "check_stimulus_file"),
    ("rule_sweep_drift_acceptable", "use_one_clock"),
    ("rule_sweep_snr_acceptable", "rerecord_quieter"),
)
AskField = Literal["max_level_db", "recorder_gain_adjustable", "can_retest", "connection"]
# ``measurement_failed``: the remaining steps cannot produce a valid result
# (fixes tried, nothing left to test); a refinement of the design's three statuses.
SessionStatus = Literal[
    "resolved", "blocked_by_user", "budget_exhausted", "measurement_failed"
]
Outcome = Literal["supported_fault", "no_supported_fault", "inconclusive"]
_LABEL = re.compile(r"^([+-]?\d+(?:\.\d+)?) dB$")


class SessionRejected(ValueError):
    def __init__(self, check: str, detail: str) -> None:
        super().__init__(f"{check}: {detail}")
        self.check = check
        self.detail = detail


def level_label(level_db: float) -> str:
    """The sweep level label for a session level: ``-12 dB``, ``0 dB``, ``+3 dB``."""
    if level_db > 0:
        return f"+{level_db:g} dB"
    return f"{level_db:g} dB"


def parse_level_label(label: str) -> float | None:
    match = _LABEL.match(label.strip())
    return float(match.group(1)) if match else None


def _on_grid(level_db: float) -> bool:
    return abs(level_db / GRID_STEP_DB - round(level_db / GRID_STEP_DB)) < 1e-9


# --- actions ------------------------------------------------------------------


class ProposeTest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["propose_test"] = "propose_test"
    plan_id: Literal["sweep_levels"] = "sweep_levels"
    levels_db: tuple[float, ...]
    fix: FixCode | None = None
    reason_refs: tuple[str, ...]


class AskUser(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ask_user"] = "ask_user"
    field: AskField
    question: str = Field(min_length=1, max_length=200)


class Finish(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["finish"] = "finish"
    status: SessionStatus


SessionAction = Annotated[ProposeTest | AskUser | Finish, Field(discriminator="kind")]


# --- state --------------------------------------------------------------------


class LevelObservation(BaseModel):
    """One level of one round, reduced from the engine's sweep result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    round_index: int
    level_db: float
    outcome: Outcome
    fault_types: tuple[str, ...]
    failed_validity: tuple[str, ...]
    fix_applied: FixCode | None

    @property
    def valid(self) -> bool:
        return not self.failed_validity


class SessionRound(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    action: ProposeTest
    run_id: str
    observations: tuple[LevelObservation, ...]


class SessionState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    version: str = SESSION_VERSION
    sample_rate_hz: int = DEFAULT_RATE
    connection: str | None = None
    max_rounds: int = DEFAULT_MAX_ROUNDS
    start_outcome: Outcome | None = None
    answers: dict[str, bool | float | str] = Field(default_factory=dict)
    asked: tuple[str, ...] = ()
    rounds: tuple[SessionRound, ...] = ()
    pending: ProposeTest | None = None
    finished: Finish | None = None


def new_session(
    *,
    sample_rate_hz: int = DEFAULT_RATE,
    connection: str | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    start_outcome: Outcome | None = None,
    answers: Mapping[str, bool | float | str] | None = None,
    seed: str = "",
) -> SessionState:
    if sample_rate_hz not in SWEEP_RATES:
        raise SessionRejected("parameters", f"sample rate must be one of {SWEEP_RATES}")
    if connection is not None and connection not in CONNECTIONS:
        raise SessionRejected("parameters", f"unknown connection {connection!r}")
    if not 1 <= max_rounds <= MAX_ROUNDS_LIMIT:
        raise SessionRejected("parameters", f"max_rounds must be 1 to {MAX_ROUNDS_LIMIT}")
    state = SessionState(
        session_id="placeholder",
        sample_rate_hz=sample_rate_hz,
        connection=connection,
        max_rounds=max_rounds,
        start_outcome=start_outcome,
    )
    for field, value in (answers or {}).items():
        state = apply_answer(state, field, value)
    digest = hashlib.sha256(
        json.dumps([state.model_dump(mode="json", exclude={"session_id"}), seed], sort_keys=True).encode()
    ).hexdigest()[:24]
    return state.model_copy(update={"session_id": f"sess_{digest}"})


def _check_answer(field: str, value: bool | float | str) -> bool | float | str:
    if field in ("recorder_gain_adjustable", "can_retest"):
        if not isinstance(value, bool):
            raise SessionRejected("answer", f"{field} is yes or no")
        return value
    if field == "max_level_db":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SessionRejected("answer", "max_level_db is a number of dB")
        level = float(value)
        if not (MIN_LEVEL_DB <= level <= MAX_LEVEL_LIMIT_DB and _on_grid(level)):
            raise SessionRejected(
                "answer", f"max_level_db is a multiple of 3 from {MIN_LEVEL_DB:g} to {MAX_LEVEL_LIMIT_DB:g}"
            )
        return level
    if field == "connection":
        if value not in CONNECTIONS:
            raise SessionRejected("answer", f"connection is one of {CONNECTIONS}")
        return value
    raise SessionRejected("answer", f"unknown field {field!r}")


def apply_answer(state: SessionState, field: str, value: bool | float | str) -> SessionState:
    checked = _check_answer(field, value)
    answers = {**state.answers, field: checked}
    update: dict[str, object] = {"answers": answers}
    if field == "connection":
        update["connection"] = checked
    return state.model_copy(update=update)


def _observations(diagnosis: SweepDiagnosis, round_index: int, fix: FixCode | None) -> tuple[LevelObservation, ...]:
    result = []
    for level in diagnosis.levels:
        level_db = parse_level_label(level.level_label)
        if level_db is None:
            raise SessionRejected("result", f"level label {level.level_label!r} is not a session level")
        failed = tuple(
            item.rule_id
            for item in level.rule_evaluations
            if item.role == "validity" and item.judgment == "fail"
        )
        result.append(
            LevelObservation(
                ref=f"{diagnosis.run_id}:{level.level_label}",
                round_index=round_index,
                level_db=level_db,
                outcome=level.outcome,
                fault_types=tuple(claim.fault_type for claim in level.claims),
                failed_validity=failed,
                fix_applied=fix,
            )
        )
    return tuple(result)


def record_result(state: SessionState, diagnosis: SweepDiagnosis) -> SessionState:
    """Attach the engine's result for the pending proposal as a new round."""
    if state.pending is None:
        raise SessionRejected("result", "no test is waiting for a result")
    proposal = state.pending
    labels = tuple(level.level_label for level in diagnosis.levels)
    expected = tuple(level_label(level) for level in proposal.levels_db)
    if labels != expected:
        raise SessionRejected("result", f"the run measured {labels}, the proposal was {expected}")
    if diagnosis.sample_rate_hz != state.sample_rate_hz:
        raise SessionRejected("result", "the run's sample rate differs from the session's")
    index = len(state.rounds)
    round_ = SessionRound(
        index=index,
        action=proposal,
        run_id=diagnosis.run_id,
        observations=_observations(diagnosis, index, proposal.fix),
    )
    return state.model_copy(update={"rounds": (*state.rounds, round_), "pending": None})


# --- resolution ---------------------------------------------------------------


class Resolution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved: bool
    onset_db: float | None
    highest_clean_db: float | None
    clean_up_to_max: bool
    max_level_db: float


def _all_observations(state: SessionState) -> list[LevelObservation]:
    return [obs for round_ in state.rounds for obs in round_.observations]


def _fixes_tried(state: SessionState) -> set[str]:
    return {round_.action.fix for round_ in state.rounds if round_.action.fix}


def _confirmed(state: SessionState) -> dict[float, LevelObservation]:
    """Latest valid, judged observation per level.

    A full-scale (clipping) result counts only once the recorder's gain was
    checked, or the user said it cannot be changed: until then it may be the
    recorder, not the device.
    """
    recorder_settled = (
        "check_recorder_gain" in _fixes_tried(state)
        or state.answers.get("recorder_gain_adjustable") is False
    )
    latest: dict[float, LevelObservation] = {}
    for obs in _all_observations(state):
        if not obs.valid or obs.outcome == "inconclusive":
            continue
        if "clipping" in obs.fault_types and not recorder_settled:
            continue
        latest[obs.level_db] = obs
    return latest


def max_level(state: SessionState) -> float:
    value = state.answers.get("max_level_db", DEFAULT_MAX_LEVEL_DB)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else DEFAULT_MAX_LEVEL_DB


def resolution(state: SessionState) -> Resolution:
    confirmed = _confirmed(state)
    faulty = sorted(level for level, obs in confirmed.items() if obs.outcome == "supported_fault")
    clean = sorted(level for level, obs in confirmed.items() if obs.outcome == "no_supported_fault")
    onset = faulty[0] if faulty else None
    below = [level for level in clean if onset is None or level < onset]
    highest_clean = below[-1] if below else None
    top = max_level(state)
    if not state.rounds and state.start_outcome in ("supported_fault", "no_supported_fault"):
        return Resolution(resolved=True, onset_db=None, highest_clean_db=None, clean_up_to_max=False, max_level_db=top)
    if onset is not None:
        bracketed = highest_clean is not None and onset - highest_clean <= GRID_STEP_DB + 1e-9
        at_floor = onset <= MIN_LEVEL_DB + 1e-9
        return Resolution(
            resolved=bracketed or at_floor,
            onset_db=onset,
            highest_clean_db=highest_clean,
            clean_up_to_max=False,
            max_level_db=top,
        )
    # "Clean up to the maximum" needs the user's maximum, not the default.
    clean_to_max = bool(clean) and "max_level_db" in state.answers and clean[-1] >= top - 1e-9
    return Resolution(
        resolved=clean_to_max,
        onset_db=None,
        highest_clean_db=clean[-1] if clean else None,
        clean_up_to_max=clean_to_max,
        max_level_db=top,
    )


# --- validation ---------------------------------------------------------------


def known_refs(state: SessionState) -> set[str]:
    refs = {START} if not state.rounds else set()
    refs.update(obs.ref for obs in _all_observations(state))
    return refs


def _needed_fixes(state: SessionState) -> set[str]:
    if not state.rounds:
        return set()
    needed: set[str] = set()
    for obs in state.rounds[-1].observations:
        for rule_id, fix in VALIDITY_FIXES:
            if rule_id in obs.failed_validity:
                needed.add(fix)
        if "clipping" in obs.fault_types:
            needed.add("check_recorder_gain")
        if obs.valid and obs.outcome == "inconclusive":
            needed.add("rerecord_quieter")
    return needed


def _blocked(state: SessionState) -> bool:
    return state.answers.get("can_retest") is False


def validate_action(action: ProposeTest | AskUser | Finish, state: SessionState) -> None:
    """Raise ``SessionRejected`` unless ``action`` is a legal next step."""
    if state.finished is not None:
        raise SessionRejected("state", "the session has finished")
    if state.pending is not None:
        raise SessionRejected("state", "a proposed test is waiting for its result")
    if isinstance(action, ProposeTest):
        _validate_proposal(action, state)
    elif isinstance(action, AskUser):
        if action.field in state.answers or action.field in state.asked:
            raise SessionRejected("ask", f"{action.field} was already asked")
    else:
        _validate_finish(action, state)


def _validate_proposal(action: ProposeTest, state: SessionState) -> None:
    if len(state.rounds) >= state.max_rounds:
        raise SessionRejected("budget", "no rounds left")
    if state.answers.get("can_retest") is False:
        raise SessionRejected("precondition", "the user cannot re-test the device")
    levels = action.levels_db
    if not 1 <= len(levels) <= MAX_LEVELS_PER_TEST:
        raise SessionRejected("levels", f"a test has 1 to {MAX_LEVELS_PER_TEST} levels")
    if list(levels) != sorted(set(levels)):
        raise SessionRejected("levels", "levels are unique and increasing")
    top = max_level(state)
    for level in levels:
        if not _on_grid(level):
            raise SessionRejected("levels", f"{level:g} dB is not on the {GRID_STEP_DB:g} dB grid")
        if not MIN_LEVEL_DB <= level <= top:
            raise SessionRejected("levels", f"{level:g} dB is outside {MIN_LEVEL_DB:g} to {top:g} dB")
    tested = [obs.level_db for obs in _all_observations(state)]
    if tested:
        low, high = min(tested) - REACH_DB, max(tested) + REACH_DB
        for level in levels:
            if not low - 1e-9 <= level <= high + 1e-9:
                raise SessionRejected("levels", f"{level:g} dB is more than {REACH_DB:g} dB from the levels tested")
    if not action.reason_refs or not set(action.reason_refs) <= known_refs(state):
        raise SessionRejected("citation", "reasons must cite this session's results")
    if action.fix is not None and action.fix not in _needed_fixes(state):
        raise SessionRejected("fix", f"{action.fix} is not called for by the last result")
    if action.fix == "check_recorder_gain" and state.answers.get("recorder_gain_adjustable") is False:
        raise SessionRejected("fix", "the user cannot change the recorder's gain")
    for round_ in state.rounds:
        if round_.action.levels_db == levels and round_.action.fix == action.fix:
            raise SessionRejected("repeat", "this exact test was already run")


def _validate_finish(action: Finish, state: SessionState) -> None:
    if action.status == "resolved" and not resolution(state).resolved:
        raise SessionRejected("finish", "the result is not resolved yet")
    if action.status == "budget_exhausted" and len(state.rounds) < state.max_rounds:
        raise SessionRejected("finish", "rounds remain")
    if action.status == "blocked_by_user" and not _blocked(state):
        raise SessionRejected("finish", "nothing the user said blocks the next test")
    if action.status == "measurement_failed" and (not state.rounds or resolution(state).resolved):
        raise SessionRejected("finish", "there is no failed measurement to report")


# --- rule policy --------------------------------------------------------------

_QUESTIONS: dict[str, str] = {
    "max_level_db": "最大能把音量开到多少 dB（相对平时音量）？",
    "recorder_gain_adjustable": "录音设备的输入增益能调低吗？",
    "can_retest": "设备还在手边、可以重新播放测试信号并录音吗？",
    "connection": "设备输出是怎么录回来的：线路接声卡、麦克风拾音，还是 USB/数字直录？",
}


def ask(field: AskField) -> AskUser:
    return AskUser(field=field, question=_QUESTIONS[field])


def _refs(state: SessionState) -> tuple[str, ...]:
    if not state.rounds:
        return (START,)
    return tuple(obs.ref for obs in state.rounds[-1].observations)


def _grid(low: float, high: float) -> list[float]:
    """Grid levels strictly between ``low`` and ``high``."""
    steps = round((high - low) / GRID_STEP_DB)
    return [low + GRID_STEP_DB * index for index in range(1, steps)]


def _spread(levels: Sequence[float]) -> tuple[float, ...]:
    """At most three levels, evenly spread, always keeping the top one."""
    if len(levels) <= MAX_LEVELS_PER_TEST:
        return tuple(levels)
    last = len(levels) - 1
    picks = {round(last * k / (MAX_LEVELS_PER_TEST - 1)) for k in range(MAX_LEVELS_PER_TEST)}
    return tuple(levels[index] for index in sorted(picks))


def rule_next_action(state: SessionState) -> ProposeTest | AskUser | Finish:
    """The deterministic next step (§32 rule policy ``session-rules-1.0``)."""
    if state.answers.get("can_retest") is False:
        return Finish(status="blocked_by_user")
    if not state.rounds:
        if state.start_outcome in ("supported_fault", "no_supported_fault"):
            return Finish(status="resolved")
        if state.start_outcome == "inconclusive" and "can_retest" not in state.answers:
            return ask("can_retest")
        levels = tuple(level for level in DEFAULT_LEVELS_DB if level <= max_level(state))
        return ProposeTest(levels_db=levels or (max_level(state),), reason_refs=(START,))
    state_resolution = resolution(state)
    if state_resolution.resolved:
        return Finish(status="resolved")
    if len(state.rounds) >= state.max_rounds:
        return Finish(status="budget_exhausted")
    last = state.rounds[-1]
    last_levels = last.action.levels_db
    tried = _fixes_tried(state)
    needed = _needed_fixes(state)
    for _, fix in VALIDITY_FIXES:
        if fix in needed and fix not in tried:
            return ProposeTest(levels_db=last_levels, fix=fix, reason_refs=_refs(state))
    if "check_recorder_gain" in needed and "check_recorder_gain" not in tried:
        adjustable = state.answers.get("recorder_gain_adjustable")
        if adjustable is None:
            return ask("recorder_gain_adjustable")
        if adjustable:
            return ProposeTest(levels_db=last_levels, fix="check_recorder_gain", reason_refs=_refs(state))
    proposal = _bracket(state, state_resolution)
    if proposal is not None:
        return proposal
    if (
        state_resolution.onset_db is None
        and state_resolution.highest_clean_db is not None
        and "max_level_db" not in state.answers
        and "max_level_db" not in state.asked
    ):
        return ask("max_level_db")
    return Finish(status="measurement_failed")


def _bracket(state: SessionState, found: Resolution) -> ProposeTest | None:
    tested = {obs.level_db for obs in _all_observations(state)}
    reach_low = min(tested) - REACH_DB if tested else MIN_LEVEL_DB
    reach_high = max(tested) + REACH_DB if tested else max_level(state)
    candidates: list[float]
    if found.onset_db is not None:
        if found.highest_clean_db is None:
            floor = max(MIN_LEVEL_DB, reach_low, found.onset_db - REACH_DB)
            candidates = [floor + GRID_STEP_DB * k for k in range(round((found.onset_db - floor) / GRID_STEP_DB))]
        else:
            candidates = _grid(found.highest_clean_db, found.onset_db)
    elif found.highest_clean_db is not None and "max_level_db" in state.answers:
        top = min(max_level(state), reach_high)
        candidates = [found.highest_clean_db + GRID_STEP_DB * k for k in range(1, 4)]
        candidates = [level for level in candidates if level <= top + 1e-9]
    else:
        return None
    fresh = [level for level in candidates if MIN_LEVEL_DB <= level and level not in tested]
    if not fresh:
        return None
    return ProposeTest(levels_db=_spread(sorted(fresh)), reason_refs=_refs(state))


# --- applying actions -----------------------------------------------------------


def apply_action(state: SessionState, action: ProposeTest | AskUser | Finish) -> SessionState:
    """Validate and apply an action: a proposal waits for its result."""
    validate_action(action, state)
    if isinstance(action, ProposeTest):
        return state.model_copy(update={"pending": action})
    if isinstance(action, AskUser):
        return state.model_copy(update={"asked": (*state.asked, action.field)})
    return state.model_copy(update={"finished": action})


def summary_lines(state: SessionState, language: Literal["zh", "en"] = "zh") -> tuple[str, ...]:
    """Deterministic session summary, built only from engine results."""
    found = resolution(state)
    zh = language == "zh"
    lines: list[str] = []
    rounds = len(state.rounds)
    lines.append(f"共进行 {rounds} 轮测试。" if zh else f"{rounds} test round(s) run.")
    if found.onset_db is not None:
        onset = level_label(found.onset_db)
        if found.highest_clean_db is not None:
            clean = level_label(found.highest_clean_db)
            lines.append(
                f"失真从 {onset} 开始出现，{clean} 时没有发现失真。"
                if zh
                else f"Distortion starts at {onset}; none was found at {clean}."
            )
        else:
            lines.append(f"在测到的最低电平 {onset} 已经出现失真。" if zh else f"Distortion is present already at {onset}.")
    elif found.highest_clean_db is not None:
        clean = level_label(found.highest_clean_db)
        lines.append(f"直到 {clean} 都没有发现失真。" if zh else f"No distortion up to {clean}.")
    fixes = sorted(_fixes_tried(state))
    if fixes:
        lines.append(("测量过程中处理过：" if zh else "Measurement issues addressed: ") + ", ".join(fixes))
    if state.finished is not None:
        lines.append(("结束状态：" if zh else "Status: ") + state.finished.status)
    return tuple(lines)


__all__ = [
    "DEFAULT_LEVELS_DB",
    "DEFAULT_MAX_ROUNDS",
    "GRID_STEP_DB",
    "MIN_LEVEL_DB",
    "RULE_POLICY_VERSION",
    "SESSION_VERSION",
    "AskUser",
    "Finish",
    "LevelObservation",
    "ProposeTest",
    "Resolution",
    "SessionAction",
    "SessionRejected",
    "SessionRound",
    "SessionState",
    "apply_action",
    "apply_answer",
    "ask",
    "known_refs",
    "level_label",
    "max_level",
    "new_session",
    "parse_level_label",
    "record_result",
    "resolution",
    "rule_next_action",
    "summary_lines",
    "validate_action",
]
