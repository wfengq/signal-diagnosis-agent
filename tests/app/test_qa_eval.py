"""T-CX517: result Q&A acceptance harness (D060 C), offline and scripted."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from signal_diag.agent.qa import ScriptedAnswerer
from signal_diag.app.qa_eval import _run, load_cases
from signal_diag.app.qa_service import AnswererIdentity, QAService

ROOT = Path(__file__).resolve().parents[2]


def test_t_cx517_dev_questions_are_well_formed() -> None:
    cases = load_cases("dev")
    assert len(cases) == 40 and len({case["case_id"] for case in cases}) == 40
    assert sum(case["expect"] == "decline" for case in cases) == 10
    assert {case["language"] for case in cases} == {"zh", "en"}
    assert all(0 < len(case["question"]) <= 500 for case in cases)


def test_t_cx517_offline_harness_writes_the_acceptance_files(tmp_path: Path) -> None:
    summary = asyncio.run(_run(ROOT, tmp_path, live=False))
    assert summary["cases"] == 40 and summary["model_calls"] == 0
    assert summary["expect"] == {"answer": 30, "decline": 10}
    assert summary["groups"] == {"contextual_dev": 20, "sweep": 20}
    # The deterministic answer declines every hardware question and no other.
    assert summary["final_declined_when_expected"] == 10
    assert summary["declined_when_answerable"] == 0
    assert (
        summary["validation_pass_rate"] is None
        and summary["model_decline_rate"] is None
    )
    assert not summary["meets_validation_bar"] and not summary["meets_decline_bar"]
    rows = [
        json.loads(line)
        for line in (tmp_path / "results.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 40 and {row["source"] for row in rows} == {"template"}
    review = (tmp_path / "review.md").read_text(encoding="utf-8")
    assert review.count("- wrong statement:") == 20
    assert all(line == line.rstrip() for line in review.splitlines())
    for name in ("results.jsonl", "summary.json", "review.md"):
        assert "DEEPSEEK_API_KEY" not in (tmp_path / name).read_text(encoding="utf-8")


def test_t_cx517_live_mode_counts_fallbacks(tmp_path: Path) -> None:
    service = QAService(
        ScriptedAnswerer("not json"),
        identity=AnswererIdentity(provider="scripted", model="s"),
    )
    summary = asyncio.run(_run(ROOT, tmp_path, live=True, service=service))
    assert summary["model_calls"] == 40 and summary["model_answers"] == 0
    assert (
        summary["validation_pass_rate"] == 0.0 and summary["model_decline_rate"] == 0.0
    )
    assert summary["fallback_reasons"] == {"illegal_output": 40}
    assert (
        summary["meets_validation_bar"] is False
        and summary["meets_decline_bar"] is False
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / "results.jsonl").read_text().splitlines()
    ]
    assert all(row["rejected_answer"] == "not json" for row in rows)


def test_t_cx518_heldout_questions_are_frozen(tmp_path: Path) -> None:
    import hashlib

    digest = "c323c5ae60b69a0de0b582eb971f296f2159c9a66d94935613a50fddb57d781d"
    frozen = (
        ROOT
        / "docs"
        / "evaluations"
        / "v0_3"
        / "qa"
        / "heldout"
        / "qa_cases_heldout.json"
    )
    asset = (
        ROOT / "src" / "signal_diag" / "evaluation" / "assets" / "qa_cases_heldout.json"
    )
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == digest
    cases = load_cases("heldout")
    assert len(cases) == 20
    assert not {case["case_id"] for case in cases} & {
        case["case_id"] for case in load_cases("dev")
    }
    summary = asyncio.run(_run(ROOT, tmp_path, live=False, case_set="heldout"))
    assert summary["case_set"] == "heldout" and summary["model_calls"] == 0
    assert summary["expect"] == {"answer": 15, "decline": 5}


def test_t_cx520_review_ends_with_one_newline_and_heldout_2_is_registered(
    tmp_path: Path,
) -> None:
    from signal_diag.agent.qa import QA_PROMPT_VERSION, SYSTEM_PROMPT
    from signal_diag.app.qa_eval import CASE_SETS
    from signal_diag.app.result_qa import QA_VERSION

    asyncio.run(_run(ROOT, tmp_path, live=False))
    review = (tmp_path / "review.md").read_text(encoding="utf-8")
    assert review.endswith("\n") and not review.endswith("\n\n")
    assert CASE_SETS["heldout_2"] == "qa_cases_heldout_2.json"
    assert QA_VERSION.startswith("result-qa-1.") and QA_PROMPT_VERSION.startswith("v0.3-s1-qa-1.")
    assert (
        "'only' did one check" in SYSTEM_PROMPT
        and "at least two levels" in SYSTEM_PROMPT
    )


def test_t_cx521_heldout_2_questions_are_frozen_and_new(tmp_path: Path) -> None:
    import hashlib

    digest = "25eb24e0af6f7c94f4624594ecd3d7d078a474931823c6d18aa4f7f58bfe661d"
    frozen = ROOT / "docs" / "evaluations" / "v0_3" / "qa" / "heldout_2" / "qa_cases_heldout_2.json"
    asset = ROOT / "src" / "signal_diag" / "evaluation" / "assets" / "qa_cases_heldout_2.json"
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == digest
    cases = load_cases("heldout_2")
    earlier = load_cases("dev") + load_cases("heldout")
    assert len(cases) == 20
    assert not {c["case_id"] for c in cases} & {c["case_id"] for c in earlier}
    assert not {c["question"] for c in cases} & {c["question"] for c in earlier}
    summary = asyncio.run(_run(ROOT, tmp_path, live=False, case_set="heldout_2"))
    assert summary["model_calls"] == 0 and summary["expect"] == {"answer": 15, "decline": 5}


def test_t_cx523_prompt_1_2_rules_and_heldout_3_is_registered() -> None:
    from signal_diag.agent.qa import QA_PROMPT_VERSION, SYSTEM_PROMPT
    from signal_diag.app.qa_eval import CASE_SETS
    from signal_diag.app.result_qa import QA_VERSION

    assert QA_VERSION == "result-qa-1.2" and QA_PROMPT_VERSION == "v0.3-s1-qa-1.2"
    assert CASE_SETS["heldout_3"] == "qa_cases_heldout_3.json"
    assert "never put a step_id in refs" in SYSTEM_PROMPT
    assert "not even to deny them" in SYSTEM_PROMPT and "合格" in SYSTEM_PROMPT


def test_t_cx524_heldout_3_questions_are_frozen_and_new(tmp_path: Path) -> None:
    import hashlib

    digest = "5833302070a5f096ed3f2d8bb19a761ae9d1f6102bfc269cc383f53e91d2cc47"
    frozen = ROOT / "docs" / "evaluations" / "v0_3" / "qa" / "heldout_3" / "qa_cases_heldout_3.json"
    asset = ROOT / "src" / "signal_diag" / "evaluation" / "assets" / "qa_cases_heldout_3.json"
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == digest
    cases = load_cases("heldout_3")
    earlier = load_cases("dev") + load_cases("heldout") + load_cases("heldout_2")
    assert len(cases) == 20
    assert not {c["case_id"] for c in cases} & {c["case_id"] for c in earlier}
    assert not {c["question"] for c in cases} & {c["question"] for c in earlier}
    summary = asyncio.run(_run(ROOT, tmp_path, live=False, case_set="heldout_3"))
    assert summary["model_calls"] == 0 and summary["expect"] == {"answer": 15, "decline": 5}
