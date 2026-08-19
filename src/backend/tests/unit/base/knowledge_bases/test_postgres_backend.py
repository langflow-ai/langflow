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
