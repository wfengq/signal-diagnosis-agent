"""Checkpoint C — bounded public-source acquisition (EV-T011–EV-T014)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pytest

from signal_diag.evaluation.external.models import SourceCatalog, SourceCatalogEntry
from signal_diag.evaluation.external.source import (
    SourceExistsError,
    SourceLimitError,
    acquire_assets,
    validate_source_catalog,
)

_DEFAULT_TERMS_SHA256 = "d" * 64


class FailIfCalledOpener:
    def open(self, url: str) -> Iterator[BinaryIO]:
        raise AssertionError(f"network opener must not be called for {url}")


class BytesOpener:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.opened_urls: list[str] = []

    @contextmanager
    def open(self, url: str) -> Iterator[BinaryIO]:
        self.opened_urls.append(url)
        yield BytesIO(self.payload)


def _catalog_entry(
    *,
    source_id: str = "src_001",
    direct_asset_url: str = "https://github.com/example/project/archive/main.zip",
    authoritative_page_url: str = "https://github.com/example/project",
    terms_url: str = "https://github.com/example/project/blob/main/LICENSE",
    maximum_bytes: int = 1024,
    published_checksum: str | None = None,
) -> SourceCatalogEntry:
    return SourceCatalogEntry(
        source_id=source_id,
        official_name="Example Source",
        authoritative_page_url=authoritative_page_url,
        direct_asset_url=direct_asset_url,
        citation="Example et al., 2026",
        terms_url=terms_url,
        terms_snapshot_sha256=_DEFAULT_TERMS_SHA256,
        upstream_asset_id=f"asset_{source_id}",
        upstream_group_id=f"group_{source_id}",
        published_checksum=published_checksum,
        maximum_bytes=maximum_bytes,
        license_classification="research_use",
        redistribution_decision="reference_only",
        attribution="Example Source Project",
    )


def one_asset_catalog(*, expected_max_bytes: int = 1024) -> SourceCatalog:
    return SourceCatalog(
        catalog_id="catalog_test",
        version="1.0.0",
        sources=(_catalog_entry(maximum_bytes=expected_max_bytes),),
    )


@pytest.fixture
def catalog() -> SourceCatalog:
    return one_asset_catalog()


def test_ev_t011_network_is_opt_in(tmp_path: Path, catalog: SourceCatalog) -> None:
    with pytest.raises(PermissionError, match="--allow-network"):
        acquire_assets(
            catalog,
            tmp_path,
            opener=FailIfCalledOpener(),
            allow_network=False,
            max_total_bytes=5 * 1024**3,
        )


def test_ev_t012_partial_or_oversize_download_is_removed(tmp_path: Path) -> None:
    opener = BytesOpener(b"x" * 33)
    with pytest.raises(SourceLimitError):
        acquire_assets(
            one_asset_catalog(expected_max_bytes=32),
            tmp_path,
            opener=opener,
            allow_network=True,
            max_total_bytes=32,
        )
    assert list(tmp_path.iterdir()) == []


def test_ev_t013_approved_host_policy_rejects_http() -> None:
    catalog = SourceCatalog(
        catalog_id="catalog_bad",
        version="1.0.0",
        sources=(
            _catalog_entry(
                direct_asset_url="http://github.com/example/project/archive/main.zip",
            ),
        ),
    )
    with pytest.raises(ValueError, match="must use HTTPS"):
        validate_source_catalog(catalog)


def test_ev_t013_approved_host_policy_rejects_unknown_host() -> None:
    catalog = SourceCatalog(
        catalog_id="catalog_bad",
        version="1.0.0",
        sources=(
            _catalog_entry(
                direct_asset_url="https://example.com/audio/sample.wav",
            ),
        ),
    )
    with pytest.raises(ValueError, match="approved host"):
        validate_source_catalog(catalog)


def test_ev_t014_existing_digest_is_not_overwritten(tmp_path: Path) -> None:
    payload = b"already-on-disk"
    digest = hashlib.sha256(payload).hexdigest()
    catalog = SourceCatalog(
        catalog_id="catalog_existing",
        version="1.0.0",
        sources=(_catalog_entry(published_checksum=digest),),
    )
    existing_path = tmp_path / f"{digest}.asset"
    existing_path.write_bytes(payload)

    opener = BytesOpener(b"new-bytes")
    with pytest.raises(SourceExistsError):
        acquire_assets(
            catalog,
            tmp_path,
            opener=opener,
            allow_network=True,
            max_total_bytes=1024,
        )
    assert existing_path.read_bytes() == payload
    assert opener.opened_urls == []


def test_acquire_assets_writes_expected_file_and_metadata(tmp_path: Path) -> None:
    payload = b"external-wav-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    catalog = one_asset_catalog()
    before = datetime.now(UTC)
    assets = acquire_assets(
        catalog,
        tmp_path,
        opener=BytesOpener(payload),
        allow_network=True,
        max_total_bytes=1024,
    )
    after = datetime.now(UTC)
    assert len(assets) == 1
    asset = assets[0]
    assert asset.asset_id == "src_001"
    assert asset.sha256 == digest
    assert asset.byte_count == len(payload)
    assert before <= asset.acquired_at_utc <= after
    written = tmp_path / f"{digest}.asset"
    assert written.read_bytes() == payload


def test_acquire_assets_validates_published_checksum(tmp_path: Path) -> None:
    catalog = SourceCatalog(
        catalog_id="catalog_checksum",
        version="1.0.0",
        sources=(_catalog_entry(published_checksum="f" * 64),),
    )
    with pytest.raises(ValueError, match="published checksum mismatch"):
        acquire_assets(
            catalog,
            tmp_path,
            opener=BytesOpener(b"mismatch"),
            allow_network=True,
            max_total_bytes=1024,
        )
    assert list(tmp_path.iterdir()) == []
