"""Deterministic keyword and tag retrieval over a local corpus."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from signal_diag.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeMatch,
    KnowledgeRetrievalResult,
)


@dataclass(frozen=True)
class _IndexedChunk:
    document: KnowledgeDocument
    chunk: KnowledgeChunk


def _tokens(text: str) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for token in re.split(r"[\W_]+", text.casefold()):
        if token and token not in seen:
            seen.add(token)
            output.append(token)
    return tuple(output)


def _normalize_stem(stem: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()


def _document_id(stem: str) -> str:
    return f"doc_{_normalize_stem(stem)}"


def _chunk_id(stem: str, ordinal: int) -> str:
    return f"chunk_{_normalize_stem(stem)}_{ordinal:03d}"


def _parse_tags(line: str) -> tuple[str, ...]:
    if not line.lower().startswith("tags:"):
        return ()
    raw = line.split(":", 1)[1]
    return tuple(tag.strip() for tag in raw.split(",") if tag.strip())


def _load_document(path: Path, corpus_root: Path) -> tuple[KnowledgeDocument, list[KnowledgeChunk]]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    title: str | None = None
    tags: tuple[str, ...] = ()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and title is None:
            title = stripped[2:].strip()
            continue
        if stripped.lower().startswith("tags:"):
            tags = _parse_tags(stripped)
            continue
        if stripped and title is not None:
            break
    if title is None:
        raise ValueError(f"malformed knowledge document missing H1 title: {path.name}")

    stem = path.stem
    document = KnowledgeDocument(
        document_id=_document_id(stem),
        title=title,
        source_path=str(path.relative_to(corpus_root)).replace("\\", "/"),
        tags=tags,
        version=hashlib.sha256(content.encode("utf-8")).hexdigest()[:12],
    )

    section_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    matches = list(section_pattern.finditer(content))
    if not matches:
        raise ValueError(f"malformed knowledge document missing H2 sections: {path.name}")

    chunks: list[KnowledgeChunk] = []
    for ordinal, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[ordinal + 1].start() if ordinal + 1 < len(matches) else len(content)
        excerpt = content[start:end].strip()
        if not excerpt:
            raise ValueError(f"empty excerpt in knowledge document: {path.name}")
        chunks.append(
            KnowledgeChunk(
                chunk_id=_chunk_id(stem, ordinal),
                document_id=document.document_id,
                title=f"{title} / {heading}",
                excerpt=excerpt,
                tags=tags,
                heading_path=(title, heading),
            )
        )
    return document, chunks


def _load_corpus(corpus_root: Path) -> list[_IndexedChunk]:
    indexed: list[_IndexedChunk] = []
    for path in sorted(corpus_root.glob("*.md")):
        document, chunks = _load_document(path, corpus_root)
        indexed.extend(_IndexedChunk(document=document, chunk=item) for item in chunks)
    return indexed


def _chunk_tokens(item: _IndexedChunk) -> set[str]:
    parts = [
        item.chunk.title,
        item.chunk.excerpt,
        *item.chunk.heading_path,
        *item.chunk.tags,
        *item.document.tags,
    ]
    tokens: set[str] = set()
    for part in parts:
        tokens.update(_tokens(part))
    return tokens


def _trace_id(prefix: str, payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


class KnowledgeIndex:
    def __init__(self, corpus_root: Path) -> None:
        self._corpus_root = corpus_root
        self._indexed_chunks = _load_corpus(corpus_root)

    def retrieve(
        self,
        *,
        query_text: str,
        tags: Sequence[str] = (),
        max_results: int = 5,
    ) -> KnowledgeRetrievalResult:
        if max_results < 1:
            raise ValueError("max_results must be at least 1")

        query_terms = _tokens(query_text)
        query_tags = tuple(tag.strip() for tag in tags if tag.strip())

        if not query_terms and not query_tags:
            return KnowledgeRetrievalResult(
                retrieval_id=_trace_id(
                    "know_",
                    {
                        "query_text": "",
                        "query_tags": [],
                        "match_ids": [],
                    },
                ),
                query_text="",
                query_tags=query_tags,
                matches=(),
                chunks=(),
            )

        ranked: list[tuple[int, str, str, KnowledgeMatch, KnowledgeChunk]] = []
        for item in self._indexed_chunks:
            chunk_tag_set = set(item.chunk.tags) | set(item.document.tags)
            matched_tags = tuple(tag for tag in query_tags if tag in chunk_tag_set)
            chunk_tokens = _chunk_tokens(item)
            matched_terms = tuple(term for term in query_terms if term in chunk_tokens)
            if not matched_terms and not matched_tags:
                continue
            score = len(matched_terms) + len(matched_tags)
            match = KnowledgeMatch(
                document_id=item.document.document_id,
                chunk_id=item.chunk.chunk_id,
                matched_terms=matched_terms,
                matched_tags=matched_tags,
            )
            ranked.append(
                (
                    score,
                    item.document.document_id,
                    item.chunk.chunk_id,
                    match,
                    item.chunk,
                )
            )

        ranked.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
        selected = ranked[:max_results]
        matches = tuple(entry[3] for entry in selected)
        chunks = tuple(entry[4] for entry in selected)
        retrieval_payload: dict[str, object] = {
            "query_text": query_text,
            "query_tags": list(query_tags),
            "match_ids": [match.chunk_id for match in matches],
        }
        return KnowledgeRetrievalResult(
            retrieval_id=_trace_id("know_", retrieval_payload),
            query_text=query_text,
            query_tags=query_tags,
            matches=matches,
            chunks=chunks,
        )
