"""Result Q&A acceptance run (D060 phase C, §33).

``python -m signal_diag.app.qa_eval --out DIR [--cases dev|heldout] [--live]``
answers each question about its run (a case id of the explanation evaluation:
recorded contextual engine runs or synthetic sweeps) and writes
``results.jsonl``, ``summary.json`` and ``review.md`` (20 seeded samples for
the operator). Without ``--live`` it uses the deterministic answer and makes no
model call; ``--live`` calls the real model once per question and needs
``DEEPSEEK_API_KEY`` (never written to any output). A rejected model answer is
kept in its row so the reason can be read.

The model path is accepted only when, on the frozen held-out questions, the
validation pass rate is at least 90 %, at least 90 % of the questions the
evidence cannot answer are declined by the model, and the operator finds no
wrong statement in the 20 reviewed answers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
from collections import Counter
from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path
from typing import Any

from signal_diag.app.engine_comparison import engine_cases, run_engine
from signal_diag.app.explanation import (
    VALIDATOR_VERSION,
    ExplanationPacket,
    contextual_packet,
)
from signal_diag.app.explanation_eval import _SWEEP_CASES, SEED, _sweep_wav
from signal_diag.app.explanation_service import sweep_explanation_packet
from signal_diag.app.qa_service import (
    ENABLE_FLAG,
    QARejection,
    QAResult,
    QAService,
    build_qa_service,
)
from signal_diag.app.result_qa import QA_VERSION
from signal_diag.app.sweep import diagnose_sweep

EVAL_SCHEMA = "qa_eval/1"
# "heldout" (#101) informed result-qa 1.1 (§33.1), "heldout_2" (#105) informed
# 1.2 (§33.2) and "heldout_3" (#107) informed 1.3 (§33.3); acceptance of 1.3 runs
# on "heldout_4", the last round (§33.3).
CASE_SETS = {
    "dev": "qa_cases.json",
    "heldout": "qa_cases_heldout.json",
    "heldout_2": "qa_cases_heldout_2.json",
    "heldout_3": "qa_cases_heldout_3.json",
    "heldout_4": "qa_cases_heldout_4.json",
}
PASS_RATE_BAR = 0.9
DECLINE_BAR = 0.9
REVIEW_SAMPLES = 20


def load_cases(case_set: str = "dev") -> list[dict[str, Any]]:
    path = files("signal_diag").joinpath("evaluation", "assets", CASE_SETS[case_set])
    return list(json.loads(path.read_text(encoding="utf-8"))["cases"])


async def run_packets(
    root: Path, wanted: Iterable[str]
) -> dict[str, tuple[str, ExplanationPacket]]:
    """(group, packet) for each wanted explanation-evaluation case id."""
    wanted = set(wanted)
    packets: dict[str, tuple[str, ExplanationPacket]] = {}
    for case in engine_cases(root):
        if case.case_id not in wanted or not case.group.startswith("contextual_"):
            continue
        reference = case.load_reference() if case.load_reference else None
        result = await run_engine(
            case.load_test(),
            reference,
            mode=case.mode,
            nominal_fundamental_hz=case.nominal_fundamental_hz,
        )
        packets[case.case_id] = (case.group, contextual_packet(result, mode=case.mode))
    for index, (name, levels) in enumerate(_SWEEP_CASES.items()):
        if name not in wanted:
            continue
        recordings = [
            (_sweep_wav(device, SEED + index * 10 + offset), label)
            for offset, (label, device) in enumerate(levels)
        ]
        packets[name] = ("sweep", sweep_explanation_packet(diagnose_sweep(recordings)))
    missing = wanted - set(packets)
    if missing:
        raise ValueError(f"unknown runs: {sorted(missing)}")
    return packets


def _row(
    case: dict[str, Any],
    group: str,
    packet: ExplanationPacket,
    result: QAResult,
    rejection: QARejection | None,
) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "run": case["run"],
        "group": group,
        "outcome": packet.outcome,
        "language": case["language"],
        "expect": case["expect"],
        "question": case["question"],
        "packet_digest": result.packet_digest,
        "source": result.source,
        "fallback_reason": result.fallback_reason,
        "model_calls": result.model_calls,
        "declined": result.answer.declined,
        "answer": result.answer.model_dump(mode="json"),
        "lines": list(result.lines),
        "qa_version": result.qa_version,
        "rejection_detail": rejection.detail if rejection else None,
        "rejected_answer": rejection.raw if rejection else None,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(
    rows: list[dict[str, Any]], *, live: bool, case_set: str
) -> dict[str, Any]:
    model_rows = [row for row in rows if row["model_calls"]]
    model_answers = [row for row in rows if row["source"] == "model"]
    decline = [row for row in rows if row["expect"] == "decline"]
    answer = [row for row in rows if row["expect"] == "answer"]
    model_declined = sum(
        row["declined"] and row["source"] == "model" for row in decline
    )
    rate = _rate(len(model_answers), len(model_rows))
    decline_rate = _rate(model_declined, len(decline)) if model_rows else None
    return {
        "schema": EVAL_SCHEMA,
        "case_set": case_set,
        "live": live,
        "cases": len(rows),
        "expect": dict(Counter(row["expect"] for row in rows)),
        "groups": dict(Counter(row["group"] for row in rows)),
        "model_calls": sum(row["model_calls"] for row in rows),
        "model_answers": len(model_answers),
        "validation_pass_rate": rate,
        "fallback_reasons": dict(
            Counter(row["fallback_reason"] for row in rows if row["fallback_reason"])
        ),
        "rejection_details": dict(
            Counter(row["rejection_detail"] for row in rows if row["rejection_detail"])
        ),
        "final_declined_when_expected": sum(row["declined"] for row in decline),
        "model_declined_when_expected": model_declined,
        "model_decline_rate": decline_rate,
        "declined_when_answerable": sum(row["declined"] for row in answer),
        "qa_version": QA_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "pass_rate_bar": PASS_RATE_BAR,
        "decline_bar": DECLINE_BAR,
        "meets_validation_bar": rate is not None and rate >= PASS_RATE_BAR,
        "meets_decline_bar": decline_rate is not None and decline_rate >= DECLINE_BAR,
        "human_review": "pending: operator scores review.md (no wrong statement in 20 samples)",
    }


def review_markdown(rows: list[dict[str, Any]]) -> str:
    candidates = [row for row in rows if row["source"] == "model"] or rows
    picked = random.Random(SEED).sample(
        candidates, min(REVIEW_SAMPLES, len(candidates))
    )
    lines = [
        "# Result Q&A review (D060 C)",
        "",
        "For each sample, mark: answers the question (Y/N), wrong statement (Y/N),",
        "declined correctly when the evidence cannot answer (Y/N/-).",
        "Acceptance needs 0 wrong statements across all samples.",
        "",
    ]
    for index, row in enumerate(picked, 1):
        lines.extend(
            [
                f"## {index}. {row['case_id']} ({row['run']}, {row['outcome']}, expect {row['expect']})",
                "",
                f"    Q: {row['question']}",
                *(f"    {line}" for line in row["lines"]),
                f"    [source: {row['source']}"
                + (
                    f", fallback: {row['fallback_reason']}"
                    if row["fallback_reason"]
                    else ""
                )
                + "]",
                "",
                "- answers the question:",
                "- wrong statement:",
                "- declined correctly:",
                "",
            ]
        )
    # No trailing whitespace, so the committed review passes `git diff --check`.
    return "\n".join(line.rstrip() for line in lines)


async def _run(
    root: Path,
    out: Path,
    *,
    live: bool,
    case_set: str = "dev",
    service: QAService | None = None,
) -> dict[str, Any]:
    cases = load_cases(case_set)
    if service is None and live:
        if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
            raise SystemExit("--live needs DEEPSEEK_API_KEY")
        service = build_qa_service({**os.environ, ENABLE_FLAG: "enabled"})
    rejections: list[QARejection] = []
    service = (service or QAService()).with_rejection_sink(rejections.append)
    rows: list[dict[str, Any]] = []
    try:
        packets = await run_packets(root, (case["run"] for case in cases))
        for case in cases:
            group, packet = packets[case["run"]]
            rejections.clear()
            result = await service.answer(
                packet, case["question"], language=case["language"], use_model=live
            )
            rows.append(
                _row(
                    case, group, packet, result, rejections[-1] if rejections else None
                )
            )
    finally:
        await service.aclose()
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    summary = summarize(rows, live=live, case_set=case_set)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # review_markdown already ends with a newline; adding one leaves a blank
    # line at EOF that `git diff --check` rejects.
    (out / "review.md").write_text(review_markdown(rows), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.app.qa_eval")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--cases", choices=sorted(CASE_SETS), default="dev")
    parser.add_argument(
        "--live", action="store_true", help="call the real model once per question"
    )
    args = parser.parse_args(argv)
    summary = asyncio.run(
        _run(args.root, args.out, live=args.live, case_set=args.cases)
    )
    keys = ("cases", "model_calls", "validation_pass_rate", "model_decline_rate")
    print(json.dumps({key: summary[key] for key in keys}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
