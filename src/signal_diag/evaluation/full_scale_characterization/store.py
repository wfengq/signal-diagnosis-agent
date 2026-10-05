"""Write-once characterization artifact directory with SHA256SUMS (T-CX378).

Layout follows plan D (``docs/evaluations/v0_3/full_scale_characterization/<round>/``).
Every artifact is written exactly once; ``SHA256SUMS`` is the only file that is
rewritten, and only by appending entries.  Shards are deterministic gzip
(``mtime=0``, fixed level) of canonical JSON lines.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from signal_diag.evaluation.full_scale_characterization.gate import (
    require_validation_access,
)

SHARD_MAX_BYTES = 50_000_000
GZIP_LEVEL = 9
SUMS_NAME = "SHA256SUMS"

_FAMILY = r"[A-Za-z0-9_]+"
_ALLOWED = tuple(
    re.compile(p)
    for p in (
        r"manifest\.json",
        r"identity\.json",
        rf"calibration_measurements/{_FAMILY}\.jsonl\.gz",
        rf"calibration_pairs/{_FAMILY}\.jsonl\.gz",
        r"calibration_report_stage1\.(json|md)",
        r"freeze_record_stage1\.json",
        r"calibration_report_stage2\.(json|md)",
        r"freeze_record\.json",
        rf"validation_measurements/{_FAMILY}\.jsonl\.gz",
        rf"validation_pairs/{_FAMILY}\.jsonl\.gz",
        r"validation_report\.(json|md)",
        r"abort_record\.json",
    )
)


class WriteOnceViolation(FileExistsError):
    """An artifact already exists and may not be rewritten."""


class ShardTooLarge(Exception):
    """A compressed shard exceeds the 50 MB stop limit (A.7 / A.13)."""


class StoreIntegrityError(Exception):
    """SHA256SUMS and the files on disk disagree."""


def canonical_json_line(row: Mapping[str, Any] | BaseModel) -> str:
    payload = row.model_dump(mode="json") if isinstance(row, BaseModel) else dict(row)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_json_document(payload: Mapping[str, Any] | BaseModel) -> str:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else dict(payload)
    return json.dumps(data, sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False) + "\n"


def deterministic_gzip(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=GZIP_LEVEL, mtime=0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_validation_path(relpath: str) -> bool:
    return relpath.startswith("validation_")


class CharacterizationStore:
    """One round directory; artifacts are written once and listed in SHA256SUMS."""

    def __init__(self, round_dir: Path) -> None:
        self.root = Path(round_dir)

    # -- paths -------------------------------------------------------------

    def _check_relpath(self, relpath: str) -> str:
        if not any(p.fullmatch(relpath) for p in _ALLOWED):
            raise ValueError(f"{relpath!r} is not a characterization artifact path")
        return relpath

    def path(self, relpath: str) -> Path:
        return self.root / self._check_relpath(relpath)

    def exists(self, relpath: str) -> bool:
        return self.path(relpath).exists()

    # -- reading -----------------------------------------------------------

    def read_bytes(self, relpath: str) -> bytes:
        return self.path(relpath).read_bytes()

    def read_json(self, relpath: str) -> Any:
        return json.loads(self.read_bytes(relpath).decode("utf-8"))

    def file_sha256(self, relpath: str) -> str:
        return sha256_bytes(self.read_bytes(relpath))

    def directory_sha256(self, directory: str) -> str:
        """Combined digest of every shard under ``directory`` (sorted ``path\\0sha\\n``)."""
        digest = hashlib.sha256()
        base = self.root / directory
        if base.is_dir():
            for path in sorted(base.iterdir()):
                relpath = f"{directory}/{path.name}"
                digest.update(f"{relpath}\0{self.file_sha256(relpath)}\n".encode())
        return digest.hexdigest()

    # -- writing -----------------------------------------------------------

    def write_bytes(self, relpath: str, data: bytes, *, validation_access: object = None) -> str:
        target = self.path(relpath)
        if _is_validation_path(relpath):
            require_validation_access(validation_access, what=f"write {relpath}")
        if target.exists():
            raise WriteOnceViolation(f"{relpath} already exists; artifacts are written once")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
        digest = sha256_bytes(data)
        self._append_sum(relpath, digest)
        return digest

    def write_text(self, relpath: str, text: str, *, validation_access: object = None) -> str:
        return self.write_bytes(relpath, text.encode("utf-8"), validation_access=validation_access)

    def write_json(
        self, relpath: str, payload: Mapping[str, Any] | BaseModel, *, validation_access: object = None
    ) -> str:
        return self.write_text(
            relpath, canonical_json_document(payload), validation_access=validation_access
        )

    def write_jsonl_gz(
        self,
        relpath: str,
        rows: Iterable[Mapping[str, Any] | BaseModel],
        *,
        validation_access: object = None,
    ) -> str:
        if not relpath.endswith(".jsonl.gz"):
            raise ValueError(f"{relpath!r} is not a .jsonl.gz shard")
        self._check_relpath(relpath)
        if _is_validation_path(relpath):
            require_validation_access(validation_access, what=f"write {relpath}")
        text = "".join(canonical_json_line(row) + "\n" for row in rows)
        data = deterministic_gzip(text.encode("utf-8"))
        if len(data) > SHARD_MAX_BYTES:
            raise ShardTooLarge(
                f"{relpath}: compressed size {len(data)} B exceeds {SHARD_MAX_BYTES} B; "
                "stop for an operator decision"
            )
        return self.write_bytes(relpath, data, validation_access=validation_access)

    # -- SHA256SUMS --------------------------------------------------------

    def read_sums(self) -> dict[str, str]:
        sums_path = self.root / SUMS_NAME
        if not sums_path.exists():
            return {}
        sums: dict[str, str] = {}
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            digest, relpath = line.split("  ", 1)
            sums[relpath] = digest
        return sums

    def _append_sum(self, relpath: str, digest: str) -> None:
        sums = self.read_sums()
        if relpath in sums:
            raise WriteOnceViolation(f"{relpath} is already listed in {SUMS_NAME}")
        sums[relpath] = digest
        text = "".join(f"{sums[p]}  {p}\n" for p in sorted(sums))
        (self.root / SUMS_NAME).write_text(text, encoding="utf-8")

    def verify_sha256sums(self) -> None:
        sums = self.read_sums()
        problems: list[str] = []
        for relpath, digest in sorted(sums.items()):
            path = self.root / relpath
            if not path.is_file():
                problems.append(f"missing {relpath}")
            elif sha256_bytes(path.read_bytes()) != digest:
                problems.append(f"sha256 mismatch {relpath}")
        if self.root.is_dir():
            for path in sorted(self.root.rglob("*")):
                if not path.is_file() or path.name == SUMS_NAME:
                    continue
                relpath = path.relative_to(self.root).as_posix()
                if relpath not in sums:
                    problems.append(f"unlisted {relpath}")
        if problems:
            raise StoreIntegrityError("; ".join(problems))
