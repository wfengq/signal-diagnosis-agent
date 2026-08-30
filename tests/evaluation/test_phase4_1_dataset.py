"""Phase 4.1 fresh v1.1.0 dataset (T191–T193)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from signal_diag.evaluation.dataset import (
    _SUPPORTED_DATASETS,
    _materialize_case,
    load_dataset_manifest,
    validate_dataset,
)
from signal_diag.evaluation.models import (
    CombinedDistortionSignalSpec,
    DatasetManifest,
    WhiteNoiseSignalSpec,
)
from signal_diag.rules.engine import RuleEngine
from signal_diag.rules.loader import YamlRuleProfileLoader
from signal_diag.signal import InMemorySignalRepository
from signal_diag.tools.contracts import ClippingInput, HarmonicDistortionInput
from signal_diag.tools.service import SignalToolService
from tests.evaluation.conftest import (
    CANONICAL_MANIFEST,
    PHASE4_1_MANIFEST,
    make_dataset_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_PROFILE = (
    REPO_ROOT / "src" / "signal_diag" / "rules" / "profiles" / "s1_distortion_v1.yaml"
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
DEV_CASE_IDS = (
    "case_v11_dev_clean_01",
    "case_v11_dev_clean_02",
    "case_v11_dev_clipping_boundary",
    "case_v11_dev_clipping_strong",
    "case_v11_dev_harmonic_boundary",
    "case_v11_dev_harmonic_strong",
    "case_v11_dev_combined_01",
    "case_v11_dev_invalid_noise_01",
)
HELD_CASE_IDS = (
    "case_v11_held_clean_01",
    "case_v11_held_clean_02",
    "case_v11_held_clean_03",
    "case_v11_held_clipping_01",
    "case_v11_held_clipping_02",
    "case_v11_held_clipping_03",
    "case_v11_held_clipping_04",
    "case_v11_held_harmonic_01",
    "case_v11_held_harmonic_02",
    "case_v11_held_harmonic_03",
    "case_v11_held_harmonic_04",
    "case_v11_held_combined_01",
    "case_v11_held_combined_02",
    "case_v11_held_combined_03",
    "case_v11_held_invalid_noise_01",
    "case_v11_held_invalid_noise_02",
)
DEV_REQUESTS = (
    "Explain what is making this periodic signal sound distorted.",
    "Analyze the audible distortion in this waveform.",
)
HELD_REQUESTS = (
    "Why does this signal sound distorted?",
    "What is causing the distortion I hear in this waveform?",
    "Diagnose the source of this signal's audible distortion.",
    "Analyze why this periodic waveform sounds wrong.",
)
_TOOL_NAMES = (
    "detect_clipping",
    "analyze_spectrum",
    "estimate_fundamental",
    "analyze_harmonic_distortion",
    "evaluate_rules",
    "retrieve_knowledge",
)
_ANSWER_TOKENS = ("clipping", "harmonic_distortion", "causal_faults")
_ORDER_WORDS = ("first", "then", "pipeline")
_ORDER_WORD_RE = re.compile(r"\b(?:first|then|pipeline)\b", re.IGNORECASE)


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


def _phase4_1_manifest() -> DatasetManifest:
    return load_dataset_manifest(PHASE4_1_MANIFEST)


def _split_cases(
    manifest: DatasetManifest,
) -> tuple[list, list]:
    development = [case for case in manifest.cases if case.split == "development"]
    held_out = [case for case in manifest.cases if case.split == "held_out"]
    return development, held_out


def _clipping_ratio(case) -> float:
    record = _materialize_case(case, InMemorySignalRepository())
    isolated = InMemorySignalRepository()
    isolated.put(record)
    result = SignalToolService(isolated).detect_clipping(
        record.meta.signal_id,
        ClippingInput(),
    )
    value = next(item.value for item in result.evidence if item.metric == "clipping_ratio")
    assert isinstance(value, float)
    return value


def _thd_percent(case) -> float:
    record = _materialize_case(case, InMemorySignalRepository())
    isolated = InMemorySignalRepository()
    isolated.put(record)
    result = SignalToolService(isolated).analyze_harmonic_distortion(
        record.meta.signal_id,
        HarmonicDistortionInput(),
    )
    value = next(item.value for item in result.evidence if item.metric == "thd_percent")
    assert isinstance(value, float)
    return value


def _signal_dump(case) -> str:
    return json.dumps(case.signal.model_dump(), sort_keys=True, default=str)


def _harmonic_ratios(case) -> dict[int, float]:
    return {item.order: item.ratio for item in case.signal.harmonic_ratios}


def test_t191_v11_manifest_identity_allocation_and_reconstruction() -> None:
    assert _SUPPORTED_DATASETS == frozenset(
        {
            ("s1-distortion-synthetic", "1.0.0"),
            ("s1-distortion-synthetic", "1.1.0"),
            ("s1-distortion-synthetic", "1.2.0"),
        }
    )
    unknown = make_dataset_manifest(version="9.9.9")
    unknown_report = validate_dataset(unknown, *_validation_stack())
    assert unknown_report.valid is False
    assert any(issue.code == "dataset_identity" for issue in unknown_report.issues)

    assert PHASE4_1_MANIFEST.is_file()
    assert CANONICAL_MANIFEST.name == "s1_distortion_v1.yaml"
    manifest = _phase4_1_manifest()
    assert manifest.dataset_id == "s1-distortion-synthetic"
    assert manifest.version == "1.1.0"
    assert manifest.rule_profile_id == "profile_s1_distortion"
    assert manifest.rule_profile_version == "1.0.0-demo"

    development, held_out = _split_cases(manifest)
    assert tuple(case.case_id for case in development) == DEV_CASE_IDS
    assert tuple(case.case_id for case in held_out) == HELD_CASE_IDS
    assert len(development) == 8
    assert len(held_out) == 16
    assert Counter(case.category for case in development) == DEV_CATEGORY_COUNTS
    assert Counter(case.category for case in held_out) == HELD_CATEGORY_COUNTS
    case_ids = [case.case_id for case in manifest.cases]
    assert len(case_ids) == len(set(case_ids))
    assert all(case_id.startswith("case_v11_") for case_id in case_ids)

    by_id = {case.case_id: case for case in manifest.cases}
    clean_01 = by_id["case_v11_dev_clean_01"].signal
    assert clean_01.frequency_hz == 150.0
    assert clean_01.amplitude == pytest.approx(0.53)
    assert clean_01.phase_rad == 0.0
    assert clean_01.dc_offset == 0.0
    clean_02 = by_id["case_v11_dev_clean_02"].signal
    assert clean_02.frequency_hz == 350.0
    assert clean_02.amplitude == pytest.approx(0.61)
    clip_b = by_id["case_v11_dev_clipping_boundary"].signal
    assert clip_b.frequency_hz == 63.0
    assert clip_b.amplitude == pytest.approx(0.95)
    assert clip_b.clip_level == pytest.approx(0.94999)
    clip_s = by_id["case_v11_dev_clipping_strong"].signal
    assert clip_s.frequency_hz == 150.0
    assert clip_s.amplitude == pytest.approx(0.88)
    assert clip_s.clip_level == pytest.approx(0.64)
    harm_b = by_id["case_v11_dev_harmonic_boundary"]
    assert harm_b.signal.fundamental_hz == 200.0
    assert harm_b.signal.fundamental_amplitude == pytest.approx(0.48)
    assert _harmonic_ratios(harm_b) == {2: pytest.approx(0.04999999)}
    assert harm_b.causal_faults == ("harmonic_distortion",)
    thd_pairs = {
        (condition.comparator, condition.expected_value)
        for condition in harm_b.observable_conditions
        if condition.metric == "thd_percent"
    }
    assert ("lte", 5.0) in thd_pairs
    harm_s = by_id["case_v11_dev_harmonic_strong"]
    assert harm_s.signal.fundamental_hz == 425.0
    assert _harmonic_ratios(harm_s) == {2: pytest.approx(0.085)}
    combined = by_id["case_v11_dev_combined_01"]
    assert isinstance(combined.signal, CombinedDistortionSignalSpec)
    assert combined.signal.fundamental_hz == 150.0
    assert combined.signal.fundamental_amplitude == pytest.approx(0.88)
    assert _harmonic_ratios(combined) == {3: pytest.approx(0.16)}
    assert combined.signal.clip_level == pytest.approx(0.70)
    assert combined.identifiability is not None
    assert combined.identifiability.signature_metric == (
        "harmonic_order_3_relative_amplitude"
    )
    assert combined.identifiability.minimum_absolute_separation == pytest.approx(0.08)
    noise = by_id["case_v11_dev_invalid_noise_01"]
    assert isinstance(noise.signal, WhiteNoiseSignalSpec)
    assert noise.signal.seed == 101
    assert noise.signal.rms == pytest.approx(0.1)
    assert noise.knowledge_tags == ("inconclusive",)
    assert noise.acceptable_outcomes == ("inconclusive",)
    assert noise.requires_limitation is True

    held_clean = by_id["case_v11_held_clean_01"].signal
    assert held_clean.frequency_hz == 175.0
    assert held_clean.amplitude == pytest.approx(0.43)
    assert by_id["case_v11_held_clean_02"].signal.frequency_hz == 375.0
    assert by_id["case_v11_held_clean_02"].signal.amplitude == pytest.approx(0.57)
    assert by_id["case_v11_held_clean_03"].signal.frequency_hz == 475.0
    assert by_id["case_v11_held_clean_03"].signal.amplitude == pytest.approx(0.67)
    held_c1 = by_id["case_v11_held_clipping_01"].signal
    assert held_c1.frequency_hz == 65.0
    assert held_c1.amplitude == pytest.approx(0.88)
    assert held_c1.clip_level == pytest.approx(0.87999)
    held_c2 = by_id["case_v11_held_clipping_02"].signal
    assert held_c2.frequency_hz == 80.0
    assert held_c2.clip_level == pytest.approx(0.87999)
    held_c3 = by_id["case_v11_held_clipping_03"].signal
    assert held_c3.frequency_hz == 61.0
    assert held_c3.clip_level == pytest.approx(0.87999)
    held_c4 = by_id["case_v11_held_clipping_04"].signal
    assert held_c4.frequency_hz == 425.0
    assert held_c4.amplitude == pytest.approx(0.90)
    assert held_c4.clip_level == pytest.approx(0.70)
    held_h1 = by_id["case_v11_held_harmonic_01"]
    assert held_h1.signal.fundamental_hz == 225.0
    assert _harmonic_ratios(held_h1) == {2: pytest.approx(0.04)}
    assert held_h1.causal_faults == ("harmonic_distortion",)
    held_h2 = by_id["case_v11_held_harmonic_02"]
    assert held_h2.signal.fundamental_hz == 350.0
    assert _harmonic_ratios(held_h2) == {2: pytest.approx(0.04999999)}
    held_h3 = by_id["case_v11_held_harmonic_03"]
    assert held_h3.signal.fundamental_hz == 475.0
    assert _harmonic_ratios(held_h3) == {2: pytest.approx(0.075)}
    held_h4 = by_id["case_v11_held_harmonic_04"]
    assert held_h4.signal.fundamental_hz == 300.0
    assert _harmonic_ratios(held_h4) == {2: pytest.approx(0.07), 3: pytest.approx(0.03)}
    held_comb1 = by_id["case_v11_held_combined_01"]
    assert held_comb1.signal.fundamental_hz == 225.0
    assert _harmonic_ratios(held_comb1) == {3: pytest.approx(0.17)}
    assert held_comb1.signal.clip_level == pytest.approx(0.71)
    assert held_comb1.identifiability.signature_metric == (
        "harmonic_order_3_relative_amplitude"
    )
    assert held_comb1.identifiability.minimum_absolute_separation == pytest.approx(0.05)
    held_comb2 = by_id["case_v11_held_combined_02"]
    assert held_comb2.signal.fundamental_hz == 350.0
    assert _harmonic_ratios(held_comb2) == {
        2: pytest.approx(0.11),
        3: pytest.approx(0.07),
    }
    assert held_comb2.signal.clip_level == pytest.approx(0.69)
    assert held_comb2.identifiability.signature_metric == (
        "harmonic_order_2_relative_amplitude"
    )
    assert held_comb2.identifiability.minimum_absolute_separation == pytest.approx(0.06)
    held_comb3 = by_id["case_v11_held_combined_03"]
    assert held_comb3.signal.fundamental_hz == 400.0
    assert _harmonic_ratios(held_comb3) == {2: pytest.approx(0.14)}
    assert held_comb3.signal.clip_level == pytest.approx(0.77)
    assert held_comb3.identifiability.signature_metric == (
        "harmonic_order_2_relative_amplitude"
    )
    assert held_comb3.identifiability.minimum_absolute_separation == pytest.approx(0.10)
    assert by_id["case_v11_held_invalid_noise_01"].signal.seed == 211
    assert by_id["case_v11_held_invalid_noise_02"].signal.seed == 307

    for case in manifest.cases:
        assert case.signal.sample_rate_hz == 48_000
        assert case.signal.duration_s == pytest.approx(2.0)
        first = _materialize_case(case, InMemorySignalRepository())
        second = _materialize_case(case, InMemorySignalRepository())
        assert first.meta.signal_id == f"sig_eval_{case.case_id.removeprefix('case_')}"
        assert first.meta == second.meta
        assert np.array_equal(first.samples, second.samples)

    repository, tool_service, rule_engine, profile_loader = _validation_stack()
    report = validate_dataset(
        manifest,
        repository,
        tool_service,
        rule_engine,
        profile_loader,
    )
    assert report.valid is True
    assert report.issues == ()
    assert report.dataset_id == "s1-distortion-synthetic"
    assert report.dataset_version == "1.1.0"
    assert report.checked_case_ids == tuple(case.case_id for case in manifest.cases)

    truncated = manifest.model_copy(update={"cases": manifest.cases[1:]})
    truncated_report = validate_dataset(truncated, *_validation_stack())
    assert truncated_report.valid is False
    assert any(issue.code == "allocation" for issue in truncated_report.issues)

    assert _clipping_ratio(by_id["case_v11_dev_clipping_boundary"]) == pytest.approx(
        0.009875, abs=1e-12
    )
    assert _clipping_ratio(by_id["case_v11_dev_clipping_strong"]) == pytest.approx(
        0.48125, abs=1e-12
    )
    assert _clipping_ratio(by_id["case_v11_held_clipping_01"]) == pytest.approx(
        0.009375, abs=1e-12
    )
    assert _clipping_ratio(by_id["case_v11_held_clipping_02"]) == pytest.approx(
        0.010000, abs=1e-12
    )
    assert _clipping_ratio(by_id["case_v11_held_clipping_03"]) == pytest.approx(
        0.011625, abs=1e-12
    )
    assert _clipping_ratio(by_id["case_v11_held_clipping_04"]) == pytest.approx(
        0.432292, abs=1e-5
    )
    assert _thd_percent(by_id["case_v11_dev_harmonic_boundary"]) == pytest.approx(
        5.0, abs=0.05
    )
    assert _thd_percent(by_id["case_v11_dev_harmonic_strong"]) == pytest.approx(
        8.5, abs=0.05
    )
    assert _thd_percent(by_id["case_v11_held_harmonic_01"]) == pytest.approx(4.0, abs=0.05)
    assert _thd_percent(by_id["case_v11_held_harmonic_02"]) == pytest.approx(5.0, abs=0.05)
    assert _thd_percent(by_id["case_v11_held_harmonic_03"]) == pytest.approx(7.5, abs=0.05)
    assert _thd_percent(by_id["case_v11_held_harmonic_04"]) == pytest.approx(
        7.616, abs=0.05
    )
    for case_id in (
        "case_v11_dev_harmonic_boundary",
        "case_v11_held_harmonic_01",
        "case_v11_held_harmonic_02",
    ):
        case = by_id[case_id]
        assert case.causal_faults == ("harmonic_distortion",)
        assert any(
            condition.metric == "thd_percent"
            and condition.comparator == "lte"
            and condition.expected_value == 5.0
            for condition in case.observable_conditions
        )


def test_t192_v11_requests_are_natural_and_non_leading() -> None:
    manifest = _phase4_1_manifest()
    development, held_out = _split_cases(manifest)
    assert [case.user_request for case in development] == [
        DEV_REQUESTS[index % 2] for index in range(len(development))
    ]
    assert [case.user_request for case in held_out] == [
        HELD_REQUESTS[index % 4] for index in range(len(held_out))
    ]
    assert set(DEV_REQUESTS).isdisjoint(HELD_REQUESTS)

    for case in manifest.cases:
        request = case.user_request
        lowered = request.lower()
        for token in _TOOL_NAMES + _ANSWER_TOKENS:
            assert token not in lowered, f"{token!r} leaked into {case.case_id}"
        assert _ORDER_WORD_RE.search(lowered) is None, (
            f"order word leaked into {case.case_id}: {request!r}"
        )
        for word in _ORDER_WORDS:
            assert word not in lowered.split()


def test_t193_v11_split_isolation() -> None:
    v11 = _phase4_1_manifest()
    v10 = load_dataset_manifest(CANONICAL_MANIFEST)
    development, held_out = _split_cases(v11)
    v10_held = [case for case in v10.cases if case.split == "held_out"]

    dev_ids = {case.case_id for case in development}
    held_ids = {case.case_id for case in held_out}
    assert not dev_ids & held_ids
    assert not {case.case_id for case in v10.cases} & (dev_ids | held_ids)

    dev_specs = {_signal_dump(case) for case in development}
    held_specs = {_signal_dump(case) for case in held_out}
    v10_held_specs = {_signal_dump(case) for case in v10_held}
    assert not dev_specs & held_specs
    assert not v10_held_specs & held_specs

    def _noise_seeds(cases: list) -> set[int]:
        return {
            case.signal.seed
            for case in cases
            if isinstance(case.signal, WhiteNoiseSignalSpec)
        }

    assert not _noise_seeds(development) & _noise_seeds(held_out)
    assert not {case.user_request for case in development} & {
        case.user_request for case in held_out
    }
