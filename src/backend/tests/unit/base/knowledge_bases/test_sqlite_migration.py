"""Strict, inert migration interchange and destination qualification tests."""

from __future__ import annotations

import asyncio
import io
import json
import threading
from dataclasses import replace
from uuid import uuid4

import pytest
from lfx.base.knowledge_bases.backends.base import IngestedDocument
from lfx.base.knowledge_bases.migration import (
    ExportHeader,
    ExportLimits,
    MigrationProtocolError,
    import_qualified_export,
    qualify_export,
    write_export,
)


@pytest.fixture
def header():
    return ExportHeader(
        source_id="collection-123",
        source_fingerprint="a" * 64,
        source_version="1.5.9",
        count=2,
        dimensions=2,
        metric="l2",
        model_fingerprint="b" * 64,
    )


@pytest.fixture
def documents():
    return [
        IngestedDocument(
            id="native-1",
            content="héllo",
            embedding=[0.1, 0.2],
            metadata={"_id": "logical-id", "source_metadata": '{"active": true}', "list": [True, 1, None]},
        ),
        IngestedDocument(id="native-2", content="", embedding=[1, 2], metadata={}),
    ]


def encoded(header, documents):
    stream = io.BytesIO()
    write_export(stream, header, documents)
    return stream.getvalue()


def test_complete_export_preserves_ids_and_typed_metadata(header, documents, tmp_path):
    with qualify_export(
        io.BytesIO(encoded(header, documents)), expected_header=header, scratch_directory=tmp_path
    ) as source:
        batch = source.read_batch(0, batch_size=500)
        assert [doc.id for doc in batch] == ["native-1", "native-2"]
        assert batch[0].metadata == documents[0].metadata
        assert batch[0].embedding == pytest.approx(documents[0].embedding)
        assert source.manifest.count == 2
        staging_path = source.path
    assert not staging_path.exists()


def test_truncated_export_never_qualifies(header, documents, tmp_path):
    data = encoded(header, documents).splitlines(keepends=True)
    with pytest.raises(MigrationProtocolError, match="terminal"):
        qualify_export(io.BytesIO(b"".join(data[:-1])), expected_header=header, scratch_directory=tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("change", ["count", "digest", "header", "duplicate", "trailing"])
def test_corrupt_export_rejected(header, documents, change):
    lines = encoded(header, documents).splitlines(keepends=True)
    terminal = json.loads(lines[-1])
    if change == "count":
        terminal["count"] = 1
    elif change == "digest":
        terminal["records_sha256"] = "0" * 64
    elif change == "header":
        terminal["header_sha256"] = "0" * 64
    elif change == "duplicate":
        lines[2] = lines[1]
    lines[-1] = json.dumps(terminal).encode() + b"\n"
    if change == "trailing":
        lines.append(b"{}\n")
    with pytest.raises(MigrationProtocolError):
        qualify_export(io.BytesIO(b"".join(lines)), expected_header=header)


def test_source_fingerprint_must_match_trusted_inventory(header, documents):
    with pytest.raises(MigrationProtocolError, match="inventory"):
        qualify_export(
            io.BytesIO(encoded(header, documents)), expected_header=replace(header, source_fingerprint="c" * 64)
        )


@pytest.mark.parametrize(
    "document",
    [
        IngestedDocument(id=None, content="bad", embedding=[1, 2]),
        IngestedDocument(id="", content="bad", embedding=[1, 2]),
        IngestedDocument(id="x", content="bad", embedding=None),
        IngestedDocument(id="x", content="bad", embedding=[1]),
        IngestedDocument(id="x", content="bad", embedding=[1, float("nan")]),
        IngestedDocument(id="x", content="bad", embedding=[1, float("inf")]),
        IngestedDocument(id="x", content="bad", embedding=[True, 1]),
        IngestedDocument(id="x", content="bad", embedding=[1e100, 1]),
        IngestedDocument(id="x", content="bad", embedding=[1, 2], metadata={1: "bad"}),
        IngestedDocument(id="x", content="bad", embedding=[1, 2], metadata={"bad": float("nan")}),
    ],
)
def test_export_rejects_invalid_records_without_terminal_manifest(header, document):
    output = io.BytesIO()
    with pytest.raises(MigrationProtocolError):
        write_export(output, replace(header, count=1), [document])
    assert b'"type":"complete"' not in output.getvalue()


def test_reader_rejects_duplicate_json_keys(header, documents):
    data = encoded(header, documents).replace(b'"id":"native-1"', b'"id":"native-1","id":"other"')
    with pytest.raises(MigrationProtocolError, match="duplicate"):
        qualify_export(io.BytesIO(data), expected_header=header)


def test_reader_enforces_record_and_total_byte_limits(header, documents):
    data = encoded(header, documents)
    with pytest.raises(MigrationProtocolError, match="limit"):
        qualify_export(io.BytesIO(data), expected_header=header, limits=ExportLimits(max_line_bytes=32))
    with pytest.raises(MigrationProtocolError, match="limit"):
        qualify_export(io.BytesIO(data), expected_header=header, limits=ExportLimits(max_total_bytes=64))


def test_successful_empty_export_requires_terminal_manifest(header):
    header = replace(header, count=0, dimensions=None)
    with qualify_export(io.BytesIO(encoded(header, [])), expected_header=header) as source:
        assert source.manifest.count == 0
        assert source.read_batch(0, batch_size=500) == []


def test_exporter_partial_source_read_is_error(header, documents):
    with pytest.raises(MigrationProtocolError, match="count"):
        encoded(header, documents[:1])


def test_exporter_does_not_mask_iterator_failure(header, documents):
    def broken():
        yield documents[0]
        msg = "source unreadable"
        raise OSError(msg)

    output = io.BytesIO()
    with pytest.raises(OSError, match="source unreadable"):
        write_export(output, header, broken())
    assert b'"type":"complete"' not in output.getvalue()


@pytest.fixture
def target(tmp_path, header):
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext

    return SQLiteBackend(
        "migration-test",
        storage_context=SQLiteStorageContext(root=tmp_path, owner_id=uuid4(), kb_id=uuid4(), generation=2),
        backend_config={"metric": header.metric, "model_fingerprint": header.model_fingerprint},
        create=True,
    )


@pytest.mark.asyncio
async def test_real_sqlite_import_verifies_all_rows_and_replays_completed_generation(header, documents, target):
    from langchain_core.embeddings import Embeddings

    class NoEmbeddings(Embeddings):
        def embed_documents(self, _texts):
            msg = "Migration must not embed documents"
            raise AssertionError(msg)

        def embed_query(self, _text):
            msg = "Migration must not embed a query"
            raise AssertionError(msg)

    target.embedding_function = NoEmbeddings()
    migration_id = uuid4()
    with qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source:
        receipt = await import_qualified_export(source, target, migration_id=migration_id, batch_size=1)
        assert receipt.count == 2
        assert receipt.generation == 2
        assert await target.count() == 2
        assert (await target.read_migration_manifest())["status"] == "complete"
        assert await import_qualified_export(source, target, migration_id=migration_id) == receipt


@pytest.mark.asyncio
async def test_interrupted_import_resumes_same_source_without_duplicates(header, documents, target, monkeypatch):
    migration_id = uuid4()
    original = target.add_embedded_documents
    calls = 0

    async def interrupt(batch):
        nonlocal calls
        calls += 1
        if calls == 2:
            msg = "interrupted import"
            raise OSError(msg)
        await original(batch)

    monkeypatch.setattr(target, "add_embedded_documents", interrupt)
    with qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source:
        with pytest.raises(OSError, match="interrupted import"):
            await import_qualified_export(source, target, migration_id=migration_id, batch_size=1)
        assert await target.count() == 1
        assert (await target.read_migration_manifest())["status"] == "importing"
        monkeypatch.setattr(target, "add_embedded_documents", original)
        receipt = await import_qualified_export(source, target, migration_id=migration_id, batch_size=1)
        assert receipt.count == 2
        assert await target.count() == 2


@pytest.mark.asyncio
async def test_nonempty_target_without_migration_identity_is_not_overwritten(header, documents, target):
    await target.add_embedded_documents([documents[0]])
    with (
        qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source,
        pytest.raises(MigrationProtocolError, match="must be empty"),
    ):
        await import_qualified_export(source, target, migration_id=uuid4())
    assert await target.count() == 1
    assert await target.read_migration_manifest() is None


@pytest.mark.asyncio
async def test_retry_with_different_migration_identity_rejected(header, documents, target):
    with qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source:
        await import_qualified_export(source, target, migration_id=uuid4())
        with pytest.raises(MigrationProtocolError, match="different source or migration"):
            await import_qualified_export(source, target, migration_id=uuid4())


@pytest.mark.asyncio
async def test_completed_import_reverification_rejects_changed_metadata(header, documents, target):
    migration_id = uuid4()
    with qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source:
        await import_qualified_export(source, target, migration_id=migration_id)
        await target.add_embedded_documents([replace(documents[0], metadata={"tampered": True})])
        with pytest.raises(MigrationProtocolError, match="differs from qualified source"):
            await import_qualified_export(source, target, migration_id=migration_id)


@pytest.mark.asyncio
async def test_masked_short_destination_iterator_never_completes(header, documents, target, monkeypatch):
    async def short_iterator(**_kwargs):
        yield [documents[0]]

    monkeypatch.setattr(target, "iter_documents", short_iterator)
    with (
        qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source,
        pytest.raises(MigrationProtocolError, match="incomplete record set"),
    ):
        await import_qualified_export(source, target, migration_id=uuid4())
    assert (await target.read_migration_manifest())["status"] == "importing"


@pytest.mark.asyncio
async def test_cancellation_waits_for_staging_worker_before_releasing_files():
    from lfx.base.knowledge_bases.migration.importer import _run_worker

    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def worker():
        started.set()
        if not release.wait(timeout=5):
            msg = "Test worker was not released"
            raise TimeoutError(msg)
        finished.set()

    task = asyncio.create_task(_run_worker(worker))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


@pytest.mark.asyncio
async def test_empty_source_preserves_known_dimensions(header, target):
    source_header = replace(header, count=0, dimensions=3)
    with qualify_export(io.BytesIO(encoded(source_header, [])), expected_header=source_header) as source:
        receipt = await import_qualified_export(source, target, migration_id=uuid4())
    assert receipt.count == 0
    assert (await target.inspect_store())["dimension"] == 3
    with pytest.raises(ValueError, match="dimension"):
        await target.add_embedded_documents([IngestedDocument(id="wrong", content="", embedding=[1, 2])])
    assert await target.count() == 0


@pytest.mark.asyncio
async def test_migration_preserves_object_order_used_by_source_filters(header, target):
    from langchain_core.embeddings import Embeddings

    class FixedEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return [[1.0, 2.0] for _ in texts]

        def embed_query(self, _text):
            return [1.0, 2.0]

    metadata = {"source_metadata": {"object": {"b": 1, "a": 2}}}
    document = IngestedDocument(id="ordered", content="text", embedding=[1.0, 2.0], metadata=metadata)
    source_header = replace(header, count=1)
    migration_id = uuid4()
    with qualify_export(io.BytesIO(encoded(source_header, [document])), expected_header=source_header) as source:
        staged = source.read_batch(0)
        assert list(staged[0].metadata["source_metadata"]["object"]) == ["b", "a"]
        await import_qualified_export(source, target, migration_id=migration_id)
        target.embedding_function = FixedEmbeddings()
        matches = await target.similarity_search("query", 2, source_filter={"object": ["{'b': 1, 'a': 2}"]})
        assert [doc.id for doc, _ in matches] == ["ordered"]
        await target.add_embedded_documents(
            [replace(document, metadata={"source_metadata": {"object": {"a": 2, "b": 1}}})]
        )
        with pytest.raises(MigrationProtocolError, match="differs from qualified source"):
            await import_qualified_export(source, target, migration_id=migration_id)


@pytest.mark.asyncio
async def test_failed_integrity_check_does_not_complete_import(header, documents, target, monkeypatch):
    async def corrupt():
        msg = "integrity check failed"
        raise ValueError(msg)

    monkeypatch.setattr(target, "integrity_check", corrupt)
    with (
        qualify_export(io.BytesIO(encoded(header, documents)), expected_header=header) as source,
        pytest.raises(ValueError, match="integrity check failed"),
    ):
        await import_qualified_export(source, target, migration_id=uuid4())
    assert (await target.read_migration_manifest())["status"] == "importing"
