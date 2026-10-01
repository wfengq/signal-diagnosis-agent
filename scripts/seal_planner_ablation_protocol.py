#!/usr/bin/env python3
"""Planner-ablation protocol seal generate / verify CLI.

Generate refuses an existing destination (no overwrite). Verify is read-only.
Does not call RealLLM.
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from signal_diag.evaluation.contextual.calibration import product_package_sha256
from signal_diag.evaluation.planner_ablation.decision import StudyDecisionProtocol
from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
)
from signal_diag.evaluation.planner_ablation.sealing import (
    seal_planner_ablation_bundle,
    verify_planner_ablation_bundle,
)
from signal_diag.evaluation.planner_ablation.study_score import (
    StudyOracleLabel,
    StudySlotKey,
    content_digest,
    study_input_from_verified_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = (
    PROJECT_ROOT
    / "docs/evaluations/v0_3/contextual/development/study_v0_3_contextual_dev_1"
)
STUDY_ROOT = (
    PROJECT_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_1"
)
SEAL_DEST = STUDY_ROOT / "protocol_seal"

# Dual-mode ready development sources (test + reference WAV both present).
_CASE_IDS: tuple[str, ...] = (
    "825a759a0ea47bb7",
    "857fac53e4d2e57e",
    "abd9010438d4ad93",
    "a4a0853be9983f8c",
    "2be730b9113701de",
    "6fb80bbda391c26c",
    "aa9b4a91b0253c33",
    "393940e92c58cf0b",
    "04f4068ec91d2621",
    "163185980dc8f7a4",
)
_MODES: tuple[str, ...] = ("single_signal", "paired_reference")


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _load_dev_cases() -> dict[str, dict[str, object]]:
    manifest = json.loads((DEV_ROOT / "contextual_manifest.json").read_text(encoding="utf-8"))
    return {str(row["case_id"]): row for row in manifest["cases"]}


def _single_signal_oracle(case: dict[str, object]) -> StudyOracleLabel:
    case_id = str(case["case_id"])
    role = str(case["role"])
    if role in {"clean", "natural_even_control"}:
        return StudyOracleLabel(
            case_id=case_id,
            mode="single_signal",
            expected_outcome="no_supported_fault",
            expected_causal_faults=(),
        )
    if role == "clipping":
        return StudyOracleLabel(
            case_id=case_id,
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        )
    if role == "combined":
        # HEAD single_signal can support clipping (Option C) but not harmonic attribution.
        return StudyOracleLabel(
            case_id=case_id,
            mode="single_signal",
            expected_outcome="supported_fault",
            expected_causal_faults=("clipping",),
        )
    if role in {"harmonic", "invalid_comparison"}:
        return StudyOracleLabel(
            case_id=case_id,
            mode="single_signal",
            expected_outcome="inconclusive",
            expected_causal_faults=(),
        )
    raise ValueError(f"unsupported role for single_signal oracle: {role}")


def _paired_oracle(case: dict[str, object]) -> StudyOracleLabel:
    case_id = str(case["case_id"])
    outcome = str(case["expected_outcome"])
    raw_faults = case.get("expected_causal_set", ())
    if not isinstance(raw_faults, (list, tuple)):
        raise TypeError(f"expected_causal_set must be a sequence for {case_id}")
    faults = tuple(str(item) for item in raw_faults)
    return StudyOracleLabel(
        case_id=case_id,
        mode="paired_reference",
        expected_outcome=outcome,
        expected_causal_faults=faults,
    )


def _code_identity() -> str:
    package_root = PROJECT_ROOT / "src" / "signal_diag"
    paths: list[str] = []
    for directory in (
        "signal",
        "dsp",
        "tools",
        "rules",
        "knowledge",
        "agent",
        "app",
        "evaluation/planner_ablation",
    ):
        base = package_root / directory
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in {".py", ".yaml", ".md"}:
                continue
            relative = str(path.relative_to(package_root)).replace("\\", "/")
            if relative == "app/contextual_campaign.py":
                continue
            paths.append(relative)
    return product_package_sha256(*paths)


def build_manifest() -> dict[str, object]:
    cases = _load_dev_cases()
    schedule: list[StudySlotKey] = []
    oracle: list[StudyOracleLabel] = []
    case_sources: list[dict[str, object]] = []

    input_rows: list[dict[str, object]] = []
    for case_id in _CASE_IDS:
        case = cases[case_id]
        test_path = DEV_ROOT / "wav" / f"cxdev_{case_id}_test.wav"
        ref_path = DEV_ROOT / "wav" / f"cxdev_{case_id}_ref.wav"
        if not test_path.is_file() or not ref_path.is_file():
            raise FileNotFoundError(f"missing dual-mode WAVs for {case_id}")
        test_sha = _sha256_file(test_path)
        ref_sha = _sha256_file(ref_path)
        if test_sha != case["test_wav_sha256"]:
            raise ValueError(f"test wav digest mismatch for {case_id}")
        if ref_sha != case["reference_wav_sha256"]:
            raise ValueError(f"reference wav digest mismatch for {case_id}")

        case_sources.append(
            {
                "case_id": case_id,
                "role": case["role"],
                "source_id": case["source_id"],
                "parent_master_id": case.get("parent_master_id"),
                "license_id": case.get("license_id"),
                "test_wav_relpath": str(test_path.relative_to(PROJECT_ROOT)),
                "reference_wav_relpath": str(ref_path.relative_to(PROJECT_ROOT)),
                "test_wav_sha256": test_sha,
                "reference_wav_sha256": ref_sha,
                "source_manifest_case_mode": case["mode"],
            }
        )
        input_rows.append(
            {
                "case_id": case_id,
                "test_wav_sha256": test_sha,
                "reference_wav_sha256": ref_sha,
                "test_wav_relpath": str(test_path.relative_to(PROJECT_ROOT)),
                "reference_wav_relpath": str(ref_path.relative_to(PROJECT_ROOT)),
            }
        )

        for mode in _MODES:
            schedule.append(StudySlotKey(case_id=case_id, mode=mode))  # type: ignore[arg-type]
            if mode == "single_signal":
                oracle.append(_single_signal_oracle(case))
            else:
                oracle.append(_paired_oracle(case))

    schedule_t = tuple(schedule)
    oracle_t = tuple(oracle)
    n_slots = len(schedule_t) * 2
    protocol = StudyDecisionProtocol(
        study_id=PLANNER_ABLATION_STUDY_ID,
        scoring_identity=PLANNER_ABLATION_SCORING_IDENTITY,
        non_inferiority_max_gap=1.0 / n_slots,
        material_improvement_ratio=0.20,
        n_unit="scorable_slots",
        advantage_endpoint="quality",
    )
    input_identity = sha256(
        _canonical_json(input_rows).encode("utf-8")
    ).hexdigest()
    code_identity = _code_identity()

    return {
        "study_id": PLANNER_ABLATION_STUDY_ID,
        "scoring_identity": PLANNER_ABLATION_SCORING_IDENTITY,
        "scoring_version": "1.0.0-dev.1",
        "denominator_derivation": "completion_slots",
        "decision_protocol": protocol.model_dump(mode="json"),
        "schedule": [item.model_dump(mode="json") for item in schedule_t],
        "oracle": [item.model_dump(mode="json") for item in oracle_t],
        "population_identity": content_digest(schedule_t),
        "oracle_identity": content_digest(oracle_t),
        "input_identity": input_identity,
        "code_identity": code_identity,
        "arm_order": ["product_agent", "fixed_pipeline"],
        "llm_repetitions": 1,
        "modes": list(_MODES),
        "case_count": len(_CASE_IDS),
        "schedule_key_count": len(schedule_t),
        "scorable_slot_count": n_slots,
        "stop_rules": {
            "infrastructure_failure": "stop_campaign",
            "behavioral_failure": "continue_and_occupy_denominators",
            "campaign_retry": "forbidden",
            "post_hoc_extra_runs_after_results": "forbidden",
        },
        "case_sources": case_sources,
        "source_development_manifest_id": "study_v0_3_contextual_dev_1",
        "notes": {
            "plan_draft_case_count": 12,
            "frozen_case_count": len(_CASE_IDS),
            "freeze_rationale": (
                "Only 10 development cases provide both test and reference WAVs "
                "required for each case x {single_signal, paired_reference}."
            ),
        },
    }


def verify_existing_seal(*, seal_dir: Path = SEAL_DEST) -> dict[str, Any]:
    """Read-only verification of an existing seal directory."""
    if not seal_dir.is_dir():
        raise FileNotFoundError(f"seal directory missing: {seal_dir}")
    verify_planner_ablation_bundle(seal_dir)
    loaded = json.loads((seal_dir / "manifest.json").read_text(encoding="utf-8"))
    study = study_input_from_verified_manifest(loaded)
    return {
        "status": "verify_ok",
        "seal": str(seal_dir),
        "schedule_keys": len(study.schedule),
        "oracle_rows": len(study.oracle),
        "non_inferiority_max_gap": study.protocol.non_inferiority_max_gap,
        "population_identity": study.population_identity,
        "oracle_identity": study.oracle_identity,
        "input_identity": study.input_identity,
        "code_identity": study.code_identity,
    }


def generate_seal(*, seal_dir: Path = SEAL_DEST) -> dict[str, Any]:
    """Create a new seal only when the destination path is absent.

    Any existing path is refused, including an empty directory. Only a
    non-existent destination path may be created.
    """
    if seal_dir.exists():
        raise FileExistsError(
            f"seal destination already exists: {seal_dir}; "
            "refuse overwrite even for an empty directory "
            "(use --verify-only for read-only checks)"
        )
    seal_dir.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    seal_planner_ablation_bundle(
        destination=seal_dir,
        study_id=PLANNER_ABLATION_STUDY_ID,
        scoring_identity=PLANNER_ABLATION_SCORING_IDENTITY,
        denominator_derivation="completion_slots",
        manifest=manifest,
    )
    verified = verify_existing_seal(seal_dir=seal_dir)
    return {
        "status": "generated",
        **{key: value for key, value in verified.items() if key != "status"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="read-only verify of the committed seal; never writes",
    )
    parser.add_argument(
        "--seal-dir",
        type=Path,
        default=SEAL_DEST,
        help="seal directory (default: study protocol_seal)",
    )
    args = parser.parse_args(argv)
    seal_dir = args.seal_dir.resolve()
    try:
        if args.verify_only:
            payload = verify_existing_seal(seal_dir=seal_dir)
        else:
            payload = generate_seal(seal_dir=seal_dir)
    except FileExistsError as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, indent=2))
        return 2
    except FileNotFoundError as exc:
        print(json.dumps({"status": "missing", "error": str(exc)}, indent=2))
        return 1
    try:
        payload["seal"] = str(Path(payload["seal"]).relative_to(PROJECT_ROOT))
    except ValueError:
        pass
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
