"""Storage contract tests against the real APSW and sqlite-vec runtime."""

from __future__ import annotations

import asyncio
import math
import os
import struct
import sys
import threading
from uuid import uuid4

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError, IngestedDocument
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext


class FixedEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(text), 0.0] for text in texts]

    def embed_query(self, text):
        return [float(text), 0.0]


@pytest.fixture
def context(tmp_path):
    return SQLiteStorageContext(root=tmp_path, owner_id=uuid4(), kb_id=uuid4())


def backend(context, *, create=True, metric="l2"):
    return SQLiteBackend(
        "display-name",
        storage_context=context,
        create=create,
        backend_config={"metric": metric},
        embedding_function=FixedEmbeddings(),
    )


@pytest.mark.asyncio
async def test_existing_only_does_not_create_missing_store(context):
    with pytest.raises(FileNotFoundError):
        await backend(context, create=False).count()
    assert not context.database_path.exists()


def test_store_location_is_the_generation_database(context):
    assert backend(context, create=False).store_location == (context.database_path,)


@pytest.mark.parametrize(("metric", "distance_metric"), [("l2", "l2"), ("cosine", "cosine"), ("ip", "inner_product")])
def test_distance_metric_names_the_configured_metric(context, metric, distance_metric):
    assert backend(context, create=False, metric=metric).distance_metric == distance_metric


@pytest.mark.asyncio
async def test_read_only_count_never_initializes_missing_storage(context):
    assert await backend(context, create=True).read_only_count() is None
    assert not context.database_path.parent.exists()


@pytest.mark.asyncio
async def test_read_only_count_includes_committed_wal_rows(context):
    import apsw

    store = backend(context)
    await store.ensure_ready()
    # Hold a reader at the old snapshot so the committed insert must stay in WAL.
    reader = apsw.Connection(str(context.database_path))
    try:
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
        await store.add_embedded_documents([IngestedDocument("one", {}, [1.0, 0.0], id="one")])

        assert await store.read_only_count() == 1
        assert reader.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
    finally:
        reader.close()


@pytest.mark.asyncio
async def test_trusted_root_ancestor_alias_is_canonicalized(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    context = SQLiteStorageContext(alias / "root", uuid4(), uuid4())
    assert context.root == actual / "root"
    assert await backend(context).count() == 0


@pytest.mark.asyncio
async def test_configured_root_itself_cannot_be_a_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    context = SQLiteStorageContext(alias, uuid4(), uuid4())
    with pytest.raises(BackendConfigurationError, match="symlink"):
        await backend(context).count()


@pytest.mark.asyncio
async def test_persistence_ids_typed_metadata_and_upsert(context):
    store = backend(context)
    metadata = {"_id": "user-id", "job_id": "job-1", "source_metadata": {"bool": True, "list": [1, "b"]}}
    docs = [IngestedDocument("one", metadata, [1.0, 0.0], id="physical-id")]
    await store.add_embedded_documents(docs)
    await store.add_embedded_documents(docs)
    await store.teardown()
    reopened = backend(context, create=False)
    assert await reopened.count() == 1
    batches = [batch async for batch in reopened.iter_documents(batch_size=1, include_embeddings=True)]
    assert batches == [docs]
    assert (await reopened.inspect_store())["dimension"] == 2
    assert await reopened.storage_size_bytes() > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("metric", "expected"), [("l2", 25.0), ("cosine", 1.0), ("ip", 1.0)])
async def test_metric_semantics(context, metric, expected):
    store = backend(context, metric=metric)
    await store.add_embedded_documents([IngestedDocument("point", {}, [0.0, 4.0], id="a")])
    results = await store.similarity_search("3", 1, with_scores=True)
    assert results[0][0].id == "a"
    assert results[0][1] == pytest.approx(expected)
    assert store.normalize_score(results[0][1]) == pytest.approx(-expected)


@pytest.mark.asyncio
async def test_source_filters_are_applied_before_top_k(context):
    store = backend(context)
    await store.add_embedded_documents(
        [
            IngestedDocument(str(i), {"source_metadata": {"group": "other"}}, [float(i), 0.0], id=str(i))
            for i in range(8)
        ]
        + [IngestedDocument("wanted", {"source_metadata": '{"group":["wanted","x"],"flag":true}'}, [50.0, 0.0], id="z")]
    )
    result = await store.similarity_search("0", 1, source_filter={"group": ["wanted"], "flag": ["True"]})
    assert [doc.id for doc, _ in result] == ["z"]
    assert not await store.similarity_search("0", 1, source_filter={"missing": ["None"]})


@pytest.mark.asyncio
async def test_internal_filter_and_delete_are_not_source_filter(context):
    store = backend(context)
    await store.add_embedded_documents(
        [
            IngestedDocument("a", {"session_id": "a", "source_metadata": {"session_id": "b"}}, [1.0, 0.0], id="a"),
            IngestedDocument("b", {"session_id": "b"}, [1.0, 0.0], id="b"),
        ]
    )
    assert [doc.id for doc, _ in await store.similarity_search("1", 2, filter={"session_id": "a"})] == ["a"]
    await store.delete_by({"session_id": "a"})
    assert await store.count() == 1
    with pytest.raises(ValueError, match="filter"):
        await store.delete_by({})
    with pytest.raises(ValueError, match="filter"):
        await store.delete_by({"session_id": {"$ne": "b"}})


@pytest.mark.asyncio
async def test_invalid_batch_is_atomic_and_dimensions_stay_fixed(context):
    store = backend(context)
    for embedding in ([float("nan"), 0.0], [float("inf"), 0.0], [1e100, 0.0], []):
        with pytest.raises(ValueError, match=r"embedding|Embedding"):
            await store.add_embedded_documents([IngestedDocument("bad", {}, embedding, id="bad")])
    assert await store.count() == 0
    assert (await store.inspect_store())["dimension"] is None
    await store.add_embedded_documents([IngestedDocument("good", {}, [1.0, 0.0], id="good")])
    with pytest.raises(BackendConfigurationError, match="dimension"):
        await store.add_embedded_documents([IngestedDocument("wrong", {}, [1.0], id="wrong")])
    assert await store.count() == 1


@pytest.mark.asyncio
async def test_facade_add_search_get_and_delete(context):
    store = backend(context)
    ids = await store.vector_store.aadd_documents([Document(page_content="2", id="id-2", metadata={"flag": True})])
    assert ids == ["id-2"]
    assert (await store.vector_store.asimilarity_search("2"))[0].metadata == {"flag": True}
    assert [doc.id for doc in await store.vector_store.aget_by_ids(ids)] == ids
    assert await store.vector_store.adelete(ids=ids)
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_store_identity_metric_and_symlink_are_verified(context, tmp_path):
    await backend(context).count()
    with pytest.raises(BackendConfigurationError, match="metric"):
        await backend(context, create=False, metric="cosine").count()
    moved = tmp_path / "moved"
    context.database_path.parent.rename(moved)
    context.database_path.parent.symlink_to(moved, target_is_directory=True)
    with pytest.raises(BackendConfigurationError, match="symlink"):
        await backend(context, create=False).count()


@pytest.mark.asyncio
async def test_integrity_and_migration_manifest(context):
    store = backend(context)
    await store.add_embedded_documents([IngestedDocument("x", {}, [1.0, 0.0], id="x")])
    await store.integrity_check()
    manifest = {"version": 1, "source_fingerprint": "abc", "complete": True, "count": 1}
    await store.finalize_migration(manifest)
    assert await backend(context, create=False).read_migration_manifest() == manifest


@pytest.mark.asyncio
async def test_cancel_waits_for_in_flight_worker(context):
    store = backend(context)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def operation():
        started.set()
        release.wait(5)
        finished.set()

    task = asyncio.create_task(store._run(operation))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0.01)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


@pytest.mark.asyncio
async def test_concurrent_processes_commit_without_losing_rows(context):
    store = backend(context)
    await store.ensure_ready()
    script = """
import asyncio, sys
from pathlib import Path
from uuid import UUID
from lfx.base.knowledge_bases.backends.base import IngestedDocument
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
async def main():
    context = SQLiteStorageContext(Path(sys.argv[1]), UUID(sys.argv[2]), UUID(sys.argv[3]))
    store = SQLiteBackend('display', storage_context=context)
    for index in range(10):
        doc = IngestedDocument(str(index), {}, [float(index), 0.0], id=f'{sys.argv[4]}-{index}')
        await store.add_embedded_documents([doc])
asyncio.run(main())
"""
    processes = [
        await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            str(context.root),
            str(context.owner_id),
            str(context.kb_id),
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        for name in ("first", "second")
    ]
    outputs = await asyncio.gather(*(process.communicate() for process in processes))
    for process, (_stdout, stderr) in zip(processes, outputs, strict=True):
        assert process.returncode == 0, stderr.decode()
    assert await store.count() == 20
    await store.integrity_check()


@pytest.mark.asyncio
async def test_metadata_order_bool_type_and_projection_updates(context):
    store = backend(context)
    nested = {"z": 1, "a": 2}
    await store.add_embedded_documents(
        [
            IngestedDocument("a", {"flag": True, "source_metadata": {"object": nested}}, [1.0, 0.0], id="a"),
            IngestedDocument("b", {"flag": 1}, [1.0, 0.0], id="b"),
        ]
    )
    assert [doc.id for doc, _ in await store.similarity_search("1", 2, filter={"flag": True})] == ["a"]
    assert [doc.id for doc, _ in await store.similarity_search("1", 2, filter={"flag": 1})] == ["b"]
    assert [doc.id for doc, _ in await store.similarity_search("1", 2, source_filter={"object": [str(nested)]})] == [
        "a"
    ]
    doc = (await store.vector_store.aget_by_ids(["a"]))[0]
    assert str(doc.metadata["source_metadata"]["object"]) == str(nested)
    await store.add_embedded_documents([IngestedDocument("a", {}, [1.0, 0.0], id="a")])
    assert not await store.similarity_search("1", 2, source_filter={"object": [str(nested)]})


@pytest.mark.asyncio
async def test_deleted_generation_cannot_be_recreated_by_stale_handle(context):
    store = backend(context)
    await store.add_embedded_documents([IngestedDocument("a", {}, [1.0, 0.0], id="a")])
    await store.delete_collection()
    for handle in (store, backend(context)):
        with pytest.raises(BackendConfigurationError, match="deleted"):
            await handle.add_embedded_documents([IngestedDocument("b", {}, [1.0, 0.0], id="b")])


@pytest.mark.asyncio
async def test_erasure_does_not_require_unpublished_embedding_config(context):
    store = backend(context, metric="cosine")
    await store.add_embedded_documents([IngestedDocument("private-document", {}, [1.0, 0.0], id="a")])
    default_config = backend(context, create=False)
    with pytest.raises(BackendConfigurationError, match="metric"):
        await default_config.count()
    await default_config.delete_collection()
    with pytest.raises(BackendConfigurationError, match="deleted"):
        await store.count()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["owner_id", "kb_id", "generation"])
async def test_erasure_still_requires_matching_immutable_identity(context, field):
    store = backend(context)
    await store.add_embedded_documents([IngestedDocument("retained-document", {}, [1.0, 0.0], id="a")])

    def alter_identity():
        with store._connect() as connection:
            value = 2 if field == "generation" else str(uuid4())
            connection.execute(f"UPDATE store_header SET {field}=? WHERE singleton=1", (value,))  # noqa: S608 -- parametrized constant fields

    await store._run(alter_identity)
    with pytest.raises(BackendConfigurationError, match=f"{field} does not match"):
        await store.delete_collection()


@pytest.mark.asyncio
async def test_cosine_zero_vectors_and_duplicate_ids_are_rejected(context):
    store = backend(context, metric="cosine")
    with pytest.raises(BackendConfigurationError, match="nonzero"):
        await store.add_embedded_documents([IngestedDocument("a", {}, [0.0, 0.0], id="a")])
    with pytest.raises(ValueError, match="unique"):
        await store.add_embedded_documents(
            [IngestedDocument("a", {}, [1.0, 0.0], id="a"), IngestedDocument("a", {}, [1.0, 0.0], id="a")]
        )
    assert await store.count() == 0


@pytest.mark.asyncio
@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is unavailable on this platform")
async def test_worker_executor_is_reinitialized_after_fork(context):
    script = """
import asyncio, os, sys
from pathlib import Path
from uuid import UUID
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
context = SQLiteStorageContext(Path(sys.argv[1]), UUID(sys.argv[2]), UUID(sys.argv[3]))
store = SQLiteBackend('display', storage_context=context, create=True)
asyncio.run(store.ensure_ready())
pid = os.fork()
if pid == 0:
    async def read():
        return await asyncio.wait_for(store.count(), timeout=5)
    try:
        result = asyncio.run(read())
    except BaseException:
        os._exit(2)
    os._exit(0 if result == 0 else 3)
_, status = os.waitpid(pid, 0)
sys.exit(os.waitstatus_to_exitcode(status))
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        str(context.root),
        str(context.owner_id),
        str(context.kb_id),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
    assert process.returncode == 0, stderr.decode()


@pytest.mark.asyncio
async def test_iteration_byte_budget_does_not_drop_next_record(context):
    store = backend(context)
    docs = [IngestedDocument("payload", {}, [1.0, 0.0], id=str(i)) for i in range(3)]
    await store.add_embedded_documents(docs)
    batches = [batch async for batch in store.iter_documents(include_embeddings=True, max_batch_bytes=20)]
    assert batches == [[doc] for doc in docs]
    with pytest.raises(BackendConfigurationError, match="byte limit"):
        _ = [batch async for batch in store.iter_documents(include_embeddings=True, max_batch_bytes=1)]


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_scale", [1e-45, 1e-30, 1.0, 1e30, 3e38])
@pytest.mark.parametrize("query_scale", [1e-45, 1e-30, 1.0, 1e30, 3e38])
async def test_cosine_is_stable_for_extreme_finite_stored_and_query_values(context, stored_scale, query_scale):
    store = backend(context, metric="cosine")
    await store.add_embedded_documents(
        [
            IngestedDocument("parallel", {}, [stored_scale, 0.0], id="parallel"),
            IngestedDocument("perpendicular", {}, [0.0, stored_scale], id="perpendicular"),
            IngestedDocument("opposite", {}, [-stored_scale, 0.0], id="opposite"),
        ]
    )
    results = await store.similarity_search(str(query_scale), 3, with_scores=True)
    assert [doc.id for doc, _ in results] == ["parallel", "perpendicular", "opposite"]
    assert [score for _, score in results] == pytest.approx([0.0, 1.0, 2.0])


@pytest.mark.asyncio
@pytest.mark.parametrize("scale", [1e-45, 1e-30, 1.0, 1e30, 3e38])
async def test_l2_is_stable_for_extreme_finite_stored_and_query_values(context, scale):
    store = backend(context)
    canonical_scale = struct.unpack("<f", struct.pack("<f", scale))[0]
    await store.add_embedded_documents(
        [
            IngestedDocument("identical", {}, [scale, 0.0], id="identical"),
            IngestedDocument("zero", {}, [0.0, 0.0], id="zero"),
            IngestedDocument("opposite", {}, [-scale, 0.0], id="opposite"),
        ]
    )
    results = await store.similarity_search(str(scale), 3, with_scores=True)
    assert [doc.id for doc, _ in results] == ["identical", "zero", "opposite"]
    assert all(math.isfinite(score) for _, score in results)
    assert [score for _, score in results] == pytest.approx(
        [0.0, canonical_scale**2, 4 * canonical_scale**2], rel=1e-6, abs=0.0
    )


@pytest.mark.asyncio
async def test_mixed_native_and_stable_distances_share_prefiltered_top_k(context):
    store = backend(context, metric="cosine")
    await store.add_embedded_documents(
        [
            IngestedDocument("filtered", {"source_metadata": {"group": "other"}}, [1.0, 0.0], id="a"),
            IngestedDocument("stable", {"source_metadata": {"group": "wanted"}}, [1e30, 0.0], id="b"),
            IngestedDocument("native", {"source_metadata": {"group": "wanted"}}, [1.0, 0.0], id="c"),
            IngestedDocument("perpendicular", {"source_metadata": {"group": "wanted"}}, [0.0, 1e-30], id="d"),
        ]
    )
    results = await store.similarity_search("1", 2, source_filter={"group": ["wanted"]}, with_scores=True)
    assert [doc.id for doc, _ in results] == ["b", "c"]
    assert [score for _, score in results] == pytest.approx([0.0, 0.0])
    # Upserts must refresh the derived native-distance safety flag.
    await store.add_embedded_documents(
        [
            IngestedDocument("changed", {"source_metadata": {"group": "wanted"}}, [0.0, 1.0], id="b"),
            IngestedDocument("changed", {"source_metadata": {"group": "wanted"}}, [1e-30, 0.0], id="c"),
        ]
    )
    results = await backend(context, create=False, metric="cosine").similarity_search(
        "1", 2, source_filter={"group": ["wanted"]}, with_scores=True
    )
    assert [doc.id for doc, _ in results] == ["c", "b"]
    assert [score for _, score in results] == pytest.approx([0.0, 1.0])
