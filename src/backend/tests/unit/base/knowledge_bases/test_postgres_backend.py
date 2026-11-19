"""Live pgVector integration tests for ``PostgresBackend``.

Gated on an explicit opt-in plus a reachable pgvector database: set
``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and ``PGVECTOR_CONNECTION_STRING``
(and install the pgvector extra) to exercise the real add / search / count /
iter / delete path against Postgres; they skip cleanly otherwise.

The database-free unit tests for this backend live next to the code, in
``src/lfx/tests/unit/base/knowledge_bases/test_postgres_backend.py``.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.backends import create_backend
from lfx.base.knowledge_bases.backends.base import IngestedDocument

if TYPE_CHECKING:
    from pathlib import Path


# --------------------------------------------------------------------------
# Integration: requires a reachable pgvector database.
# --------------------------------------------------------------------------


def _require_live_pgvector() -> str:
    if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1":
        pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 to run live pgvector tests")
    conn = os.getenv("PGVECTOR_CONNECTION_STRING")
    if not conn:
        pytest.skip("PGVECTOR_CONNECTION_STRING not set — skipping live pgvector integration test")
    try:
        import pgvector  # noqa: F401
        from pgvector.sqlalchemy import Vector  # noqa: F401
    except (ImportError, RuntimeError):
        pytest.skip("pgvector client package not installed — install the pgvector extra")
    return conn


@pytest.fixture
def fake_embeddings():
    from langchain_core.embeddings import DeterministicFakeEmbedding

    return DeterministicFakeEmbedding(size=16)


@pytest.mark.api_key_required
class TestPostgresBackendLive:
    """Exercises the real vector path against a pgvector database when available."""

    async def test_full_lifecycle(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document

        kb_name = f"kb_it_{uuid.uuid4().hex[:8]}"
        backend = create_backend(
            "postgres",
            kb_name=kb_name,
            kb_path=tmp_path,
            backend_config={},
            embedding_function=fake_embeddings,
            user_id=uuid.uuid4(),
        )
        try:
            await backend.ensure_ready()
            tc = await backend.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            await backend.add_documents(
                [
                    Document(page_content="cats are great", metadata={"topic": "cats"}),
                    Document(page_content="dogs are loyal", metadata={"topic": "dogs"}),
                ]
            )
            assert await backend.count() == 2

            results = await backend.similarity_search("feline", k=1, with_scores=True)
            assert len(results) == 1  # inherited base similarity_search path

            streamed = 0
            async for batch in backend.iter_documents(batch_size=1):
                streamed += len(batch)
            assert streamed == 2

            await backend.delete_by({"topic": "dogs"})
            assert await backend.count() == 1
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_hnsw_index_created_on_ingest(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from sqlalchemy import text

        backend = create_backend(
            "postgres",
            kb_name=f"kb_idx_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=fake_embeddings,
            user_id=uuid.uuid4(),
        )
        try:
            await backend.ensure_ready()
            tc = await backend.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            await backend.add_documents([Document(page_content="hello", metadata={})])

            engine = backend._ensure_async_engine()
            async with engine.connect() as conn:
                index_defs = (
                    (
                        await conn.execute(
                            text("SELECT indexdef FROM pg_indexes WHERE tablename = :name"),
                            {"name": backend.table_name},
                        )
                    )
                    .scalars()
                    .all()
                )
            # A 16-dim table (well under the HNSW ceiling) must carry an HNSW index.
            assert any("hnsw" in definition.lower() for definition in index_defs), index_defs
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_similarity_search_plan_uses_hnsw_index(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from sqlalchemy import text

        backend = create_backend(
            "postgres",
            kb_name=f"kb_plan_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=fake_embeddings,
            user_id=uuid.uuid4(),
        )
        try:
            await backend.ensure_ready()
            tc = await backend.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            await backend.add_documents([Document(page_content=f"doc {i}", metadata={}) for i in range(50)])

            query_vector = await fake_embeddings.aembed_query("doc 1")
            literal = "[" + ",".join(str(v) for v in query_vector) + "]"
            engine = backend._ensure_async_engine()
            async with engine.begin() as conn:
                # Force the planner to prefer the ANN index for this tiny table so
                # the assertion is about "is the index usable", not planner cost.
                await conn.execute(text("SET LOCAL enable_seqscan = off"))
                plan_rows = (
                    (
                        await conn.execute(
                            text(
                                f'EXPLAIN SELECT id FROM "{backend.table_name}" '  # noqa: S608 — validated name
                                f"ORDER BY embedding <=> '{literal}'::vector LIMIT 5"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            plan = "\n".join(plan_rows)
            assert f"{backend.table_name}_hnsw" in plan, plan
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_mixed_embedding_dimensions_coexist(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from langchain_core.embeddings import DeterministicFakeEmbedding

        # Two KBs on the same deployment using different embedding dimensions.
        # The shared-table layout could not do this; per-collection typed tables can.
        small = create_backend(
            "postgres",
            kb_name=f"kb_small_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=DeterministicFakeEmbedding(size=8),
            user_id=uuid.uuid4(),
        )
        large = create_backend(
            "postgres",
            kb_name=f"kb_large_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=DeterministicFakeEmbedding(size=32),
            user_id=uuid.uuid4(),
        )
        try:
            await small.ensure_ready()
            tc = await small.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")

            assert small.table_name != large.table_name
            await small.add_documents([Document(page_content="a", metadata={})])
            await large.add_documents([Document(page_content="b", metadata={})])

            assert await small.count() == 1
            assert await large.count() == 1
            assert len(await small.similarity_search("a", k=1)) == 1
            assert len(await large.similarity_search("b", k=1)) == 1
        finally:
            for backend in (small, large):
                with contextlib.suppress(Exception):
                    await backend.delete_collection()
                await backend.teardown()


@pytest.mark.api_key_required
class TestPostgresEmbeddedDocumentsLive:
    """Write chunks with precomputed vectors, the path a KB migration uses."""

    def _backend(self, tmp_path: Path, *, embedding_function=None):
        return create_backend(
            "postgres",
            kb_name=f"kb_emb_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            embedding_function=embedding_function,
            user_id=uuid.uuid4(),
        )

    async def _read_all(self, backend):
        out = []
        async for batch in backend.iter_documents(batch_size=2, include_embeddings=True):
            out.extend(batch)
        return out

    async def test_copy_preserves_ids_and_vectors_without_an_embedder(self, tmp_path: Path, fake_embeddings) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document

        source = self._backend(tmp_path, embedding_function=fake_embeddings)
        # No embedding function on the target: nothing on this path may call a model.
        target = self._backend(tmp_path)
        try:
            await source.ensure_ready()
            tc = await source.test_connection()
            if not tc.ok:
                pytest.skip(f"pgvector not reachable: {tc.message}")
            await source.add_documents(
                [
                    Document(id="chunk-a", page_content="alpha", metadata={"n": 1}),
                    Document(id="chunk-b", page_content="beta", metadata={"n": 2}),
                    Document(id="chunk-c", page_content="gamma", metadata={"n": 3}),
                ]
            )
            original = await self._read_all(source)
            assert sorted(d.id for d in original) == ["chunk-a", "chunk-b", "chunk-c"]

            await target.add_embedded_documents(original)
            await target.add_embedded_documents(original)  # a re-run must upsert
            assert await target.count() == 3

            copied = {d.id: d for d in await self._read_all(target)}
            for doc in original:
                assert copied[doc.id].content == doc.content
                assert copied[doc.id].metadata == doc.metadata
                assert copied[doc.id].embedding == pytest.approx(doc.embedding)
        finally:
            for backend in (source, target):
                with contextlib.suppress(Exception):
                    await backend.delete_collection()
                await backend.teardown()


class TestPostgresJobReadsLive:
    """Read one ingestion job's chunks, the path a deploy copy uses."""

    @staticmethod
    async def _seeded(tmp_path: Path):
        backend = create_backend(
            "postgres",
            kb_name=f"kb_job_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            user_id=uuid.uuid4(),
        )
        docs = [
            IngestedDocument(id=f"a-{i}", content=f"a {i}", metadata={"job_id": "job-a"}, embedding=[i / 10, 1.0])
            for i in range(5)
        ] + [
            IngestedDocument(id=f"b-{i}", content=f"b {i}", metadata={"job_id": "job-b"}, embedding=[i / 10, 2.0])
            for i in range(3)
        ]
        await backend.add_embedded_documents([*docs, IngestedDocument(id="c", content="old", embedding=[0.5, 3.0])])
        return backend

    @staticmethod
    async def _read(backend, job_id, **kwargs):
        return [doc async for batch in backend.iter_job_documents(job_id, **kwargs) for doc in batch]

    async def test_two_jobs_read_back_apart_with_ids_and_vectors(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        backend = await self._seeded(tmp_path)
        try:
            job_a = await self._read(backend, "job-a", batch_size=2)
            assert [doc.id for doc in job_a] == [f"a-{i}" for i in range(5)]
            assert job_a[3].embedding == pytest.approx([0.3, 1.0])
            assert job_a[3].content == "a 3"
            assert await backend.count_job("job-a") == 5
            assert await backend.count_job("job-b") == 3
            assert await backend.count_job("job-missing") == 0
        finally:
            await backend.delete_collection()
            await backend.teardown()

    async def test_resuming_returns_only_what_is_left(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        backend = await self._seeded(tmp_path)
        try:
            rest = await self._read(backend, "job-a", after_id="a-2")
            assert [doc.id for doc in rest] == ["a-3", "a-4"]
        finally:
            await backend.delete_collection()
            await backend.teardown()

    async def test_no_job_id_reads_every_chunk_including_unlabelled(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        backend = await self._seeded(tmp_path)
        try:
            assert [doc.id for doc in await self._read(backend, None, after_id="b-2")] == ["c"]
            assert len(await self._read(backend, None)) == 9
        finally:
            await backend.delete_collection()
            await backend.teardown()

    async def test_a_kb_with_no_table_has_no_job_chunks(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        backend = create_backend(
            "postgres",
            kb_name=f"kb_job_{uuid.uuid4().hex[:8]}",
            kb_path=tmp_path,
            backend_config={},
            user_id=uuid.uuid4(),
        )
        try:
            assert await self._read(backend, "job-a") == []
            assert await backend.count_job("job-a") == 0
        finally:
            await backend.teardown()

    async def test_reading_one_job_uses_the_metadata_index(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        from lfx.base.knowledge_bases.backends.postgres import _job_documents_sql
        from sqlalchemy import text

        backend = await self._seeded(tmp_path)
        try:
            # A large KB with one small job: the read must not scan every chunk.
            await backend.add_embedded_documents(
                [
                    IngestedDocument(id=f"z-{i:05}", content="z", metadata={"job_id": f"job-{i}"}, embedding=[0.1, 0.2])
                    for i in range(5000)
                ]
            )
            engine = backend._ensure_async_engine()
            async with engine.begin() as conn:
                await conn.execute(text(f'ANALYZE "{backend.table_name}"'))
                plan_rows = (
                    (
                        await conn.execute(
                            text("EXPLAIN " + _job_documents_sql(backend.table_name, by_job=True, resume=True)),
                            {"where": '{"job_id": "job-a"}', "after_id": "a-2"},
                        )
                    )
                    .scalars()
                    .all()
                )
            assert "_cmeta_gin" in "\n".join(plan_rows), plan_rows
        finally:
            await backend.delete_collection()
            await backend.teardown()
