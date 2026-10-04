"""Administrator recovery of pending deletions without identity or history loss."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from langflow.services.knowledge_base_storage import cleanup, runtime
from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
async def storage_root(client, active_user, monkeypatch, tmp_path):  # noqa: ARG001 -- initialize application services
    from langflow.services.knowledge_base_storage import coordinator

    await coordinator.wait_for_upgrade()
    root = tmp_path / "knowledge"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    await coordinator.reconcile_legacy_inventory()
    return root


@pytest.fixture
async def admin_headers(client, active_user):  # noqa: ARG001 -- distinguish the KB owner from its administrator
    username = f"cleanup-admin-{uuid4()}"
    password = uuid4().hex
    admin = User(
        username=username,
        password=get_auth_service().get_password_hash(password),
        is_active=True,
        is_superuser=True,
    )
    async with session_scope() as session:
        session.add(admin)
        await session.commit()
    response = await client.post("/api/v1/login", data={"username": username, "password": password})
    assert response.status_code == 200
    yield {"Authorization": f"Bearer {response.json()['access_token']}"}
    async with session_scope() as session:
        user = await session.get(User, admin.id)
        if user is not None:
            await session.delete(user)
            await session.commit()


async def pending_record(user_id, *, state="deleting", backend_type="sqlite", name="pending-cleanup"):
    record = await knowledge_base_service.create_record(user_id=user_id, name=name, backend_type=backend_type)
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = state
        await session.commit()
    return record


def retry_url(kb_id):
    return f"/api/v1/knowledge-base-storage/pending-cleanup/{kb_id}/retry"


async def test_retry_deletes_only_captured_identity_and_retains_source_binding(
    client, admin_headers, active_user, storage_root
):
    record = await pending_record(active_user.id)
    legacy = storage_root / "retained-source"
    legacy.mkdir()
    source = legacy / "chroma.sqlite3"
    source.write_bytes(b"retained migration source")
    bindings = storage_root / ".migration" / "bindings"
    bindings.mkdir(parents=True)
    binding = bindings / "source.json"
    binding.write_text("retained binding")
    response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"
    assert await knowledge_base_service.get_by_id(record.id) is None
    assert source.read_bytes() == b"retained migration source"
    assert binding.read_text() == "retained binding"

    replacement = await knowledge_base_service.create_record(user_id=active_user.id, name=record.name)
    response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "already_absent"
    assert await knowledge_base_service.get_by_id(replacement.id) is not None
    backend = await runtime.backend_for_record(replacement)
    assert await backend.count() == 0
    await backend.teardown()


async def test_retry_requires_superuser(client, logged_in_headers, active_user, storage_root):  # noqa: ARG001
    record = await pending_record(active_user.id)
    for method, url in (
        (client.get, "/api/v1/knowledge-base-storage/pending-cleanup"),
        (client.post, retry_url(record.id)),
    ):
        kwargs = {"json": {"expected_generation": 1}} if method == client.post else {}
        response = await method(url, headers=logged_in_headers, **kwargs)
        assert response.status_code == 403, response.text
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "deleting"


@pytest.mark.parametrize("state", ["ready", "migrating", "needs_attention"])
async def test_retry_rejects_nonpending_states(client, admin_headers, active_user, storage_root, state):  # noqa: ARG001
    record = await pending_record(active_user.id, state=state)
    response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 409, response.text
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == state


async def test_retry_rejects_stale_generation(client, admin_headers, active_user, storage_root):  # noqa: ARG001
    record = await pending_record(active_user.id)
    response = await client.post(retry_url(record.id), json={"expected_generation": 2}, headers=admin_headers)
    assert response.status_code == 409
    assert (await knowledge_base_service.get_by_id(record.id)).storage_generation == 1


async def test_retry_rechecks_generation_after_waiting_for_lock(active_user, storage_root, monkeypatch):  # noqa: ARG001
    record = await pending_record(active_user.id)
    entered, release = asyncio.Event(), asyncio.Event()
    original_operation = cleanup.operation

    @asynccontextmanager
    async def delayed_operation(*args, **kwargs):
        entered.set()
        await release.wait()
        async with original_operation(*args, **kwargs) as current:
            yield current

    monkeypatch.setattr(cleanup, "operation", delayed_operation)
    task = asyncio.create_task(cleanup.retry_pending_cleanup(record.id, expected_generation=1))
    await asyncio.wait_for(entered.wait(), 2)
    async with session_scope() as session:
        current = await session.get(KnowledgeBaseRecord, record.id)
        current.storage_generation = 2
        await session.commit()
    release.set()
    with pytest.raises(runtime.StorageUnavailableError, match="changed"):
        await task
    assert (await knowledge_base_service.get_by_id(record.id)).storage_generation == 2


async def test_retry_failure_retains_metadata_then_recovers(
    client,
    admin_headers,
    active_user,
    storage_root,  # noqa: ARG001
    monkeypatch,
):
    record = await pending_record(active_user.id)

    async def failed_delete(_self):
        msg = "private provider or filesystem details"
        raise OSError(msg)

    with monkeypatch.context() as context:
        context.setattr(SQLiteBackend, "delete_collection", failed_delete)
        response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 503
    assert "private provider" not in response.text
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "deleting"
    response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 200


async def test_concurrent_retries_are_idempotent(active_user, storage_root):  # noqa: ARG001
    record = await pending_record(active_user.id)
    results = await asyncio.gather(
        cleanup.retry_pending_cleanup(record.id, expected_generation=1),
        cleanup.retry_pending_cleanup(record.id, expected_generation=1),
    )
    assert sorted(results) == [False, True]
    assert await knowledge_base_service.get_by_id(record.id) is None


async def test_completed_storage_cleanup_only_removes_metadata(active_user, storage_root, monkeypatch):  # noqa: ARG001
    record = await pending_record(active_user.id)
    current = await knowledge_base_service.get_by_id(record.id)
    await runtime.delete_storage_for_record(current)
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "deleted"

    async def unexpected_delete(_self):
        pytest.fail("Completed storage deletion must not contact the store again")

    monkeypatch.setattr(SQLiteBackend, "delete_collection", unexpected_delete)
    assert await cleanup.retry_pending_cleanup(record.id, expected_generation=1) is True
    assert await knowledge_base_service.get_by_id(record.id) is None


async def test_memory_reference_preserves_history_and_guides_normal_deletion(
    client,
    admin_headers,
    logged_in_headers,
    active_user,
    storage_root,  # noqa: ARG001
):
    record = await pending_record(active_user.id)
    memory = MemoryBase(name="pending memory", flow_id=uuid4(), user_id=active_user.id, kb_name=record.name)
    history = MemoryBaseSession(memory_base_id=memory.id, session_id="preserve-until-memory-delete", total_processed=3)
    async with session_scope() as session:
        session.add_all([memory, history])
        await session.commit()
    response = await client.get("/api/v1/knowledge-base-storage/pending-cleanup", headers=admin_headers)
    assert response.status_code == 200
    pending = next(item for item in response.json() if item["kb_id"] == str(record.id))
    assert pending["storage_generation"] == 1
    assert pending["memory_base_ids"] == [str(memory.id)]
    assert "Memory Base" in pending["guidance"]
    response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 409
    async with session_scope() as session:
        assert await session.get(MemoryBase, memory.id) is not None
        assert (await session.get(MemoryBaseSession, history.id)).total_processed == 3
    response = await client.delete(f"/api/v1/memories/{memory.id}", headers=logged_in_headers)
    assert response.status_code == 204, response.text
    async with session_scope() as session:
        assert await session.get(MemoryBase, memory.id) is None
        assert await session.get(MemoryBaseSession, history.id) is None
    response = await client.post(retry_url(record.id), json={"expected_generation": 1}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "already_absent"


async def test_remote_failure_propagates_and_uses_kb_owner(active_user, storage_root, monkeypatch):  # noqa: ARG001
    record = await pending_record(active_user.id, backend_type="postgres")
    calls = []

    class Remote:
        async def ensure_ready(self):
            calls.append("ready")

        async def delete_collection(self):
            calls.append("delete")
            msg = "remote unavailable"
            raise OSError(msg)

        async def teardown(self):
            calls.append("teardown")

    def owner_backend(current):
        assert current.id == record.id
        assert current.user_id == active_user.id
        return Remote()

    monkeypatch.setattr(runtime, "_raw_backend", owner_backend)
    with pytest.raises(OSError, match="remote unavailable"):
        await cleanup.retry_pending_cleanup(record.id, expected_generation=1)
    assert calls == ["ready", "delete", "teardown"]
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "deleting"


async def test_cancelled_remote_delete_drains_before_concurrent_retry(active_user, storage_root, monkeypatch):  # noqa: ARG001
    record = await pending_record(active_user.id, backend_type="opensearch")
    entered, release = threading.Event(), threading.Event()
    calls = []

    def delete_index(**_kwargs):
        calls.append("delete")
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return {"acknowledged": True}

    def backend_for_record(current):
        backend = OpenSearchBackend(kb_name=current.name, backend_config={}, user_id=current.user_id)
        backend._secrets_resolved = True
        backend._os_index = "disposable-test-index"
        backend._os_client = SimpleNamespace(indices=SimpleNamespace(delete=delete_index))
        return backend

    monkeypatch.setattr(runtime, "_raw_backend", backend_for_record)
    first = asyncio.create_task(cleanup.retry_pending_cleanup(record.id, expected_generation=1))
    assert await asyncio.to_thread(entered.wait, 3)
    first.cancel()
    second = asyncio.create_task(cleanup.retry_pending_cleanup(record.id, expected_generation=1))
    try:
        await asyncio.sleep(0.1)
        assert not first.done()
        assert not second.done()
        assert calls == ["delete"]
        assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "deleting"
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert await second is True
    assert calls == ["delete", "delete"]
    assert await knowledge_base_service.get_by_id(record.id) is None


@pytest.mark.parametrize("route", ["inventory", "migrations", "pending-cleanup"])
async def test_storage_status_requires_superuser(client, logged_in_headers, route):
    """Ordinary authenticated users cannot enumerate storage administration state."""
    response = await client.get(f"/api/v1/knowledge-base-storage/{route}", headers=logged_in_headers)
    assert response.status_code == 403


@pytest.mark.parametrize("route", ["migrations/{id}/retry", "attention/{id}/detach"])
async def test_storage_recovery_requires_superuser(client, logged_in_headers, route):
    """Recovery authorization precedes lookup and mutation."""
    response = await client.post(
        f"/api/v1/knowledge-base-storage/{route.format(id=uuid4())}",
        headers=logged_in_headers,
        json={"expected_generation": 1},
    )
    assert response.status_code == 403


async def test_inventory_and_empty_status_routes(client, admin_headers, storage_root):  # noqa: ARG001 -- isolated inventory
    """Inventory and empty status endpoints expose their documented HTTP response shapes."""
    inventory = await client.get("/api/v1/knowledge-base-storage/inventory", headers=admin_headers)
    assert inventory.status_code == 200
    assert inventory.json() == {"complete": True, "issues": 0}
    for route in ("migrations", "pending-cleanup"):
        response = await client.get(f"/api/v1/knowledge-base-storage/{route}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json() == []


async def _attention_migration(user_id):
    """Bind an attention ledger to a retired cloud store without opening its source."""
    from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration

    record = await pending_record(user_id, state="needs_attention", backend_type="chroma")
    run = KnowledgeBaseStorageMigration(
        kb_id=record.id,
        source_generation=1,
        target_generation=2,
        phase="needs_attention",
        error_code="remote_source_requires_migration",
    )
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.backend_config = {"mode": "cloud"}
        row.active_migration_id = run.id
        session.add(run)
        await session.commit()
    return record, run


async def test_migration_status_retry_and_detach(client, admin_headers, active_user, storage_root, monkeypatch):
    """Admins can inspect, retry, and explicitly detach a blocked store while retaining its evidence."""
    from unittest.mock import Mock

    from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
    from langflow.services.knowledge_base_storage import coordinator

    record, run = await _attention_migration(active_user.id)
    source = storage_root / "retained-source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "chroma.sqlite3").write_bytes(b"operator-owned source")
    scheduled = Mock()
    monkeypatch.setattr("langflow.api.v1.knowledge_base_storage.schedule_upgrade", scheduled)
    response = await client.get("/api/v1/knowledge-base-storage/migrations", headers=admin_headers)
    assert response.status_code == 200
    entry = next(row for row in response.json() if row["id"] == str(run.id))
    assert entry["kb_id"] == str(record.id)
    assert entry["error_code"] == "remote_source_requires_migration"
    assert "pgVector" in entry["guidance"]
    response = await client.post(f"/api/v1/knowledge-base-storage/migrations/{run.id}/retry", headers=admin_headers)
    assert response.status_code == 202
    assert response.json() == {"id": str(run.id), "status": "scheduled"}
    scheduled.assert_called_once_with(retry=True)
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "needs_attention"
    assert not await coordinator.readiness()
    assert await coordinator.readiness(require_storage_ready=False)
    response = await client.post(
        f"/api/v1/knowledge-base-storage/attention/{record.id}/detach",
        headers=admin_headers,
        json={"expected_generation": 1},
    )
    assert response.status_code == 200
    assert response.json() == {"kb_id": str(record.id), "status": "detached", "source_preserved": True}
    assert (source / "chroma.sqlite3").read_bytes() == b"operator-owned source"
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "detached"
    async with session_scope() as session:
        assert (await session.get(KnowledgeBaseStorageMigration, run.id)).phase == "detached"
    assert await coordinator.readiness()


@pytest.mark.parametrize("state", ["ready", "deleting", "detached"])
async def test_migration_retry_rejects_changed_routing(client, admin_headers, active_user, state):
    """The ledger alone cannot authorize a retry after the routing fence changed."""
    record, run = await _attention_migration(active_user.id)
    async with session_scope() as session:
        row = await session.get(KnowledgeBaseRecord, record.id)
        row.storage_state = state
        await session.commit()
    response = await client.post(f"/api/v1/knowledge-base-storage/migrations/{run.id}/retry", headers=admin_headers)
    assert response.status_code == 409
    assert response.json() == {"detail": "This storage migration cannot be retried"}


async def test_unknown_migration_retry_returns_404(client, admin_headers):
    """An unknown migration UUID has a stable not-found response."""
    response = await client.post(f"/api/v1/knowledge-base-storage/migrations/{uuid4()}/retry", headers=admin_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Storage migration not found"}


@pytest.mark.parametrize("generation", [2, 0, "1"])
async def test_detach_rejects_stale_or_invalid_generation(client, admin_headers, active_user, generation):
    """Detachment cannot bypass the original immutable generation confirmation."""
    record, _run = await _attention_migration(active_user.id)
    response = await client.post(
        f"/api/v1/knowledge-base-storage/attention/{record.id}/detach",
        headers=admin_headers,
        json={"expected_generation": generation},
    )
    assert response.status_code == (409 if generation == 2 else 422)
    assert (await knowledge_base_service.get_by_id(record.id)).storage_state == "needs_attention"


@pytest.mark.parametrize("outcome", ["ready", "blocked", "exception"])
@pytest.mark.parametrize("strict", [False, True])
async def test_http_healthz_storage_gate(client, monkeypatch, outcome, strict):
    """HTTP readiness fails closed on inventory errors and preserves the controller's strict option."""
    from unittest.mock import AsyncMock

    ready = AsyncMock(return_value=outcome == "ready")
    if outcome == "exception":
        ready.side_effect = RuntimeError("private storage details")
    monkeypatch.setattr("langflow.services.knowledge_base_storage.coordinator.readiness", ready)
    response = await client.get(f"/healthz?require_storage_ready={str(strict).lower()}")
    ready.assert_awaited_once_with(require_storage_ready=strict)
    assert response.status_code == (200 if outcome == "ready" else 503)
    if outcome != "ready":
        assert response.json() == {"detail": "Knowledge base storage upgrade requires attention"}
