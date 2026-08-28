"""Curated knowledge corpus and retrieval result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str = Field(pattern=r"^doc_")
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    version: str = Field(min_length=1)


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(pattern=r"^chunk_")
    document_id: str = Field(pattern=r"^doc_")
    title: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    heading_path: tuple[str, ...] = ()


class KnowledgeMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str = Field(pattern=r"^doc_")
    chunk_id: str = Field(pattern=r"^chunk_")
    matched_terms: tuple[str, ...] = ()
    matched_tags: tuple[str, ...] = ()


class KnowledgeRetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    retrieval_id: str = Field(pattern=r"^know_")
    query_text: str = Field(default="")
    query_tags: tuple[str, ...] = ()
    matches: tuple[KnowledgeMatch, ...]
    chunks: tuple[KnowledgeChunk, ...]
