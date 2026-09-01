"""Protected-asset audit and write-once final external-test sealing."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC
from pathlib import Path

from signal_diag.evaluation.external.manifest import (
    canonical_json_bytes,
    manifest_sha256,
)
from signal_diag.evaluation.external.models import FinalSeal, FinalSealInputs
from signal_diag.evaluation.external.review import (
    audit_single_reviewer_provenance,
    score_delayed_review,
)
from signal_diag.evaluation.external.validation import validate_external_manifest

_FILE_RECORD_PATTERN = re.compile(r"^([0-9a-f]{64})  (.+)$")
_GIT_RECORD_PATTERN = re.compile(r"^([0-9a-f]{40})  (.+)$")
_TAG_OBJECT_PATH, _TAG_COMMIT_PATH = "git/tag/v0.2.0", "git/commit/v0.2.0"
_PROTECTED_ROOTS = (
    "docs/evaluations/phase4_3_1/development",
    "docs/evaluations/phase4_3_1/official",
    "docs/demo/phase5/v0_2_acceptance",
)
_PROTECTED_FILES = (
    "src/signal_diag/agent/prompts.py",
    "src/signal_diag/evaluation/scoring.py",
    "src/signal_diag/rules/profiles/s1_distortion_v1.yaml",
)


def verify_protected_assets(repo_root: Path, checksum_file: Path) -> None:
    repo_root, checksum_file = repo_root.resolve(), checksum_file.resolve()
    if not checksum_file.is_file():
        raise FileNotFoundError(
            f"protected asset checksum file not found: {checksum_file}"
        )
    records: dict[str, str] = {}
    for number, raw in enumerate(
        checksum_file.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _FILE_RECORD_PATTERN.fullmatch(line) or _GIT_RECORD_PATTERN.fullmatch(
            line
        )
        if match is None:
            raise ValueError(f"invalid checksum record at line {number}")
        digest, rel_path = match.groups()
        if len(digest) == 40 and not rel_path.startswith("git/"):
            raise ValueError(
                "40-character hex digests are allowed only for git/* paths"
            )
        if rel_path in records:
            raise ValueError(f"duplicate protected asset path: {rel_path}")
        _validate_repo_relative_path(repo_root, rel_path)
        records[rel_path] = digest
    for path, label in (
        (_TAG_OBJECT_PATH, "tag object"),
        (_TAG_COMMIT_PATH, "peeled commit"),
    ):
        if path not in records:
            raise ValueError(f"missing {label} record: {path}")
    required = _required_protected_paths(repo_root)
    missing = sorted(required - records.keys())
    if missing:
        raise ValueError(f"missing protected asset record: {missing[0]}")
    extra = sorted(
        path for path in records if not path.startswith("git/") and path not in required
    )
    if extra:
        raise ValueError(f"unexpected protected asset record: {extra[0]}")
    for rel_path, expected in sorted(records.items()):
        if rel_path == _TAG_OBJECT_PATH:
            actual = _git_rev_parse(repo_root, "v0.2.0")
        elif rel_path == _TAG_COMMIT_PATH:
            actual = _git_rev_parse(repo_root, "v0.2.0^{}")
        else:
            asset_path = repo_root / Path(*rel_path.split("/"))
            if not asset_path.is_file():
                raise FileNotFoundError(f"protected asset missing: {rel_path}")
            actual = _sha256_file(asset_path)
        if actual != expected:
            raise ValueError(
                f"protected asset hash mismatch for {rel_path}: expected {expected}, got {actual}"
            )


def seal_final_external_test(inputs: FinalSealInputs, destination: Path) -> FinalSeal:
    if destination.exists():
        if (destination / "attempts.jsonl").exists():
            raise FileExistsError("existing run output blocks sealing")
        raise FileExistsError("destination already exists")
    report = validate_external_manifest(
        inputs.manifest, inputs.asset_root, stage="final_preflight"
    )
    if not report.valid:
        raise ValueError(f"final preflight failed: {report.issues[0].message}")
    if inputs.review_mode == "single_reviewer_provenance_audit":
        agreement = audit_single_reviewer_provenance(inputs.manifest, inputs.round1)
    else:
        if inputs.round2 is None:
            raise ValueError("delayed_blind_review requires round2")
        agreement = score_delayed_review(inputs.round1, inputs.round2)
        if (
            agreement.raw_outcome_agreement is not None
            and agreement.raw_outcome_agreement
            < inputs.review_targets.minimum_raw_outcome_agreement
        ):
            raise ValueError("review target not met")
    verify_protected_assets(inputs.repo_root, inputs.checksum_file)
    final_cases = tuple(
        c for c in inputs.manifest.cases if c.split == "final_external_test"
    )
    scoreable = tuple(
        c.case_id
        for c in final_cases
        if c.confidence in {"strong_ground_truth", "reference_supported"}
    )
    summaries = inputs.round1.reference_summaries
    if set(summaries) != {c.case_id for c in inputs.manifest.cases}:
        raise ValueError("round 1 reference summaries must cover the manifest")
    destination.mkdir(parents=True, exist_ok=False)
    files = {
        "study_manifest.json": canonical_json_bytes(inputs.manifest),
        "scoreability_mask.json": _json_bytes({"scoreable_case_ids": scoreable}),
        "reference_summaries.jsonl": b"".join(
            _json_bytes({"case_id": k, "summary": summaries[k].model_dump(mode="json")})
            for k in sorted(summaries)
        ),
        "review_agreement.json": canonical_json_bytes(agreement),
        "protected_assets.json": _json_bytes(
            {
                "checksum_file": inputs.checksum_file.relative_to(
                    inputs.repo_root
                ).as_posix(),
                "checksum_file_sha256": _sha256_file(inputs.checksum_file),
            }
        ),
    }
    for name, payload in files.items():
        (destination / name).write_bytes(payload)
    checksums = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in sorted(files.items())
    ).encode("ascii")
    (destination / "seal.sha256").write_bytes(checksums)
    return FinalSeal(
        seal_id=hashlib.sha256(checksums).hexdigest(),
        study_id=inputs.manifest.study_id,
        manifest_sha256=manifest_sha256(inputs.manifest),
        sealed_at_utc=inputs.sealed_at_utc.astimezone(UTC),
        case_count=len(inputs.manifest.cases),
        scoreable_case_count=len(scoreable),
    )


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_rev_parse(root: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref], cwd=root, check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"git rev-parse {ref!r} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _required_protected_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", *_PROTECTED_ROOTS, *_PROTECTED_FILES],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"git ls-files failed: {result.stderr.strip()}")
    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def _validate_repo_relative_path(root: Path, rel_path: str) -> None:
    if rel_path.startswith("/") or re.match(r"^[A-Za-z]:", rel_path):
        raise ValueError(f"absolute path is not allowed in checksum file: {rel_path}")
    parts = rel_path.split("/")
    if ".." in parts:
        raise ValueError(f"path traversal is not allowed in checksum file: {rel_path}")
    if rel_path.startswith("git/"):
        if rel_path not in {_TAG_OBJECT_PATH, _TAG_COMMIT_PATH}:
            raise ValueError(f"unsupported git record path: {rel_path}")
        return
    try:
        (root / Path(*parts)).resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {rel_path}") from exc
