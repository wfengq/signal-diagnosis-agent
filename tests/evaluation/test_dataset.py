"""Checkpoint I — official synthetic dataset (T133–T140)."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest

from signal_diag.evaluation import (
    DatasetValidationReport,
    load_dataset_manifest,
    validate_dataset,
)
from signal_diag.evaluation.dataset import _materialize_case
from signal_diag.evaluation.models import (
    CombinedDistortionSignalSpec,
    DatasetManifest,
    EvaluationCase,
    EvidenceCondition,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import (
    InMemorySignalRepository,
    generate_clipped_sine,
    generate_combined_distortion,
    generate_harmonic_sine,
    generate_sine,
    generate_white_noise,
)
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.evidence import Evidence
from signal_diag.tools.service import SignalToolService

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "evaluation"
    / "manifests"
    / "s1_distortion_v1.yaml"
)
SHIPPED_PROFILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "signal_diag"
    / "rules"
    / "profiles"
    / "s1_distortion_v1.yaml"
)
_CAUSAL_LABELS = frozenset({"clipping", "harmonic_distortion"})
_COMPARATORS = {
    "eq": lambda left, right: left == right,
    "neq": lambda left, right: left != right,
    "lt": lambda left, right: left < right,
    "lte": lambda left, right: left <= right,
    "gt": lambda left, right: left > right,
    "gte": lambda left, right: left >= right,
}
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


def _official_manifest() -> DatasetManifest:
    return load_dataset_manifest(CANONICAL_MANIFEST)


def _condition_satisfied(condition: EvidenceCondition, evidence: Evidence) -> bool:
    if evidence.source_tool != condition.tool_name:
        return False
    if evidence.metric != condition.metric:
        return False
    if evidence.validity != condition.validity:
        return False
    if type(evidence.value) is not type(condition.expected_value):
        return False
    if evidence.unit != condition.unit:
        return False
    return bool(_COMPARATORS[condition.comparator](evidence.value, condition.expected_value))


def _run_case_tools(
    case: EvaluationCase,
    signal_id: str,
    tool_service: SignalToolService,
) -> dict[tuple[str, str], Evidence]:
    indexed: dict[tuple[str, str], Evidence] = {}
    needed = {condition.tool_name for condition in case.observable_conditions}
    if "detect_clipping" in needed:
        result = tool_service.detect_clipping(signal_id, ClippingInput())
        for item in result.evidence:
            indexed[(item.source_tool, item.metric)] = item
    if "analyze_harmonic_distortion" in needed:
        result = tool_service.analyze_harmonic_distortion(
            signal_id,
            HarmonicDistortionInput(),
        )
        for item in result.evidence:
            indexed[(item.source_tool, item.metric)] = item
    return indexed


def _synthetic_from_spec(case: EvaluationCase):
    spec = case.signal
    if spec.generator == "sine":
        return generate_sine(
            frequency_hz=spec.frequency_hz,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            amplitude=spec.amplitude,
            phase_rad=spec.phase_rad,
            dc_offset=spec.dc_offset,
        )
    if spec.generator == "clipped_sine":
        return generate_clipped_sine(
            frequency_hz=spec.frequency_hz,
            clip_level=spec.clip_level,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            amplitude=spec.amplitude,
        )
    if spec.generator == "harmonic_sine":
        return generate_harmonic_sine(
            fundamental_hz=spec.fundamental_hz,
            harmonic_ratios={item.order: item.ratio for item in spec.harmonic_ratios},
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            fundamental_amplitude=spec.fundamental_amplitude,
        )
    if spec.generator == "combined_distortion":
        return generate_combined_distortion(
            fundamental_hz=spec.fundamental_hz,
            harmonic_ratios={item.order: item.ratio for item in spec.harmonic_ratios},
            clip_level=spec.clip_level,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            fundamental_amplitude=spec.fundamental_amplitude,
        )
    return generate_white_noise(
        sample_rate_hz=spec.sample_rate_hz,
        duration_s=spec.duration_s,
        rms=spec.rms,
        seed=spec.seed,
    )


def _metric_value(
    indexed: dict[tuple[str, str], Evidence],
    tool_name: str,
    metric: str,
) -> object:
    return indexed[(tool_name, metric)].value


def _corrupt_allocation(manifest: DatasetManifest) -> DatasetManifest:
    return manifest.model_copy(update={"cases": manifest.cases[1:]})


def _corrupt_observable(manifest: DatasetManifest) -> DatasetManifest:
    case = manifest.cases[0]
    broken = case.observable_conditions[0].model_copy(update={"expected_value": True})
    updated = case.model_copy(
        update={"observable_conditions": (broken, *case.observable_conditions[1:])}
    )
    return manifest.model_copy(update={"cases": (updated, *manifest.cases[1:])})


def _corrupt_profile(manifest: DatasetManifest) -> DatasetManifest:
    return manifest.model_copy(update={"rule_profile_version": "9.9.9-wrong"})


def _corrupt_identifiability(manifest: DatasetManifest) -> DatasetManifest:
    updated: list[EvaluationCase] = []
    for case in manifest.cases:
        if case.identifiability is None:
            updated.append(case)
            continue
        ident = case.identifiability.model_copy(
            update={"minimum_absolute_separation": 10.0}
        )
        updated.append(case.model_copy(update={"identifiability": ident}))
    return manifest.model_copy(update={"cases": tuple(updated)})


def test_t133_official_case_allocation_and_packaging(tmp_path: Path) -> None:
    manifest = _official_manifest()
    assert manifest.dataset_id == "s1-distortion-synthetic"
    assert manifest.version == "1.0.0"
    assert manifest.rule_profile_id == "profile_s1_distortion"
    assert manifest.rule_profile_version == "1.0.0-demo"
    development = [case for case in manifest.cases if case.split == "development"]
    held_out = [case for case in manifest.cases if case.split == "held_out"]
    assert len(development) == 8
    assert len(held_out) == 16
    assert Counter(case.category for case in development) == DEV_CATEGORY_COUNTS
    assert Counter(case.category for case in held_out) == HELD_CATEGORY_COUNTS

    wheel_dir = tmp_path
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    wheel = next(wheel_dir.glob("signal_diagnosis_agent-*.whl"))
    with ZipFile(wheel) as archive:
        assert (
            "signal_diag/evaluation/manifests/s1_distortion_v1.yaml"
            in archive.namelist()
        )


def test_t134_reconstruction_determinism() -> None:
    manifest = _official_manifest()
    for case in manifest.cases:
        first = _materialize_case(case, InMemorySignalRepository())
        second = _materialize_case(case, InMemorySignalRepository())
        assert first.meta.signal_id == f"sig_eval_{case.case_id.removeprefix('case_')}"
        assert first.meta == second.meta
        assert np.array_equal(first.samples, second.samples)


def test_t135_dual_ground_truth_consistency() -> None:
    manifest = _official_manifest()
    for case in manifest.cases:
        generated = _synthetic_from_spec(case)
        observed_causal = tuple(
            label
            for label in generated.ground_truth.fault_labels
            if label in _CAUSAL_LABELS
        )
        assert observed_causal == case.causal_faults
        assert generated.ground_truth.generator == case.signal.generator
        condition_metrics = tuple(
            condition.metric for condition in case.observable_conditions
        )
        assert "causal_faults" not in condition_metrics
        assert case.causal_faults != case.observable_conditions


def test_t136_observable_condition_verification() -> None:
    manifest = _official_manifest()
    repository, tool_service, rule_engine, profile_loader = _validation_stack()
    report = validate_dataset(
        manifest,
        repository,
        tool_service,
        rule_engine,
        profile_loader,
    )
    assert isinstance(report, DatasetValidationReport)
    assert report.valid is True
    assert report.issues == ()
    assert report.checked_case_ids == tuple(case.case_id for case in manifest.cases)

    for case in manifest.cases:
        record = _materialize_case(case, InMemorySignalRepository())
        isolated = InMemorySignalRepository()
        isolated.put(record)
        indexed = _run_case_tools(
            case,
            record.meta.signal_id,
            SignalToolService(isolated),
        )
        for condition in case.observable_conditions:
            evidence = indexed[(condition.tool_name, condition.metric)]
            assert _condition_satisfied(condition, evidence)


def test_t137_boundary_coverage() -> None:
    manifest = _official_manifest()
    by_id = {case.case_id: case for case in manifest.cases}

    def clipping_ratio(case_id: str) -> float:
        case = by_id[case_id]
        record = _materialize_case(case, InMemorySignalRepository())
        isolated = InMemorySignalRepository()
        isolated.put(record)
        result = SignalToolService(isolated).detect_clipping(
            record.meta.signal_id,
            ClippingInput(),
        )
        value = _metric_value(
            {(item.source_tool, item.metric): item for item in result.evidence},
            "detect_clipping",
            "clipping_ratio",
        )
        assert isinstance(value, float)
        return value

    def thd_percent(case_id: str) -> float:
        case = by_id[case_id]
        record = _materialize_case(case, InMemorySignalRepository())
        isolated = InMemorySignalRepository()
        isolated.put(record)
        result = SignalToolService(isolated).analyze_harmonic_distortion(
            record.meta.signal_id,
            HarmonicDistortionInput(),
        )
        value = _metric_value(
            {(item.source_tool, item.metric): item for item in result.evidence},
            "analyze_harmonic_distortion",
            "thd_percent",
        )
        assert isinstance(value, float)
        return value

    below = clipping_ratio("case_held_clipping_01")
    at_boundary = clipping_ratio("case_held_clipping_02")
    above = clipping_ratio("case_held_clipping_03")
    assert below == pytest.approx(0.009375, abs=1e-12)
    assert at_boundary == pytest.approx(0.010000, abs=1e-12)
    assert above == pytest.approx(0.010416666666666666, abs=1e-12)
    assert below < 0.01 <= above
    assert 0.0095 <= at_boundary <= 0.0105

    thd_below = thd_percent("case_held_harmonic_01")
    thd_at = thd_percent("case_held_harmonic_02")
    thd_at_dev = thd_percent("case_dev_harmonic_boundary")
    thd_above = thd_percent("case_held_harmonic_03")
    assert thd_below == pytest.approx(4.0, abs=0.05)
    assert thd_at == pytest.approx(4.9999993522848, abs=1e-6)
    assert thd_at_dev == pytest.approx(4.9999993522848, abs=1e-6)
    assert thd_above == pytest.approx(8.0, abs=0.05)
    assert thd_below < 5.0 < thd_above
    assert 4.999 <= thd_at <= 5.001
    assert 4.999 <= thd_at_dev <= 5.001
    assert thd_at <= 5.0
    assert thd_at_dev <= 5.0

    clean_01 = by_id["case_held_clean_01"]
    assert clean_01.signal.frequency_hz == 220.0
    assert clean_01.signal.amplitude == pytest.approx(0.35)

    for case_id in ("case_dev_harmonic_boundary", "case_held_harmonic_02"):
        case = by_id[case_id]
        ratios = {item.order: item.ratio for item in case.signal.harmonic_ratios}
        assert ratios[2] == pytest.approx(0.04999999)
        thd_pairs = {
            (condition.comparator, condition.expected_value)
            for condition in case.observable_conditions
            if condition.metric == "thd_percent"
        }
        assert ("gte", 4.999) in thd_pairs
        assert ("lte", 5.001) in thd_pairs
        assert ("lte", 5.0) in thd_pairs
        thd_refs = [
            condition.condition_id
            for condition in case.observable_conditions
            if (
                condition.metric == "thd_percent"
                and condition.comparator == "lte"
                and condition.expected_value == 5.0
            )
        ]
        assert thd_refs
        for evidence_set in case.sufficient_evidence_sets:
            assert thd_refs[0] in evidence_set.condition_refs


def test_t138_invalid_noise_behavior() -> None:
    manifest = _official_manifest()
    noise_cases = [case for case in manifest.cases if case.category == "invalid_noise"]
    assert noise_cases
    for case in noise_cases:
        record = _materialize_case(case, InMemorySignalRepository())
        isolated = InMemorySignalRepository()
        isolated.put(record)
        result = SignalToolService(isolated).analyze_harmonic_distortion(
            record.meta.signal_id,
            HarmonicDistortionInput(),
        )
        metrics = {item.metric: item for item in result.evidence}
        assert "valid" in metrics
        assert metrics["valid"].validity == "not_applicable"
        assert metrics["valid"].value is False
        assert "thd_percent" not in metrics


def test_t139_combined_identifiability() -> None:
    manifest = _official_manifest()
    repository, tool_service, rule_engine, profile_loader = _validation_stack()
    report = validate_dataset(
        manifest,
        repository,
        tool_service,
        rule_engine,
        profile_loader,
    )
    assert report.valid is True
    official_ids = {
        f"sig_eval_{case.case_id.removeprefix('case_')}" for case in manifest.cases
    }
    stored_ids = {meta.signal_id for meta in repository.list_meta()}
    assert stored_ids == official_ids

    for case in manifest.cases:
        if case.category != "combined":
            continue
        assert case.identifiability is not None
        spec = case.signal
        assert isinstance(spec, CombinedDistortionSignalSpec)
        combined = _materialize_case(case, InMemorySignalRepository())
        control_generated = generate_clipped_sine(
            frequency_hz=spec.fundamental_hz,
            clip_level=spec.clip_level,
            sample_rate_hz=spec.sample_rate_hz,
            duration_s=spec.duration_s,
            amplitude=spec.fundamental_amplitude,
        )
        combined_repo = InMemorySignalRepository()
        combined_repo.put(combined)
        control_repo = InMemorySignalRepository()
        control_repo.put(control_generated.record)
        combined_result = SignalToolService(combined_repo).analyze_harmonic_distortion(
            combined.meta.signal_id,
            HarmonicDistortionInput(),
        )
        control_result = SignalToolService(control_repo).analyze_harmonic_distortion(
            control_generated.record.meta.signal_id,
            HarmonicDistortionInput(),
        )
        metric = case.identifiability.signature_metric
        combined_value = next(
            item.value for item in combined_result.evidence if item.metric == metric
        )
        control_match = next(
            (item for item in control_result.evidence if item.metric == metric),
            None,
        )
        control_value = 0.0 if control_match is None else control_match.value
        assert isinstance(combined_value, float)
        assert isinstance(control_value, float)
        assert (
            abs(combined_value - control_value)
            >= case.identifiability.minimum_absolute_separation
        )


@pytest.mark.parametrize(
    ("corrupt", "issue_code"),
    [
        (_corrupt_allocation, "allocation"),
        (_corrupt_observable, "observable_condition"),
        (_corrupt_profile, "profile_identity"),
        (None, "reconstruction"),
        (_corrupt_identifiability, "identifiability"),
    ],
    ids=[
        "allocation",
        "observable_condition",
        "profile_identity",
        "reconstruction",
        "identifiability",
    ],
)
def test_t140_dataset_gate(
    monkeypatch: pytest.MonkeyPatch,
    corrupt: Callable[[DatasetManifest], DatasetManifest] | None,
    issue_code: str,
) -> None:
    manifest = _official_manifest()
    if issue_code == "reconstruction":
        call_count = {"n": 0}
        original = generate_white_noise

        def _flaky_noise(**kwargs: object):
            call_count["n"] += 1
            seed = int(kwargs.get("seed", 0))  # type: ignore[arg-type]
            patched = dict(kwargs)
            patched["seed"] = seed + call_count["n"]
            return original(**patched)  # type: ignore[arg-type]

        monkeypatch.setattr(
            "signal_diag.evaluation.dataset.generate_white_noise",
            _flaky_noise,
        )
        candidate = manifest
    else:
        assert corrupt is not None
        candidate = corrupt(manifest)

    repository, tool_service, rule_engine, profile_loader = _validation_stack()
    report = validate_dataset(
        candidate,
        repository,
        tool_service,
        rule_engine,
        profile_loader,
    )
    assert report.valid is False
    assert any(issue.code == issue_code for issue in report.issues)
    assert report.valid is not True
