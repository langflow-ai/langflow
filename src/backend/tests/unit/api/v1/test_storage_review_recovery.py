"""Users can retire unavailable stores and delete their own Memory history."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.memory_base import ingestion
from sqlmodel import select

pytestmark = [pytest.mark.no_blockbuster, pytest.mark.usefixtures("storage_root")]


@pytest.fixture
def storage_root(active_user, monkeypatch, tmp_path):  # noqa: ARG001 -- initialized settings dependency
    root = tmp_path / "knowledge"
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    return root


@pytest.mark.parametrize(
    ("state", "backend_type"),
    [
        ("detached", "sqlite"),
        ("needs_attention", "chroma"),
        ("migrating", "chroma"),
    ],
)
async def test_memory_delete_has_recovery_or_busy_response(
    client,
    logged_in_headers,
    active_user,
    state,
    backend_type,
):
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name=f"mem_{uuid4().hex}", backend_type="sqlite"
    )
    memory = MemoryBase(name="memory", flow_id=uuid4(), user_id=active_user.id, kb_name=record.name)
    async with session_scope() as db:
        current = await db.get(KnowledgeBaseRecord, record.id)
        current.storage_state = state
        current.backend_type = backend_type
        db.add(memory)
        await db.commit()
    response = await client.delete(f"/api/v1/memories/{memory.id}", headers=logged_in_headers)
    assert response.status_code == (409 if state == "migrating" else 204), response.text
    async with session_scope() as db:
        assert (await db.get(MemoryBase, memory.id) is not None) == (state == "migrating")
        assert (await db.get(KnowledgeBaseRecord, record.id) is not None) == (state == "migrating")


@pytest.mark.parametrize("bulk", [False, True])
async def test_session_delete_without_messages_still_purges_memory(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    bulk,
):
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name=f"mem_{uuid4().hex}", backend_type="sqlite"
    )
    memory = MemoryBase(name="memory", flow_id=uuid4(), user_id=active_user.id, kb_name=record.name)
    tracking = MemoryBaseSession(memory_base_id=memory.id, session_id=uuid4().hex, total_processed=4)
    async with session_scope() as db:
        db.add_all([memory, tracking])
        await db.commit()
    deleted_chunks = AsyncMock()
    monkeypatch.setattr(ingestion, "_delete_chunks_for_session", deleted_chunks)
    if bulk:
        response = await client.request(
            "DELETE", "/api/v1/monitor/messages/sessions", json=[tracking.session_id], headers=logged_in_headers
        )
    else:
        response = await client.delete(
            f"/api/v1/monitor/messages/session/{tracking.session_id}", headers=logged_in_headers
        )
    assert response.status_code == (200 if bulk else 204), response.text
    deleted_chunks.assert_awaited_once()
    async with session_scope() as db:
        assert await db.get(MemoryBaseSession, tracking.id) is None


@pytest.mark.parametrize("state", ["needs_attention", "detached"])
async def test_fenced_memory_does_not_prevent_session_history_deletion(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    state,
):
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name=f"mem_{uuid4().hex}", backend_type="sqlite"
    )
    flow = Flow(name="chat", data={}, user_id=active_user.id)
    memory = MemoryBase(name="memory", flow_id=flow.id, user_id=active_user.id, kb_name=record.name)
    tracking = MemoryBaseSession(memory_base_id=memory.id, session_id=uuid4().hex, total_processed=4)
    message = MessageTable(
        sender="User", sender_name="User", text="removed history", session_id=tracking.session_id, flow_id=flow.id
    )
    async with session_scope() as db:
        current = await db.get(KnowledgeBaseRecord, record.id)
        current.storage_state = state
        current.backend_type = "chroma"
        current.backend_config = {"mode": "cloud"}
        db.add_all([flow, memory, tracking, message])
        await db.commit()
    deleted_chunks = AsyncMock()
    monkeypatch.setattr(ingestion, "_delete_chunks_for_session", deleted_chunks)
    response = await client.delete(f"/api/v1/monitor/messages/session/{tracking.session_id}", headers=logged_in_headers)
    assert response.status_code == 204, response.text
    deleted_chunks.assert_not_awaited()
    async with session_scope() as db:
        pending = await db.get(MemoryBaseSession, tracking.id)
        assert pending.purge_pending
        assert pending.total_processed == 0
        assert not list(
            (await db.exec(select(MessageTable).where(MessageTable.session_id == tracking.session_id))).all()
        )
