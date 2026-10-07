"""Offline sandbox for multi-round test sessions (D060, §32).

A scenario names a simulated device (how it distorts with level), the
recording conditions (noise, clock drift, recorder gain, truncated or wrong
stimulus) and the user's answers. The sandbox plays the versioned sweep
through the device at each proposed level, runs the real sweep engine on the
result and feeds it back to the session, so a whole session runs offline and
repeatably. A condition stays until the session applies its fix.

``python -m signal_diag.app.session_eval --out DIR`` runs the rule policy on
the scenarios and writes ``results.jsonl`` and ``summary.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np

from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.sweep import diagnose_sweep
from signal_diag.app.test_session import (
    GRID_STEP_DB,
    MIN_LEVEL_DB,
    RULE_POLICY_VERSION,
    AskUser,
    Finish,
    ProposeTest,
    SessionState,
    apply_action,
    apply_answer,
    level_label,
    new_session,
    record_result,
    resolution,
    rule_next_action,
    summary_lines,
)
from signal_diag.dsp.sweep import generate_stimulus

EVAL_SCHEMA = "session_eval/1"
CASE_SETS = {"dev": "session_cases.json", "heldout": "session_cases_heldout.json"}
FINAL_BAR = 0.9
Policy = Callable[[SessionState], ProposeTest | AskUser | Finish]
_DEFAULT_ANSWERS: dict[str, Any] = {
    "max_level_db": 0.0,
    "recorder_gain_adjustable": True,
    "can_retest": True,
    "connection": "line_loopback",
}


def load_cases(case_set: str = "dev") -> list[dict[str, Any]]:
    path = files("signal_diag").joinpath("evaluation", "assets", CASE_SETS[case_set])
    return list(json.loads(path.read_text(encoding="utf-8"))["cases"])


@cache
def _stimulus(rate: int) -> np.ndarray:
    stimulus, _ = generate_stimulus(rate)
    return stimulus


def _device(spec: dict[str, Any], x: np.ndarray) -> np.ndarray:
    kind = spec["kind"]
    if kind == "clean":
        return x
    if kind == "hard_clip":
        return np.clip(x, -spec["ceiling"], spec["ceiling"])
    if kind == "soft":
        drive = spec["drive"]
        return np.tanh(drive * x) / drive
    if kind == "poly":
        return x + spec["a2"] * x**2 + spec["a3"] * x**3
    raise ValueError(f"unknown device kind {kind!r}")


def render(case: dict[str, Any], level_db: float, fixes: frozenset[str], rate: int = 48_000) -> bytes:
    """The recording a scenario's device and room give at ``level_db``."""
    stimulus = _stimulus(rate)
    env = case.get("conditions", {})
    key = json.dumps([case["case_id"], level_db, sorted(fixes)]).encode()
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], "little"))
    y = _device(case["device"], 10 ** (level_db / 20) * stimulus)
    if env.get("recorder_gain") and "check_recorder_gain" not in fixes:
        y = np.clip(env["recorder_gain"] * y, -1.0, 1.0)
    if env.get("wrong_stimulus") and "check_stimulus_file" not in fixes:
        y = 0.3 * rng.standard_normal(len(y))
    if env.get("drift_ppm") and "use_one_clock" not in fixes:
        factor = 1 + env["drift_ppm"] * 1e-6
        y = np.interp(np.arange(int(len(y) * factor)) / factor, np.arange(len(y)), y)
    if env.get("noise") and "rerecord_quieter" not in fixes:
        y = y + env["noise"] * rng.standard_normal(len(y))
    if env.get("truncate") and "record_whole_stimulus" not in fixes:
        y = y[: len(y) // 2]
    recording = np.concatenate([np.zeros(rate // 5), y, np.zeros(rate * 3 // 10)])
    return encode_pcm32_wav(recording.astype(np.float32).reshape(-1, 1), sample_rate_hz=rate)


def _answer(case: dict[str, Any], field: str) -> Any:
    return case.get("user", {}).get(field, _DEFAULT_ANSWERS[field])


def run_session(case: dict[str, Any], policy: Policy = rule_next_action) -> tuple[SessionState, list[dict[str, Any]]]:
    """Run one scenario to the end; returns the final state and a step log."""
    state = new_session(
        max_rounds=case.get("max_rounds", 4),
        start_outcome=case.get("start_outcome"),
        seed=case["case_id"],
    )
    log: list[dict[str, Any]] = []
    for _ in range(4 * state.max_rounds + 4):
        action = policy(state)
        state = apply_action(state, action)
        entry: dict[str, Any] = {"action": action.model_dump(mode="json")}
        if isinstance(action, AskUser):
            value = _answer(case, action.field)
            state = apply_answer(state, action.field, value)
            entry["answer"] = value
        elif isinstance(action, ProposeTest):
            fixes = frozenset(r.action.fix for r in state.rounds if r.action.fix) | (
                {action.fix} if action.fix else set()
            )
            recordings = [(render(case, level, fixes), level_label(level)) for level in action.levels_db]
            diagnosis = diagnose_sweep(recordings)
            state = record_result(state, diagnosis)
            entry["result"] = {lvl.level_label: lvl.outcome for lvl in diagnosis.levels}
        log.append(entry)
        if isinstance(action, Finish):
            return state, log
    raise RuntimeError(f"{case['case_id']}: the policy did not finish")


def oracle_onset(case: dict[str, Any], rate: int = 48_000) -> float | None:
    """The lowest grid level the engine judges distorted under clean conditions."""
    top = float(case.get("user", {}).get("max_level_db", 0.0))
    clean = {**case, "conditions": {}}
    level = MIN_LEVEL_DB
    while level <= top + 1e-9:
        diagnosis = diagnose_sweep([(render(clean, level, frozenset(), rate), level_label(level))])
        if diagnosis.outcome == "supported_fault":
            return level
        level += GRID_STEP_DB
    return None


def score(case: dict[str, Any], state: SessionState) -> dict[str, Any]:
    expected = case["expected"]
    found = resolution(state)
    status = state.finished.status if state.finished else None
    fixes = sorted({r.action.fix for r in state.rounds if r.action.fix})
    onset_ok: bool
    if expected.get("onset_db") is None:
        onset_ok = found.onset_db is None
    else:
        onset_ok = found.onset_db is not None and abs(found.onset_db - expected["onset_db"]) <= GRID_STEP_DB + 1e-9
    fixes_ok = set(expected.get("fixes", [])) <= set(fixes)
    correct = status == expected["status"] and (onset_ok or expected["status"] != "resolved") and fixes_ok
    return {
        "case_id": case["case_id"],
        "tags": case.get("tags", []),
        "status": status,
        "expected_status": expected["status"],
        "onset_db": found.onset_db,
        "expected_onset_db": expected.get("onset_db"),
        "fixes": fixes,
        "rounds": len(state.rounds),
        "min_rounds": expected.get("min_rounds"),
        "extra_rounds": max(0, len(state.rounds) - expected["min_rounds"]) if "min_rounds" in expected else None,
        "correct": correct,
    }


def summarize(rows: list[dict[str, Any]], *, policy: str, case_set: str) -> dict[str, Any]:
    total = len(rows)
    correct = sum(row["correct"] for row in rows)
    return {
        "schema": EVAL_SCHEMA,
        "policy": policy,
        "case_set": case_set,
        "cases": total,
        "final_correct": round(correct / total, 4) if total else None,
        "mean_rounds": round(sum(row["rounds"] for row in rows) / total, 3) if total else None,
        "extra_rounds": sum(row["extra_rounds"] or 0 for row in rows),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "bar": FINAL_BAR,
        "meets_bar": bool(total) and correct / total >= FINAL_BAR,
        "model_calls": 0,
    }


def run(out: Path, *, case_set: str = "dev", case_ids: list[str] | None = None) -> dict[str, Any]:
    rows = []
    for case in load_cases(case_set):
        if case_ids and case["case_id"] not in case_ids:
            continue
        state, log = run_session(case)
        row = score(case, state)
        row["summary"] = list(summary_lines(state))
        row["steps"] = log
        rows.append(row)
    summary = summarize(rows, policy=RULE_POLICY_VERSION, case_set=case_set)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.app.session_eval")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cases", choices=sorted(CASE_SETS), default="dev")
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args(argv)
    summary = run(args.out, case_set=args.cases, case_ids=args.case_ids)
    print(json.dumps({key: summary[key] for key in ("cases", "final_correct", "mean_rounds", "meets_bar")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
