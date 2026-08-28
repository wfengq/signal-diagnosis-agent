"""RuleEngine deterministic evaluation tests (T096, T098–T105)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from signal_diag.rules.engine import RuleEngine, evaluate_one
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleDefinition, RuleProfile
from signal_diag.tools.evidence import Evidence, EvidenceValue

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPROVED_PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)

RATIO_RULE = RuleDefinition(
    rule_id="rule_ratio",
    metric="clipping_ratio",
    source_tool="detect_clipping",
    comparator="lte",
    threshold=0.01,
    description="demo ratio",
)

THD_RULE = RuleDefinition(
    rule_id="rule_thd",
    metric="thd_percent",
    source_tool="analyze_harmonic_distortion",
    comparator="lte",
    threshold=5.0,
    unit="%",
    description="demo thd",
)

SINGLE_RULE_PROFILE = RuleProfile(
    profile_id="profile_test",
    version="1",
    description="test",
    rules=(RATIO_RULE,),
)


def make_evidence(
    *,
    evidence_id: str = "ev_test_001",
    source_tool: str = "detect_clipping",
    metric: str = "clipping_ratio",
    value: EvidenceValue = 0.0,
    unit: str | None = None,
    validity: str = "valid",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=source_tool,  # type: ignore[arg-type]
        call_id="call_test_001",
        metric=metric,
        value=value,
        unit=unit,
        validity=validity,  # type: ignore[arg-type]
        channel="mixdown",
    )


def test_t096_approved_profile_passes_at_boundary_values() -> None:
    loader = YamlRuleProfileLoader(
        {"profile_s1_distortion": APPROVED_PROFILE_PATH}
    )
    profile = loader.load("profile_s1_distortion")
    engine = RuleEngine()
    ratio_evidence = make_evidence(
        evidence_id="ev_ratio",
        metric="clipping_ratio",
        value=0.01,
    )
    thd_evidence = make_evidence(
        evidence_id="ev_thd",
        source_tool="analyze_harmonic_distortion",
        metric="thd_percent",
        value=5.0,
        unit="%",
    )
    batch = engine.evaluate_profile(
        profile,
        [ratio_evidence, thd_evidence],
    )
    ratio_eval = next(e for e in batch.evaluations if e.rule_id == "rule_clipping_ratio_acceptable")
    thd_eval = next(e for e in batch.evaluations if e.rule_id == "rule_thd_acceptable")
    assert ratio_eval.judgment == "pass"
    assert thd_eval.judgment == "pass"


def test_t096_approved_profile_fails_above_boundary_values() -> None:
    loader = YamlRuleProfileLoader(
        {"profile_s1_distortion": APPROVED_PROFILE_PATH}
    )
    profile = loader.load("profile_s1_distortion")
    engine = RuleEngine()
    ratio_evidence = make_evidence(
        evidence_id="ev_ratio",
        metric="clipping_ratio",
        value=0.0101,
    )
    thd_evidence = make_evidence(
        evidence_id="ev_thd",
        source_tool="analyze_harmonic_distortion",
        metric="thd_percent",
        value=5.01,
        unit="%",
    )
    batch = engine.evaluate_profile(profile, [ratio_evidence, thd_evidence])
    ratio_eval = next(e for e in batch.evaluations if e.rule_id == "rule_clipping_ratio_acceptable")
    thd_eval = next(e for e in batch.evaluations if e.rule_id == "rule_thd_acceptable")
    assert ratio_eval.judgment == "fail"
    assert thd_eval.judgment == "fail"


def test_t096_approved_profile_passes_below_boundary_values() -> None:
    loader = YamlRuleProfileLoader(
        {"profile_s1_distortion": APPROVED_PROFILE_PATH}
    )
    profile = loader.load("profile_s1_distortion")
    engine = RuleEngine()
    ratio_evidence = make_evidence(
        evidence_id="ev_ratio",
        metric="clipping_ratio",
        value=0.0099,
    )
    thd_evidence = make_evidence(
        evidence_id="ev_thd",
        source_tool="analyze_harmonic_distortion",
        metric="thd_percent",
        value=4.99,
        unit="%",
    )
    batch = engine.evaluate_profile(profile, [ratio_evidence, thd_evidence])
    ratio_eval = next(e for e in batch.evaluations if e.rule_id == "rule_clipping_ratio_acceptable")
    thd_eval = next(e for e in batch.evaluations if e.rule_id == "rule_thd_acceptable")
    assert ratio_eval.judgment == "pass"
    assert thd_eval.judgment == "pass"


@pytest.mark.parametrize(
    ("comparator", "observed", "threshold", "expected"),
    [
        ("lt", 0.5, 1.0, "pass"),
        ("lt", 1.0, 1.0, "fail"),
        ("lte", 1.0, 1.0, "pass"),
        ("gt", 2.0, 1.0, "pass"),
        ("gte", 1.0, 1.0, "pass"),
        ("eq", True, True, "pass"),
        ("eq", True, False, "fail"),
        ("neq", 1.0, 2.0, "pass"),
        ("neq", 1.0, 1.0, "fail"),
    ],
)
def test_t096_comparator_pass_semantics(
    comparator: str,
    observed: EvidenceValue,
    threshold: EvidenceValue,
    expected: str,
) -> None:
    rule = RuleDefinition(
        rule_id="rule_cmp",
        metric="value",
        source_tool="detect_clipping",
        comparator=comparator,  # type: ignore[arg-type]
        threshold=threshold,
        description="comparator test",
    )
    evidence = make_evidence(metric="value", value=observed)
    evaluation = evaluate_one(rule=rule, evidence=evidence, profile=SINGLE_RULE_PROFILE)
    assert evaluation.judgment == expected


def test_t098_pass_on_valid_evidence() -> None:
    evidence = make_evidence(value=0.005)
    evaluation = evaluate_one(rule=RATIO_RULE, evidence=evidence, profile=SINGLE_RULE_PROFILE)
    assert evaluation.judgment == "pass"
    assert evaluation.evidence_refs == (evidence.evidence_id,)
    assert evaluation.observed_value == 0.005
    assert evaluation.reason is None


def test_t099_fail_on_valid_evidence() -> None:
    evidence = make_evidence(value=0.02)
    evaluation = evaluate_one(rule=RATIO_RULE, evidence=evidence, profile=SINGLE_RULE_PROFILE)
    assert evaluation.judgment == "fail"
    assert evaluation.evidence_refs == (evidence.evidence_id,)
    assert evaluation.reason is None


def test_t100_no_matching_evidence() -> None:
    engine = RuleEngine()
    batch = engine.evaluate_profile(SINGLE_RULE_PROFILE, [])
    assert len(batch.evaluations) == 1
    evaluation = batch.evaluations[0]
    assert evaluation.judgment == "not_applicable"
    assert evaluation.evidence_refs == ()
    assert evaluation.observed_value is None
    assert evaluation.reason


def test_t101_invalid_evidence_is_not_applicable() -> None:
    evidence = make_evidence(value=0.5, validity="not_applicable")
    evaluation = evaluate_one(rule=RATIO_RULE, evidence=evidence, profile=SINGLE_RULE_PROFILE)
    assert evaluation.judgment == "not_applicable"
    assert evaluation.evidence_refs == (evidence.evidence_id,)
    assert evaluation.reason


@pytest.mark.parametrize(
    ("observed", "threshold", "unit"),
    [(1, 1.0, None), (True, 1, None), (5.0, 5.0, "Hz")],
)
def test_t101_incompatible_evidence_is_not_applicable(
    observed: EvidenceValue,
    threshold: EvidenceValue,
    unit: str | None,
) -> None:
    rule = RuleDefinition(
        rule_id="rule_compat",
        metric="value",
        source_tool="detect_clipping",
        comparator="lte",
        threshold=threshold,
        unit=unit,
        description="compat test",
    )
    evidence = make_evidence(value=observed, unit="%" if unit else None)
    evaluation = evaluate_one(rule=rule, evidence=evidence, profile=SINGLE_RULE_PROFILE)
    assert evaluation.judgment == "not_applicable"
    assert evaluation.evidence_refs == (evidence.evidence_id,)
    assert evaluation.reason


def test_t102_multiple_matching_evidence() -> None:
    first = make_evidence(evidence_id="ev_first", value=0.005)
    second = make_evidence(evidence_id="ev_second", value=0.02)
    engine = RuleEngine()
    batch = engine.evaluate_profile(SINGLE_RULE_PROFILE, [first, second])
    ratio_evals = [e for e in batch.evaluations if e.rule_id == "rule_ratio"]
    assert len(ratio_evals) == 2
    assert ratio_evals[0].evidence_refs == ("ev_first",)
    assert ratio_evals[0].judgment == "pass"
    assert ratio_evals[1].evidence_refs == ("ev_second",)
    assert ratio_evals[1].judgment == "fail"


def test_t103_evidence_filter() -> None:
    included = make_evidence(evidence_id="ev_included", value=0.005)
    excluded = make_evidence(evidence_id="ev_excluded", value=0.02)
    engine = RuleEngine()
    batch = engine.evaluate_profile(
        SINGLE_RULE_PROFILE,
        [included, excluded],
        evidence_filter=frozenset({"ev_included"}),
    )
    ratio_evals = [e for e in batch.evaluations if e.rule_id == "rule_ratio"]
    assert len(ratio_evals) == 1
    assert ratio_evals[0].evidence_refs == ("ev_included",)
    assert ratio_evals[0].judgment == "pass"


def test_t104_deterministic_batch_output() -> None:
    evidence = make_evidence(value=0.005)
    engine = RuleEngine()
    first = engine.evaluate_profile(SINGLE_RULE_PROFILE, [evidence])
    second = engine.evaluate_profile(SINGLE_RULE_PROFILE, [evidence])
    assert first.model_dump(exclude={"batch_id"}) == second.model_dump(exclude={"batch_id"})
    for left, right in zip(first.evaluations, second.evaluations, strict=True):
        assert left.model_dump(exclude={"evaluation_id"}) == right.model_dump(
            exclude={"evaluation_id"}
        )


def test_t105_engine_isolation() -> None:
    engine_path = PROJECT_ROOT / "src" / "signal_diag" / "rules" / "engine.py"
    source = engine_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(engine_path))
    forbidden_prefixes = (
        "signal_diag.agent",
        "signal_diag.dsp",
        "signal_diag.evaluation",
        "signal_diag.app",
    )
    llm_markers = ("openai", "langchain", "langgraph")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules = [node.module]
        else:
            continue
        for module in modules:
            for prefix in forbidden_prefixes:
                assert not (
                    module == prefix or module.startswith(f"{prefix}.")
                ), f"forbidden import: {module}"
            for marker in llm_markers:
                assert marker not in module.lower(), f"forbidden import: {module}"
