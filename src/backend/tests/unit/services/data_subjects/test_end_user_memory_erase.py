"""End-user erase inside a Memory Base: the person's chunks leave the store and the row's counts follow."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langflow.api.utils import knowledge_base_service
from langflow.services.data_subjects.engine import run_request
from langflow.services.data_subjects.requests import approve, create_end_user_request
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.knowledge_base_storage.runtime import backend_for_record, unfenced_backend
from langflow.services.memory_base.document_builders import sync_kb_stats_to_record

from tests.unit.services.data_subjects._seed import create_user

SURVIVING_CHUNK = "bob asked about shipping"


class _LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@pytest.fixture
def local_storage(client, monkeypatch, tmp_path):  # noqa: ARG001 - initialize the app first
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path / "knowledge"))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)


async def _seed_memory_base_row(owner, kb_name: str) -> None:
    async with session_scope() as session:
        flow = Flow(name="support", user_id=owner)
        session.add(flow)
        await session.flush()
        session.add(MemoryBase(name="memory", kb_name=kb_name, flow_id=flow.id, user_id=owner))


async def _seed_memory_base(username: str):
    owner = await create_user(username)
    record = await knowledge_base_service.create_record(user_id=owner, name="support_memory", source_types=["memory"])
    await _seed_memory_base_row(owner, record.name)
    backend = await backend_for_record(record, embedding_function=_LocalEmbeddings())
    try:
        await backend.add_documents(
            [
                Document(page_content="alice asked about refunds", metadata={"end_user_id": "alice"}),
                Document(page_content="alice shared her order number", metadata={"end_user_id": "alice"}),
                Document(page_content=SURVIVING_CHUNK, metadata={"end_user_id": "bob"}),
            ]
        )
        # Ingestion refreshes the row after every write, so the erase starts from accurate counts.
        await sync_kb_stats_to_record(user_id=owner, kb_name=record.name, backend=backend)
    finally:
        await backend.teardown()
    return owner, record


async def _erase(end_user: str) -> tuple[str | None, DataSubjectRequest]:
    admin = await create_user(f"{end_user}-admin", superuser=True)
    async with session_scope() as session:
        request, _ = await create_end_user_request(
            session, end_user_id=end_user, scope_flow_ids=None, requested_by=admin, source=DataSubjectRequestSource.API
        )
        await approve(session, request, admin)
        request_id = request.id
    status = await run_request(request_id)
    async with session_scope() as session:
        return status, await session.get(DataSubjectRequest, request_id)


async def _set_storage_state(record, state: str) -> None:
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = state
        session.add(row)


async def _retry(request_id) -> tuple[str | None, DataSubjectRequest]:
    async with session_scope() as session:
        request = await session.get(DataSubjectRequest, request_id)
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        request.error = {**(request.error or {}), "retry_at": past}
        session.add(request)
    status = await run_request(request_id)
    async with session_scope() as session:
        return status, await session.get(DataSubjectRequest, request_id)


async def _store_count(record, *, fenced: bool = True) -> int:
    # A store that is not ready refuses fenced reads, so inspect it the way offline tools do.
    backend = await backend_for_record(record) if fenced else unfenced_backend(record)
    try:
        return await backend.count()
    finally:
        await backend.teardown()


@pytest.mark.usefixtures("local_storage")
async def test_should_refresh_the_memory_base_counts_after_erasing_an_end_users_chunks():
    owner, record = await _seed_memory_base("memory-owner")
    assert (await knowledge_base_service.get_by_id(record.id)).chunks == 3

    status, request = await _erase("alice")

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert await _store_count(record) == 1
    refreshed = await knowledge_base_service.get_by_user_and_name(owner, record.name)
    assert refreshed.chunks == 1
    assert refreshed.words == len(SURVIVING_CHUNK.split())
    assert refreshed.characters == len(SURVIVING_CHUNK)


@pytest.mark.usefixtures("local_storage")
async def test_should_finish_the_erase_when_the_metrics_refresh_fails(monkeypatch):
    _, record = await _seed_memory_base("memory-owner-metrics")

    async def _fail(*_args, **_kwargs):
        msg = "metrics backend unavailable"
        raise RuntimeError(msg)

    monkeypatch.setattr("langflow.services.memory_base.document_builders.sync_kb_stats_to_record", _fail)

    status, request = await _erase("alice")

    assert status == DataSubjectRequestStatus.DONE.value, request.error
    assert await _store_count(record) == 1


@pytest.mark.usefixtures("local_storage")
async def test_should_keep_the_request_open_until_an_upgrading_store_can_be_erased():
    owner, record = await _seed_memory_base("memory-owner-upgrade")
    await _set_storage_state(record, "migrating")

    first, request = await _erase("alice")

    assert first == DataSubjectRequestStatus.ERASING.value
    assert request.error["code"] == "StorageUnavailableError"
    await _set_storage_state(record, "ready")
    assert await _store_count(record) == 3

    second, request = await _retry(request.id)

    assert second == DataSubjectRequestStatus.DONE.value, request.error
    assert await _store_count(record) == 1
    assert (await knowledge_base_service.get_by_user_and_name(owner, record.name)).chunks == 1


@pytest.mark.usefixtures("local_storage")
async def test_should_keep_the_request_open_until_an_unfinished_deletion_completes():
    _, record = await _seed_memory_base("memory-owner-deleting")
    # A teardown that failed after fencing the store leaves it deleting with every chunk still in place.
    await _set_storage_state(record, "deleting")

    first, request = await _erase("alice")

    assert first == DataSubjectRequestStatus.ERASING.value
    assert request.error["code"] == "StorageUnavailableError"
    assert await _store_count(record, fenced=False) == 3

    await _set_storage_state(record, "deleted")
    second, request = await _retry(request.id)

    assert second == DataSubjectRequestStatus.DONE.value, request.error


@pytest.mark.usefixtures("local_storage")
async def test_should_skip_a_memory_base_whose_legacy_store_was_never_written():
    owner = await create_user("memory-owner-legacy-empty")
    await _seed_memory_base_row(owner, "legacy_memory")

    status, request = await _erase("alice")

    assert status == DataSubjectRequestStatus.DONE.value, request.error


@pytest.mark.usefixtures("local_storage")
async def test_should_keep_the_request_open_while_a_legacy_store_awaits_its_upgrade():
    owner = await create_user("memory-owner-legacy")
    await _seed_memory_base_row(owner, "legacy_memory")
    (Path(get_settings_service().settings.knowledge_bases_dir) / "memory-owner-legacy" / "legacy_memory").mkdir(
        parents=True
    )

    status, request = await _erase("alice")

    assert status == DataSubjectRequestStatus.ERASING.value
    assert request.error["code"] == "ChromaMigrationRequiredError"
