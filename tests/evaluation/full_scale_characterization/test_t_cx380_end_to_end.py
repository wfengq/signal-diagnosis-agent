"""T-CX380: six-step CLI run on a two-group mini manifest is reproducible byte for byte."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from signal_diag.evaluation.full_scale_characterization.__main__ import main
from signal_diag.evaluation.full_scale_characterization.fitting import stage1_row_id
from signal_diag.evaluation.full_scale_characterization.store import (
    CharacterizationStore,
)
from tests.evaluation.full_scale_characterization.mini_manifest import MINI

E2E = MINI.model_copy(
    update={
        "round_id": "e2e",
        "m1_calibration_amplitudes": (),
        "m1_validation_amplitudes_heldout": (),
        "m2_calibration_peaks": (),
        "m2_validation_peaks_heldout": (),
        "validation_fixed_m2_peaks": (),
        "m4_calibration_levels": (),
        "m4_validation_levels_heldout": (),
        "validation_fixed_m4_levels": (),
        "m5_calibration_harmonics": (),
        "m5_validation_harmonics_heldout": (),
        "validation_fixed_m5_harmonics": (),
        "m6_calibration_harmonics": (),
        "m6_validation_harmonics": (),
        "m9_calibration_layouts": (),
        "m9_validation_layouts": (),
        "m3_validation_depths_heldout": (),
        "validation_start_phases_heldout_rad": (),
        "validation_f0_heldout": (),
        "m3_calibration_levels": (0.995,),
        "m3_validation_levels_heldout": (0.991,),
        "p5_calibration_gains": (1e-4,),
    }
)

APPROVAL = ["--rationale", "e2e selection", "--approved-by", "tester", "--approved-at", "2026-10-05T00:00:00Z"]

EXPECTED_FILES = {
    "manifest.json",
    "identity.json",
    "calibration_measurements/M3.jsonl.gz",
    "calibration_pairs/M3.jsonl.gz",
    "calibration_report_stage1.json",
    "calibration_report_stage1.md",
    "freeze_record_stage1.json",
    "calibration_report_stage2.json",
    "calibration_report_stage2.md",
    "freeze_record.json",
    "validation_report.json",
    "validation_report.md",
    "SHA256SUMS",
}


def _steps(out: Path, constants_path: Path) -> list[list[str]]:
    o = ["--out", str(out)]
    return [
        ["manifest", "--constants-json", str(constants_path), *o],
        ["calibrate", *o],
        ["report-calibration", "--stage", "1", *o],
        ["freeze", "--stage", "1", "--zone-row-id", stage1_row_id(480.0, 1, "K2"), *APPROVAL, *o],
        ["report-calibration", "--stage", "2", *o],
        ["freeze", "--stage", "2", "--floor-row-id", "F2", *APPROVAL, *o],
        ["validate", *o],
        ["report-validation", *o],
    ]


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_t_cx380_six_steps_end_to_end_reproducible(tmp_path: Path) -> None:
    started = time.monotonic()
    constants_path = tmp_path / "constants.json"
    constants_path.write_text(json.dumps(E2E.model_dump(mode="json")), encoding="utf-8")
    out = tmp_path / "e2e"
    steps = _steps(out, constants_path)

    # Validation is refused before any freeze record exists.
    assert main(steps[0]) == 0
    assert main(["validate", "--out", str(out)]) != 0
    assert main(["report-validation", "--out", str(out)]) != 0
    for i, argv in enumerate(steps[1:], start=1):
        assert main(argv) == 0, argv
        if i == 3:  # only part one of the freeze record exists
            assert main(["validate", "--out", str(out)]) != 0

    files = {
        p.relative_to(out).as_posix()
        for p in out.rglob("*")
        if p.is_file() and not p.relative_to(out).as_posix().startswith("validation_measurements")
        and not p.relative_to(out).as_posix().startswith("validation_pairs")
    }
    assert files == EXPECTED_FILES
    store = CharacterizationStore(out)
    store.verify_sha256sums()
    assert store.list_dir("validation_measurements") and store.list_dir("validation_pairs")
    assert not store.exists("abort_record.json")
    report = store.read_json("validation_report.json")
    assert {"hard_condition_1", "hard_condition_2", "disclosures"} <= set(report)

    first = _snapshot(out)
    # Every step is refused when re-run (write once), and nothing changes.
    for argv in steps:
        assert main(argv) != 0, argv
    assert _snapshot(out) == first

    shutil.rmtree(out)
    for argv in steps:
        assert main(argv) == 0, argv
    assert _snapshot(out) == first

    assert time.monotonic() - started < 120.0


def test_t_cx380_freeze_accepts_only_row_ids_from_reports(tmp_path: Path) -> None:
    constants_path = tmp_path / "constants.json"
    constants_path.write_text(json.dumps(E2E.model_dump(mode="json")), encoding="utf-8")
    out = tmp_path / "e2e"
    steps = _steps(out, constants_path)
    for argv in steps[:3]:
        assert main(argv) == 0
    assert main(["freeze", "--stage", "1", "--zone-row-id", "n=480.0;p=3;K2", *APPROVAL, "--out", str(out)]) != 0
    assert main(["report-calibration", "--stage", "2", "--out", str(out)]) != 0
    assert main(steps[3]) == 0
    assert main(steps[4]) == 0
    assert main(["freeze", "--stage", "2", "--floor-row-id", "F3[periods<3.0|F2]", *APPROVAL, "--out", str(out)]) != 0
    assert main(["validate", "--out", str(out)]) != 0
    assert not CharacterizationStore(out).exists("freeze_record.json")


def test_t_cx380_dry_run_writes_nothing_and_prints_fit_row_counts(tmp_path: Path, capsys) -> None:
    constants_path = tmp_path / "constants.json"
    constants_path.write_text(json.dumps(E2E.model_dump(mode="json")), encoding="utf-8")
    out = tmp_path / "never"
    assert main(["manifest", "--constants-json", str(constants_path), "--dry-run", "--out", str(out)]) == 0
    assert not out.exists()
    printed = capsys.readouterr().out
    assert "estimated_measurement_rows=" in printed
    assert "estimated_shard_gzip_bytes" in printed
    assert "stage1_rows=63" in printed
    assert "stage2_rows_max=" in printed
    assert "calibration/M3/P0" in printed
    assert "stage2_rows_max=15" in printed


def test_t_cx380_reruns_are_refused_before_any_measurement(
    tmp_path: Path, monkeypatch
) -> None:
    from signal_diag.evaluation.full_scale_characterization import runs

    constants_path = tmp_path / "constants.json"
    constants_path.write_text(json.dumps(E2E.model_dump(mode="json")), encoding="utf-8")
    out = tmp_path / "e2e"
    steps = _steps(out, constants_path)
    for argv in steps:
        assert main(argv) == 0, argv

    calls: list[str] = []

    def counting(*args, **kwargs):
        calls.append("measure")
        raise AssertionError("re-run must be refused before measuring")

    monkeypatch.setattr(runs, "measure_pair_checked", counting)
    for argv in (steps[1], steps[6]):  # calibrate, validate
        assert main(argv) != 0, argv
    assert calls == []

    # An aborted round refuses calibrate before measuring anything.
    aborted = tmp_path / "aborted"
    assert main(["manifest", "--constants-json", str(constants_path), "--out", str(aborted)]) == 0
    CharacterizationStore(aborted).write_json("abort_record.json", {"stage": "calibration"})
    assert main(["calibrate", "--out", str(aborted)]) != 0
    assert calls == []
