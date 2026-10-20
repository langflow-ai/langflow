"""Tests for Memory Base cleanup on flow deletion.

When a flow is deleted, the Memory Bases it owns must be reclaimed:

* Memory rows and their children are removed with the flow, while backing KB
  routing remains fenced until storage cleanup succeeds, and
* a failed collection deletion retains routing for retry while allowing the
  other Memory Bases in the batch to finish cleanup.

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
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.flow import FlowCreate
from langflow.services.database.models.folder.model import FolderCreate
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
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
from langflow.services.memory_base.ingestion import cancel_active_jobs
from lfx.base.knowledge_bases.backends.base import TestConnectionResult
from sqlmodel import col, select

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.fixture(autouse=True)
def local_store_root(active_user, tmp_path, monkeypatch):  # noqa: ARG001 - initialize the app first
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path / "knowledge"))


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

    Uses a real SQLite backing store so teardown exercises persisted tombstones.
    """
    now = datetime.now(timezone.utc)
    mb_id = uuid.uuid4()
    async with session_scope() as db:
        db.add(
            MemoryBase(id=mb_id, name=f"mb-{uuid.uuid4().hex[:6]}", flow_id=flow_id, user_id=user_id, kb_name=kb_name)
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
    await knowledge_base_service.create_record(user_id=user_id, name=kb_name, source_types=["memory"])
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
    assert handle.backend_type == "sqlite"
    assert handle.backend_config == {}
    record = await knowledge_base_service.get_by_id(handle.kb_record_id)
    assert record.storage_state == "deleting"
    await finalize_flow_memory_base_cleanup(handles)
    assert await knowledge_base_service.get_by_id(handle.kb_record_id) is None


async def test_purge_no_memory_bases_returns_empty():
    async with session_scope() as db:
        handles = await purge_flow_memory_bases(db, uuid.uuid4())
    assert handles == []


# ------------------------------------------------------------------ #
#  cancel_active_jobs — reuses the caller's session                   #
# ------------------------------------------------------------------ #


@pytest.mark.usefixtures("client")
async def test_cancel_active_jobs_cancels_every_active_job():
    """Every IN_PROGRESS/QUEUED job for the Memory Base is cancelled, not just the first.

    Regression for a bug where the per-job status update went through
    ``JobService.update_job_status``, which opens its own ``session_scope()`` —
    a second writer session distinct from the caller's (here, the flow-deletion
    transaction's) session. Under SQLite's single-writer model that second
    writer contends with the still-open outer transaction; the resulting lock
    error was not caught by the loop's narrow exception filter, so it aborted
    the loop and left later jobs uncancelled. The fix updates status through
    the caller's own session, so no second writer is ever opened.
    """
    mb_id = uuid.uuid4()
    flow_id = uuid.uuid4()
    job_ids = [uuid.uuid4(), uuid.uuid4()]

    async with session_scope() as db:
        for job_id in job_ids:
            db.add(
                Job(
                    job_id=job_id,
                    flow_id=flow_id,
                    status=JobStatus.IN_PROGRESS,
                    type=JobType.INGESTION,
                    asset_id=mb_id,
                    asset_type="memory_base",
                )
            )

    async with session_scope() as db:
        # Exercised on the SAME open session a flow-deletion transaction would
        # already be using — the exact scenario the bug reproduced under.
        await cancel_active_jobs(memory_base_id=mb_id, db=db)

    async with session_scope() as db:
        rows = (await db.exec(select(Job).where(col(Job.job_id).in_(job_ids)))).all()

    assert len(rows) == len(job_ids)
    assert {row.status for row in rows} == {JobStatus.CANCELLED}


@pytest.mark.usefixtures("client")
async def test_cancel_active_jobs_does_not_open_a_second_session(monkeypatch):
    """cancel_active_jobs must not go through JobService's own session_scope().

    Direct regression for the root cause: asserts get_job_service (the old
    path to the second-writer update_job_status) is never touched.
    """
    from langflow.services.memory_base import ingestion as ingestion_module

    def _fail_if_called():
        msg = "cancel_active_jobs must not open a second session via get_job_service()"
        raise AssertionError(msg)

    monkeypatch.setattr(ingestion_module, "get_job_service", _fail_if_called)

    mb_id = uuid.uuid4()
    flow_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with session_scope() as db:
        db.add(
            Job(
                job_id=job_id,
                flow_id=flow_id,
                status=JobStatus.QUEUED,
                type=JobType.INGESTION,
                asset_id=mb_id,
                asset_type="memory_base",
            )
        )

    async with session_scope() as db:
        await cancel_active_jobs(memory_base_id=mb_id, db=db)  # must not raise via the patched get_job_service

    async with session_scope() as db:
        row = (await db.exec(select(Job).where(Job.job_id == job_id))).first()
    assert row.status == JobStatus.CANCELLED


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


async def test_finalize_drops_remote_collection(active_user, monkeypatch):
    backend = _fake_backend()
    monkeypatch.setattr("langflow.services.knowledge_base_storage.runtime._raw_backend", lambda *_a, **_k: backend)
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name="remote_cleanup", backend_type="opensearch"
    )
    handle = FlowMemoryBaseCleanup(
        kb_name=record.name,
        user_id=record.user_id,
        kb_username=None,
        backend_type="opensearch",
        kb_record_id=record.id,
    )
    await finalize_flow_memory_base_cleanup([handle])
    backend.delete_collection.assert_awaited_once()
    backend.teardown.assert_awaited_once()
    assert await knowledge_base_service.get_by_id(record.id) is None


async def test_finalize_failure_retains_retryable_routing(active_user, monkeypatch):
    backend = _fake_backend(delete_error=ConnectionError("no route to host"), connection_ok=False)
    monkeypatch.setattr("langflow.services.knowledge_base_storage.runtime._raw_backend", lambda *_a, **_k: backend)
    record = await knowledge_base_service.create_record(
        user_id=active_user.id, name="remote_retry", backend_type="opensearch"
    )
    handle = FlowMemoryBaseCleanup(
        kb_name=record.name,
        user_id=record.user_id,
        kb_username=None,
        backend_type="opensearch",
        kb_record_id=record.id,
    )
    await finalize_flow_memory_base_cleanup([handle])
    retained = await knowledge_base_service.get_by_id(record.id)
    assert retained.storage_state == "deleting"
    assert retained.backend_type == "opensearch"
    backend.delete_collection.side_effect = None
    await finalize_flow_memory_base_cleanup([handle])
    assert await knowledge_base_service.get_by_id(record.id) is None


async def test_finalize_continues_after_one_failed_handle(active_user, monkeypatch):
    failing = await knowledge_base_service.create_record(
        user_id=active_user.id, name="failed_cleanup", backend_type="opensearch"
    )
    healthy = await knowledge_base_service.create_record(
        user_id=active_user.id, name="healthy_cleanup", backend_type="opensearch"
    )
    backend = _fake_backend()

    def construct(record, **_kwargs):
        if record.id == failing.id:
            msg = "unavailable provider"
            raise ValueError(msg)
        return backend

    monkeypatch.setattr("langflow.services.knowledge_base_storage.runtime._raw_backend", construct)
    handles = [
        FlowMemoryBaseCleanup(
            kb_name=row.name,
            user_id=row.user_id,
            kb_username=None,
            backend_type=row.backend_type,
            kb_record_id=row.id,
        )
        for row in (failing, healthy)
    ]
    await finalize_flow_memory_base_cleanup(handles)
    # Initialization failed before the destructive operation started.
    assert (await knowledge_base_service.get_by_id(failing.id)).storage_state == "ready"
    assert await knowledge_base_service.get_by_id(healthy.id) is None


async def test_finalize_handle_without_routing_does_not_guess_storage(monkeypatch):
    delete_kb = AsyncMock()
    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.delete_kb", delete_kb)
    handle = FlowMemoryBaseCleanup(
        kb_name="legacy_local",
        user_id=uuid.uuid4(),
        kb_username="alice",
        backend_type="chroma",
    )
    await finalize_flow_memory_base_cleanup([handle])
    delete_kb.assert_awaited_once_with(kb_name="legacy_local", kb_username="alice")


async def test_owner_cascade_cannot_leave_sqlite_vectors_live(active_user):
    from langflow.services.knowledge_base_storage.runtime import _raw_backend

    record = await knowledge_base_service.create_record(user_id=active_user.id, name="owner_cascade")
    raw = _raw_backend(record)
    handle = FlowMemoryBaseCleanup(
        kb_name=record.name,
        user_id=record.user_id,
        kb_username=active_user.username,
        backend_type="sqlite",
        kb_record_id=record.id,
        storage_record=record.model_copy(deep=True),
    )
    # Emulate the user FK cascade: the post-commit cleanup has a trusted
    # snapshot but the routing row no longer exists.
    async with session_scope() as db:
        row = await db.get(KnowledgeBaseRecord, record.id)
        await db.delete(row)
        await db.commit()
    await finalize_flow_memory_base_cleanup([handle])
    with pytest.raises(ValueError, match="deleted"):
        await raw.count()
    await raw.teardown()


async def test_owner_cascade_preserves_unfinished_legacy_migration(active_user, monkeypatch):
    record = KnowledgeBaseRecord(
        user_id=active_user.id, name="legacy_migration_source", backend_type="chroma", storage_state="migrating"
    )
    handle = FlowMemoryBaseCleanup(
        kb_name=record.name,
        user_id=record.user_id,
        kb_username=active_user.username,
        backend_type="chroma",
        kb_record_id=record.id,
        storage_record=record,
    )
    delete_kb = AsyncMock()
    monkeypatch.setattr("langflow.services.memory_base.flow_cleanup.delete_kb", delete_kb)
    await finalize_flow_memory_base_cleanup([handle])
    delete_kb.assert_not_awaited()


@pytest.mark.parametrize(
    ("backend", "state"), [("sqlite", "migrating"), ("sqlite", "needs_attention"), ("chroma", "ready")]
)
async def test_flow_purge_preserves_migration_fence(client, json_flow, logged_in_headers, backend, state):
    """Reject flow deletion without overwriting a migration or retired-store fence."""
    from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError

    flow_id, user_id = await _create_flow(client, json_flow, logged_in_headers)
    kb_name = f"fenced_{uuid.uuid4().hex[:8]}"
    mb_id = await _seed_memory_base(flow_id, user_id, kb_name=kb_name)
    record = await knowledge_base_service.get_by_user_and_name(user_id, kb_name)
    async with session_scope() as db:
        row = await db.get(KnowledgeBaseRecord, record.id)
        row.backend_type = backend
        row.storage_state = state
    with pytest.raises(StorageUnavailableError):
        async with session_scope() as db:
            await purge_flow_memory_bases(db, flow_id)
    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 409, response.text
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == state
    assert await _count_rows(MemoryBase, id=mb_id) == 1
    assert await _count_rows(MemoryBaseSession, memory_base_id=mb_id) == 1


async def test_flow_delete_retains_detached_store(client, json_flow, logged_in_headers):
    """A detached Memory can leave its flow without deleting retained storage."""
    flow_id, user_id = await _create_flow(client, json_flow, logged_in_headers)
    kb_name = f"detached_{uuid.uuid4().hex[:8]}"
    mb_id = await _seed_memory_base(flow_id, user_id, kb_name=kb_name)
    record = await knowledge_base_service.get_by_user_and_name(user_id, kb_name)
    async with session_scope() as db:
        row = await db.get(KnowledgeBaseRecord, record.id)
        row.storage_state = "detached"
    response = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    assert await _count_rows(MemoryBase, id=mb_id) == 0
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "detached"
