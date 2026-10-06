"""T-CX398: scripted three-arm offline run writes a complete report."""

from __future__ import annotations

from pathlib import Path

from signal_diag.evaluation.agent_increment.offline import run_offline

_STUDY = (
    Path(__file__).resolve().parents[3]
    / "docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1"
)


def test_t_cx398_scripted_arms_write_a_complete_report(tmp_path: Path) -> None:
    report = run_offline(_STUDY, tmp_path / "run")
    identity = report["identity"]
    assert isinstance(identity, dict)
    assert identity["study_id"] == "study_s1_agent_increment_1"
    assert identity["model"] == "deepseek-v4-flash"
    assert identity["prompt_version"] == "v0.3-s1-planner-9.14"
    assert identity["prompt_sha256"]
    assert identity["intake_identity"] == "v0.3-s1-intake-1.1"
    assert identity["rule_profile_id"] == "profile_s1_segment_evidence"
    assert identity["rule_profile_version"] == "1.0.0-demo"
    assert identity["http_calls"] == 0
    assert identity["scripted_stand_in"] is True
    assert report["case_count"] == 72
    assert report["arms"] == ["agent", "strong_fixed", "weak_fixed"]
    dev = report["dry_run_dev"]
    held = report["dry_run_heldout"]
    assert isinstance(dev, dict) and isinstance(held, dict)
    assert dev["cases"] == 24
    assert dev["max_calls"] == 504
    assert held["cases"] == 48
    assert held["max_calls"] == 1008
    families = report["families"]
    assert isinstance(families, list) and len(families) == 2
    for family in families:
        assert isinstance(family, dict)
        assert "increment" in family
        assert "increment_label" in family
        assert "safety_hard_pass" in family
        assert family["evidence_traceability"] == 1.0
    assert (tmp_path / "run" / "report.json").is_file()
    root = Path(__file__).resolve().parents[3]
    html = (root / "src/signal_diag/app/static/index.html").read_text(encoding="utf-8")
    script = (root / "src/signal_diag/app/static/app.js").read_text(encoding="utf-8")
    assert 'id="intake-draft"' in html
    assert "requestIntakeDraft" in script
    draft_fn = script.split("async function requestIntakeDraft", 1)[1].split(
        "function bindIntake", 1
    )[0]
    assert "/api/v1/intake/draft" in draft_fn
    assert "/api/v1/contextual-runs/wav" not in draft_fn
