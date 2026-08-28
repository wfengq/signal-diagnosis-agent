"""KnowledgeIndex deterministic retrieval tests (T106–T112)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from signal_diag.knowledge.index import KnowledgeIndex

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXED_CORPUS_ROOT = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "corpus"


@pytest.fixture
def corpus_root(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "alpha.md").write_text(
        "# Alpha topic\n"
        "Tags: alpha-tag, shared\n\n"
        "## First section\n"
        "Alpha first excerpt about distortion.\n\n"
        "## Second section\n"
        "Alpha second excerpt mentions THD and clipping together.\n",
        encoding="utf-8",
    )
    (root / "beta.md").write_text(
        "# Beta topic\n"
        "Tags: beta-tag\n\n"
        "## Overview\n"
        "Beta overview with clipping context.\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def index(corpus_root: Path) -> KnowledgeIndex:
    return KnowledgeIndex(corpus_root)


def test_t106_fixed_corpus_produces_stable_chunks() -> None:
    first = KnowledgeIndex(FIXED_CORPUS_ROOT).retrieve(query_text="clipping")
    second = KnowledgeIndex(FIXED_CORPUS_ROOT).retrieve(query_text="clipping")
    assert first.chunks == second.chunks
    assert first.chunks[0].chunk_id == "chunk_clipping_000"


def test_t107_empty_query_and_invalid_limit(index: KnowledgeIndex) -> None:
    result = index.retrieve(query_text="")
    assert result.query_text == ""
    assert result.matches == ()
    assert result.chunks == ()
    with pytest.raises(ValueError, match="max_results"):
        index.retrieve(query_text="clipping", max_results=0)


def test_t108_unicode_casefold_punctuation_and_dedup(index: KnowledgeIndex) -> None:
    result = index.retrieve(query_text="THD, thd; CLIPPING!")
    assert result.matches
    assert result.matches[0].matched_terms == ("thd", "clipping")


def test_t109_tag_matching_is_strip_only_and_case_sensitive(index: KnowledgeIndex) -> None:
    by_tag = index.retrieve(query_text="", tags=(" alpha-tag ",))
    assert by_tag.matches
    assert by_tag.matches[0].matched_tags == ("alpha-tag",)
    no_match = index.retrieve(query_text="", tags=("ALPHA-TAG",))
    assert no_match.matches == ()


def test_t110_matches_and_chunks_are_one_to_one(index: KnowledgeIndex) -> None:
    result = index.retrieve(query_text="distortion")
    assert len(result.matches) == len(result.chunks)
    assert [match.chunk_id for match in result.matches] == [
        chunk.chunk_id for chunk in result.chunks
    ]


def test_t111_ranking_is_deterministic(index: KnowledgeIndex) -> None:
    first = index.retrieve(query_text="distortion clipping")
    second = index.retrieve(query_text="distortion clipping")
    assert first.matches == second.matches
    assert first.chunks == second.chunks
    scores = [
        len(match.matched_terms) + len(match.matched_tags) for match in first.matches
    ]
    assert scores == sorted(scores, reverse=True)


def test_t112_knowledge_index_isolation() -> None:
    index_path = PROJECT_ROOT / "src" / "signal_diag" / "knowledge" / "index.py"
    source = index_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(index_path))
    forbidden_prefixes = (
        "signal_diag.agent",
        "signal_diag.rules",
        "signal_diag.dsp",
        "signal_diag.tools",
        "signal_diag.evaluation",
        "signal_diag.app",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules = [node.module]
        else:
            continue
        for module in modules:
            for prefix in forbidden_prefixes:
                assert not (
                    module == prefix or module.startswith(f"{prefix}.")
                ), f"forbidden import: {module}"


def test_malformed_document_raises_value_error(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "broken.md").write_text("No heading here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        KnowledgeIndex(corpus)
