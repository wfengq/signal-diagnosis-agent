"""Phase 4.2 dataset 1.2.0 integrity (T203–T204)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from signal_diag.evaluation.dataset import (
    _collect_evidence,
    _identifiability_issues,
    _materialize_case,
    load_dataset_manifest,
    validate_dataset,
)
from signal_diag.evaluation.models import (
    CombinedDistortionSignalSpec,
    CombinedIdentifiabilitySpec,
    HarmonicRatioSpec,
    WhiteNoiseSignalSpec,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.tools.contracts import HarmonicDistortionOutput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.results import ToolResult
from signal_diag.tools.service import SignalToolService
from tests.evaluation.conftest import (
    CANONICAL_MANIFEST,
    PHASE4_1_MANIFEST,
    make_condition,
    make_dataset_manifest,
    make_evaluation_case,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_PROFILE = (
    REPO_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
)
PHASE4_2_MANIFEST = (
    REPO_ROOT
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1_2.yaml"
)
DEV_CATEGORY_COUNTS = {
    "clean": 2,
    "clipping": 2,
    "harmonic": 2,
    "combined": 1,
    "invalid_noise": 1,
}
HELD_CATEGORY_COUNTS = {
    "clean": 3,
    "clipping": 4,
    "harmonic": 4,
    "combined": 3,
    "invalid_noise": 2,
}
_FORBIDDEN_REQUEST_TOKENS = {
    "detect_clipping",
    "analyze_harmonic_distortion",
    "estimate_fundamental",
    "causal_faults",
    "acceptable_first_tools",
    "development",
    "held_out",
    "clipping_strong",
    "invalid_noise",
    "combined_01",
}
_ORDER2_METRIC = "harmonic_order_2_relative_amplitude"
_ORDER3_METRIC = "harmonic_order_3_relative_amplitude"


def _validation_stack() -> tuple[
    InMemorySignalRepository,
    SignalToolService,
    RuleEngine,
    YamlRuleProfileLoader,
]:
    repository = InMemorySignalRepository()
    return (
        repository,
        SignalToolService(repository),
        RuleEngine(),
        YamlRuleProfileLoader({"profile_s1_distortion": SHIPPED_PROFILE}),
    )


def _split_cases(manifest):
    development = [case for case in manifest.cases if case.split == "development"]
    held_out = [case for case in manifest.cases if case.split == "held_out"]
    return development, held_out


def _parameter_tuple(case) -> str:
    return json.dumps(case.signal.model_dump(), sort_keys=True, default=str)


def _noise_seeds(cases: list) -> set[int]:
    return {
        case.signal.seed
        for case in cases
        if isinstance(case.signal, WhiteNoiseSignalSpec)
    }


def _phase4_2_manifest():
    return load_dataset_manifest(PHASE4_2_MANIFEST)


def _visible_key(case) -> tuple[str, str]:
    record = _materialize_case(case, InMemorySignalRepository())
    meta = record.meta.model_dump(exclude={"signal_id"})
    return (case.user_request, json.dumps(meta, sort_keys=True, default=str))


def _has_unstable_or_nonperiodic_cue(request: str) -> bool:
    lowered = request.lower()
    return (
        ("unstable" in lowered and "pitch" in lowered)
        or "non-periodic" in lowered
        or "not periodic" in lowered
        or "does not stay periodic" in lowered
        or "does not sound periodic" in lowered
    )


def _combined_case(*, signature_metric: str = _ORDER2_METRIC):
    ratios = (HarmonicRatioSpec(order=2, ratio=0.12),)
    if signature_metric == _ORDER3_METRIC:
        ratios = (HarmonicRatioSpec(order=3, ratio=0.12),)
    return make_evaluation_case(
        "combined",
        case_id="case_v12_ident_probe",
        signal=CombinedDistortionSignalSpec(
            fundamental_hz=168.0,
            harmonic_ratios=ratios,
            clip_level=0.72,
            fundamental_amplitude=0.86,
        ),
        identifiability=CombinedIdentifiabilitySpec(
            signature_metric=signature_metric,
            minimum_absolute_separation=0.05,
        ),
        observable_conditions=(
            make_condition(
                supports_claims=("clipping", "harmonic_distortion"),
            ),
            make_condition(
                condition_id="cond_harmonic_valid",
                tool_name="analyze_harmonic_distortion",
                metric="valid",
                comparator="eq",
                expected_value=True,
                supports_claims=("harmonic_distortion",),
            ),
        ),
    )


def _invalid_harmonic_result(call_id: str = "call_analyze_harmonic_distortion_000099"):
    return ToolResult(
        call_id=call_id,
        tool_name="analyze_harmonic_distortion",
        status="invalid",
        result=HarmonicDistortionOutput(
            valid=False,
            invalid_reason="synthetic invalid control",
            fundamental_frequency_hz=None,
            thd_percent=None,
            components=(),
        ),
        evidence=(
            Evidence(
                evidence_id="ev_analyze_harmonic_distortion_control_invalid_000",
                source_tool="analyze_harmonic_distortion",
                call_id=call_id,
                metric="valid",
                value=False,
                validity="not_applicable",
                channel="mixdown",
            ),
        ),
        warnings=("harmonic distortion analysis invalid",),
    )


def _error_harmonic_result(call_id: str = "call_analyze_harmonic_distortion_000098"):
    return ToolResult(
        call_id=call_id,
        tool_name="analyze_harmonic_distortion",
        status="error",
        error_message="harmonic analysis was not called",
    )


def _identifiability_for(
    case,
    monkeypatch,
    *,
    treat_absent_order_2_as_zero: bool,
    patch_control=None,
):
    repository = InMemorySignalRepository()
    record = _materialize_case(case, repository)
    tool_service = SignalToolService(repository)
    indexed = _collect_evidence(case, record.meta.signal_id, tool_service)
    if patch_control is not None:
        original = tool_service.analyze_harmonic_distortion

        def _wrapped(signal_id: str, args):
            if str(signal_id).startswith("sig_eval_control_"):
                return patch_control(original(signal_id, args))
            return original(signal_id, args)

        monkeypatch.setattr(tool_service, "analyze_harmonic_distortion", _wrapped)
    return _identifiability_issues(
        case,
        indexed,
        repository,
        tool_service,
        treat_absent_order_2_as_zero=treat_absent_order_2_as_zero,
    )


def test_t203_v12_allocation_freshness_and_reconstruction() -> None:
    v10 = load_dataset_manifest(CANONICAL_MANIFEST)
    v11 = load_dataset_manifest(PHASE4_1_MANIFEST)
    assert PHASE4_2_MANIFEST.is_file()
    manifest = _phase4_2_manifest()
    assert manifest.schema_version == "1.0"
    assert manifest.dataset_id == "s1-distortion-synthetic"
    assert manifest.version == "1.2.0"
    assert manifest.rule_profile_id == "profile_s1_distortion"
    assert manifest.rule_profile_version == "1.0.0-demo"

    development, held_out = _split_cases(manifest)
    counts = {
        "development": dict(Counter(case.category for case in development)),
        "held_out": dict(Counter(case.category for case in held_out)),
    }
    assert counts["development"] == {
        "clean": 2,
        "clipping": 2,
        "harmonic": 2,
        "combined": 1,
        "invalid_noise": 1,
    }
    assert counts["held_out"] == {
        "clean": 3,
        "clipping": 4,
        "harmonic": 4,
        "combined": 3,
        "invalid_noise": 2,
    }
    assert counts["development"] == DEV_CATEGORY_COUNTS
    assert counts["held_out"] == HELD_CATEGORY_COUNTS
    assert len(development) == 8
    assert len(held_out) == 16

    v12_case_ids = {case.case_id for case in manifest.cases}
    v10_case_ids = {case.case_id for case in v10.cases}
    v11_case_ids = {case.case_id for case in v11.cases}
    assert not v12_case_ids & (v10_case_ids | v11_case_ids)

    v12_parameter_tuples = {_parameter_tuple(case) for case in manifest.cases}
    v10_parameter_tuples = {_parameter_tuple(case) for case in v10.cases}
    v11_parameter_tuples = {_parameter_tuple(case) for case in v11.cases}
    assert not v12_parameter_tuples & (v10_parameter_tuples | v11_parameter_tuples)

    dev_ids = {case.case_id for case in development}
    held_ids = {case.case_id for case in held_out}
    assert not dev_ids & held_ids
    assert not {_parameter_tuple(case) for case in development} & {
        _parameter_tuple(case) for case in held_out
    }
    assert not _noise_seeds(development) & _noise_seeds(held_out)
    assert not _noise_seeds(list(manifest.cases)) & (
        _noise_seeds(list(v10.cases)) | _noise_seeds(list(v11.cases))
    )
    assert not {case.user_request for case in development} & {
        case.user_request for case in held_out
    }
    assert not {case.user_request for case in manifest.cases} & (
        {case.user_request for case in v10.cases}
        | {case.user_request for case in v11.cases}
    )

    for case in manifest.cases:
        first = _materialize_case(case, InMemorySignalRepository())
        second = _materialize_case(case, InMemorySignalRepository())
        assert first.meta == second.meta
        assert first.samples.tobytes() == second.samples.tobytes()


def test_t203_v12_request_fairness() -> None:
    manifest = _phase4_2_manifest()
    by_key: dict[tuple[str, str], set[tuple[str, ...]]] = defaultdict(set)
    for case in manifest.cases:
        lowered = case.user_request.lower()
        for token in _FORBIDDEN_REQUEST_TOKENS:
            assert token not in lowered, f"{token!r} leaked into {case.case_id}"
        by_key[_visible_key(case)].add(tuple(case.acceptable_first_tools))
    for key, tool_sets in by_key.items():
        assert len(tool_sets) == 1, (
            "identical initial visible request/metadata cannot have "
            f"disjoint acceptable first Tools: {key[0]!r}"
        )

    noise_cases = [case for case in manifest.cases if case.category == "invalid_noise"]
    assert noise_cases
    for case in noise_cases:
        assert "estimate_fundamental" in case.acceptable_first_tools
        assert "analyze_harmonic_distortion" in case.acceptable_first_tools
        assert _has_unstable_or_nonperiodic_cue(case.user_request)
        assert "inconclusive" not in case.user_request.lower()
        assert "white_noise" not in case.user_request.lower()


def test_t204_v12_combined_identifiability_and_validation() -> None:
    manifest = _phase4_2_manifest()
    combined = [case for case in manifest.cases if case.category == "combined"]
    assert combined
    for case in combined:
        assert isinstance(case.signal, CombinedDistortionSignalSpec)
        assert any(item.order == 2 and item.ratio > 0.0 for item in case.signal.harmonic_ratios)
        order2_conditions = [
            condition
            for condition in case.observable_conditions
            if condition.metric == _ORDER2_METRIC
            and "harmonic_distortion" in condition.supports_claims
        ]
        assert order2_conditions
        by_id = {condition.condition_id: condition for condition in case.observable_conditions}
        assert any(
            _sufficient_set_covers_combined(by_id, evidence_set)
            for evidence_set in case.sufficient_evidence_sets
        )

    report = validate_dataset(manifest, *_validation_stack())
    assert report.valid is True
    assert report.issues == ()
    assert report.dataset_id == "s1-distortion-synthetic"
    assert report.dataset_version == "1.2.0"
    assert report.checked_case_ids == tuple(case.case_id for case in manifest.cases)


def _sufficient_set_covers_combined(by_id: dict, evidence_set) -> bool:
    conditions = [by_id[ref] for ref in evidence_set.condition_refs]
    has_clipping = any(
        condition.tool_name == "detect_clipping" and "clipping" in condition.supports_claims
        for condition in conditions
    )
    has_valid = any(
        condition.tool_name == "analyze_harmonic_distortion" and condition.metric == "valid"
        for condition in conditions
    )
    has_thd = any(condition.metric == "thd_percent" for condition in conditions)
    has_order2 = any(condition.metric == _ORDER2_METRIC for condition in conditions)
    return has_clipping and has_valid and has_thd and has_order2


def test_t204_v12_absent_valid_order2_control_is_zero(monkeypatch) -> None:
    case = _combined_case()

    def _omit_order2(result):
        filtered = tuple(
            item for item in result.evidence if item.metric != _ORDER2_METRIC
        )
        return result.model_copy(update={"evidence": filtered})

    issues = _identifiability_for(
        case,
        monkeypatch,
        treat_absent_order_2_as_zero=True,
        patch_control=_omit_order2,
    )
    assert issues == []


def test_t204_v12_invalid_or_missing_control_fails_identifiability(monkeypatch) -> None:
    case = _combined_case()

    def _as_invalid(_result):
        return _invalid_harmonic_result()

    def _as_error(_result):
        return _error_harmonic_result()

    invalid_issues = _identifiability_for(
        case,
        monkeypatch,
        treat_absent_order_2_as_zero=True,
        patch_control=_as_invalid,
    )
    assert any(issue.code == "identifiability" for issue in invalid_issues)

    error_issues = _identifiability_for(
        case,
        monkeypatch,
        treat_absent_order_2_as_zero=True,
        patch_control=_as_error,
    )
    assert any(issue.code == "identifiability" for issue in error_issues)

    order3_case = _combined_case(signature_metric=_ORDER3_METRIC)

    def _omit_order3(result):
        filtered = tuple(
            item for item in result.evidence if item.metric != _ORDER3_METRIC
        )
        return result.model_copy(update={"evidence": filtered})

    arbitrary_issues = _identifiability_for(
        order3_case,
        monkeypatch,
        treat_absent_order_2_as_zero=True,
        patch_control=_omit_order3,
    )
    assert any(issue.code == "identifiability" for issue in arbitrary_issues)


def test_t204_historical_missing_component_semantics_unchanged(monkeypatch) -> None:
    case = _combined_case()

    def _omit_order2(result):
        filtered = tuple(
            item for item in result.evidence if item.metric != _ORDER2_METRIC
        )
        return result.model_copy(update={"evidence": filtered})

    def _as_invalid(_result):
        return _invalid_harmonic_result()

    for version in ("1.0.0", "1.1.0", "9.9.9"):
        historical = _identifiability_for(
            case,
            monkeypatch,
            treat_absent_order_2_as_zero=False,
            patch_control=_omit_order2,
        )
        assert historical == [], f"{version} must keep treating absent components as zero"

        still_zero = _identifiability_for(
            case,
            monkeypatch,
            treat_absent_order_2_as_zero=False,
            patch_control=_as_invalid,
        )
        assert still_zero == [], f"{version} must keep prior missing-component semantics"

    v10 = load_dataset_manifest(CANONICAL_MANIFEST)
    v11 = load_dataset_manifest(PHASE4_1_MANIFEST)
    assert validate_dataset(v10, *_validation_stack()).valid is True
    assert validate_dataset(v11, *_validation_stack()).valid is True

    unsupported = make_dataset_manifest(version="9.9.9")
    unsupported_report = validate_dataset(unsupported, *_validation_stack())
    assert unsupported_report.valid is False
    assert any(issue.code == "dataset_identity" for issue in unsupported_report.issues)
    assert not any(issue.code == "identifiability" for issue in unsupported_report.issues)
