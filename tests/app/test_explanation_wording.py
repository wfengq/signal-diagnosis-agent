"""T-CX494–T-CX497: explanation wording check 1.1 and rejection records (D058). No network."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from signal_diag.agent.explain import ScriptedExplainer
from signal_diag.app.explanation import (
    VALIDATOR_VERSION,
    ExplanationRejected,
    ExplanationSentence,
    template_explanation,
    validate_explanation,
)
from signal_diag.app.explanation_eval import _run
from signal_diag.app.explanation_service import (
    ExplainerIdentity,
    ExplanationService,
    Rejection,
)
from tests.app.test_explanation import _packet, _replace

ROOT = Path(__file__).resolve().parents[2]
SCRIPTED = ExplainerIdentity(provider="scripted", model="scripted")


def _check(text: str) -> str | None:
    """The failing check for one evidence sentence, or None when it passes."""
    packet = _packet("both")
    good = template_explanation(packet, "zh")
    growth = next(i for i in packet.items if i.label == "rule_even_harmonic_growth_acceptable")
    sentence = ExplanationSentence(text=text, refs=(growth.ref_id,))
    try:
        validate_explanation(_replace(good, "evidence", sentences=(sentence,)), packet)
    except ExplanationRejected as rejected:
        return rejected.check
    return None


@pytest.mark.parametrize(
    "text",
    [
        "The growth is slightly larger; the limitation is the short recording.",
        "Even harmonics appear in several pieces of the recording.",
        "The analysis is limited to the recorded band.",
    ],
)
def test_t_cx494_ordinary_english_words_pass(text: str) -> None:
    assert VALIDATOR_VERSION == "explain-validator-1.1"
    assert _check(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "The result meets the standard.",
        "Industry standards apply to this result.",
        "The device is SLA compliant.",
        "演示值下达到SLA要求。",
        "演示值，参考IEC60268。",
        "The demo result is certified.",
        "The threshold is exceeded.",
        "The limits are exceeded.",
        "Thresholds were exceeded.",
    ],
)
def test_t_cx494_whole_english_words_still_rejected(text: str) -> None:
    assert _check(text) == "wording"


@pytest.mark.parametrize(
    "text",
    [
        "These are demonstration thresholds, not universal standards.",
        "These demo limits are not a standard.",
        "The demo values are used rather than industry standards.",
        "这些阈值是演示值，不是通用标准。",
        "这些是演示阈值，而非行业标准。",
        "演示阈值并非标准。",
    ],
)
def test_t_cx495_standard_disclaimer_passes(text: str) -> None:
    assert _check(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "The demo result meets the standard.",
        "These demo values are not meeting the standard.",
        "These are thresholds, not universal standards.",
        "Not universal standards.",
        "The demo value is not a certified result.",
        "演示阈值下符合标准。",
        "演示阈值下不符合标准。",
        "演示阈值下未达标。",
        "行业标准要求更低，演示阈值仅供参考。",
        "不是通用标准，但结果合格（演示）。",
        "这些阈值不是通用标准。",
        "演示阈值不是通用标准，符合标准。",
    ],
)
def test_t_cx495_counter_examples_rejected(text: str) -> None:
    assert _check(text) == "wording"


def test_t_cx496_rejection_sink_records_check_detail_and_text() -> None:
    packet = _packet("both")
    draft = template_explanation(packet, "zh").model_dump(mode="json")
    draft["sections"][1]["sentences"][0]["text"] = "The result meets the standard."
    raw = json.dumps(draft, ensure_ascii=False)
    seen: list[Rejection] = []
    service = ExplanationService(ScriptedExplainer(raw), identity=SCRIPTED, rejection_sink=seen.append)
    result = asyncio.run(service.explain(packet, use_model=True))
    assert result.source == "template" and result.fallback_reason == "validation_failed:wording"
    assert result.validator_version == VALIDATOR_VERSION
    assert seen == [Rejection(check="wording", detail="forbidden wording 'standard'", raw=raw)]
    payload = result.model_dump(mode="json")
    assert "rejection" not in json.dumps(payload) and raw not in json.dumps(payload, ensure_ascii=False)

    seen.clear()
    sinked = ExplanationService(ScriptedExplainer("not json"), identity=SCRIPTED).with_rejection_sink(seen.append)
    assert sinked.status().model_available is True
    asyncio.run(sinked.explain(packet))
    assert seen == []
    asyncio.run(sinked.explain(packet, use_model=True))
    (rejection,) = seen
    assert rejection.check == "illegal_output" and rejection.raw == "not json" and rejection.detail

    seen.clear()
    good = template_explanation(packet, "zh").model_dump_json()
    passed = ExplanationService(ScriptedExplainer(good), identity=SCRIPTED, rejection_sink=seen.append)
    assert asyncio.run(passed.explain(packet, use_model=True)).source == "model" and seen == []


def test_t_cx497_eval_rows_record_rejections(tmp_path: Path) -> None:
    service = ExplanationService(ScriptedExplainer("not json"), identity=SCRIPTED)
    summary = asyncio.run(_run(ROOT, tmp_path, live=True, service=service))
    assert summary["validator_version"] == VALIDATOR_VERSION
    assert sum(summary["rejection_details"].values()) == 50
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    for row in rows:
        assert row["validator_version"] == VALIDATOR_VERSION
        assert row["rejected_draft"] == "not json" and row["rejection_detail"]
    for name in ("results.jsonl", "summary.json", "review.md"):
        assert "DEEPSEEK_API_KEY" not in (tmp_path / name).read_text(encoding="utf-8")

    offline = tmp_path / "offline"
    summary = asyncio.run(_run(ROOT, offline, live=False))
    assert summary["model_calls"] == 0 and summary["rejection_details"] == {}
    rows = [json.loads(line) for line in (offline / "results.jsonl").read_text().splitlines()]
    assert all(row["rejection_detail"] is None and row["rejected_draft"] is None for row in rows)
