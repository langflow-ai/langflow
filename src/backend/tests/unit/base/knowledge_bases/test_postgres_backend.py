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


def _live_backend(tmp_path: Path, *, kb_name: str, user_id: uuid.UUID, size: int = 16):
    from langchain_core.embeddings import DeterministicFakeEmbedding

    return create_backend(
        "postgres",
        kb_name=kb_name,
        kb_path=tmp_path,
        backend_config={},
        embedding_function=DeterministicFakeEmbedding(size=size),
        user_id=user_id,
    )


@pytest.mark.api_key_required
class TestPostgresBootstrapLive:
    """The per-table bootstrap stays correct under concurrency and stays off the write path."""

    @pytest.fixture(autouse=True)
    def _fresh_process_memo(self):
        # Each test starts as a process that has verified no tables yet.
        from lfx.base.knowledge_bases.backends import postgres as pg_module

        pg_module._READY_TABLES.clear()
        yield
        pg_module._READY_TABLES.clear()

    async def _ready(self, backend) -> None:
        await backend.ensure_ready()
        tc = await backend.test_connection()
        if not tc.ok:
            pytest.skip(f"pgvector not reachable: {tc.message}")

    async def _index_names(self, backend) -> set[str]:
        from sqlalchemy import text

        async with backend._ensure_async_engine().connect() as conn:
            rows = await conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = :name"), {"name": backend.table_name}
            )
            return set(rows.scalars().all())

    async def test_concurrent_first_ingests_create_one_table(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        import asyncio

        from langchain_core.documents import Document
        from lfx.base.knowledge_bases.backends import postgres as pg_module

        kb_name, owner = f"kb_race_{uuid.uuid4().hex[:8]}", uuid.uuid4()
        writers = [_live_backend(tmp_path, kb_name=kb_name, user_id=owner) for _ in range(8)]
        try:
            await self._ready(writers[0])
            for writer in writers[1:]:
                await writer.ensure_ready()

            async def first_write(index: int, writer) -> None:
                # Forget the memo so every writer runs the catalog check, as
                # separate processes would.
                pg_module._READY_TABLES.clear()
                await writer.add_documents([Document(page_content=f"doc {index}", metadata={})])

            await asyncio.gather(*(first_write(i, w) for i, w in enumerate(writers)))

            assert await writers[0].count() == len(writers)
            names = await self._index_names(writers[0])
            table = writers[0].table_name
            assert {f"{table}_pkey", f"{table}_cmeta_gin", f"{table}_hnsw"} <= names
        finally:
            with contextlib.suppress(Exception):
                await writers[0].delete_collection()
            for writer in writers:
                await writer.teardown()

    async def test_write_does_not_wait_for_another_open_insert(self, tmp_path: Path) -> None:
        # ``CREATE INDEX IF NOT EXISTS`` takes a SHARE lock on the table before
        # it sees that the index exists, so a bootstrap that always issued it
        # would queue behind any open insert into the same KB.
        _require_live_pgvector()
        import asyncio

        from langchain_core.documents import Document
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        kb_name, owner = f"kb_busy_{uuid.uuid4().hex[:8]}", uuid.uuid4()
        first = _live_backend(tmp_path, kb_name=kb_name, user_id=owner)
        second = _live_backend(tmp_path, kb_name=kb_name, user_id=owner)
        holder = None
        try:
            await self._ready(first)
            await second.ensure_ready()
            await first.add_documents([Document(page_content="seed", metadata={})])

            holder = create_async_engine(first._resolved_connection_string)
            async with holder.connect() as conn:
                await conn.execute(text("BEGIN"))
                vector = "[" + ",".join(["0.1"] * 16) + "]"
                await conn.execute(
                    text(
                        f'INSERT INTO "{first.table_name}" (id, embedding, document, cmetadata) '  # noqa: S608
                        "VALUES ('held', CAST(:v AS vector), 'held', '{}')"
                    ),
                    {"v": vector},
                )
                # A new process (empty memo) writes while that insert is open.
                from lfx.base.knowledge_bases.backends import postgres as pg_module

                pg_module._READY_TABLES.clear()
                await asyncio.wait_for(
                    second.add_documents([Document(page_content="concurrent", metadata={})]), timeout=10
                )
                await conn.execute(text("ROLLBACK"))
            assert await first.count() == 2
        finally:
            if holder is not None:
                await holder.dispose()
            with contextlib.suppress(Exception):
                await first.delete_collection()
            await first.teardown()
            await second.teardown()

    async def test_bootstrap_of_one_kb_does_not_wait_for_another(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        import asyncio

        from langchain_core.documents import Document
        from lfx.base.knowledge_bases.backends.postgres import _ddl_lock_key
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        busy = _live_backend(tmp_path, kb_name=f"kb_a_{uuid.uuid4().hex[:8]}", user_id=uuid.uuid4())
        other = _live_backend(tmp_path, kb_name=f"kb_b_{uuid.uuid4().hex[:8]}", user_id=uuid.uuid4())
        holder = None
        try:
            await self._ready(busy)
            await other.ensure_ready()
            holder = create_async_engine(busy._resolved_connection_string)
            async with holder.connect() as conn:
                # Hold the first KB's DDL lock as an in-progress bootstrap would.
                await conn.execute(text("BEGIN"))
                await conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _ddl_lock_key(busy.table_name)})
                await asyncio.wait_for(other.add_documents([Document(page_content="b", metadata={})]), timeout=10)
                await conn.execute(text("ROLLBACK"))
            assert await other.count() == 1
        finally:
            if holder is not None:
                await holder.dispose()
            for backend in (busy, other):
                with contextlib.suppress(Exception):
                    await backend.delete_collection()
                await backend.teardown()

    async def test_table_dropped_elsewhere_is_recreated_on_next_write(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document
        from sqlalchemy import text

        backend = _live_backend(tmp_path, kb_name=f"kb_drop_{uuid.uuid4().hex[:8]}", user_id=uuid.uuid4())
        try:
            await self._ready(backend)
            await backend.add_documents([Document(page_content="before", metadata={})])
            # Another process drops the table; this process still remembers it.
            async with backend._ensure_async_engine().begin() as conn:
                await conn.execute(text(f'DROP TABLE "{backend.table_name}"'))

            await backend.add_documents([Document(page_content="after", metadata={})])

            assert await backend.count() == 1
            assert f"{backend.table_name}_hnsw" in await self._index_names(backend)
        finally:
            with contextlib.suppress(Exception):
                await backend.delete_collection()
            await backend.teardown()

    async def test_table_recreated_for_another_model_is_reported(self, tmp_path: Path) -> None:
        _require_live_pgvector()
        from langchain_core.documents import Document

        kb_name, owner = f"kb_dim_{uuid.uuid4().hex[:8]}", uuid.uuid4()
        old_model = _live_backend(tmp_path, kb_name=kb_name, user_id=owner, size=16)
        new_model = _live_backend(tmp_path, kb_name=kb_name, user_id=owner, size=8)
        try:
            await self._ready(old_model)
            await new_model.ensure_ready()
            await old_model.add_documents([Document(page_content="a", metadata={})])
            # The KB is deleted and recreated for an 8-dim model by another process.
            await new_model.delete_collection()
            await new_model.add_documents([Document(page_content="b", metadata={})])
            from lfx.base.knowledge_bases.backends import postgres as pg_module

            pg_module._READY_TABLES.add(old_model._ready_key(16))  # this process's stale memo

            with pytest.raises(ValueError, match="was created with 8-dimensional embeddings"):
                await old_model.add_documents([Document(page_content="c", metadata={})])
            assert await new_model.count() == 1
        finally:
            with contextlib.suppress(Exception):
                await new_model.delete_collection()
            await old_model.teardown()
            await new_model.teardown()
