"""Offline sealing helpers for planner-ablation study bundles."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from signal_diag.evaluation.planner_ablation.identity import (
    PLANNER_ABLATION_SCORING_IDENTITY,
    PLANNER_ABLATION_STUDY_ID,
    validate_scoring_identity_derivation,
    validate_study_identity,
)

_CHECKSUM_LINE = "{digest}  {name}\n"
_REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "study_id",
        "scoring_identity",
        "denominator_derivation",
        "decision_protocol",
    }
)
_REQUIRED_INDEX_FILES = frozenset({"manifest.json", "seal_meta.json"})


def _sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _validate_manifest_protocol(
    manifest: dict[str, object],
    *,
    study_id: str,
    scoring_identity: str,
    denominator_derivation: str,
) -> None:
    missing = _REQUIRED_MANIFEST_KEYS - set(manifest)
    if missing:
        raise ValueError(f"manifest missing protocol fields: {sorted(missing)}")
    if manifest["study_id"] != study_id:
        raise ValueError("manifest study_id mismatch")
    if manifest["scoring_identity"] != scoring_identity:
        raise ValueError("manifest scoring_identity mismatch")
    if manifest["denominator_derivation"] != denominator_derivation:
        raise ValueError("manifest denominator_derivation mismatch")


def seal_planner_ablation_bundle(
    *,
    destination: Path,
    study_id: str,
    scoring_identity: str,
    denominator_derivation: str,
    manifest: dict[str, object],
) -> Path:
    validate_scoring_identity_derivation(
        study_id=study_id,
        scoring_identity=scoring_identity,
        derivation=denominator_derivation,
    )
    protocol_manifest = {
        **manifest,
        "study_id": study_id,
        "scoring_identity": scoring_identity,
        "denominator_derivation": denominator_derivation,
    }
    _validate_manifest_protocol(
        protocol_manifest,
        study_id=study_id,
        scoring_identity=scoring_identity,
        denominator_derivation=denominator_derivation,
    )
    if destination.exists():
        raise FileExistsError(f"seal destination already exists: {destination}")
    destination.mkdir(parents=True)
    (destination / "manifest.json").write_text(
        json.dumps(protocol_manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    meta = {
        "study_id": study_id,
        "scoring_identity": scoring_identity,
        "denominator_derivation": denominator_derivation,
    }
    (destination / "seal_meta.json").write_text(
        json.dumps(meta, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    lines: list[str] = []
    for name in sorted(path.name for path in destination.iterdir() if path.is_file()):
        digest = _sha256_file(destination / name)
        lines.append(_CHECKSUM_LINE.format(digest=digest, name=name))
    if not lines:
        raise ValueError("seal checksum index must not be empty")
    indexed_names = {line.split("  ", 1)[1].strip() for line in lines}
    if not _REQUIRED_INDEX_FILES.issubset(indexed_names):
        raise ValueError("seal checksum index must list manifest.json and seal_meta.json")
    (destination / "seal.sha256").write_text("".join(lines), encoding="utf-8")
    return destination


def verify_planner_ablation_bundle(destination: Path) -> None:
    seal_path = destination / "seal.sha256"
    if not seal_path.is_file():
        raise FileNotFoundError("missing seal.sha256")
    records: dict[str, str] = {}
    for raw in seal_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        digest, name = raw.split("  ", 1)
        if name in records:
            raise ValueError(f"duplicate seal checksum entry: {name}")
        records[name] = digest
    if not records:
        raise ValueError("seal checksum index must not be empty")
    if not _REQUIRED_INDEX_FILES.issubset(records):
        raise ValueError("seal checksum index missing required manifest entries")
    for name, expected in sorted(records.items()):
        path = destination / name
        if not path.is_file():
            raise FileNotFoundError(f"sealed artifact missing on disk: {name}")
        if _sha256_file(path) != expected:
            raise ValueError(f"seal hash mismatch for {name}")
    meta = json.loads((destination / "seal_meta.json").read_text(encoding="utf-8"))
    validate_study_identity(str(meta["study_id"]))
    if meta["scoring_identity"] != PLANNER_ABLATION_SCORING_IDENTITY:
        raise ValueError("seal scoring identity mismatch")
    if meta["study_id"] != PLANNER_ABLATION_STUDY_ID:
        raise ValueError("seal study identity mismatch")
    validate_scoring_identity_derivation(
        study_id=str(meta["study_id"]),
        scoring_identity=str(meta["scoring_identity"]),
        derivation=str(meta["denominator_derivation"]),
    )
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    _validate_manifest_protocol(
        manifest,
        study_id=str(meta["study_id"]),
        scoring_identity=str(meta["scoring_identity"]),
        denominator_derivation=str(meta["denominator_derivation"]),
    )
