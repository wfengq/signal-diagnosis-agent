"""Knowledge corpus model tests (T106 prerequisites)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_diag.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeMatch,
    KnowledgeRetrievalResult,
)


def test_knowledge_chunk_contract_is_frozen() -> None:
    chunk = KnowledgeChunk(
        chunk_id="chunk_clipping_001",
        document_id="doc_clipping",
        title="Clipping / Observable evidence",
        excerpt="Flat tops and a non-zero clipping ratio support clipping.",
        tags=("clipping", "flat-top"),
        heading_path=("Clipping", "Observable evidence"),
    )
    assert chunk.model_dump()["chunk_id"] == "chunk_clipping_001"
    with pytest.raises(ValidationError):
        KnowledgeChunk(
            chunk_id="bad",
            document_id="doc_clipping",
            title="x",
            excerpt="x",
        )


def test_knowledge_document_requires_non_empty_fields() -> None:
    document = KnowledgeDocument(
        document_id="doc_clipping",
        title="Clipping",
        source_path="clipping.md",
        tags=("clipping",),
        version="abc123def456",
    )
    assert document.tags == ("clipping",)
    with pytest.raises(ValidationError):
        KnowledgeDocument(
            document_id="doc_bad",
            title="",
            source_path="clipping.md",
            version="v1",
        )


def test_knowledge_match_and_retrieval_defaults() -> None:
    chunk = KnowledgeChunk(
        chunk_id="chunk_clipping_000",
        document_id="doc_clipping",
        title="Observable evidence",
        excerpt="Flat tops support clipping.",
    )
    match = KnowledgeMatch(
        document_id="doc_clipping",
        chunk_id="chunk_clipping_000",
    )
    assert match.matched_terms == ()
    result = KnowledgeRetrievalResult(
        retrieval_id="know_test_001",
        matches=(match,),
        chunks=(chunk,),
    )
    assert result.query_text == ""
    assert result.query_tags == ()
