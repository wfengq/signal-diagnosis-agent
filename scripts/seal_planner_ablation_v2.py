#!/usr/bin/env python3
"""Planner-ablation v2 protocol seal generate / verify CLI.

Separate ``--verify-only`` and ``--generate`` modes.
Generate refuses any existing destination (including empty directories).
Verification is read-only and never creates files.
Does not call RealLLM. Never generates against ``study_s1_planner_ablation_dev_1``.
Real evidence-root generation additionally requires ``PLANNER_ABLATION_V2_SEAL_GRANT=1``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from signal_diag.evaluation.planner_ablation.v2.models import (
    EffectiveConfiguration,
    StudyProtocolV2,
)
from signal_diag.evaluation.planner_ablation.v2.sealing import (
    build_candidate_manifest,
    generate_seal,
    make_complete_budget_assessment,
    tree_file_digests,
    verify_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV2_ROOT = (
    PROJECT_ROOT
    / "docs/evaluations/v0_3/planner_ablation/study_s1_planner_ablation_dev_2"
)
DEFAULT_SEAL_DEST = DEV2_ROOT / "protocol_seal"
DEV1_MARKER = "study_s1_planner_ablation_dev_1"


def _refuse_dev1(path: Path) -> None:
    text = str(path.resolve()).replace("\\", "/")
    if DEV1_MARKER in text:
        raise ValueError(
            "refusing generate against study_s1_planner_ablation_dev_1 under any mode"
        )


def verify_existing_seal(
    *,
    seal_dir: Path,
    repository_root: Path = PROJECT_ROOT,
    input_root: Path | None = None,
) -> dict[str, Any]:
    """Read-only verification of an existing v2 seal directory."""
    inputs = input_root or repository_root
    before = tree_file_digests(seal_dir) if seal_dir.is_dir() else {}
    before_inputs = tree_file_digests(inputs)
    study = verify_manifest(
        seal_dir,
        repository_root=repository_root,
        input_root=inputs,
    )
    after = tree_file_digests(seal_dir)
    after_inputs = tree_file_digests(inputs)
    if after != before:
        raise RuntimeError("verify mutated seal directory")
    if after_inputs != before_inputs:
        raise RuntimeError("verify mutated input tree")
    return {
        "status": "verify_ok",
        "seal": str(seal_dir),
        "study_id": study.protocol.study_id,
        "slot_count": len(study.schedule.slots),
        "verified_identity": study.verified_identity,
        "input_identity": study.input_identity,
        "code_identity": study.code_identity,
        "construction_path": study.construction_path,
    }


def generate_new_seal(
    *,
    seal_dir: Path,
    repository_root: Path = PROJECT_ROOT,
    input_root: Path | None = None,
    allow_incomplete_budget: bool = False,
) -> dict[str, Any]:
    """Create a new seal only when the destination path is absent."""
    _refuse_dev1(seal_dir)
    inputs = input_root or repository_root
    if allow_incomplete_budget:
        budget = None
        config = None
    else:
        # Temporary/offline path: only seal-ready when limits are complete.
        # Unknown production limits remain blockers unless an explicit complete
        # budget is supplied by a later seal grant workflow.
        config = EffectiveConfiguration(
            max_tool_calls=8,
            max_planner_retries=2,
            max_no_progress=2,
            max_rule_evaluations=4,
            max_knowledge_retrievals=4,
            temperature=0.0,
            thinking_disabled=True,
            max_tokens_explicit=True,
            max_tokens=4096,
            request_timeout_explicit=True,
            request_timeout_s=120.0,
            transport_retry_override_explicit=True,
            transport_retry_override=1,
            transport_attempts_per_call_bound=1,
            planner_calls_per_slot_bound=8,
            input_token_bound_per_call=8000,
            output_token_bound_per_call=2000,
            retry_telemetry_available=True,
            provider_sdk_version="test-complete",
        )
        budget = make_complete_budget_assessment(
            planner_calls_per_slot_bound=8,
            transport_attempts_per_call_bound=1,
            input_token_bound_per_call=8000,
            output_token_bound_per_call=2000,
        )
    candidate = build_candidate_manifest(
        repository_root=repository_root,
        input_root=inputs,
        protocol=StudyProtocolV2(),
        effective_configuration=config,
        budget_assessment=budget,
        operator_authorization_references=("offline_harness_temporary_fixture",),
    )
    destination = generate_seal(
        candidate, seal_dir, repository_root=repository_root
    )
    verified = verify_existing_seal(
        seal_dir=destination,
        repository_root=repository_root,
        input_root=inputs,
    )
    return {
        "status": "generated",
        **{key: value for key, value in verified.items() if key != "status"},
        "seal_ready": candidate.seal_ready,
        "candidate_digest": candidate.candidate_digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="read-only verify of an existing seal; never writes",
    )
    mode.add_argument(
        "--generate",
        action="store_true",
        help="create a new seal only when destination is absent",
    )
    parser.add_argument(
        "--seal-dir",
        type=Path,
        default=DEFAULT_SEAL_DEST,
        help="seal directory (default: study_s1_planner_ablation_dev_2/protocol_seal)",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=PROJECT_ROOT,
        help="repository root for code bindings",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=None,
        help="input root for WAV resolution (defaults to repository root)",
    )
    args = parser.parse_args(argv)
    seal_dir = args.seal_dir.resolve()
    repository_root = args.repository_root.resolve()
    input_root = args.input_root.resolve() if args.input_root else None
    try:
        if args.verify_only:
            payload = verify_existing_seal(
                seal_dir=seal_dir,
                repository_root=repository_root,
                input_root=input_root,
            )
        else:
            payload = generate_new_seal(
                seal_dir=seal_dir,
                repository_root=repository_root,
                input_root=input_root,
            )
    except FileExistsError as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, indent=2))
        return 2
    except PermissionError as exc:
        print(json.dumps({"status": "grant_required", "error": str(exc)}, indent=2))
        return 3
    except FileNotFoundError as exc:
        print(json.dumps({"status": "missing", "error": str(exc)}, indent=2))
        return 1
    except ValueError as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, indent=2))
        return 1
    try:
        payload["seal"] = str(Path(payload["seal"]).relative_to(PROJECT_ROOT))
    except (ValueError, KeyError):
        pass
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
