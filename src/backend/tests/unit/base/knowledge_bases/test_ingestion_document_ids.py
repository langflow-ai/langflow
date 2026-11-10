"""Repeated ingestion preserves document identity and earlier successful writes."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.embeddings import Embeddings
from langflow.api.utils.kb_helpers import KBIngestionHelper, backend_for_name
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError
from langflow.services.memory_base.document_builders import build_documents_from_messages, build_preprocessed_document
from lfx.base.knowledge_bases.ingestion_sources import FolderSource


def test_memory_ids_distinguish_messages_chunks_and_scopes():
    messages = [
        MessageTable(id=uuid4(), text="same message " * 200, sender="User", sender_name="User") for _ in range(2)
    ]
    kwargs = {"session_id": "session", "flow_id": "flow"}
    original = build_documents_from_messages(messages, **kwargs, job_id="first")
    repeated = build_documents_from_messages(messages, **kwargs, job_id="second")
    ids = {doc.id for doc in original}
    assert None not in ids
    assert len(ids) == len(original) > len(messages)
    assert [doc.id for doc in original] == [doc.id for doc in repeated]
    for field in kwargs:
        other = build_documents_from_messages(messages, **(kwargs | {field: "other"}))
        assert ids.isdisjoint(doc.id for doc in other)


def test_preprocessed_memory_ids_are_stable_for_the_saved_output():
    kwargs = {
        "output_text": "summary " * 300,
        "source_message_ids": ["first", "second"],
        "session_id": "session",
        "flow_id": "flow",
        "preproc_output_id": "output",
    }
    original = build_preprocessed_document(**kwargs, job_id="first")
    repeated = build_preprocessed_document(**kwargs, job_id="second")
    ids = {doc.id for doc in original}
    assert None not in ids
    assert len(ids) == len(original) > 1
    assert [doc.id for doc in original] == [doc.id for doc in repeated]
    other = build_preprocessed_document(**(kwargs | {"preproc_output_id": "other"}), job_id="second")
    assert ids.isdisjoint(doc.id for doc in other)


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@pytest.fixture
async def ingestion(client, logged_in_headers, active_user, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    embeddings = LocalEmbeddings()
    monkeypatch.setattr(KBIngestionHelper, "build_embeddings", AsyncMock(return_value=embeddings))
    name = "stable_ingestion"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text

    async def ingest(files=None, *, source=None, source_name="documents"):
        job_id = uuid4()
        result = await KBIngestionHelper.perform_ingestion(
            kb_name=name,
            kb_path=None,
            files_data=files,
            chunk_size=20,
            chunk_overlap=0,
            separator="",
            source_name=source_name,
            current_user=active_user,
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            task_job_id=job_id,
            job_service=AsyncMock(),
            source=source,
        )
        return job_id, result

    async def documents():
        backend = await backend_for_name(active_user.id, name)
        try:
            return [doc async for batch in backend.iter_documents() for doc in batch]
        finally:
            await backend.teardown()

    return ingest, documents, embeddings


async def test_repeated_uploads_keep_ids_when_batch_order_changes(ingestion):
    ingest, documents, _ = ingestion
    files = [("first.txt", b"first document " * 4), ("second.txt", b"second document " * 4)]
    first_job, first_result = await ingest(files)
    original = await documents()
    assert len(original) > len(files)
    assert len({doc.id for doc in original}) == len(original)
    _, repeated_result = await ingest(list(reversed(files)))
    repeated = await documents()
    assert {doc.id for doc in repeated} == {doc.id for doc in original}
    assert len(repeated) == len(original)
    assert first_result["chunks_created"] == len(original)
    assert repeated_result["chunks_created"] == 0
    assert {doc.metadata["job_id"] for doc in repeated} == {str(first_job)}
    await ingest(files, source_name="other source")
    assert len(await documents()) == 2 * len(original)


async def test_folder_files_with_same_name_have_distinct_stable_ids(ingestion, tmp_path):
    ingest, documents, _ = ingestion
    for name in ("first", "second"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "same.txt").write_text("same text")
    source = FolderSource(
        user_id=None,
        source_config={"path": str(tmp_path), "allowed_roots": [str(tmp_path)], "extensions": ["txt"]},
    )
    await ingest(source=source)
    original = await documents()
    assert len(original) == 2
    assert len({doc.id for doc in original}) == 2
    await ingest(source=source)
    assert {doc.id for doc in await documents()} == {doc.id for doc in original}


async def test_failed_repeat_and_retry_preserve_previously_ingested_chunks(ingestion, monkeypatch):
    ingest, documents, embeddings = ingestion
    first_job, _ = await ingest([("original.txt", b"original")])
    original = await documents()
    monkeypatch.setattr("langflow.api.utils.kb_helpers.MAX_RETRY_ATTEMPTS", 1)
    embed = embeddings.aembed_documents

    async def fail_last_file(texts):
        if texts == ["fail"]:
            msg = "embedding failed"
            raise RuntimeError(msg)
        return await embed(texts)

    monkeypatch.setattr(embeddings, "aembed_documents", fail_last_file)
    files = [("original.txt", b"original"), ("new.txt", b"new"), ("last.txt", b"fail")]
    with pytest.raises(RuntimeError, match="embedding failed"):
        await ingest(files)
    retained = await documents()
    assert retained == original
    assert retained[0].metadata["job_id"] == str(first_job)
    monkeypatch.setattr(embeddings, "aembed_documents", embed)
    await ingest(files)
    assert len(await documents()) == 3

    await ingest(files)
    assert len(await documents()) == 3


@pytest.mark.parametrize("status", ["queued", "in_progress", "suspended"])
async def test_repeat_waits_for_the_previous_jobs_outcome(ingestion, status):
    ingest, documents, _ = ingestion
    files = [("original.txt", b"original")]
    first_job, _ = await ingest(files)
    original = await documents()
    async with session_scope() as session:
        job = Job(job_id=first_job, flow_id=uuid4(), status=JobStatus(status))
        session.add(job)
        await session.commit()
    with pytest.raises(StorageUnavailableError, match="unfinished ingestion"):
        await ingest(files)
    assert await documents() == original
    async with session_scope() as session:
        job = await session.get(Job, first_job)
        job.status = JobStatus.COMPLETED
        session.add(job)
        await session.commit()
    await ingest(files)
    assert await documents() == original


@pytest.mark.parametrize("status", ["failed", "cancelled", "timed_out"])
async def test_retry_reclaims_failed_job_chunks_before_late_cleanup(ingestion, active_user, status):
    ingest, documents, _ = ingestion
    files = [("original.txt", b"original")]
    first_job, _ = await ingest(files)
    original = await documents()
    async with session_scope() as session:
        session.add(Job(job_id=first_job, flow_id=uuid4(), status=JobStatus(status)))
        await session.commit()
    retry_job, result = await ingest(files)
    assert result["chunks_created"] == 1
    stored = await documents()
    assert [doc.id for doc in stored] == [doc.id for doc in original]
    assert stored[0].metadata["job_id"] == str(retry_job)
    await KBIngestionHelper.cleanup_chroma_chunks_by_job(first_job, None, "stable_ingestion", user_id=active_user.id)
    assert await documents() == stored


async def test_partial_write_retry_counts_the_jobs_existing_chunks(ingestion, monkeypatch):
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

    ingest, documents, _ = ingestion
    write = SQLiteBackend.add_embedded_documents
    failed = False

    async def partially_write(self, docs):
        nonlocal failed
        if docs and not failed:
            failed = True
            await write(self, docs[:1])
            msg = "connection lost after write"
            raise RuntimeError(msg)
        await write(self, docs)

    monkeypatch.setattr(SQLiteBackend, "add_embedded_documents", partially_write)
    monkeypatch.setattr("langflow.api.utils.kb_helpers.EXPONENTIAL_BACKOFF_MULTIPLIER", 0)
    _, result = await ingest([("same.txt", b"multiple chunks " * 10)])
    stored = await documents()
    assert len(stored) > 1
    assert result["chunks_created"] == len(stored)


async def test_duplicate_items_in_one_job_count_each_stored_chunk_once(ingestion):
    ingest, documents, _ = ingestion
    _, result = await ingest([("same.txt", b"same"), ("same.txt", b"same")])
    assert len(await documents()) == 1
    assert result["files_processed"] == 2
    assert result["chunks_created"] == 1


@pytest.mark.parametrize("lookup_shape", ["missing_id", "unrequested_id", "duplicate_result"])
async def test_lookup_results_do_not_abort_repeated_ingestion(ingestion, monkeypatch, lookup_shape):
    from langchain_core.documents import Document
    from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

    ingest, documents, _ = ingestion
    lookup = SQLiteBackend.get_documents_by_ids

    async def lookup_with_unexpected_results(self, ids):
        existing = await lookup(self, ids)
        if lookup_shape == "duplicate_result":
            return [*existing, *existing]
        unexpected_id = None if lookup_shape == "missing_id" else "unrequested"
        return [
            *existing,
            Document(id=unexpected_id, page_content="unrelated", metadata={"job_id": str(uuid4())}),
        ]

    monkeypatch.setattr(SQLiteBackend, "get_documents_by_ids", lookup_with_unexpected_results)

    _, first_result = await ingest([("same.txt", b"same")])
    original = await documents()
    _, repeated_result = await ingest([("same.txt", b"same")])

    assert first_result["chunks_created"] == 1
    assert repeated_result["chunks_created"] == 0
    assert await documents() == original


async def test_cached_ids_still_validate_reclaimed_ownership(ingestion, active_user):
    from langchain_core.documents import Document

    _, documents, embeddings = ingestion
    old_job, new_job = uuid4(), uuid4()
    original = Document(id="shared", page_content="same", metadata={"job_id": str(old_job)})
    replacement = Document(id="shared", page_content="same", metadata={"job_id": str(new_job)})
    old_writer = await backend_for_name(
        active_user.id, "stable_ingestion", embedding_function=embeddings, preserve_existing_documents=True
    )
    new_writer = await backend_for_name(
        active_user.id, "stable_ingestion", embedding_function=embeddings, preserve_existing_documents=True
    )
    try:
        assert await old_writer.add_documents([original]) == 1
        async with session_scope() as session:
            session.add(Job(job_id=old_job, flow_id=uuid4(), status=JobStatus.FAILED))
            session.add(Job(job_id=new_job, flow_id=uuid4(), status=JobStatus.IN_PROGRESS))
            await session.commit()
        assert await new_writer.add_documents([replacement]) == 1
        with pytest.raises(StorageUnavailableError, match="unfinished ingestion"):
            await old_writer.add_documents([original])
        await new_writer.delete_by({"job_id": str(new_job)})
        assert await documents() == []
        assert await old_writer.add_documents([original]) == 0
        restored = await documents()
        assert len(restored) == 1
        assert restored[0].metadata["job_id"] == str(old_job)
    finally:
        await old_writer.teardown()
        await new_writer.teardown()
