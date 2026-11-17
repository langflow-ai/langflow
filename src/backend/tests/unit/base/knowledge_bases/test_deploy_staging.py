"""A deploy stages a knowledge base's chunks in a hidden store and merges them when it commits.

The naming tests always run. The round trips are opt-in, as the other live tests:
``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` with ``PGVECTOR_CONNECTION_STRING``, and
``LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1`` with ``OPENSEARCH_URL``.
"""

from __future__ import annotations

import os
import uuid

import pytest
from lfx.base.knowledge_bases.backends import IngestedDocument, create_backend
from lfx.base.knowledge_bases.backends.naming import OWNER_SCOPED_NAME_RE, owner_scoped_collection_name

WIDTH = 8


def _live(kind: str) -> dict:
    if kind == "postgres":
        if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1" or not os.getenv("PGVECTOR_CONNECTION_STRING"):
            pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 and PGVECTOR_CONNECTION_STRING")
        pytest.importorskip("pgvector")
        return {}
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1" or not os.getenv("OPENSEARCH_URL"):
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 and OPENSEARCH_URL")
    pytest.importorskip("opensearchpy")
    return {"url_variable": "OPENSEARCH_URL"}


def _docs(ids: range, *, text: str = "v1") -> list[IngestedDocument]:
    return [
        IngestedDocument(id=f"c{i}", content=f"{text} {i}", metadata={"job_id": "job-1"}, embedding=[i / 10] * WIDTH)
        for i in ids
    ]


async def _ids(backend) -> dict[str, str]:
    """Every chunk in the store, id to text; an absent store reads as empty."""
    if backend.backend_type.value == "opensearch":
        _ = backend.vector_store
        client = backend._os_client
        if not client.indices.exists(index=backend._os_index):
            return {}
        client.indices.refresh(index=backend._os_index)
    found = {}
    async for batch in backend.iter_documents(batch_size=50, include_embeddings=False):
        found.update({doc.id: doc.content for doc in batch})
    return found


@pytest.mark.parametrize("kind", ["postgres", "opensearch"])
def test_staging_store_is_never_the_live_store(kind: str) -> None:
    owner = uuid.uuid4()
    # An operator override names the live index; staging must not follow it there.
    config = {"index_name": "ops-managed-index"} if kind == "opensearch" else {}
    live = create_backend(kind, kb_name="policies", kb_path=None, backend_config=config, user_id=owner)
    staged = live.staging("op-1")
    name = staged._resolve_index_name() if kind == "opensearch" else staged.table_name

    assert OWNER_SCOPED_NAME_RE.fullmatch(name)
    assert name not in {"ops-managed-index", owner_scoped_collection_name(owner, "policies")}
    assert name != live.staging("op-2")._staging_name()  # one deploy's staging is its own
    with pytest.raises(ValueError, match="token"):
        live.staging("")


def test_a_backend_without_its_own_staging_store_refuses_before_any_write(tmp_path) -> None:
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteStorageContext

    live = create_backend(
        "sqlite", kb_name="policies", storage_context=SQLiteStorageContext(tmp_path, uuid.uuid4(), uuid.uuid4())
    )
    # It names its store without the token, so a "staged" copy would write into live.
    with pytest.raises(NotImplementedError, match="cannot stage"):
        live.staging("op-1")


@pytest.mark.api_key_required
@pytest.mark.parametrize("kind", ["postgres", "opensearch"])
async def test_staged_chunks_stay_hidden_until_the_merge(kind: str) -> None:
    config = _live(kind)
    live = create_backend(
        kind, kb_name=f"kb_{uuid.uuid4().hex[:8]}", kb_path=None, backend_config=config, user_id=uuid.uuid4()
    )
    staged = live.staging(f"op-{uuid.uuid4().hex[:8]}")
    try:
        await live.ensure_ready()
        await staged.ensure_ready()
        await live.add_embedded_documents(_docs(range(3)))  # what the last deploy left: c0..c2 at v1
        await staged.add_embedded_documents(_docs(range(2, 6), text="v2"))  # this deploy: c2 changed, c3..c5 new

        assert await _ids(live) == {f"c{i}": f"v1 {i}" for i in range(3)}  # flows see nothing staged

        assert await live.merge_staging(staged.staging_token) == 4

        assert await _ids(live) == {"c0": "v1 0", "c1": "v1 1"} | {f"c{i}": f"v2 {i}" for i in range(2, 6)}
        assert await _ids(staged) == {}  # staging is gone
        assert await live.merge_staging(staged.staging_token) == 0  # a retry after success does nothing
    finally:
        await staged.delete_collection()
        await live.delete_collection()
        await staged.teardown()
        await live.teardown()


@pytest.mark.api_key_required
@pytest.mark.parametrize("kind", ["postgres", "opensearch"])
async def test_a_sliced_merge_moves_at_most_limit_per_call_until_staging_is_gone(kind: str) -> None:
    config = _live(kind)
    live = create_backend(
        kind, kb_name=f"kb_{uuid.uuid4().hex[:8]}", kb_path=None, backend_config=config, user_id=uuid.uuid4()
    )
    staged = live.staging(f"op-{uuid.uuid4().hex[:8]}")
    try:
        await live.ensure_ready()
        await staged.ensure_ready()
        await live.add_embedded_documents(_docs(range(2)))  # c0, c1 at v1
        await staged.add_embedded_documents(_docs(range(1, 6), text="v2"))  # c1 changed, c2..c5 new

        moved, left = [], []
        while (step := await live.merge_staging(staged.staging_token, limit=2)) > 0:
            moved.append(step)
            left.append(await staged.count())

        assert moved == [2, 2, 1], moved
        assert left == [3, 1, 0], left  # each call takes its slice out of staging, so a resend carries on
        assert await _ids(live) == {"c0": "v1 0"} | {f"c{i}": f"v2 {i}" for i in range(1, 6)}
        assert await live.merge_staging(staged.staging_token, limit=2) == 0  # staging is gone
    finally:
        await staged.delete_collection()
        await live.delete_collection()
        await staged.teardown()
        await live.teardown()


@pytest.mark.api_key_required
async def test_a_postgres_staging_store_opens_no_connection_pool_of_its_own() -> None:
    """Battle test: a pool per staging copy ran serving's Postgres out of connections under four pods."""
    live = create_backend(
        "postgres", kb_name=f"kb_{uuid.uuid4().hex[:8]}", kb_path=None, backend_config=_live("postgres"),
        user_id=uuid.uuid4(),
    )  # fmt: skip
    first, second = live.staging("op-a"), live.staging("op-b")
    try:
        await first.ensure_ready()  # staging used before live ever opened a pool, as the batch route does
        await first.add_embedded_documents(_docs(range(2)))
        await live.ensure_ready()
        await second.ensure_ready()

        assert await second.count() == 0
        pools = {id(backend._ensure_async_engine()) for backend in (live, first, second)}
        assert len(pools) == 1, "each staging copy opened a pool of its own"
    finally:
        await first.delete_collection()
        await live.delete_collection()
        await first.teardown()
        await second.teardown()
        await live.teardown()


@pytest.mark.api_key_required
async def test_an_opensearch_slice_never_exceeds_its_own_cap_whatever_the_caller_asks(monkeypatch) -> None:
    from lfx.base.knowledge_bases.backends import opensearch

    monkeypatch.setattr(opensearch, "MERGE_SLICE_MAX", 2)
    live = create_backend(
        "opensearch", kb_name=f"kb_{uuid.uuid4().hex[:8]}", kb_path=None, backend_config=_live("opensearch"),
        user_id=uuid.uuid4(),
    )  # fmt: skip
    staged = live.staging(f"op-{uuid.uuid4().hex[:8]}")
    try:
        await live.ensure_ready()
        await staged.ensure_ready()
        await staged.add_embedded_documents(_docs(range(5)))

        assert await live.merge_staging(staged.staging_token, limit=5_000) == 2
        assert await staged.count() == 3  # the rest waits for the next call
    finally:
        await staged.delete_collection()
        await live.delete_collection()
        await staged.teardown()
        await live.teardown()


@pytest.mark.api_key_required
@pytest.mark.parametrize("kind", ["postgres", "opensearch"])
async def test_first_deploy_merge_creates_a_searchable_live_store(kind: str) -> None:
    config = _live(kind)
    live = create_backend(
        kind, kb_name=f"kb_{uuid.uuid4().hex[:8]}", kb_path=None, backend_config=config, user_id=uuid.uuid4()
    )
    staged = live.staging("op-first")
    try:
        await live.ensure_ready()
        await staged.ensure_ready()
        await staged.add_embedded_documents(_docs(range(4)))

        assert await live.merge_staging("op-first") == 4

        assert set(await _ids(live)) == {f"c{i}" for i in range(4)}
        assert await live.count_job("job-1") == 4
        if kind == "opensearch":  # the live index got a kNN mapping, not a dynamic one
            mapping = live._os_client.indices.get_mapping(index=live._os_index)[live._os_index]["mappings"]
            assert "knn_vector" in str(mapping)
    finally:
        await staged.delete_collection()
        await live.delete_collection()
        await staged.teardown()
        await live.teardown()


@pytest.mark.api_key_required
@pytest.mark.parametrize("kind", ["postgres", "opensearch"])
async def test_cancel_drops_staging_and_leaves_live_as_it_was(kind: str) -> None:
    config = _live(kind)
    live = create_backend(
        kind, kb_name=f"kb_{uuid.uuid4().hex[:8]}", kb_path=None, backend_config=config, user_id=uuid.uuid4()
    )
    staged = live.staging("op-cancel")
    try:
        await live.ensure_ready()
        await staged.ensure_ready()
        await live.add_embedded_documents(_docs(range(2)))
        await staged.add_embedded_documents(_docs(range(2, 5), text="travel"))

        await staged.delete_collection()  # what a cancelled deploy does

        assert await _ids(live) == {"c0": "v1 0", "c1": "v1 1"}
        assert await live.merge_staging("op-cancel") == 0  # nothing left to bring in later
        assert await _ids(live) == {"c0": "v1 0", "c1": "v1 1"}
    finally:
        await staged.delete_collection()
        await live.delete_collection()
        await staged.teardown()
        await live.teardown()
