"""T220 — versioned invalid-Evidence scoring policy 2.0.0."""

from __future__ import annotations

import inspect

import pytest

from signal_diag.evaluation import score_evaluation_trace
from signal_diag.evaluation.models import EvaluationTrace, RunScore
from signal_diag.evaluation.runner import (
    _run_deterministic_benchmark,
    _run_real_benchmark_for_split,
)
from signal_diag.rules.models import RuleEvaluation, RuleEvaluationBatch
from tests.evaluation.test_scoring import (
    _agent_trace,
    _baseline_trace,
    _claim,
    _clip_ev,
    _evidence,
    _legal_clipping_trace,
    _legal_noise_trace,
    _noise_case,
    _observation,
    _retrieval,
    _rule_batch,
)

_SCORING_KEY = "signal_diag.scoring"
_SCORING_V2 = "2.0.0"

# Pre-change public literals from legal clipping/noise traces at Task 3 start.
_LEGACY_CLIPPING = {
    "correct_rule_actions": 1,
    "rule_action_opportunities": 1,
    "failure_codes": (),
    "causal_exact_set_correct": True,
    "outcome_correct": True,
    "first_tool_correct": True,
    "appropriate_replans": 2,
    "replan_opportunities": 2,
    "unnecessary_tool_actions": 0,
    "tool_actions": 1,
    "timely_stop": True,
    "required_knowledge_actions": 0,
    "required_knowledge_opportunities": 0,
    "unnecessary_knowledge_actions": 0,
    "knowledge_actions": 0,
    "cited_knowledge_actions": 0,
    "planner_calls": 3,
    "grounded_claims": 1,
    "scored_claims": 1,
    "unsupported_fault_claims": 0,
    "predicted_fault_claims": 1,
    "predicted_faults": ("clipping",),
    "predicted_outcome": "supported_fault",
    "expected_faults": ("clipping",),
    "completion_reason": "planner_finished",
    "execution_path": "agent",
}
_LEGACY_NOISE = {
    "correct_rule_actions": 1,
    "rule_action_opportunities": 1,
    "failure_codes": (),
    "causal_exact_set_correct": True,
    "outcome_correct": True,
    "first_tool_correct": True,
    "appropriate_replans": 3,
    "replan_opportunities": 3,
    "unnecessary_tool_actions": 0,
    "tool_actions": 1,
    "timely_stop": True,
    "required_knowledge_actions": 1,
    "required_knowledge_opportunities": 1,
    "unnecessary_knowledge_actions": 0,
    "knowledge_actions": 1,
    "cited_knowledge_actions": 1,
    "planner_calls": 4,
    "grounded_claims": 1,
    "scored_claims": 1,
    "unsupported_fault_claims": 0,
    "predicted_fault_claims": 0,
    "predicted_faults": (),
    "predicted_outcome": "inconclusive",
    "expected_faults": (),
    "completion_reason": "planner_finished",
    "execution_path": "agent",
}


def _assert_literals(score: RunScore, expected: dict[str, object]) -> None:
    for key, value in expected.items():
        assert getattr(score, key) == value, key


def _with_sdk_versions(
    trace: EvaluationTrace, sdk_versions: dict[str, str]
) -> EvaluationTrace:
    config = trace.config.model_copy(update={"sdk_versions": dict(sdk_versions)})
    return trace.model_copy(update={"config": config})


def _not_applicable_batch(
    batch_id: str, evaluation_id: str, evidence_refs: tuple[str, ...]
) -> RuleEvaluationBatch:
    return RuleEvaluationBatch(
        batch_id=batch_id,
        profile_id="profile_s1_distortion",
        profile_version="1.0.0-demo",
        evaluations=(
            RuleEvaluation(
                evaluation_id=evaluation_id,
                rule_id="rule_harmonic_thd_percent",
                judgment="not_applicable",
                observed_value=None,
                comparator="gt",
                threshold=5.0,
                profile_id="profile_s1_distortion",
                profile_version="1.0.0-demo",
                evidence_refs=evidence_refs,
                reason="harmonic analysis was not applicable",
            ),
        ),
    )


def _invalid_harmonic_evidence(evidence_id: str = "ev_noise") -> object:
    return _evidence(
        evidence_id=evidence_id,
        call_id="call_000",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        value=False,
        validity="not_applicable",
    )


def _invalid_noise_agent_trace(
    sdk_versions: dict[str, str],
) -> tuple[object, EvaluationTrace]:
    case = _noise_case()
    evidence = _invalid_harmonic_evidence()
    batch = _not_applicable_batch("rulebatch_noise", "ruleval_noise", ("ev_noise",))
    retrieval = _retrieval(retrieval_id="know_noise", tags=case.knowledge_tags)
    claims = (
        _claim(
            claim_id="claim_noise",
            fault_type="inconclusive",
            evidence_refs=("ev_noise",),
            rule_refs=("ruleval_noise",),
            knowledge_refs=("know_noise",),
        ),
    )
    trace = _agent_trace(
        case,
        (
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (evidence,),
                "status": "invalid",
            },
            {"kind": "rules", "batch": batch},
            {"kind": "knowledge", "retrieval": retrieval},
            {"kind": "finish"},
        ),
        claims=claims,
        outcome="inconclusive",
    )
    return case, _with_sdk_versions(trace, sdk_versions)


def _invalid_noise_baseline_trace(
    sdk_versions: dict[str, str],
) -> tuple[object, EvaluationTrace]:
    case = _noise_case()
    evidence = _invalid_harmonic_evidence()
    observation = _observation(
        observation_id="obs_000",
        call_id="call_000",
        tool_name="analyze_harmonic_distortion",
        evidence_ids=("ev_noise",),
        status="invalid",
    )
    batch = _not_applicable_batch("rulebatch_noise", "ruleval_noise", ("ev_noise",))
    claims = (
        _claim(
            claim_id="claim_noise",
            fault_type="inconclusive",
            evidence_refs=("ev_noise",),
            rule_refs=("ruleval_noise",),
        ),
    )
    trace = _baseline_trace(
        case,
        observations=(observation,),
        evidence=(evidence,),
        batches=(batch,),
        claims=claims,
        outcome="inconclusive",
    )
    return case, _with_sdk_versions(trace, sdk_versions)


def test_t220_public_signature_remains_case_trace() -> None:
    signature = inspect.signature(score_evaluation_trace)
    assert tuple(signature.parameters) == ("case", "trace")


@pytest.mark.parametrize(
    "sdk_versions",
    [{}, {"openai": "1.0.0"}],
)
def test_t220_legacy_clipping_and_noise_literals(
    sdk_versions: dict[str, str],
) -> None:
    clip_case, clip_trace = _legal_clipping_trace()
    noise_case, noise_trace = _legal_noise_trace()
    assert _SCORING_KEY not in clip_trace.config.sdk_versions
    assert _SCORING_KEY not in noise_trace.config.sdk_versions
    clip = score_evaluation_trace(clip_case, _with_sdk_versions(clip_trace, sdk_versions))
    noise = score_evaluation_trace(
        noise_case, _with_sdk_versions(noise_trace, sdk_versions)
    )
    _assert_literals(clip, _LEGACY_CLIPPING)
    _assert_literals(noise, _LEGACY_NOISE)


@pytest.mark.parametrize(
    "sdk_versions",
    [{}, {"openai": "1.0.0"}],
)
def test_t220_legacy_invalid_observation_is_not_rule_eligible(
    sdk_versions: dict[str, str],
) -> None:
    case, trace = _invalid_noise_agent_trace(sdk_versions)
    assert _SCORING_KEY not in trace.config.sdk_versions
    assert trace.events[1].observation.status == "invalid"
    score = score_evaluation_trace(case, trace)
    assert score.correct_rule_actions == 0
    assert "premature_rule" in score.failure_codes


def test_t220_scoring_2_0_0_invalid_evidence_is_rule_eligible() -> None:
    case, trace = _invalid_noise_agent_trace({_SCORING_KEY: _SCORING_V2})
    events = list(trace.events)
    assert events[0].record.decision.call.tool_name == "analyze_harmonic_distortion"
    assert events[1].observation.status == "invalid"
    assert events[1].evidence[0].validity == "not_applicable"
    assert events[2].record.decision.evidence_refs == ("ev_noise",)
    assert events[3].batch.evaluations[0].judgment == "not_applicable"
    assert events[3].batch.evaluations[0].evidence_refs == ("ev_noise",)
    assert events[5].retrieval.retrieval_id == "know_noise"
    finish = events[6].record.decision
    assert finish.outcome == "inconclusive"
    assert finish.claims[0].evidence_refs == ("ev_noise",)
    assert finish.claims[0].rule_refs == ("ruleval_noise",)
    assert finish.claims[0].knowledge_refs == ("know_noise",)

    score = score_evaluation_trace(case, trace)
    assert score.correct_rule_actions == 1
    assert score.rule_action_opportunities == 1
    assert "premature_rule" not in score.failure_codes
    assert "inappropriate_replan" not in score.failure_codes
    assert "omitted_rule" not in score.failure_codes


def test_t220_scoring_2_0_0_rule_before_evidence_is_premature() -> None:
    case, _ = _legal_clipping_trace()
    evidence = _clip_ev("ev_clip", "call_000", detected=True)
    premature_batch = _rule_batch("rulebatch_pre", "ruleval_pre", ("ev_placeholder",))
    later_batch = _rule_batch("rulebatch_clip", "ruleval_clip", ("ev_clip",))
    trace = _agent_trace(
        case,
        (
            {"kind": "rules", "batch": premature_batch},
            {"kind": "tool", "tool_name": "detect_clipping", "evidence": (evidence,)},
            {"kind": "rules", "batch": later_batch},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_clip",
                fault_type="clipping",
                evidence_refs=("ev_clip",),
                rule_refs=("ruleval_clip",),
            ),
        ),
        outcome="supported_fault",
    )
    score = score_evaluation_trace(
        case, _with_sdk_versions(trace, {_SCORING_KEY: _SCORING_V2})
    )
    assert "premature_rule" in score.failure_codes
    assert score.correct_rule_actions == 1
    assert score.rule_action_opportunities == 2


def test_t220_scoring_2_0_0_repeated_invalid_rule_state_is_redundant() -> None:
    case = _noise_case()
    evidence = _invalid_harmonic_evidence()
    first = _not_applicable_batch("rulebatch_noise_a", "ruleval_noise_a", ("ev_noise",))
    second = _not_applicable_batch("rulebatch_noise_b", "ruleval_noise_b", ("ev_noise",))
    retrieval = _retrieval(retrieval_id="know_noise", tags=case.knowledge_tags)
    trace = _agent_trace(
        case,
        (
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (evidence,),
                "status": "invalid",
            },
            {"kind": "rules", "batch": first},
            {"kind": "rules", "batch": second},
            {"kind": "knowledge", "retrieval": retrieval},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_noise",
                fault_type="inconclusive",
                evidence_refs=("ev_noise",),
                rule_refs=("ruleval_noise_a",),
                knowledge_refs=("know_noise",),
            ),
        ),
        outcome="inconclusive",
    )
    score = score_evaluation_trace(
        case, _with_sdk_versions(trace, {_SCORING_KEY: _SCORING_V2})
    )
    assert "redundant_rule" in score.failure_codes
    assert "premature_rule" not in score.failure_codes
    assert score.correct_rule_actions == 1
    assert score.rule_action_opportunities == 2


@pytest.mark.parametrize("policy", ["9.9.9", "1.0.0"])
def test_t220_unknown_scoring_version_raises(policy: str) -> None:
    case, trace = _legal_clipping_trace()
    unknown = _with_sdk_versions(trace, {_SCORING_KEY: policy})
    with pytest.raises(ValueError, match=f"unsupported scoring policy: {policy}"):
        score_evaluation_trace(case, unknown)


def test_t220_fixed_pipeline_shares_invalid_rule_eligibility() -> None:
    versions = {_SCORING_KEY: _SCORING_V2}
    agent_case, agent_trace = _invalid_noise_agent_trace(versions)
    baseline_case, baseline_trace = _invalid_noise_baseline_trace(versions)
    agent = score_evaluation_trace(agent_case, agent_trace)
    baseline = score_evaluation_trace(baseline_case, baseline_trace)
    assert baseline.execution_path == "fixed_pipeline"
    assert agent.correct_rule_actions == baseline.correct_rule_actions == 1
    assert agent.rule_action_opportunities == baseline.rule_action_opportunities == 1
    assert "premature_rule" not in agent.failure_codes
    assert "premature_rule" not in baseline.failure_codes
    assert "omitted_rule" not in agent.failure_codes
    assert "omitted_rule" not in baseline.failure_codes


def test_t220_invalid_evidence_does_not_satisfy_causal_set() -> None:
    case = _noise_case()
    first = _invalid_harmonic_evidence("ev_noise")
    second = _evidence(
        evidence_id="ev_noise_follow",
        call_id="call_001",
        tool_name="analyze_harmonic_distortion",
        metric="valid",
        value=False,
        validity="not_applicable",
    )
    batch = _not_applicable_batch(
        "rulebatch_noise", "ruleval_noise", ("ev_noise", "ev_noise_follow")
    )
    retrieval = _retrieval(retrieval_id="know_noise", tags=case.knowledge_tags)
    trace = _agent_trace(
        case,
        (
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (first,),
                "status": "invalid",
            },
            {
                "kind": "tool",
                "tool_name": "analyze_harmonic_distortion",
                "evidence": (second,),
                "status": "invalid",
            },
            {"kind": "rules", "batch": batch},
            {"kind": "knowledge", "retrieval": retrieval},
            {"kind": "finish"},
        ),
        claims=(
            _claim(
                claim_id="claim_noise",
                fault_type="inconclusive",
                evidence_refs=("ev_noise",),
                rule_refs=("ruleval_noise",),
                knowledge_refs=("know_noise",),
            ),
        ),
        outcome="inconclusive",
    )
    score = score_evaluation_trace(
        case, _with_sdk_versions(trace, {_SCORING_KEY: _SCORING_V2})
    )
    assert "late_tool_after_sufficiency" not in score.failure_codes
    assert score.timely_stop is True
    assert score.correct_rule_actions == 1


def test_t220_runner_and_offline_share_scoring_dispatch() -> None:
    real_src = inspect.getsource(_run_real_benchmark_for_split)
    det_src = inspect.getsource(_run_deterministic_benchmark)
    assert "score_evaluation_trace(cases[case_id], trace)" in real_src
    assert "score_evaluation_trace(cases[trace.case_id], trace)" in det_src
    assert "score_evaluation_trace(cases[case_id], trace)" in det_src
    assert "include_invalid_rule_evidence" not in real_src
    assert "include_invalid_rule_evidence" not in det_src
    assert _SCORING_KEY not in real_src
    assert _SCORING_KEY not in det_src

    versions = {_SCORING_KEY: _SCORING_V2}
    agent_case, agent_trace = _invalid_noise_agent_trace(versions)
    baseline_case, baseline_trace = _invalid_noise_baseline_trace(versions)
    assert agent_trace.config.sdk_versions == versions
    assert baseline_trace.config.sdk_versions == versions
    offline_agent = score_evaluation_trace(agent_case, agent_trace)
    runner_agent = score_evaluation_trace(agent_case, agent_trace)
    offline_baseline = score_evaluation_trace(baseline_case, baseline_trace)
    runner_baseline = score_evaluation_trace(baseline_case, baseline_trace)
    assert offline_agent == runner_agent
    assert offline_baseline == runner_baseline
    assert offline_agent.correct_rule_actions == 1
    assert offline_baseline.correct_rule_actions == 1

    clip_case, clip_trace = _legal_clipping_trace()
    noise_case, noise_trace = _legal_noise_trace()
    assert _SCORING_KEY not in clip_trace.config.sdk_versions
    assert _SCORING_KEY not in noise_trace.config.sdk_versions
    _assert_literals(score_evaluation_trace(clip_case, clip_trace), _LEGACY_CLIPPING)
    _assert_literals(score_evaluation_trace(noise_case, noise_trace), _LEGACY_NOISE)
