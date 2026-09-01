"""Canonical external manifest loading and fingerprinting."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from signal_diag.evaluation.external.models import ExternalDatasetManifest

_FROZEN_SCHEMA_VERSION = "1.0"


def _contains_non_finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    if isinstance(value, dict):
        return any(_contains_non_finite(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_non_finite(item) for item in value)
    return False


def canonical_json_bytes(value: BaseModel) -> bytes:
    """Return sorted-key UTF-8 JSON bytes with a trailing newline."""
    payload = value.model_dump(mode="json")
    if _contains_non_finite(payload):
        raise ValueError("allow_nan=False")
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:
        raise ValueError("allow_nan=False") from exc
    return (text + "\n").encode("utf-8")


def manifest_sha256(manifest: ExternalDatasetManifest) -> str:
    """Return the SHA-256 hex digest of the canonical manifest bytes."""
    return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()


def load_external_manifest(path: Path) -> ExternalDatasetManifest:
    """Load and validate an external study manifest from *path*."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest = ExternalDatasetManifest.model_validate(payload)
    if manifest.schema_version != _FROZEN_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported external manifest schema: {manifest.schema_version}"
        )
    return manifest
