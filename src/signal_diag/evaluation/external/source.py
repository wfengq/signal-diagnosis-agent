"""Explicit, bounded public-source acquisition for the external validity study."""

from __future__ import annotations

import hashlib
import os
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.parse import urlparse

from signal_diag.evaluation.external.models import (
    AcquiredAsset,
    SourceCatalog,
    SourceCatalogEntry,
)

_CHUNK_SIZE_BYTES = 1024 * 1024
_APPROVED_HOSTS = frozenset(
    {
        "www.es.aau.dk",
        "github.com",
        "raw.githubusercontent.com",
        "magenta.withgoogle.com",
        "storage.googleapis.com",
    }
)


class SourceLimitError(Exception):
    """Raised when a download exceeds configured byte limits."""


class SourceExistsError(Exception):
    """Raised when an existing acquired asset would be overwritten."""


class UrlOpener(Protocol):
    def open(self, url: str) -> AbstractContextManager[BinaryIO]: ...


def validate_source_catalog(catalog: SourceCatalog) -> None:
    """Validate HTTPS host policy for every catalog URL field."""
    for entry in catalog.sources:
        _validate_https_url(entry.authoritative_page_url, "authoritative_page_url")
        _validate_https_url(entry.direct_asset_url, "direct_asset_url")
        _validate_https_url(entry.terms_url, "terms_url")


def acquire_assets(
    catalog: SourceCatalog,
    destination: Path,
    *,
    opener: UrlOpener,
    allow_network: bool,
    max_total_bytes: int,
) -> tuple[AcquiredAsset, ...]:
    """Download catalog assets with explicit network authorization and byte limits."""
    if not allow_network:
        msg = "network acquisition requires --allow-network"
        raise PermissionError(msg)

    validate_source_catalog(catalog)
    destination.mkdir(parents=True, exist_ok=True)

    acquired: list[AcquiredAsset] = []
    remaining_campaign_bytes = max_total_bytes
    created_paths: list[Path] = []

    try:
        for entry in catalog.sources:
            if remaining_campaign_bytes <= 0:
                raise SourceLimitError("campaign byte budget exhausted")

            per_file_limit = min(entry.maximum_bytes, remaining_campaign_bytes)
            _reject_existing_asset(entry, destination)

            partial_path = destination / f"{entry.source_id}.partial"
            final_path, digest, byte_count = _stream_asset(
                entry,
                partial_path=partial_path,
                destination=destination,
                opener=opener,
                byte_limit=per_file_limit,
            )
            created_paths.append(final_path)

            if (
                entry.published_checksum is not None
                and digest != entry.published_checksum
            ):
                msg = (
                    f"published checksum mismatch for {entry.source_id}: "
                    f"expected {entry.published_checksum}, got {digest}"
                )
                raise ValueError(msg)

            acquired.append(
                AcquiredAsset(
                    asset_id=entry.source_id,
                    source_url=entry.direct_asset_url,
                    sha256=digest,
                    byte_count=byte_count,
                    acquired_at_utc=datetime.now(UTC),
                ),
            )
            remaining_campaign_bytes -= byte_count
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        for path in destination.glob("*.partial"):
            path.unlink(missing_ok=True)
        raise

    return tuple(acquired)


def _reject_existing_asset(entry: SourceCatalogEntry, destination: Path) -> None:
    partial_path = destination / f"{entry.source_id}.partial"
    if partial_path.exists():
        msg = f"partial download already exists: {partial_path.name}"
        raise SourceExistsError(msg)

    if entry.published_checksum is not None:
        digest_path = destination / f"{entry.published_checksum}.asset"
        if digest_path.exists():
            msg = f"existing digest already acquired: {entry.published_checksum}"
            raise SourceExistsError(msg)


def _validate_https_url(url: str, field_name: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        msg = f"{field_name} must use HTTPS"
        raise ValueError(msg)
    if parsed.hostname not in _APPROVED_HOSTS:
        msg = f"{field_name} host is not an approved host"
        raise ValueError(msg)


def _stream_asset(
    entry: SourceCatalogEntry,
    *,
    partial_path: Path,
    destination: Path,
    opener: UrlOpener,
    byte_limit: int,
) -> tuple[Path, str, int]:
    digest = hashlib.sha256()
    total_read = 0

    try:
        with (
            opener.open(entry.direct_asset_url) as stream,
            partial_path.open(
                "xb",
            ) as handle,
        ):
            while True:
                chunk = stream.read(_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > byte_limit:
                    raise SourceLimitError(
                        f"asset {entry.source_id} exceeds byte limit {byte_limit}",
                    )
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise

    hexdigest = digest.hexdigest()
    final_path = destination / f"{hexdigest}.asset"
    if final_path.exists():
        partial_path.unlink(missing_ok=True)
        msg = f"existing digest already acquired: {hexdigest}"
        raise SourceExistsError(msg)

    partial_path.replace(final_path)
    return final_path, hexdigest, total_read
