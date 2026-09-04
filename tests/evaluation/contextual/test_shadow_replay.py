"""T-CX184: v9.7 rule-closure shadow replay over preserved v9.6 traces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from signal_diag.agent.rule_closure import required_rule_profile
from signal_diag.evaluation.contextual.shadow_replay import replay_rule_closure
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal.context import StimulusContext

REPO = Path(__file__).resolve().parents[3]
V96_RUN_DIR = (
    REPO
    / "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1"
    / "agent_v9_6_dev_confirmation_1"
)


def profile_loader() -> YamlRuleProfileLoader:
    profile_root = REPO / "src/signal_diag/rules/profiles"
    return YamlRuleProfileLoader(
        {
            "profile_s1_distortion": profile_root / "s1_distortion_v1.yaml",
            "profile_s1_contextual_comparison": (
                profile_root / "s1_contextual_comparison_v1.yaml"
            ),
        }
    )


def test_t_cx184_v96_observations_close_under_v97_without_labels() -> None:
    before = {
        path.name: hashlib.sha256((path / "trace.json").read_bytes()).hexdigest()
        for path in sorted((V96_RUN_DIR / "cases").iterdir())
        if path.is_dir()
    }
    report = replay_rule_closure(
        V96_RUN_DIR,
        rule_engine=RuleEngine(),
        profile_loader=profile_loader(),
    )
    after = {
        path.name: hashlib.sha256((path / "trace.json").read_bytes()).hexdigest()
        for path in sorted((V96_RUN_DIR / "cases").iterdir())
        if path.is_dir()
    }
    assert before == after
    assert report["source_case_count"] == 20
    assert report["label_independent_mapping"] is True
    assert set(report["contextual_positive_fail_case_ids"]) == {
        "a4a0853be9983f8c",
        "2be730b9113701de",
        "6fb80bbda391c26c",
        "aa9b4a91b0253c33",
        "35967af7b71c5b75",
    }
    assert {
        "825a759a0ea47bb7",
        "393940e92c58cf0b",
        "04f4068ec91d2621",
        "ce8b413cf7382c3d",
    }.issubset(set(report["contextual_complete_pass_case_ids"]))
    dumped = json.dumps(report)
    assert "expected_outcome" not in dumped
    assert "expected_causal" not in dumped
    assert set(report["trace_sha256"]) == set(before)
    assert report["trace_sha256"] == before
    for row in report["rows"]:
        assert isinstance(row, dict)
        mode = str(row["mode"])
        tool_name = str(row["tool_name"])
        mapped = required_rule_profile(
            causal_policy_version="v9_7_deterministic_rule_closure",
            stimulus_context=_context_for_mode(mode),
            tool_name=tool_name,  # type: ignore[arg-type]
        )
        assert row["profile_id"] == mapped
        evidence_refs = set(row["evidence_refs"])  # type: ignore[arg-type]
        for evaluation in row["evaluations"]:  # type: ignore[assignment]
            assert set(evaluation["evidence_refs"]).issubset(evidence_refs)


def _context_for_mode(mode: str) -> StimulusContext:
    if mode == "paired_reference":
        return StimulusContext(
            mode="paired_reference",
            test_signal_id="sig_test",
            reference_signal_id="sig_ref",
            assertion_source="user_supplied",
        )
    if mode == "nominal_single_tone":
        return StimulusContext(
            mode="nominal_single_tone",
            test_signal_id="sig_test",
            nominal_fundamental_hz=440.0,
            stimulus_kind="single_tone",
            assertion_source="user_supplied",
        )
    return StimulusContext(
        mode="single_signal",
        test_signal_id="sig_test",
        assertion_source="user_supplied",
    )
