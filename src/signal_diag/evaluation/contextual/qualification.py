"""Deterministic development qualification helpers for contextual studies."""

from __future__ import annotations

import json
from pathlib import Path

from signal_diag.dsp.clipping import analyze_clipping
from signal_diag.dsp.contextual import analyze_contextual_distortion
from signal_diag.dsp.models import ClippingAnalysis
from signal_diag.evaluation.contextual.manifest import (
    load_contextual_manifest,
    validate_contextual_manifest,
)
from signal_diag.signal.wav import load_wav_bytes

_CLIPPING_RATIO_FAIL = 0.01


def _clipping_causal_ok(clip: ClippingAnalysis) -> bool:
    mechanism = bool(clip.clipping_mechanism)
    ratio = float(clip.clipping_ratio)
    flat = bool(clip.flat_top_detected)
    substantial = ratio > _CLIPPING_RATIO_FAIL or flat
    return mechanism and substantial


def qualify_development_study(
    *,
    study_dir: Path,
    growth_threshold_percent: float,
    min_natural_even_reference_thd_percent: float = 5.0,
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
            row["clipping_mechanism"] = clip.clipping_mechanism
            row["test_clipping_ratio"] = clip.clipping_ratio
            row["test_flat_top"] = clip.flat_top_detected
            ok = True
            if case.role == "clipping":
                ok = _clipping_causal_ok(clip)
            row["gate_ok"] = ok
            if not ok:
                failures.append(
                    f"{case.case_id}: single clipping gate failed "
                    f"(mechanism={clip.clipping_mechanism}, ratio={clip.clipping_ratio})"
                )
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
        test_clip = analyze_clipping(test)
        growth = analysis.even_harmonic_growth_percent
        ok = True
        if case.role == "clean":
            ok = bool(
                analysis.valid
                and (growth or 0.0) <= growth_threshold_percent
                and not _clipping_causal_ok(test_clip)
            )
        elif case.role == "clipping":
            ok = _clipping_causal_ok(test_clip)
            if case.mode == "paired_reference":
                ok = ok and bool(analysis.valid)
        elif case.role == "harmonic":
            ok = bool(
                analysis.valid
                and (growth or 0.0) > growth_threshold_percent
                and not _clipping_causal_ok(test_clip)
            )
        elif case.role == "combined":
            ok = bool(
                analysis.valid
                and _clipping_causal_ok(test_clip)
                and (growth or 0.0) > growth_threshold_percent
            )
        elif case.role == "natural_even_control":
            ref_thd = analysis.reference_thd_percent
            ok = bool(
                analysis.valid
                and (growth or 0.0) <= growth_threshold_percent
                and ref_thd is not None
                and ref_thd >= min_natural_even_reference_thd_percent
            )
        elif case.role in {"invalid_comparison", "frequency_mismatch"}:
            ok = not analysis.valid
        row.update(
            {
                "valid": analysis.valid,
                "invalid_reason": analysis.invalid_reason,
                "even_harmonic_growth_percent": growth,
                "reference_thd_percent": analysis.reference_thd_percent,
                "clipping_mechanism": test_clip.clipping_mechanism,
                "test_clipping_ratio": test_clip.clipping_ratio,
                "test_flat_top": test_clip.flat_top_detected,
                "gate_ok": ok,
            }
        )
        if not ok:
            failures.append(f"{case.case_id}: gate failed role={case.role}")
        rows.append(row)
    return {
        "study_dir": str(study_dir),
        "growth_threshold_percent": growth_threshold_percent,
        "min_natural_even_reference_thd_percent": min_natural_even_reference_thd_percent,
        "case_count": len(manifest.cases),
        "all_gates_passed": len(failures) == 0,
        "failures": failures,
        "rows": rows,
    }
