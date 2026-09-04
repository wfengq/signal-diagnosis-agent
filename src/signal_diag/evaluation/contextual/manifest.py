"""Contextual manifest loading, validation, and slot planning."""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from signal_diag.evaluation.contextual.models import (
    CONTEXTUAL_SCORING_ID,
    ArmPlan,
    ContextualCase,
    ContextualManifest,
    PairedHarmonicSlot,
)


def canonical_json_bytes(model: object) -> bytes:
    payload = model.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_sha256(manifest: ContextualManifest) -> str:
    return sha256(canonical_json_bytes(manifest)).hexdigest()


def load_contextual_manifest(path: Path) -> ContextualManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ContextualManifest.model_validate(payload)


def build_slot_plan(manifest: ContextualManifest) -> tuple[PairedHarmonicSlot, ...]:
    slots: list[PairedHarmonicSlot] = []
    for case in manifest.cases:
        if case.role not in {"harmonic", "combined"}:
            continue
        if case.mode != "paired_reference":
            continue
        by_arm = {arm.arm: arm for arm in case.arms}
        slots.append(
            PairedHarmonicSlot(
                case_id=case.case_id,
                contextual=by_arm["contextual_agent"],
                ablation=by_arm["no_context_ablation"],
            )
        )
    return tuple(slots)


def validate_contextual_manifest(manifest: ContextualManifest) -> None:
    if manifest.scoring_id != CONTEXTUAL_SCORING_ID:
        raise ValueError("unexpected scoring_id")
    if len(manifest.cases) != 20:
        raise ValueError("contextual manifest requires exactly 20 cases")
    scoreable = sum(1 for case in manifest.cases if case.scoreable)
    if scoreable != 17:
        raise ValueError("contextual manifest requires exactly 17 scoreable cases")
    mode_counts = Counter(case.mode for case in manifest.cases)
    expected_modes = {
        "paired_reference": 10,
        "nominal_single_tone": 4,
        "single_signal": 6,
    }
    if dict(mode_counts) != expected_modes:
        raise ValueError(f"unexpected mode distribution: {dict(mode_counts)}")
    case_ids = [case.case_id for case in manifest.cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("duplicate case_id")
    for case in manifest.cases:
        if case.split != manifest.split:
            raise ValueError(f"case {case.case_id} split mismatches manifest")
    _reject_identity_leakage(manifest)
    expected_slots = build_slot_plan(manifest)
    if manifest.paired_harmonic_slots:
        if tuple(slot.case_id for slot in manifest.paired_harmonic_slots) != tuple(
            slot.case_id for slot in expected_slots
        ):
            raise ValueError("paired_harmonic_slots do not match derived slot plan")
        for left, right in zip(
            manifest.paired_harmonic_slots, expected_slots, strict=True
        ):
            if left.model_dump() != right.model_dump():
                raise ValueError("paired_harmonic_slots content mismatch")


def _reject_identity_leakage(manifest: ContextualManifest) -> None:
    """Reject exact identity reuse markers reserved for the opposite split."""
    forbidden_markers = {
        "development": ("val_", "validation_"),
        "validation": ("dev_", "development_"),
    }[manifest.split]
    for case in manifest.cases:
        blob = (
            f"{case.case_id}|{case.source_id}|{case.parent_master_id}|"
            f"{case.recording_key}|{case.transform_identity}"
        ).lower()
        for marker in forbidden_markers:
            if marker in blob:
                raise ValueError(
                    f"identity/lineage leakage marker {marker!r} in case {case.case_id}"
                )


def make_arm_plans(
    *,
    mode: str,
    test_sha: str,
    reference_sha: str | None,
) -> tuple[ArmPlan, ArmPlan, ArmPlan]:
    return (
        ArmPlan(
            arm="contextual_agent",
            mode=mode,  # type: ignore[arg-type]
            test_wav_sha256=test_sha,
            reference_wav_sha256=reference_sha,
        ),
        ArmPlan(
            arm="fixed_pipeline",
            mode=mode,  # type: ignore[arg-type]
            test_wav_sha256=test_sha,
            reference_wav_sha256=reference_sha,
        ),
        ArmPlan(
            arm="no_context_ablation",
            mode="single_signal",
            test_wav_sha256=test_sha,
            reference_wav_sha256=None,
        ),
    )


def make_case(**kwargs: object) -> ContextualCase:
    return ContextualCase.model_validate(kwargs)
