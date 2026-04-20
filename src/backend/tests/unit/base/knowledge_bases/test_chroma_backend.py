"""Unit tests for ``ChromaBackend``.

Uses the in-process Chroma persistence to exercise the real backend rather
than mocking it out — this is the code path every other KB feature relies
on, so we want a real integration signal. Kept fast by scoping to
tmp_path-backed collections with tiny document sets.
"""

from __future__ import annotations

import gc
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.base.knowledge_bases.backends import (
    BackendType,
    ChromaBackend,
    IngestedDocument,
)
from lfx.base.knowledge_bases.backends.base import (
    METADATA_KEY_JOB_ID,
    METADATA_KEY_SOURCE,
    METADATA_KEY_SOURCE_TYPE,
)


class _DeterministicEmbeddings(Embeddings):
    """Hash-based embedder so tests don't need OpenAI/HF credentials.

    Produces a small fixed-length vector whose components are derived from
    the text — stable across runs, distinct enough that nearest-neighbour
    search returns sensible orderings for short inputs.
    """

    DIMENSION = 8

    def _embed(self, text: str) -> list[float]:
        h = abs(hash(text))
        return [((h >> (i * 4)) & 0xF) / 15.0 for i in range(self.DIMENSION)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@pytest.fixture
async def backend(tmp_path: Path):
    """Create a backend; async teardown runs after the test unconditionally."""
    (tmp_path / "unit_test_kb").mkdir(parents=True, exist_ok=True)
    bk = ChromaBackend(
        kb_name="unit_test_kb",
        kb_path=tmp_path / "unit_test_kb",
        embedding_function=_DeterministicEmbeddings(),
    )
    try:
        yield bk
    finally:
        await bk.teardown()
        gc.collect()


class TestChromaBackendLifecycle:
    """Smoke tests covering construction, lazy build, and teardown."""

    def test_backend_type_constant(self, backend: ChromaBackend):
        assert backend.backend_type is BackendType.CHROMA

    def test_vector_store_is_lazy(self, tmp_path: Path):
        bk = ChromaBackend(
            kb_name="lazy_kb",
            kb_path=tmp_path / "lazy_kb",
            embedding_function=_DeterministicEmbeddings(),
        )
        assert bk._vector_store is None
        # Touching the property triggers _build_vector_store.
        (tmp_path / "lazy_kb").mkdir(parents=True, exist_ok=True)
        _ = bk.vector_store
        assert bk._vector_store is not None

    async def test_teardown_is_idempotent(self, backend: ChromaBackend):
        """Teardown must be safe from ``finally`` blocks even if never touched."""
        await backend.teardown()
        await backend.teardown()  # second call should not raise


class TestChromaBackendDocumentLifecycle:
    """End-to-end: add → count → iter → search → delete."""

    async def test_add_documents_is_noop_on_empty_list(self, backend: ChromaBackend):
        await backend.add_documents([])
        assert await backend.count() == 0

    async def test_add_and_count(self, backend: ChromaBackend):
        docs = [
            Document(
                page_content=f"content {i}",
                metadata={METADATA_KEY_SOURCE: "test", METADATA_KEY_SOURCE_TYPE: "file_upload"},
            )
            for i in range(3)
        ]
        await backend.add_documents(docs)
        assert await backend.count() == 3

    async def test_iter_documents_yields_batches(self, backend: ChromaBackend):
        docs = [Document(page_content=f"content {i}", metadata={METADATA_KEY_SOURCE: f"src{i}"}) for i in range(5)]
        await backend.add_documents(docs)

        batches: list[list[IngestedDocument]] = [batch async for batch in backend.iter_documents(batch_size=2)]
        total = sum(len(b) for b in batches)
        assert total == 5
        # All items should be ``IngestedDocument`` instances with metadata preserved.
        all_contents = [item.content for batch in batches for item in batch]
        assert set(all_contents) == {f"content {i}" for i in range(5)}

    async def test_iter_documents_returns_empty_for_empty_collection(self, backend: ChromaBackend):
        batches = [batch async for batch in backend.iter_documents()]
        assert batches == []

    async def test_similarity_search_returns_tuples(self, backend: ChromaBackend):
        await backend.add_documents(
            [
                Document(page_content="alpha", metadata={}),
                Document(page_content="beta", metadata={}),
            ]
        )
        results = await backend.similarity_search("alpha", k=2)
        assert len(results) == 2
        # Default (no scores) path should return zero-score sentinel tuples.
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
        assert all(score == 0.0 for _, score in results)

    async def test_similarity_search_with_scores(self, backend: ChromaBackend):
        await backend.add_documents(
            [Document(page_content="alpha", metadata={}), Document(page_content="beta", metadata={})]
        )
        results = await backend.similarity_search("alpha", k=1, with_scores=True)
        assert len(results) == 1
        _doc, score = results[0]
        # Any real float score is fine; we just confirm Chroma's actual score plumbs through.
        assert isinstance(score, float)

    async def test_delete_by_removes_matching_documents(self, backend: ChromaBackend):
        """Per-job rollback is the critical correctness property here."""
        await backend.add_documents(
            [
                Document(
                    page_content="job-a doc",
                    metadata={METADATA_KEY_JOB_ID: "job-a", METADATA_KEY_SOURCE: "a"},
                ),
                Document(
                    page_content="job-b doc",
                    metadata={METADATA_KEY_JOB_ID: "job-b", METADATA_KEY_SOURCE: "b"},
                ),
            ]
        )
        assert await backend.count() == 2
        await backend.delete_by({METADATA_KEY_JOB_ID: "job-a"})
        assert await backend.count() == 1

        # Only the job-b doc should remain.
        remaining = [item async for batch in backend.iter_documents() for item in batch]
        assert len(remaining) == 1
        assert remaining[0].metadata.get(METADATA_KEY_JOB_ID) == "job-b"


class TestChromaBackendStorage:
    async def test_storage_size_reports_nonzero_after_ingest(self, backend: ChromaBackend):
        await backend.add_documents([Document(page_content="hello world", metadata={})])
        size = await backend.storage_size_bytes()
        assert size > 0

    async def test_storage_size_is_zero_for_missing_path(self, tmp_path: Path):
        bk = ChromaBackend(
            kb_name="ghost_kb",
            kb_path=tmp_path / "does_not_exist",
            embedding_function=_DeterministicEmbeddings(),
        )
        assert await bk.storage_size_bytes() == 0
