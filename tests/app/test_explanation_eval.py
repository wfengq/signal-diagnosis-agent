"""T-CX476: explanation acceptance harness (D055 4A), offline and scripted."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from signal_diag.agent.explain import ScriptedExplainer
from signal_diag.app.explanation_eval import _run
from signal_diag.app.explanation_service import ExplainerIdentity, ExplanationService

ROOT = Path(__file__).resolve().parents[2]


def test_t_cx476_offline_harness_writes_the_acceptance_files(tmp_path: Path) -> None:
    summary = asyncio.run(_run(ROOT, tmp_path, live=False))
    assert summary["cases"] == 50 and summary["model_calls"] == 0
    assert summary["groups"] == {"contextual_dev": 20, "contextual_validation": 20, "sweep": 10}
    assert summary["claims_covered"] == 50 and summary["steps_on_menu"] == 50
    assert summary["validation_pass_rate"] is None and not summary["meets_validation_bar"]
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 50 and {row["source"] for row in rows} == {"template"}
    review = (tmp_path / "review.md").read_text(encoding="utf-8")
    assert review.count("- wrong statement:") == 20
    for name in ("results.jsonl", "summary.json", "review.md"):
        assert "DEEPSEEK_API_KEY" not in (tmp_path / name).read_text(encoding="utf-8")


def test_t_cx476_live_mode_counts_fallbacks(tmp_path: Path) -> None:
    service = ExplanationService(
        ScriptedExplainer("not json"), identity=ExplainerIdentity(provider="scripted", model="s")
    )
    summary = asyncio.run(_run(ROOT, tmp_path, live=True, service=service))
    assert summary["model_calls"] == 50 and summary["model_explanations"] == 0
    assert summary["validation_pass_rate"] == 0.0
    assert summary["fallback_reasons"] == {"illegal_output": 50}
    assert summary["meets_validation_bar"] is False
