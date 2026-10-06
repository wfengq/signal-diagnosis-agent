"""T-CX428–T-CX433: opt-in F0 subharmonic guard and sub-sample resolution (D049)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from signal_diag.dsp import estimate_f0_autocorrelation
from signal_diag.dsp.harmonics import analyze_harmonic_distortion
from signal_diag.dsp.models import HarmonicAnalysis
from signal_diag.dsp.pitch import subharmonic_guard_enabled
from signal_diag.evaluation.dataset import _generate, load_dataset_manifest
from signal_diag.evaluation.external.reference_harmonics import estimate_f0_reference
from signal_diag.signal import load_wav_bytes

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "fixtures" / "f0_v02_baseline.json"
MANIFESTS = sorted((ROOT / "src/signal_diag/evaluation/manifests").glob("s1_distortion_v1*.yaml"))
THD_THRESHOLD_PERCENT = 5.0  # profile_s1_distortion rule_thd_acceptable (demonstration)


def _guarded_harmonics(samples: np.ndarray, rate: int) -> HarmonicAnalysis:
    with subharmonic_guard_enabled():
        return analyze_harmonic_distortion(samples, rate)


def _tone(frequency_hz: float, sample_rate_hz: int, seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(sample_rate_hz * seconds)) / sample_rate_hz
    return (0.5 * np.sin(2 * np.pi * frequency_hz * t)).astype(np.float32)


def _wav_mono(relative: str) -> tuple[np.ndarray, int]:
    loaded = load_wav_bytes((ROOT / relative).read_bytes())
    samples = np.mean(loaded.record.samples, axis=1)
    return samples, int(loaded.record.meta.sample_rate_hz)


@pytest.mark.parametrize("sample_rate_hz", [8_000, 16_000, 44_100, 48_000])
@pytest.mark.parametrize("frequency_hz", [110.0, 220.0, 440.0, 700.0, 997.0])
def test_t_cx428_pure_tones_have_no_subharmonic_lock(
    sample_rate_hz: int, frequency_hz: float
) -> None:
    estimate = estimate_f0_autocorrelation(
        _tone(frequency_hz, sample_rate_hz), sample_rate_hz, subharmonic_guard=True
    )
    assert estimate.voiced
    assert estimate.method == "autocorrelation"
    assert estimate.f0_hz == pytest.approx(frequency_hz, rel=1e-3)


@pytest.mark.parametrize(
    ("relative", "expected_hz"),
    [
        ("docs/evaluations/v0_3/dev/study_v0_3_dev_1/wav/v03dev_3a0c28b1e79d60af.wav", 700.0),
        *(
            (f"docs/evaluations/v0_3/agent_increment/study_s1_agent_increment_1/wav/{name}", 440.0)
            for name in (
                "dev_t2_00.wav",
                "dev_t2_01.wav",
                "dev_t2_02.wav",
                "dev_t2_03.wav",
                *(f"held_t2_0{i}.wav" for i in range(8)),
            )
        ),
    ],
)
def test_t_cx429_repository_probes_estimate_the_true_fundamental(
    relative: str, expected_hz: float
) -> None:
    samples, sample_rate_hz = _wav_mono(relative)
    estimate = estimate_f0_autocorrelation(samples, sample_rate_hz, subharmonic_guard=True)
    assert estimate.voiced
    assert estimate.f0_hz == pytest.approx(expected_hz, rel=5e-3)


def _v02_cases() -> list[tuple[str, object]]:
    cases: list[tuple[str, object]] = []
    for manifest in MANIFESTS:
        for case in load_dataset_manifest(manifest).cases:
            cases.append((f"{manifest.stem}:{case.case_id}", case))
    return cases


def test_t_cx430_v02_estimates_move_little_and_judgments_do_not_change() -> None:
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert payload["schema"] == "f0_v02_baseline/1"
    baseline = {row["key"]: row for row in payload["rows"]}
    cases = _v02_cases()
    assert len(cases) == len(baseline) == 72
    for key, case in cases:
        before = baseline[key]
        generated = _generate(case)  # type: ignore[arg-type]
        samples = generated.record.samples[:, 0]
        rate = generated.record.meta.sample_rate_hz
        estimate = estimate_f0_autocorrelation(samples, rate, subharmonic_guard=True)
        harmonic = _guarded_harmonics(samples, rate)
        assert estimate.voiced == before["voiced"], key
        if before["f0_hz"] is not None:
            assert estimate.f0_hz == pytest.approx(before["f0_hz"], rel=2e-3), key
        assert harmonic.valid == before["harmonic_valid"], key
        assert harmonic.series_kind == before["series_kind"], key
        passed = (
            None
            if not harmonic.valid or harmonic.thd_percent is None
            else harmonic.thd_percent <= THD_THRESHOLD_PERCENT
        )
        assert passed == before["thd_pass"], key


def test_t_cx430_auto_f0_thd_now_matches_thd_at_the_true_fundamental() -> None:
    # The pre-D049 estimate was up to 0.4 Hz off on these 2 s cases, which moved
    # the harmonic bins and under-reported THD (e.g. 9.29 % against 18.65 %).
    for key, case in _v02_cases():
        spec = case.signal  # type: ignore[attr-defined]
        true_hz = getattr(spec, "frequency_hz", None) or getattr(spec, "fundamental_hz", None)
        generated = _generate(case)  # type: ignore[arg-type]
        samples = generated.record.samples[:, 0]
        rate = generated.record.meta.sample_rate_hz
        auto = _guarded_harmonics(samples, rate)
        if not auto.valid or true_hz is None:
            continue
        pinned = analyze_harmonic_distortion(samples, rate, fundamental_hz=true_hz)
        assert auto.thd_percent == pytest.approx(pinned.thd_percent, rel=1e-3, abs=1e-6), key


def test_t_cx431_reference_analyzer_keeps_its_sealed_estimate() -> None:
    samples, sample_rate_hz = _wav_mono(
        "docs/evaluations/v0_2_external_wav/final_external_test/study_v0_2_external_wav_final_1/"
        "assets/final_external_test/extwav_final_external_test_30ae08019c74113d.wav"
    )
    sealed = ROOT / (
        "docs/evaluations/v0_2_external_wav/final_external_test/"
        "study_v0_2_external_wav_final_1/final_seal/reference_summaries.jsonl"
    )
    row = next(
        json.loads(line)
        for line in sealed.read_text(encoding="utf-8").splitlines()
        if "30ae08019c74113d" in line
    )
    reference_f0_hz, _confidence, _voiced = estimate_f0_reference(samples, sample_rate_hz)
    assert reference_f0_hz == row["summary"]["f0_hz"]
    source = (ROOT / "src/signal_diag/evaluation/external/reference_harmonics.py").read_text()
    assert "signal_diag.dsp.pitch import" not in source
    assert "from signal_diag.dsp import" not in source


def test_t_cx432_aperiodic_input_gains_no_harmonic_claim() -> None:
    rng = np.random.default_rng(20261006)
    noise = rng.normal(0.0, 0.2, 48_000).astype(np.float32)
    estimate = estimate_f0_autocorrelation(noise, 48_000, subharmonic_guard=True)
    assert not estimate.voiced
    assert estimate.f0_hz is None
    bark, rate = _wav_mono(
        "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1/wav/"
        "cxdev_e3c036eb778237c8_test.wav"
    )
    bark_estimate = estimate_f0_autocorrelation(bark, rate, subharmonic_guard=True)
    assert bark_estimate.f0_reliability == "unreliable"
    harmonic = _guarded_harmonics(bark, rate)
    assert not harmonic.valid
    assert harmonic.thd_percent is None


def test_t_cx430_default_path_is_the_pre_d049_estimator() -> None:
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline = {row["key"]: row for row in payload["rows"]}
    for key, case in _v02_cases():
        generated = _generate(case)  # type: ignore[arg-type]
        samples = generated.record.samples[:, 0]
        rate = generated.record.meta.sample_rate_hz
        estimate = estimate_f0_autocorrelation(samples, rate)
        harmonic = analyze_harmonic_distortion(samples, rate)
        assert estimate.f0_hz == baseline[key]["f0_hz"], key
        assert harmonic.thd_percent == baseline[key]["thd_percent"], key
    locked = estimate_f0_autocorrelation(_tone(440.0, 8_000), 8_000)
    assert locked.f0_hz == pytest.approx(87.91, abs=0.01)


def test_t_cx433_only_the_live_product_turns_the_guard_on() -> None:
    from signal_diag.app.guarded_tools import GuardedSignalToolService
    from signal_diag.signal import InMemorySignalRepository, build_signal_record
    from signal_diag.tools import SignalToolService
    from signal_diag.tools.contracts import FundamentalInput

    repository = InMemorySignalRepository()
    record = build_signal_record(
        _tone(440.0, 8_000).reshape(-1, 1), sample_rate_hz=8_000, source_type="generated"
    )
    repository.put(record)
    args = FundamentalInput()
    guarded = GuardedSignalToolService(repository).estimate_fundamental(
        record.meta.signal_id, args
    )
    legacy = SignalToolService(repository).estimate_fundamental(record.meta.signal_id, args)
    assert guarded.result is not None and legacy.result is not None
    assert guarded.result.f0_hz == pytest.approx(440.0, rel=1e-3)
    assert legacy.result.f0_hz == pytest.approx(87.91, abs=0.01)

    app_service = (ROOT / "src/signal_diag/app/service.py").read_text(encoding="utf-8")
    assert app_service.count("GuardedSignalToolService(") == 2
    adapter = ROOT / "src/signal_diag/app/planner_ablation_v2_adapter.py"
    # The study's fixed arm mirrors the product arm's tools.
    assert adapter.read_text(encoding="utf-8").count("GuardedSignalToolService(") == 1
    for relative in (
        "src/signal_diag/evaluation/runner.py",
        "src/signal_diag/evaluation/contextual/campaign.py",
        "src/signal_diag/evaluation/external/runner.py",
        "src/signal_diag/evaluation/agent_increment/live.py",
        "src/signal_diag/evaluation/agent_increment/offline.py",
        "src/signal_diag/evaluation/agent_increment/segment_baseline.py",
        "src/signal_diag/tools/regression_measurement.py",
        "src/signal_diag/tools/service.py",
        "src/signal_diag/dsp/harmonics.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "subharmonic_guard" not in text, relative
        assert "GuardedSignalToolService" not in text, relative
