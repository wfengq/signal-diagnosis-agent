"""Append-only contextual evaluation sealing and verification."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from signal_diag.evaluation.contextual.manifest import (
    canonical_json_bytes,
    manifest_sha256,
    validate_contextual_manifest,
)
from signal_diag.evaluation.contextual.models import ContextualManifest

_CHECKSUM_LINE = "{digest}  {name}\n"


def _sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def seal_contextual_bundle(
    *,
    destination: Path,
    manifest: ContextualManifest,
    wav_checksums: dict[str, str],
    source_decisions: dict[str, object],
    product_code_sha256: str,
    prompt_sha256: str,
    profile_s1_sha256: str,
    profile_contextual_sha256: str,
    scoring_identity: str,
    slot_plan: list[dict[str, object]],
    execution_counters: dict[str, int],
) -> Path:
    if destination.exists():
        raise FileExistsError(f"seal destination already exists: {destination}")
    validate_contextual_manifest(manifest)
    destination.mkdir(parents=True)
    (destination / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (destination / "wav_checksums.json").write_text(
        json.dumps(wav_checksums, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "source_decisions.json").write_text(
        json.dumps(source_decisions, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "slot_plan.json").write_text(
        json.dumps(slot_plan, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    meta = {
        "manifest_sha256": manifest_sha256(manifest),
        "product_code_sha256": product_code_sha256,
        "prompt_sha256": prompt_sha256,
        "profile_s1_sha256": profile_s1_sha256,
        "profile_contextual_sha256": profile_contextual_sha256,
        "scoring_identity": scoring_identity,
        "execution_counters": execution_counters,
    }
    (destination / "seal_meta.json").write_text(
        json.dumps(meta, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    lines: list[str] = []
    for name in sorted(
        path.name for path in destination.iterdir() if path.is_file()
    ):
        digest = _sha256_file(destination / name)
        lines.append(_CHECKSUM_LINE.format(digest=digest, name=name))
    (destination / "seal.sha256").write_text("".join(lines), encoding="utf-8")
    return destination


def verify_contextual_bundle(destination: Path) -> None:
    seal_path = destination / "seal.sha256"
    if not seal_path.is_file():
        raise FileNotFoundError("missing seal.sha256")
    records: dict[str, str] = {}
    for raw in seal_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        digest, name = raw.split("  ", 1)
        if name in records:
            raise ValueError(f"duplicate sealed artifact: {name}")
        records[name] = digest
    required = {
        "manifest.json",
        "wav_checksums.json",
        "source_decisions.json",
        "slot_plan.json",
        "seal_meta.json",
    }
    missing = sorted(required - records.keys())
    if missing:
        raise ValueError(f"missing sealed artifact: {missing[0]}")
    for name, expected in sorted(records.items()):
        path = destination / name
        if not path.is_file():
            raise FileNotFoundError(f"sealed artifact missing on disk: {name}")
        actual = _sha256_file(path)
        if actual != expected:
            raise ValueError(f"seal hash mismatch for {name}")
    # Credentials must never be required for verification.
    if any("api_key" in name.lower() for name in records):
        raise ValueError("seal must not include planner credentials")
    manifest = ContextualManifest.model_validate_json(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    validate_contextual_manifest(manifest)
