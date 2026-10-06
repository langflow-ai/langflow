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


@pytest.mark.parametrize("state", ["needs_attention", "detached", "deleting", "deleted"])
@pytest.mark.parametrize("bulk", [False, True])
async def test_fenced_memory_does_not_prevent_session_history_deletion(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    state,
    bulk,
):
    """Single and bulk history deletion must not wait for unavailable vector stores."""
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
    if bulk:
        response = await client.request(
            "DELETE", "/api/v1/monitor/messages/sessions", json=[tracking.session_id], headers=logged_in_headers
        )
    else:
        response = await client.delete(
            f"/api/v1/monitor/messages/session/{tracking.session_id}", headers=logged_in_headers
        )
    assert response.status_code == (200 if bulk else 204), response.text
    deleted_chunks.assert_not_awaited()
    async with session_scope() as db:
        pending = await db.get(MemoryBaseSession, tracking.id)
        assert pending.purge_pending
        assert pending.total_processed == 0
        assert not list(
            (await db.exec(select(MessageTable).where(MessageTable.session_id == tracking.session_id))).all()
        )


@pytest.mark.parametrize(
    ("state", "display_status"), [("migrating", "upgrading"), ("needs_attention", "needs_migration")]
)
async def test_storage_availability_overrides_ready_in_knowledge_and_memory(
    client,
    logged_in_headers,
    active_user,
    state,
    display_status,
):
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name=f"mem_{uuid4().hex}", backend_type="sqlite"
    )
    flow = Flow(name="storage-status-chat", data={}, user_id=active_user.id)
    memory = MemoryBase(name="storage-status", flow_id=flow.id, user_id=active_user.id, kb_name=record.name)
    async with session_scope() as db:
        current = await db.get(KnowledgeBaseRecord, record.id)
        current.storage_state = state
        current.backend_type = "chroma"
        current.chunks = 500
        current.status = "ready"
        db.add_all([flow, memory])
        await db.commit()
    # Memory's backing KB is omitted from the Knowledge list. Its own API
    # must still expose the same availability and immutable storage identity.
    response = await client.get(f"/api/v1/memories/{memory.id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["storage_state"] == state
    assert response.json()["storage_kb_id"] == str(record.id)
    response = await client.patch(f"/api/v1/memories/{memory.id}", json={"threshold": 75}, headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert response.json()["storage_state"] == state
    assert response.json()["storage_kb_id"] == str(record.id)
    response = await client.get("/api/v1/knowledge-base-storage/status", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    store = next(item for item in response.json()["stores"] if item["kb_id"] == str(record.id))
    assert store["storage_state"] == state
    assert store["name"] == memory.name
    assert store["kind"] == "memory"
    assert "source_identity" not in store
    assert "backend_config" not in store
    from langflow.api.v1.knowledge_bases import _build_kb_info

    info = _build_kb_info(
        kb_name=record.name, dir_name=record.name, metadata={"chunks": 500, "status": "ready", "storage_state": state}
    )
    assert info.status == display_status


async def test_regular_user_upgrade_status_excludes_other_owners(client, logged_in_headers, active_user):
    from langflow.services.database.models.user.model import User

    other = User(username=f"private_{uuid4().hex}", password=uuid4().hex, is_active=True)
    owned = KnowledgeBaseRecord(
        name="owned-upgrade", user_id=active_user.id, backend_type="chroma", storage_state="migrating"
    )
    hidden = KnowledgeBaseRecord(
        name="hidden-upgrade", user_id=other.id, backend_type="chroma", storage_state="needs_attention"
    )
    async with session_scope() as db:
        db.add_all([other, owned, hidden])
        await db.commit()
    response = await client.get("/api/v1/knowledge-base-storage/status", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result["is_admin"]
    assert result["inventory"] is None
    assert str(owned.id) in {item["kb_id"] for item in result["stores"]}
    assert str(hidden.id) not in {item["kb_id"] for item in result["stores"]}
    assert all(not item["can_retry"] for item in result["stores"])


async def test_status_revision_exposes_completion_between_polls(client, logged_in_headers, active_user):
    from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration

    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name=f"completed_{uuid4().hex}", backend_type="sqlite"
    )
    run = KnowledgeBaseStorageMigration(
        kb_id=record.id, source_backend="chroma", source_generation=1, target_generation=2, phase="complete"
    )
    async with session_scope() as db:
        db.add(run)
        current = await db.get(KnowledgeBaseRecord, record.id)
        current.active_migration_id = run.id
        current.storage_generation = 2
        await db.commit()
    response = await client.get("/api/v1/knowledge-base-storage/status", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["revision"]
    assert str(record.id) not in {item["kb_id"] for item in result["stores"]}
