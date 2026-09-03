"""Tests for Memory Base cleanup on flow deletion.

When a flow is deleted, the Memory Bases it owns must be reclaimed:

* every ``memory_base`` row (and its child rows) plus the backing
  ``knowledge_base`` row are removed atomically with the flow deletion, and
* the corresponding vector-store collection is dropped — best-effort, so a
  broken connection to the remote store is logged and swallowed rather than
  blocking the deletion.

The DB side is exercised end-to-end through the DELETE flow endpoint; the
external side (remote collection teardown, broken-connection logging) is
exercised directly against ``finalize_flow_memory_base_cleanup``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import orjson
import pytest
from langflow.services.database.models.flow import FlowCreate
from langflow.services.database.models.folder.model import FolderCreate
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBasePreprocessingOutput,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
    MessageIngestionRecord,
)
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from langflow.services.memory_base.flow_cleanup import (
    FlowMemoryBaseCleanup,
    finalize_flow_memory_base_cleanup,
    purge_flow_memory_bases,
)
from lfx.base.knowledge_bases.backends.base import TestConnectionResult
from sqlmodel import select

if TYPE_CHECKING:
    from httpx import AsyncClient

# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #


async def _create_flow(client: AsyncClient, json_flow: str, logged_in_headers) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a flow via the API and return ``(flow_id, owner_user_id)``."""
    data = orjson.loads(json_flow)["data"]
    payload = FlowCreate(name=f"MB Flow {uuid.uuid4()}", description="d", data=data)
    response = await client.post("api/v1/flows/", json=payload.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201, response.content
    body = response.json()
    return uuid.UUID(body["id"]), uuid.UUID(body["user_id"])


async def _seed_memory_base(flow_id: uuid.UUID, user_id: uuid.UUID, *, kb_name: str) -> uuid.UUID:
    """Insert a Memory Base (with children + backing KB row) tied to ``flow_id``.

    Uses a local-Chroma KB row so the external teardown is a no-op (no remote
    collection, and the on-disk directory simply does not exist).
    """
    now = datetime.now(timezone.utc)
    mb_id = uuid.uuid4()
    async with session_scope() as db:
        db.add(
            MemoryBase(id=mb_id, name=f"mb-{uuid.uuid4().hex[:6]}", flow_id=flow_id, user_id=user_id, kb_name=kb_name)
        )
        db.add(
            KnowledgeBaseRecord(
                name=kb_name,
                user_id=user_id,
                backend_type="chroma",
                backend_config={"mode": "local"},
                source_types=["memory"],
            )
        )
        # A message ingested into the MB — MessageIngestionRecord references it.
        msg = MessageTable(
            id=uuid.uuid4(),
            sender="AI",
            sender_name="Bot",
            session_id="sess-1",
            text="hi",
            flow_id=flow_id,
            is_output=True,
        )
        db.add(msg)
        db.add(MemoryBaseSession(memory_base_id=mb_id, session_id="sess-1"))
        db.add(MemoryBaseWorkflowRun(memory_base_id=mb_id, session_id="sess-1", recorded_at=now))
        db.add(
            MemoryBasePreprocessingOutput(
                memory_base_id=mb_id,
                session_id="sess-1",
                status="ingested",
                output_text="distilled",
                source_message_ids=[str(msg.id)],
                model_used="gpt-x",
            )
        )
        db.add(MessageIngestionRecord(message_id=msg.id, memory_base_id=mb_id, session_id="sess-1", ingested_at=now))
    return mb_id


async def _count_rows(model, **filters) -> int:
    async with session_scope() as db:
        stmt = select(model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(model, field) == value)
        return len(list((await db.exec(stmt)).all()))


# ------------------------------------------------------------------ #
#  Integration: DELETE flow reclaims its Memory Bases                  #
# ------------------------------------------------------------------ #


@pytest.mark.usefixtures("active_user")
async def test_delete_flow_deletes_memory_bases_and_children(client: AsyncClient, json_flow: str, logged_in_headers):
    flow_id, user_id = await _create_flow(client, json_flow, logged_in_headers)
    kb_name = f"kb_{uuid.uuid4().hex[:8]}"
    mb_id = await _seed_memory_base(flow_id, user_id, kb_name=kb_name)

    # Sanity: rows exist before deletion.
    assert await _count_rows(MemoryBase, id=mb_id) == 1
    assert await _count_rows(KnowledgeBaseRecord, name=kb_name, user_id=user_id) == 1

    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.content

    # Memory base, its children, and the backing knowledge_base row are gone.
    assert await _count_rows(MemoryBase, id=mb_id) == 0
    assert await _count_rows(MemoryBaseSession, memory_base_id=mb_id) == 0
    assert await _count_rows(MemoryBaseWorkflowRun, memory_base_id=mb_id) == 0
    assert await _count_rows(MemoryBasePreprocessingOutput, memory_base_id=mb_id) == 0
    assert await _count_rows(MessageIngestionRecord, memory_base_id=mb_id) == 0
    assert await _count_rows(KnowledgeBaseRecord, name=kb_name, user_id=user_id) == 0


@pytest.mark.usefixtures("active_user")
async def test_delete_flow_leaves_other_flows_memory_bases_untouched(
    client: AsyncClient, json_flow: str, logged_in_headers
):
    flow_a, user_id = await _create_flow(client, json_flow, logged_in_headers)
    flow_b, _ = await _create_flow(client, json_flow, logged_in_headers)
    kb_a = f"kb_{uuid.uuid4().hex[:8]}"
    kb_b = f"kb_{uuid.uuid4().hex[:8]}"
    mb_a = await _seed_memory_base(flow_a, user_id, kb_name=kb_a)
    mb_b = await _seed_memory_base(flow_b, user_id, kb_name=kb_b)

    response = await client.delete(f"api/v1/flows/{flow_a}", headers=logged_in_headers)
    assert response.status_code == 200, response.content

    assert await _count_rows(MemoryBase, id=mb_a) == 0
    # Deleting flow A must not touch flow B's Memory Base.
    assert await _count_rows(MemoryBase, id=mb_b) == 1
    assert await _count_rows(KnowledgeBaseRecord, name=kb_b, user_id=user_id) == 1


@pytest.mark.usefixtures("active_user")
async def test_delete_project_deletes_member_flows_memory_bases(client: AsyncClient, json_flow: str, logged_in_headers):
    # A project deletion cascades through its flows; each flow's Memory Bases
    # must be reclaimed too.
    project = FolderCreate(name=f"Proj {uuid.uuid4()}", description="d", components_list=[], flows_list=[])
    resp = await client.post("api/v1/projects/", json=project.model_dump(), headers=logged_in_headers)
    assert resp.status_code == 201, resp.content
    project_id = resp.json()["id"]

    data = orjson.loads(json_flow)["data"]
    flow_payload = FlowCreate(name=f"MB Flow {uuid.uuid4()}", description="d", data=data, folder_id=project_id)
    fresp = await client.post("api/v1/flows/", json=flow_payload.model_dump(mode="json"), headers=logged_in_headers)
    assert fresp.status_code == 201, fresp.content
    flow_id = uuid.UUID(fresp.json()["id"])
    user_id = uuid.UUID(fresp.json()["user_id"])

    kb_name = f"kb_{uuid.uuid4().hex[:8]}"
    mb_id = await _seed_memory_base(flow_id, user_id, kb_name=kb_name)

    dresp = await client.delete(f"api/v1/projects/{project_id}", headers=logged_in_headers)
    assert dresp.status_code == 204, dresp.content

    assert await _count_rows(MemoryBase, id=mb_id) == 0
    assert await _count_rows(KnowledgeBaseRecord, name=kb_name, user_id=user_id) == 0


# ------------------------------------------------------------------ #
#  purge_flow_memory_bases returns handles + is a no-op when empty     #
# ------------------------------------------------------------------ #


@pytest.mark.usefixtures("active_user")
async def test_purge_returns_handles_with_backend_config(client: AsyncClient, json_flow: str, logged_in_headers):
    flow_id, user_id = await _create_flow(client, json_flow, logged_in_headers)
    kb_name = f"kb_{uuid.uuid4().hex[:8]}"
    await _seed_memory_base(flow_id, user_id, kb_name=kb_name)

    async with session_scope() as db:
        handles = await purge_flow_memory_bases(db, flow_id)

    assert len(handles) == 1
    handle = handles[0]
    assert handle.kb_name == kb_name
    assert handle.user_id == user_id
    assert handle.backend_type == "chroma"
    assert handle.backend_config == {"mode": "local"}


async def test_purge_no_memory_bases_returns_empty():
    async with session_scope() as db:
        handles = await purge_flow_memory_bases(db, uuid.uuid4())
    assert handles == []


# ------------------------------------------------------------------ #
#  finalize_flow_memory_base_cleanup — external teardown              #
# ------------------------------------------------------------------ #


def _fake_backend(*, delete_error: Exception | None = None, connection_ok: bool = True) -> MagicMock:
    backend = MagicMock()
    backend.ensure_ready = AsyncMock()
    backend.delete_collection = AsyncMock(side_effect=delete_error)
    backend.test_connection = AsyncMock(return_value=TestConnectionResult(ok=connection_ok, message="probe"))
    backend.teardown = AsyncMock()
    return backend


async def test_finalize_drops_remote_collection(monkeypatch):
    backend = _fake_backend()
    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.create_backend", lambda *_a, **_k: backend)

    handle = FlowMemoryBaseCleanup(
        kb_name="kb1",
        user_id=uuid.uuid4(),
        kb_username=None,  # skip disk cleanup — irrelevant to remote drop
        backend_type="opensearch",
        backend_config={"url": "https://os.example"},
    )
    await finalize_flow_memory_base_cleanup([handle])

    backend.delete_collection.assert_awaited_once()
    backend.teardown.assert_awaited_once()


async def test_finalize_logs_broken_connection_and_swallows(monkeypatch):
    # delete_collection fails AND the connection probe reports the store is down.
    backend = _fake_backend(delete_error=ConnectionError("no route to host"), connection_ok=False)
    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.create_backend", lambda *_a, **_k: backend)

    warnings: list[str] = []

    async def _capture_warning(msg, *args, **_kwargs):
        warnings.append(msg % args if args else msg)

    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.logger.awarning", _capture_warning)

    handle = FlowMemoryBaseCleanup(
        kb_name="kb1",
        user_id=uuid.uuid4(),
        kb_username=None,
        backend_type="opensearch",
        backend_config={"url": "https://os.example"},
    )
    # Must not raise even though the remote delete failed.
    await finalize_flow_memory_base_cleanup([handle])

    backend.test_connection.assert_awaited_once()
    backend.teardown.assert_awaited_once()
    assert any("connection" in w.lower() and "broken" in w.lower() for w in warnings), warnings
    assert any("kb1" in w for w in warnings)


async def test_finalize_skips_remote_drop_for_local_chroma(monkeypatch):
    # Local Chroma has no remote collection: create_backend must never be called,
    # only the on-disk directory teardown.
    create_backend = MagicMock()
    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.create_backend", create_backend)
    # delete_kb is filesystem-only; stub it so the test needs no KB root configured.
    delete_kb = AsyncMock()
    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.delete_kb", delete_kb)

    handle = FlowMemoryBaseCleanup(
        kb_name="kb_local",
        user_id=uuid.uuid4(),
        kb_username="alice",
        backend_type="chroma",
        backend_config={"mode": "local"},
    )
    await finalize_flow_memory_base_cleanup([handle])

    create_backend.assert_not_called()
    delete_kb.assert_awaited_once()
