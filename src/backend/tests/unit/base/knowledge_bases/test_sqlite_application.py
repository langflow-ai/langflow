"""Real application KB and Memory storage round trips on the SQLite default."""

from __future__ import annotations

import uuid

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.kb_helpers import KBAnalysisHelper, backend_for_name
from langflow.services.deps import get_settings_service
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError, backend_for_record
from langflow.services.memory_base.ingestion import _delete_chunks_for_session
from langflow.services.memory_base.service import _create_kb_record_for_memory_base


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@pytest.fixture
def local_storage(active_user, monkeypatch, tmp_path):  # noqa: ARG001 - initialize the app first
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path / "knowledge"))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    return tmp_path / "knowledge"


async def test_api_default_roundtrip_delete_and_recreate(client, logged_in_headers, active_user, local_storage):
    name = "sqlite_roundtrip"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["backend_type"] == "sqlite"
    record = await knowledge_base_service.get_by_user_and_name(active_user.id, name)
    backend = await backend_for_record(record, embedding_function=LocalEmbeddings())
    await backend.add_documents([Document(page_content="stored content", metadata={"source_metadata": '{"tag":"x"}'})])
    response = await client.get(f"/api/v1/knowledge_bases/{name}/chunks", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["chunks"][0]["content"] == "stored content"
    assert response.json()["chunks"][0]["id"]
    assert (local_storage / "sqlite" / str(active_user.id) / str(record.id) / "1" / "vectors.sqlite3").is_file()
    response = await client.delete(f"/api/v1/knowledge_bases/{name}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    with pytest.raises(StorageUnavailableError):
        await backend.add_documents([Document(page_content="stale writer")])
    new_record = await knowledge_base_service.create_record(user_id=active_user.id, name=name)
    assert new_record.id != record.id
    new_backend = await backend_for_record(new_record)
    assert await new_backend.count() == 0


@pytest.mark.usefixtures("local_storage")
async def test_memory_backing_store_and_session_purge(active_user):
    name = "sqlite_memory"
    await _create_kb_record_for_memory_base(
        user_id=active_user.id,
        kb_name=name,
        embedding_provider="OpenAI",
        embedding_model="text-embedding-3-small",
        backend_type="sqlite",
        backend_config={},
    )
    backend = await backend_for_name(active_user.id, name, embedding_function=LocalEmbeddings())
    await backend.add_documents(
        [
            Document(page_content="first memory", metadata={"session_id": "one"}),
            Document(page_content="second memory", metadata={"session_id": "two"}),
        ]
    )
    results = await backend.similarity_search("first memory", 5, filter={"session_id": "one"}, with_scores=True)
    assert [doc.page_content for doc, _ in results] == ["first memory"]
    await _delete_chunks_for_session(
        kb_username=active_user.username, kb_name=name, user_id=active_user.id, session_id="one"
    )
    assert await backend.count() == 1
    record = await knowledge_base_service.get_by_user_and_name(active_user.id, name)
    assert record.source_types == ["memory"]
    assert record.chunks == 1


async def test_missing_store_is_an_error_not_empty(active_user, local_storage):
    record = await knowledge_base_service.create_record(user_id=active_user.id, name="missing_storage")
    database = local_storage / "sqlite" / str(active_user.id) / str(record.id) / "1" / "vectors.sqlite3"
    database.unlink()
    backend = await backend_for_record(record)
    with pytest.raises((ValueError, FileNotFoundError)):
        await backend.count()
    assert not database.exists()


@pytest.mark.usefixtures("local_storage")
async def test_invalid_sqlite_configuration_rolls_back_record(active_user):
    with pytest.raises(ValueError, match="configuration"):
        await knowledge_base_service.create_record(
            user_id=active_user.id, name="invalid_config", backend_config={"path": "/untrusted"}
        )
    assert await knowledge_base_service.get_by_user_and_name(active_user.id, "invalid_config") is None


async def test_metrics_do_not_publish_partial_iteration():
    class BrokenBackend:
        async def iter_documents(self, **_kwargs):
            from lfx.base.knowledge_bases.backends.base import IngestedDocument

            yield [IngestedDocument(id=str(uuid.uuid4()), content="one partial row", metadata={})]
            msg = "read failed"
            raise OSError(msg)

    metrics = {"chunks": 99, "words": 100, "characters": 200}
    with pytest.raises(OSError, match="read failed"):
        await KBAnalysisHelper.update_text_metrics_via_backend(metrics, BrokenBackend())
    assert metrics == {"chunks": 99, "words": 100, "characters": 200}


@pytest.mark.usefixtures("local_storage")
async def test_memory_delete_failure_preserves_identity_for_retry(active_user, monkeypatch):
    from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
    from langflow.services.deps import session_scope
    from langflow.services.knowledge_base_storage import runtime
    from langflow.services.memory_base.service import MemoryBaseService

    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name="memory_delete_retry", source_types=["memory"]
    )
    memory = MemoryBase(name="retry", kb_name=record.name, user_id=active_user.id, flow_id=uuid.uuid4())
    async with session_scope() as session:
        session.add(memory)
        session.add(MemoryBaseSession(memory_base_id=memory.id, session_id="preserved"))
        await session.commit()
    service = MemoryBaseService()

    def failed_backend(*_args, **_kwargs):
        msg = "temporary storage failure"
        raise OSError(msg)

    with monkeypatch.context() as context:
        context.setattr(runtime, "_raw_backend", failed_backend)
        with pytest.raises(OSError, match="temporary storage failure"):
            await service.delete(memory.id, active_user.id)
    assert await service.get(memory.id, active_user.id) is not None
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "ready"
    assert await service.delete(memory.id, active_user.id) is True
    assert await service.get(memory.id, active_user.id) is None
    assert await knowledge_base_service.get_by_id(record.id) is None


@pytest.fixture
async def stored_memory_history(active_user, local_storage):  # noqa: ARG001 - storage-root fixture
    from datetime import datetime, timezone

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.memory_base.model import (
        MemoryBase,
        MemoryBasePreprocessingOutput,
        MemoryBaseSession,
        MessageIngestionRecord,
    )
    from langflow.services.database.models.message.model import MessageTable
    from langflow.services.deps import session_scope

    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name="fenced_memory", source_types=["memory"]
    )
    flow = Flow(user_id=active_user.id, name="fenced memory flow")
    memory = MemoryBase(name="fenced memory", user_id=active_user.id, flow_id=flow.id, kb_name=record.name)
    message = MessageTable(flow_id=flow.id, session_id="fenced", sender="User", sender_name="User", text="retained")
    tracked = MemoryBaseSession(memory_base_id=memory.id, session_id="fenced", cursor_id=message.id, total_processed=1)
    ingested = MessageIngestionRecord(
        message_id=message.id, memory_base_id=memory.id, session_id="fenced", ingested_at=datetime.now(timezone.utc)
    )
    processed = MemoryBasePreprocessingOutput(
        memory_base_id=memory.id,
        session_id="fenced",
        status="ingested",
        model_used="test",
        output_text="retained",
        source_message_ids=[str(message.id)],
    )
    async with session_scope() as session:
        session.add_all([flow, memory, message, tracked, ingested, processed])
        await session.commit()
    backend = await backend_for_record(record, embedding_function=LocalEmbeddings())
    await backend.add_documents([Document(page_content="retained", metadata={"session_id": "fenced"})])
    return record, memory, message, tracked, ingested, processed, backend


@pytest.mark.parametrize("storage_state", ["migrating"])
@pytest.mark.parametrize("action", ["regenerate", "purge", "single_session", "bulk_session", "messages"])
async def test_memory_fences_preserve_history_and_vectors(
    active_user, stored_memory_history, storage_state, action, client, logged_in_headers
):
    from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
    from langflow.services.deps import session_scope
    from langflow.services.memory_base.service import MemoryBaseService

    record, memory, message, tracked, ingested, processed, backend = stored_memory_history
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = storage_state
        session.add(row)
        await session.commit()
    service = MemoryBaseService()
    if action == "regenerate":
        with pytest.raises(StorageUnavailableError):
            await service.regenerate(memory.id, active_user.id, active_user.id)
    elif action == "purge":
        with pytest.raises(StorageUnavailableError):
            await service.purge_session_data(active_user.id, [message.session_id])
    else:
        if action == "single_session":
            response = await client.delete(
                f"/api/v1/monitor/messages/session/{message.session_id}", headers=logged_in_headers
            )
        elif action == "bulk_session":
            response = await client.request(
                "DELETE", "/api/v1/monitor/messages/sessions", json=[message.session_id], headers=logged_in_headers
            )
        else:
            response = await client.request(
                "DELETE", "/api/v1/monitor/messages", json=[str(message.id)], headers=logged_in_headers
            )
        assert response.status_code == 409, response.text
    async with session_scope() as session:
        for original in (message, tracked, ingested, processed):
            preserved = await session.get(type(original), original.id)
            assert preserved is not None
        assert (await session.get(type(tracked), tracked.id)).cursor_id == message.id
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = "ready"
        session.add(row)
        await session.commit()
    assert await backend.count() == 1


async def test_successful_session_delete_purges_vectors_and_history(stored_memory_history, client, logged_in_headers):
    from langflow.services.deps import session_scope

    _record, _memory, message, tracked, ingested, processed, backend = stored_memory_history
    response = await client.delete(f"/api/v1/monitor/messages/session/{message.session_id}", headers=logged_in_headers)
    assert response.status_code == 204, response.text
    async with session_scope() as session:
        for original in (message, tracked, ingested, processed):
            assert await session.get(type(original), original.id) is None
    assert await backend.count() == 0


async def test_raw_ingestion_releases_embedding_lease_and_rejects_purged_snapshot(
    stored_memory_history, active_user, monkeypatch
):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from langflow.services.deps import session_scope
    from langflow.services.memory_base import task
    from langflow.services.memory_base.service import MemoryBaseService

    record, memory, message, tracked, _ingested, _processed, backend = stored_memory_history
    async with session_scope() as session:
        row = await session.get(type(tracked), tracked.id)
        row.cursor_id = None
        session.add(row)
        source = await session.get(type(message), message.id)
        source.category = "message"
        session.add(source)
        await session.commit()
    fetched = asyncio.Event()
    finish_write = asyncio.Event()

    class PausedEmbeddings(LocalEmbeddings):
        async def aembed_documents(self, texts):
            fetched.set()
            await finish_write.wait()
            return await super().aembed_documents(texts)

    monkeypatch.setattr(task, "preflight_memory_provider_use", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(task, "_build_embeddings_for_owner", AsyncMock(return_value=PausedEmbeddings()))
    request = task.IngestionRequest(
        memory_base_id=memory.id,
        session_id=message.session_id,
        flow_id=memory.flow_id,
        kb_name=record.name,
        kb_username=active_user.username,
        owner_user_id=active_user.id,
        actor_user_id=active_user.id,
        embedding_provider="OpenAI",
        embedding_model="test",
        cursor_id=None,
        task_job_id=uuid.uuid4(),
        job_service=AsyncMock(),
    )
    writer = asyncio.create_task(task.ingest_memory_task(request=request))
    try:
        started = asyncio.create_task(fetched.wait())
        await asyncio.wait((writer, started), timeout=10, return_when=asyncio.FIRST_COMPLETED)
        assert not writer.done(), f"Ingestion stopped before embedding: {writer.result()}"
        assert fetched.is_set()
        assert await asyncio.wait_for(backend.count(), timeout=1) == 1
        await asyncio.wait_for(MemoryBaseService().purge_session_data(active_user.id, [message.session_id]), timeout=5)
        finish_write.set()
        with pytest.raises(StorageUnavailableError, match="changed during preprocessing"):
            await asyncio.wait_for(writer, timeout=10)
    finally:
        finish_write.set()
        if not writer.done():
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)
    assert await backend.count() == 0


@pytest.mark.parametrize("change", ["purge", "edit"])
async def test_preprocessing_releases_storage_lock_and_rejects_stale_result(
    stored_memory_history, active_user, monkeypatch, change
):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from langflow.services.deps import session_scope
    from langflow.services.memory_base import task
    from langflow.services.memory_base.preprocessing import PreprocessingResult
    from langflow.services.memory_base.service import MemoryBaseService

    record, memory, message, tracked, _ingested, _processed, backend = stored_memory_history
    async with session_scope() as session:
        row = await session.get(type(tracked), tracked.id)
        row.cursor_id = None
        session.add(row)
        source = await session.get(type(message), message.id)
        source.category = "message"
        session.add(source)
    started = asyncio.Event()
    finish_model = asyncio.Event()

    async def paused_preprocessing(**_kwargs):
        started.set()
        await finish_model.wait()
        return PreprocessingResult(status="ingested", output_text="stale result", raw_response="stale result")

    monkeypatch.setattr(task, "preflight_memory_provider_use", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(task, "run_preprocessing", paused_preprocessing)
    request = task.IngestionRequest(
        memory_base_id=memory.id,
        session_id=message.session_id,
        flow_id=memory.flow_id,
        kb_name=record.name,
        kb_username=active_user.username,
        owner_user_id=active_user.id,
        actor_user_id=active_user.id,
        embedding_provider="OpenAI",
        embedding_model="test",
        cursor_id=None,
        task_job_id=uuid.uuid4(),
        job_service=MagicMock(),
        preprocessing=True,
        preproc_model="test",
    )
    writer = asyncio.create_task(task.ingest_memory_task(request=request))
    try:
        model_started = asyncio.create_task(started.wait())
        await asyncio.wait((writer, model_started), timeout=10, return_when=asyncio.FIRST_COMPLETED)
        assert not writer.done(), f"Ingestion stopped before preprocessing: {writer.result()}"
        assert started.is_set()
        assert await asyncio.wait_for(backend.count(), timeout=1) == 1
        if change == "purge":
            await asyncio.wait_for(
                MemoryBaseService().purge_session_data(active_user.id, [message.session_id]), timeout=5
            )
        else:
            async with session_scope() as session:
                row = await session.get(type(message), message.id)
                row.text = "edited during model call"
                session.add(row)
        finish_model.set()
        with pytest.raises(StorageUnavailableError, match="changed during preprocessing"):
            await asyncio.wait_for(writer, timeout=10)
    finally:
        started.set()
        finish_model.set()
        if not writer.done():
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)
    assert await backend.count() == (0 if change == "purge" else 1)


async def test_session_delete_fences_capture_before_tracking_row_exists(
    stored_memory_history, client, logged_in_headers
):
    from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
    from langflow.services.deps import session_scope

    record, _memory, message, tracked, _ingested, _processed, _backend = stored_memory_history
    async with session_scope() as session:
        await session.delete(await session.get(type(tracked), tracked.id))
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = "migrating"
        session.add(row)
        await session.commit()
    response = await client.delete(f"/api/v1/monitor/messages/session/{message.session_id}", headers=logged_in_headers)
    assert response.status_code == 409, response.text
    async with session_scope() as session:
        assert await session.get(type(message), message.id) is not None


@pytest.mark.parametrize("storage_state", ["migrating", "needs_attention"])
@pytest.mark.parametrize("endpoint", ["upload", "folder", "connector", "flush", "regenerate"])
async def test_ingress_rejects_unavailable_store_before_creating_job(
    active_user, stored_memory_history, client, logged_in_headers, monkeypatch, storage_state, endpoint
):
    from unittest.mock import AsyncMock

    from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
    from langflow.services.deps import get_job_service, session_scope

    memory_record, memory, *_ = stored_memory_history
    record = memory_record
    if endpoint in {"upload", "folder", "connector"}:
        record = await knowledge_base_service.create_record(user_id=active_user.id, name="fenced_ingress")
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = storage_state
        session.add(row)
        await session.commit()
    create_job = AsyncMock()
    monkeypatch.setattr(get_job_service(), "create_job", create_job)
    if endpoint == "upload":
        response = await client.post(
            f"/api/v1/knowledge_bases/{record.name}/ingest",
            files=[("files", ("test.txt", b"retained"))],
            headers=logged_in_headers,
        )
    elif endpoint == "folder":
        response = await client.post(
            f"/api/v1/knowledge_bases/{record.name}/ingest/folder",
            json={"path": "/unused"},
            headers=logged_in_headers,
        )
    elif endpoint == "connector":
        response = await client.post(
            f"/api/v1/knowledge_bases/{record.name}/ingest/connector",
            json={"source_type": "folder", "source_config": {"path": "/unused"}},
            headers=logged_in_headers,
        )
    else:
        response = await client.post(
            f"/api/v1/memories/{memory.id}/{endpoint}",
            json={"session_id": "fenced"},
            headers=logged_in_headers,
        )
    assert response.status_code == 409, response.text
    create_job.assert_not_awaited()


@pytest.mark.parametrize("consumer", ["single", "bulk", "flow", "memory", "rollback"])
@pytest.mark.usefixtures("local_storage")
async def test_deletion_never_follows_reused_name_to_a_new_uuid(
    active_user, client, logged_in_headers, monkeypatch, consumer
):
    from langflow.api.v1 import knowledge_bases as kb_api
    from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
    from langflow.services.database.models.memory_base.model import MemoryBase
    from langflow.services.deps import session_scope
    from langflow.services.knowledge_base_storage import runtime
    from langflow.services.memory_base.flow_cleanup import FlowMemoryBaseCleanup, finalize_flow_memory_base_cleanup
    from langflow.services.memory_base.service import MemoryBaseService

    old = await knowledge_base_service.create_record(user_id=active_user.id, name="reused_delete_name")
    old_memory = None
    if consumer == "memory":
        old_memory = MemoryBase(name="reused_memory", kb_name=old.name, user_id=active_user.id, flow_id=uuid.uuid4())
        async with session_scope() as session:
            session.add(old_memory)
            await session.commit()
    original_delete = runtime.delete_storage_for_record
    replacement = None
    replacement_memory = None

    async def delete_then_recreate(record):
        nonlocal replacement, replacement_memory
        await original_delete(record)
        if record.id != old.id or replacement is not None:
            return
        # Deterministically interleave a second completed delete and name reuse
        # after this request's storage cleanup, before its final metadata delete.
        async with session_scope() as session:
            if old_memory is not None:
                await session.delete(await session.get(MemoryBase, old_memory.id))
            await session.delete(await session.get(KnowledgeBaseRecord, old.id))
            await session.commit()
        replacement = await knowledge_base_service.create_record(user_id=active_user.id, name=old.name)
        backend = await backend_for_record(replacement, embedding_function=LocalEmbeddings())
        await backend.add_documents([Document(page_content="fresh generation must survive")])
        if old_memory is not None:
            replacement_memory = MemoryBase(
                name=old_memory.name, kb_name=replacement.name, user_id=active_user.id, flow_id=old_memory.flow_id
            )
            async with session_scope() as session:
                session.add(replacement_memory)
                await session.commit()

    monkeypatch.setattr(runtime, "delete_storage_for_record", delete_then_recreate)
    # Covers the old imported endpoint alias as well as the UUID-only route.
    monkeypatch.setattr(kb_api, "delete_storage_for_record", delete_then_recreate, raising=False)
    if consumer == "single":
        response = await client.delete(f"/api/v1/knowledge_bases/{old.name}", headers=logged_in_headers)
        assert response.status_code in (200, 409), response.text
    elif consumer == "bulk":
        response = await client.request(
            "DELETE", "/api/v1/knowledge_bases", json={"kb_names": [old.name]}, headers=logged_in_headers
        )
        assert response.status_code == 200, response.text
    elif consumer == "flow":
        await finalize_flow_memory_base_cleanup(
            [
                FlowMemoryBaseCleanup(
                    kb_name=old.name,
                    user_id=old.user_id,
                    kb_username=active_user.username,
                    backend_type="sqlite",
                    kb_record_id=old.id,
                    storage_record=old,
                )
            ]
        )
    elif consumer == "rollback":
        await MemoryBaseService()._cleanup_orphaned_provisioning(
            kb_record_id=old.id, kb_name=old.name, kb_username=active_user.username
        )
    else:
        assert await MemoryBaseService().delete(old_memory.id, active_user.id)
    assert replacement is not None
    fresh = await knowledge_base_service.get_by_id(replacement.id)
    assert fresh is not None
    assert fresh.storage_state == "ready"
    backend = await backend_for_record(fresh)
    assert await backend.count() == 1
    if replacement_memory is not None:
        assert await MemoryBaseService().get(replacement_memory.id, active_user.id) is not None
