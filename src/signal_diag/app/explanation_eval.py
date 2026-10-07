"""Explanation acceptance run (D055 §9 4A).

``python -m signal_diag.app.explanation_eval --out DIR`` builds 50 cases (40
recorded contextual engine runs and 10 synthetic sweep runs), explains each
and writes ``results.jsonl``, ``summary.json`` and ``review.md`` (20 seeded
samples for the operator's review). Without ``--live`` it uses the template
only and makes no model call; ``--live`` calls the real model once per case and
needs ``DEEPSEEK_API_KEY`` (never written to any output). A rejected model
draft is kept in its row (``rejection_detail``, ``rejected_draft``) so the
reason can be read (D058).

The model path is accepted only when the validation pass rate is at least 90 %
and the operator finds no wrong statement in the 20 reviewed explanations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
from collections import Counter
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np

from signal_diag.app.engine_comparison import engine_cases, run_engine
from signal_diag.app.explanation import (
    VALIDATOR_VERSION,
    ExplanationPacket,
    contextual_packet,
)
from signal_diag.app.explanation_service import (
    ENABLE_FLAG,
    ExplanationResult,
    ExplanationService,
    Rejection,
    build_explanation_service,
    explanation_lines,
    sweep_explanation_packet,
)
from signal_diag.app.pcm_wav import encode_pcm32_wav
from signal_diag.app.sweep import diagnose_sweep
from signal_diag.dsp.sweep import generate_stimulus

EVAL_SCHEMA = "explanation_eval/1"
PASS_RATE_BAR = 0.9
REVIEW_SAMPLES = 20
SEED = 20261007


def _sweep_wav(device: Any, seed: int) -> bytes:
    stimulus, _ = generate_stimulus(48_000)
    rng = np.random.default_rng(seed)
    response = device(stimulus, rng)
    recording = np.concatenate([np.zeros(9_600), response, np.zeros(14_400)])
    return encode_pcm32_wav(recording.astype(np.float32).reshape(-1, 1), sample_rate_hz=48_000)


_SWEEP_CASES: dict[str, list[tuple[str, Any]]] = {
    "sweep_clean": [("-12 dB", lambda s, r: s)],
    "sweep_soft_one_level": [("0 dB", lambda s, r: np.tanh(2 * s) / 2)],
    "sweep_onset_three_levels": [
        ("-20 dB", lambda s, r: np.tanh(0.4 * s) / 4),
        ("-6 dB", lambda s, r: np.tanh(2 * s) / 4),
        ("0 dB", lambda s, r: np.tanh(6 * s) / 4),
    ],
    "sweep_all_clean_two_levels": [("-20 dB", lambda s, r: 0.5 * s), ("-6 dB", lambda s, r: s)],
    "sweep_recorder_full_scale": [("hot", lambda s, r: np.clip(2.5 * s, -1, 1))],
    "sweep_hard_clip": [("0 dB", lambda s, r: np.clip(s, -0.4, 0.4))],
    "sweep_noisy": [("noisy", lambda s, r: s + 0.05 * r.standard_normal(len(s)))],
    "sweep_wrong_stimulus": [("wrong", lambda s, r: 0.3 * r.standard_normal(len(s)))],
    "sweep_drift": [
        (
            "drift",
            lambda s, r: np.interp(
                np.arange(int(len(s) * 1.0005)) / 1.0005, np.arange(len(s)), s
            ),
        )
    ],
    "sweep_polynomial_two_levels": [
        ("-12 dB", lambda s, r: 0.5 * s + 0.0125 * s**2),
        ("0 dB", lambda s, r: s + 0.1 * s**2 + 0.05 * s**3),
    ],
}


async def eval_packets(root: Path) -> AsyncIterator[tuple[str, str, ExplanationPacket]]:
    """(case_id, group, packet) for the fixed 50-case set, in order."""
    for case in engine_cases(root):
        if not case.group.startswith("contextual_"):
            continue
        reference = case.load_reference() if case.load_reference else None
        result = await run_engine(
            case.load_test(),
            reference,
            mode=case.mode,
            nominal_fundamental_hz=case.nominal_fundamental_hz,
        )
        yield case.case_id, case.group, contextual_packet(result, mode=case.mode)
    for index, (name, levels) in enumerate(_SWEEP_CASES.items()):
        recordings = [
            (_sweep_wav(device, SEED + index * 10 + offset), label)
            for offset, (label, device) in enumerate(levels)
        ]
        yield name, "sweep", sweep_explanation_packet(diagnose_sweep(recordings))


def _row(
    case_id: str,
    group: str,
    packet: ExplanationPacket,
    result: ExplanationResult,
    rejection: Rejection | None = None,
) -> dict[str, Any]:
    conclusion = result.draft.sections[0]
    steps = result.draft.sections[3].steps
    menu = {option.step_id for option in packet.next_steps}
    return {
        "case_id": case_id,
        "group": group,
        "outcome": packet.outcome,
        "packet_digest": result.packet_digest,
        "source": result.source,
        "fallback_reason": result.fallback_reason,
        "model_calls": result.model_calls,
        "claims_covered": set(packet.claim_ids)
        <= {ref for sentence in conclusion.sentences for ref in sentence.refs},
        "steps_on_menu": all(step.step_id in menu for step in steps),
        "draft": result.draft.model_dump(mode="json"),
        "validator_version": result.validator_version,
        "rejection_detail": rejection.detail if rejection else None,
        "rejected_draft": rejection.raw if rejection else None,
    }


def summarize(rows: list[dict[str, Any]], *, live: bool) -> dict[str, Any]:
    total = len(rows)
    model_rows = [row for row in rows if row["model_calls"]]
    passed = sum(row["source"] == "model" for row in rows)
    rate = passed / len(model_rows) if model_rows else None
    return {
        "schema": EVAL_SCHEMA,
        "live": live,
        "cases": total,
        "groups": dict(Counter(row["group"] for row in rows)),
        "model_calls": sum(row["model_calls"] for row in rows),
        "model_explanations": passed,
        "validation_pass_rate": rate,
        "fallback_reasons": dict(Counter(row["fallback_reason"] for row in rows if row["fallback_reason"])),
        "rejection_details": dict(
            Counter(row["rejection_detail"] for row in rows if row["rejection_detail"])
        ),
        "validator_version": VALIDATOR_VERSION,
        "claims_covered": sum(row["claims_covered"] for row in rows),
        "steps_on_menu": sum(row["steps_on_menu"] for row in rows),
        "pass_rate_bar": PASS_RATE_BAR,
        "meets_validation_bar": rate is not None and rate >= PASS_RATE_BAR,
        "human_review": "pending: operator scores review.md (no wrong statement in 20 samples)",
    }


def review_markdown(rows: list[dict[str, Any]], results: dict[str, ExplanationResult]) -> str:
    candidates = [row for row in rows if row["source"] == "model"] or rows
    picked = random.Random(SEED).sample(candidates, min(REVIEW_SAMPLES, len(candidates)))
    lines = [
        "# Explanation review (D055 4A)",
        "",
        "For each sample, mark: readable (Y/N), wrong statement (Y/N), next steps useful (Y/N).",
        "Acceptance needs 0 wrong statements across all samples.",
        "",
    ]
    for index, row in enumerate(picked, 1):
        lines.extend(
            [
                f"## {index}. {row['case_id']} ({row['group']}, {row['outcome']})",
                "",
                *(f"    {line}" for line in explanation_lines(results[row["case_id"]])),
                "",
                "- readable: ",
                "- wrong statement: ",
                "- next steps useful: ",
                "",
            ]
        )
    return "\n".join(lines)


async def _run(
    root: Path, out: Path, *, live: bool, service: ExplanationService | None = None
) -> dict[str, Any]:
    if service is None and live:
        if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
            raise SystemExit("--live needs DEEPSEEK_API_KEY")
        service = build_explanation_service({**os.environ, ENABLE_FLAG: "enabled"})
    rejections: list[Rejection] = []
    service = (service or ExplanationService()).with_rejection_sink(rejections.append)
    rows: list[dict[str, Any]] = []
    results: dict[str, ExplanationResult] = {}
    try:
        async for case_id, group, packet in eval_packets(root):
            rejections.clear()
            result = await service.explain(packet, language="zh", use_model=live)
            results[case_id] = result
            rows.append(_row(case_id, group, packet, result, rejections[-1] if rejections else None))
    finally:
        await service.aclose()
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary = summarize(rows, live=live)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "review.md").write_text(review_markdown(rows, results), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m signal_diag.app.explanation_eval")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--live", action="store_true", help="call the real model once per case")
    args = parser.parse_args(argv)
    summary = asyncio.run(_run(args.root, args.out, live=args.live))
    print(json.dumps({key: summary[key] for key in ("cases", "model_calls", "validation_pass_rate", "meets_validation_bar")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
