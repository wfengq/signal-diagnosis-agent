"""Deterministic development qualification helpers for contextual studies."""

from __future__ import annotations

import json
from pathlib import Path

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.dsp.contextual import analyze_contextual_distortion
from signal_diag.evaluation.contextual.manifest import (
    load_contextual_manifest,
    validate_contextual_manifest,
)
from signal_diag.signal.wav import load_wav_bytes


def qualify_development_study(
    *,
    study_dir: Path,
    growth_threshold_percent: float,
) -> dict[str, object]:
    """Re-run deterministic gates for an on-disk development study."""
    study_dir = study_dir.resolve()
    manifest = load_contextual_manifest(study_dir / "contextual_manifest.json")
    validate_contextual_manifest(manifest)
    build_rows = {
        row["case_id"]: row
        for row in json.loads((study_dir / "case_build_record.json").read_text("utf-8"))
    }
    failures: list[str] = []
    rows: list[dict[str, object]] = []
    for case in manifest.cases:
        meta = build_rows[case.case_id]
        test_path = study_dir / meta["test_path"]
        loaded = load_wav_bytes(test_path.read_bytes())
        test = loaded.record.samples[:, 0]
        rate = int(loaded.record.meta.sample_rate_hz)
        row: dict[str, object] = {
            "case_id": case.case_id,
            "role": case.role,
            "mode": case.mode,
        }
        if case.mode == "single_signal":
            clip = analyze_clipping(test)
            ok = True
            if case.role == "clipping":
                ok = clip.clipping_ratio > 0.01 or clip.flat_top_detected
            row["gate_ok"] = ok
            if not ok:
                failures.append(f"{case.case_id}: single clipping gate failed")
            rows.append(row)
            continue
        reference = None
        if meta.get("ref_path"):
            ref_loaded = load_wav_bytes((study_dir / meta["ref_path"]).read_bytes())
            reference = ref_loaded.record.samples[:, 0]
        if case.mode == "nominal_single_tone":
            analysis = analyze_contextual_distortion(
                test,
                rate,
                mode="nominal_single_tone",
                nominal_fundamental_hz=meta["nominal_hz"],
            )
        else:
            analysis = analyze_contextual_distortion(
                test,
                rate,
                mode="paired_reference",
                reference_samples=reference,
                reference_sample_rate_hz=rate,
            )
        growth = analysis.even_harmonic_growth_percent
        ok = True
        if case.role == "clean":
            ok = bool(
                analysis.valid
                and (growth or 0.0) <= growth_threshold_percent
                and analysis.test_clipping_ratio <= 0.01
            )
        elif case.role == "clipping":
            ok = analysis.test_clipping_ratio > 0.01 or bool(
                analysis.test_flat_top_detected
            )
        elif case.role == "harmonic":
            ok = bool(
                analysis.valid
                and (growth or 0.0) > growth_threshold_percent
                and analysis.test_clipping_ratio <= 0.01
            )
        elif case.role == "combined":
            ok = bool(
                analysis.valid
                and (analysis.test_clipping_ratio > 0.01 or analysis.test_flat_top_detected)
                and (growth or 0.0) > growth_threshold_percent
            )
        elif case.role == "natural_even_control":
            ok = bool(analysis.valid and (growth or 0.0) <= growth_threshold_percent)
        elif case.role in {"invalid_comparison", "frequency_mismatch"}:
            ok = not analysis.valid
        row.update(
            {
                "valid": analysis.valid,
                "invalid_reason": analysis.invalid_reason,
                "even_harmonic_growth_percent": growth,
                "gate_ok": ok,
            }
        )
        if not ok:
            failures.append(f"{case.case_id}: gate failed")
        rows.append(row)
    return {
        "study_dir": str(study_dir),
        "growth_threshold_percent": growth_threshold_percent,
        "case_count": len(manifest.cases),
        "all_gates_passed": len(failures) == 0,
        "failures": failures,
        "rows": rows,
    }
