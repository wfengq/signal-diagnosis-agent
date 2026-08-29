"""Checkpoint K — honest fixed-pipeline baseline (T149–T154)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from signal_diag.evaluation import (
    BaselineDiagnosis,
    BaselineRunResult,
    FixedPipelineBaseline,
)
from signal_diag.evaluation.models import BaselineCompletionReason
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.rules.models import RuleEvaluationBatch, RuleProfile
from signal_diag.signal import (
    InMemorySignalRepository,
    generate_clipped_sine,
    generate_sine,
)
from signal_diag.tools.contracts import (
    ClippingInput,
    ClippingOutput,
    HarmonicDistortionInput,
    HarmonicDistortionOutput,
)
from signal_diag.tools.evidence import Evidence, EvidenceValue
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService
from tests.conftest import store_synthetic_case

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = (
    PROJECT_ROOT
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)
_OFFICIAL_PROFILE_ID = "profile_s1_distortion"
_CLIPPING_RULE_IDS = frozenset(
    {
        "rule_clipping_detected_absent",
        "rule_clipping_ratio_acceptable",
        "rule_flat_top_absent",
    }
)
_USER_REQUEST = "Diagnose this signal."


class PrivilegedRepository:
    """Forwards storage; raises if manifest truth or matched controls are read."""

    def __init__(self, inner: InMemorySignalRepository) -> None:
        self._inner = inner

    @property
    def causal_faults(self) -> object:
        raise AssertionError("baseline must not read manifest causal_faults")

    @property
    def matched_control(self) -> object:
        raise AssertionError("baseline must not read matched-control data")

    @property
    def generator_ground_truth(self) -> object:
        raise AssertionError("baseline must not read generator ground truth")

    def put(self, record: object) -> None:
        self._inner.put(record)  # type: ignore[arg-type]

    def get(self, signal_id: str) -> object:
        return self._inner.get(signal_id)

    def exists(self, signal_id: str) -> bool:
        return self._inner.exists(signal_id)

    def remove(self, signal_id: str) -> None:
        self._inner.remove(signal_id)

    def list_meta(self) -> list[object]:
        return self._inner.list_meta()


class SpyToolService:
    def __init__(self, inner: SignalToolService) -> None:
        self._inner = inner
        self.calls: list[tuple[str, str, object]] = []

    def detect_clipping(self, signal_id: str, args: ClippingInput) -> object:
        self.calls.append(("detect_clipping", signal_id, args))
        return self._inner.detect_clipping(signal_id, args)

    def analyze_harmonic_distortion(
        self,
        signal_id: str,
        args: HarmonicDistortionInput,
    ) -> object:
        self.calls.append(("analyze_harmonic_distortion", signal_id, args))
        return self._inner.analyze_harmonic_distortion(signal_id, args)

    def analyze_spectrum(self, signal_id: str, args: object) -> object:
        raise AssertionError("baseline must not call analyze_spectrum / FFT")

    def estimate_fundamental(self, signal_id: str, args: object) -> object:
        raise AssertionError("baseline must not call estimate_fundamental / F0")


class SpyLoader:
    def __init__(self, inner: YamlRuleProfileLoader) -> None:
        self._inner = inner
        self.calls: list[str] = []

    def load(self, profile_id: str) -> RuleProfile:
        self.calls.append(profile_id)
        return self._inner.load(profile_id)


class SpyEngine:
    def __init__(self, inner: RuleEngine) -> None:
        self._inner = inner
        self.calls: list[tuple[str, str, tuple[str, ...], frozenset[str] | None]] = []

    def evaluate_profile(
        self,
        profile: RuleProfile,
        evidence: object,
        *,
        evidence_filter: frozenset[str] | None = None,
    ) -> RuleEvaluationBatch:
        evidence_ids = tuple(item.evidence_id for item in evidence)  # type: ignore[union-attr]
        self.calls.append(
            (profile.profile_id, profile.version, evidence_ids, evidence_filter)
        )
        return self._inner.evaluate_profile(
            profile,
            evidence,  # type: ignore[arg-type]
            evidence_filter=evidence_filter,
        )


class ScriptedToolService:
    def __init__(
        self,
        clipping: ToolResult[ClippingOutput],
        harmonic: ToolResult[HarmonicDistortionOutput],
    ) -> None:
        self._clipping = clipping
        self._harmonic = harmonic
        self.calls: list[tuple[str, str, object]] = []

    def detect_clipping(
        self,
        signal_id: str,
        args: ClippingInput,
    ) -> ToolResult[ClippingOutput]:
        self.calls.append(("detect_clipping", signal_id, args))
        return self._clipping

    def analyze_harmonic_distortion(
        self,
        signal_id: str,
        args: HarmonicDistortionInput,
    ) -> ToolResult[HarmonicDistortionOutput]:
        self.calls.append(("analyze_harmonic_distortion", signal_id, args))
        return self._harmonic

    def analyze_spectrum(self, signal_id: str, args: object) -> object:
        raise AssertionError("baseline must not call analyze_spectrum / FFT")

    def estimate_fundamental(self, signal_id: str, args: object) -> object:
        raise AssertionError("baseline must not call estimate_fundamental / F0")


def _official_loader() -> YamlRuleProfileLoader:
    return YamlRuleProfileLoader({_OFFICIAL_PROFILE_ID: PROFILE_PATH})


def _evidence(
    *,
    evidence_id: str,
    source_tool: str,
    call_id: str,
    metric: str,
    value: EvidenceValue,
    unit: str | None = None,
    validity: str = "valid",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_tool=source_tool,  # type: ignore[arg-type]
        call_id=call_id,
        metric=metric,
        value=value,
        unit=unit,
        validity=validity,  # type: ignore[arg-type]
        channel="mixdown",
    )


def _clipping_result(
    *,
    detected: bool,
    ratio: float,
    flat_top: bool,
    validity: str = "valid",
) -> ToolResult[ClippingOutput]:
    call_id = "call_detect_clipping_000000"
    output = ClippingOutput(
        detected=detected,
        clipping_ratio=ratio,
        clipped_samples=10 if detected else 0,
        clipping_events=1 if detected else 0,
        longest_event_samples=4 if detected else 0,
        peak_abs=1.0 if detected else 0.4,
        full_scale_detected=False,
        flat_top_detected=flat_top,
    )
    evidence = (
        _evidence(
            evidence_id="ev_clip_detected",
            source_tool="detect_clipping",
            call_id=call_id,
            metric="clipping_detected",
            value=detected,
            validity=validity,
        ),
        _evidence(
            evidence_id="ev_clip_ratio",
            source_tool="detect_clipping",
            call_id=call_id,
            metric="clipping_ratio",
            value=ratio,
            validity=validity,
        ),
        _evidence(
            evidence_id="ev_clip_flat",
            source_tool="detect_clipping",
            call_id=call_id,
            metric="flat_top_detected",
            value=flat_top,
            validity=validity,
        ),
    )
    return ToolResult(
        call_id=call_id,
        tool_name="detect_clipping",
        status="success",
        result=output,
        evidence=evidence,
    )


def _harmonic_result(
    *,
    valid: bool,
    thd_percent: float | None,
) -> ToolResult[HarmonicDistortionOutput]:
    call_id = "call_analyze_harmonic_distortion_000001"
    if not valid:
        output = HarmonicDistortionOutput(
            valid=False,
            invalid_reason="spectrum is not suitable for harmonic analysis",
            fundamental_frequency_hz=None,
            thd_percent=None,
            components=(),
        )
        return ToolResult(
            call_id=call_id,
            tool_name="analyze_harmonic_distortion",
            status="invalid",
            result=output,
            evidence=(
                _evidence(
                    evidence_id="ev_harm_valid",
                    source_tool="analyze_harmonic_distortion",
                    call_id=call_id,
                    metric="valid",
                    value=False,
                    validity="not_applicable",
                ),
            ),
            warnings=("spectrum is not suitable for harmonic analysis",),
        )
    assert thd_percent is not None
    output = HarmonicDistortionOutput(
        valid=True,
        invalid_reason=None,
        fundamental_frequency_hz=200.0,
        thd_percent=thd_percent,
        components=(),
    )
    return ToolResult(
        call_id=call_id,
        tool_name="analyze_harmonic_distortion",
        status="success",
        result=output,
        evidence=(
            _evidence(
                evidence_id="ev_harm_valid",
                source_tool="analyze_harmonic_distortion",
                call_id=call_id,
                metric="valid",
                value=True,
            ),
            _evidence(
                evidence_id="ev_harm_thd",
                source_tool="analyze_harmonic_distortion",
                call_id=call_id,
                metric="thd_percent",
                value=thd_percent,
                unit="%",
            ),
        ),
    )


def _scripted_baseline(
    clipping: ToolResult[ClippingOutput],
    harmonic: ToolResult[HarmonicDistortionOutput],
) -> tuple[FixedPipelineBaseline, ScriptedToolService]:
    tools = ScriptedToolService(clipping, harmonic)
    baseline = FixedPipelineBaseline(
        repository=InMemorySignalRepository(),
        tool_service=tools,  # type: ignore[arg-type]
        rule_engine=RuleEngine(),
        profile_loader=_official_loader(),
    )
    return baseline, tools


def _real_stack(
    *,
    store: Callable[[InMemorySignalRepository], str] | None = None,
) -> tuple[FixedPipelineBaseline, SpyToolService, SpyLoader, SpyEngine, str]:
    inner_repo = InMemorySignalRepository()
    signal_id = store(inner_repo) if store is not None else store_synthetic_case(
        inner_repo,
        generate_sine(frequency_hz=200.0, amplitude=0.5),
    )
    repo = PrivilegedRepository(inner_repo)
    tools = SpyToolService(SignalToolService(inner_repo))
    loader = SpyLoader(_official_loader())
    engine = SpyEngine(RuleEngine())
    baseline = FixedPipelineBaseline(
        repository=repo,  # type: ignore[arg-type]
        tool_service=tools,  # type: ignore[arg-type]
        rule_engine=engine,  # type: ignore[arg-type]
        profile_loader=loader,  # type: ignore[arg-type]
    )
    return baseline, tools, loader, engine, signal_id


def _fault_types(result: BaselineRunResult) -> tuple[str, ...]:
    assert result.diagnosis is not None
    return tuple(claim.fault_type for claim in result.diagnosis.claims)


def _assert_same_run_refs(result: BaselineRunResult) -> None:
    evidence_ids = {item.evidence_id for item in result.evidence}
    rule_ids = {
        evaluation.evaluation_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    assert result.diagnosis is not None
    for claim in result.diagnosis.claims:
        assert claim.knowledge_refs == ()
        for ref in claim.evidence_refs:
            assert ref in evidence_ids
        for ref in claim.rule_refs:
            assert ref in rule_ids


def _assert_baseline_shape(result: BaselineRunResult) -> None:
    assert isinstance(result, BaselineRunResult)
    assert result.result_type == "fixed_pipeline"
    assert result.run_id.startswith("baseline_")
    assert result.completion_reason in {
        "baseline_completed",
        "insufficient_evidence",
        "runtime_error",
    }
    assert result.completion_reason != "planner_finished"
    assert len(result.observations) == 2
    assert [item.tool_name for item in result.observations] == [
        "detect_clipping",
        "analyze_harmonic_distortion",
    ]
    assert len(result.tool_history) == 2
    assert len(result.rule_evaluation_batches) == 1
    batch = result.rule_evaluation_batches[0]
    assert batch.profile_id == _OFFICIAL_PROFILE_ID
    assert batch.profile_version == "1.0.0-demo"
    assert result.diagnosis is not None
    assert isinstance(result.diagnosis, BaselineDiagnosis)
    assert result.diagnosis.run_id == result.run_id
    assert result.diagnosis.tool_call_count == 2
    assert result.diagnosis.rule_evaluation_batches == result.rule_evaluation_batches
    assert result.observations[0].normalized_arguments == ClippingInput().model_dump(
        mode="json"
    )
    assert result.observations[1].normalized_arguments == (
        HarmonicDistortionInput().model_dump(mode="json")
    )
    _assert_same_run_refs(result)


def _cited_rule_ids(result: BaselineRunResult, fault_type: str) -> set[str]:
    assert result.diagnosis is not None
    claim = next(item for item in result.diagnosis.claims if item.fault_type == fault_type)
    evaluations = {
        evaluation.evaluation_id: evaluation.rule_id
        for batch in result.rule_evaluation_batches
        for evaluation in batch.evaluations
    }
    return {evaluations[ref] for ref in claim.rule_refs}


@pytest.mark.asyncio
async def test_t149_fixed_tool_order() -> None:
    baseline, tools, _loader, _engine, signal_id = _real_stack()
    result = await baseline.run(signal_id=signal_id, user_request=_USER_REQUEST)
    assert tools.calls == [
        ("detect_clipping", signal_id, ClippingInput()),
        ("analyze_harmonic_distortion", signal_id, HarmonicDistortionInput()),
    ]
    assert [entry.tool_name for entry in result.tool_history] == [
        "detect_clipping",
        "analyze_harmonic_distortion",
    ]


@pytest.mark.asyncio
async def test_t150_shared_injected_dependencies() -> None:
    baseline, tools, loader, engine, signal_id = _real_stack()
    result = await baseline.run(signal_id=signal_id, user_request=_USER_REQUEST)
    assert loader.calls == [_OFFICIAL_PROFILE_ID]
    assert len(engine.calls) == 1
    profile_id, version, evidence_ids, evidence_filter = engine.calls[0]
    assert profile_id == _OFFICIAL_PROFILE_ID
    assert version == "1.0.0-demo"
    assert evidence_filter is None
    assert evidence_ids == tuple(item.evidence_id for item in result.evidence)
    assert set(evidence_ids) == {item.evidence_id for item in result.evidence}
    _assert_baseline_shape(result)
    assert tools.calls[0][0] == "detect_clipping"


@pytest.mark.parametrize(
    (
        "clipping_kwargs",
        "harmonic_kwargs",
        "expected_faults",
        "expected_outcome",
        "expected_reason",
        "expect_limitation",
        "expected_status",
    ),
    [
        (
            {"detected": True, "ratio": 0.2, "flat_top": True},
            {"valid": True, "thd_percent": 12.0},
            ("clipping", "harmonic_distortion"),
            "supported_fault",
            "baseline_completed",
            False,
            "success",
        ),
        (
            {"detected": True, "ratio": 0.2, "flat_top": True},
            {"valid": True, "thd_percent": 1.0},
            ("clipping",),
            "supported_fault",
            "baseline_completed",
            False,
            "success",
        ),
        (
            {"detected": False, "ratio": 0.0, "flat_top": False},
            {"valid": True, "thd_percent": 12.0},
            ("harmonic_distortion",),
            "supported_fault",
            "baseline_completed",
            False,
            "success",
        ),
        (
            {"detected": False, "ratio": 0.0, "flat_top": False},
            {"valid": True, "thd_percent": 1.0},
            ("no_supported_fault",),
            "no_supported_fault",
            "baseline_completed",
            False,
            "success",
        ),
        (
            {"detected": True, "ratio": 0.2, "flat_top": True},
            {"valid": False, "thd_percent": None},
            ("clipping",),
            "supported_fault",
            "baseline_completed",
            True,
            "success",
        ),
        (
            {"detected": False, "ratio": 0.0, "flat_top": False},
            {"valid": False, "thd_percent": None},
            ("inconclusive",),
            "inconclusive",
            "insufficient_evidence",
            True,
            "inconclusive",
        ),
        (
            {
                "detected": False,
                "ratio": 0.0,
                "flat_top": False,
                "validity": "not_applicable",
            },
            {"valid": False, "thd_percent": None},
            ("inconclusive",),
            "inconclusive",
            "insufficient_evidence",
            True,
            "inconclusive",
        ),
    ],
    ids=[
        "clipping_and_harmonic",
        "clipping_only",
        "harmonic_only",
        "no_supported_fault",
        "clipping_invalid_harmonic",
        "inconclusive_invalid_harmonic",
        "inconclusive_clipping_unavailable",
    ],
)
@pytest.mark.asyncio
async def test_t151_t152_deterministic_mapping(
    clipping_kwargs: dict[str, Any],
    harmonic_kwargs: dict[str, Any],
    expected_faults: tuple[str, ...],
    expected_outcome: str,
    expected_reason: BaselineCompletionReason,
    expect_limitation: bool,
    expected_status: str,
) -> None:
    baseline, tools = _scripted_baseline(
        _clipping_result(**clipping_kwargs),
        _harmonic_result(**harmonic_kwargs),
    )
    result = await baseline.run(signal_id="sig_map_row", user_request=_USER_REQUEST)
    assert tools.calls == [
        ("detect_clipping", "sig_map_row", ClippingInput()),
        ("analyze_harmonic_distortion", "sig_map_row", HarmonicDistortionInput()),
    ]
    _assert_baseline_shape(result)
    assert result.status == expected_status
    assert result.completion_reason == expected_reason
    assert result.diagnosis is not None
    assert result.diagnosis.outcome == expected_outcome
    assert _fault_types(result) == expected_faults
    if expect_limitation:
        assert result.diagnosis.limitations
        joined = " ".join(result.diagnosis.limitations).lower()
        assert "harmonic" in joined
    else:
        assert result.diagnosis.limitations == ()
    if not harmonic_kwargs["valid"]:
        assert not any(item.metric == "thd_percent" for item in result.evidence)
    if "clipping" in expected_faults:
        cited = _cited_rule_ids(result, "clipping")
        assert cited
        assert cited <= _CLIPPING_RULE_IDS
    if "harmonic_distortion" in expected_faults:
        cited = _cited_rule_ids(result, "harmonic_distortion")
        assert "rule_thd_acceptable" in cited
        assert cited <= {"rule_harmonic_analysis_valid", "rule_thd_acceptable"}
    if expected_faults == ("no_supported_fault",):
        cited = _cited_rule_ids(result, "no_supported_fault")
        assert cited
        assert "rule_thd_acceptable" in cited or "rule_harmonic_analysis_valid" in cited


@pytest.mark.asyncio
async def test_t153_no_privileged_or_redundant_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid_knowledge(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("baseline must not retrieve knowledge")

    monkeypatch.setattr(
        "signal_diag.knowledge.index.KnowledgeIndex.retrieve",
        _forbid_knowledge,
    )
    baseline, tools, _loader, _engine, signal_id = _real_stack()
    result = await baseline.run(signal_id=signal_id, user_request=_USER_REQUEST)
    assert tools.calls == [
        ("detect_clipping", signal_id, ClippingInput()),
        ("analyze_harmonic_distortion", signal_id, HarmonicDistortionInput()),
    ]
    assert {name for name, _signal, _args in tools.calls} == {
        "detect_clipping",
        "analyze_harmonic_distortion",
    }
    _assert_same_run_refs(result)
    assert all(claim.knowledge_refs == () for claim in result.diagnosis.claims)  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_t154_reproducibility_and_clipping_thd_honesty() -> None:
    clipped = generate_clipped_sine(
        frequency_hz=200.0,
        sample_rate_hz=48_000,
        duration_s=2.0,
        amplitude=0.9,
        clip_level=0.5,
    )

    def store_clipped(repo: InMemorySignalRepository) -> str:
        return store_synthetic_case(repo, clipped)

    first_baseline, _tools, _loader, _engine, signal_id = _real_stack(store=store_clipped)
    first = await first_baseline.run(signal_id=signal_id, user_request=_USER_REQUEST)
    second_baseline, _tools2, _loader2, _engine2, signal_id_2 = _real_stack(
        store=store_clipped
    )
    assert signal_id == signal_id_2
    second = await second_baseline.run(signal_id=signal_id_2, user_request=_USER_REQUEST)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    _assert_baseline_shape(first)
    assert "clipping" in _fault_types(first)
    batch = first.rule_evaluation_batches[0]
    harmonic_valid = any(
        item.rule_id == "rule_harmonic_analysis_valid" and item.judgment == "pass"
        for item in batch.evaluations
    )
    harmonic = harmonic_valid and any(
        item.rule_id == "rule_thd_acceptable" and item.judgment == "fail"
        for item in batch.evaluations
    )
    if harmonic:
        assert "harmonic_distortion" in _fault_types(first)
    assert first.diagnosis is not None
    assert first.diagnosis.outcome == "supported_fault"
