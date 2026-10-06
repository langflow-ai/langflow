"""Upgrade, privacy and concurrency regressions reproduced by the PR review."""

import asyncio
import hashlib
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pandas as pd
import pytest
from langchain_core.documents import Document
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
from langflow.services.knowledge_base_storage import cleanup, coordinator, maintenance, runtime
from langflow.services.memory_base import ingestion
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError, BaseVectorStoreBackend, IngestedDocument
from lfx.base.knowledge_bases.backends.sqlite import SQLiteBackend, SQLiteStorageContext
from lfx.components.files_and_knowledge.knowledge import KnowledgeComponent
from sqlmodel import SQLModel

from . import test_storage_upgrade as storage_tests

database = storage_tests.database
export_helper = storage_tests.export_helper
make_kb = storage_tests.make_kb
read_kb = storage_tests.read_kb
frozen_source = storage_tests.frozen_source

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("name", ["../victim/knowledge", ".", "..", "bad\\name", "bad\0name"])
async def test_create_service_rejects_unsafe_names_before_disk_or_persistence(database, monkeypatch, name):
    """Every create entry point must reject unsafe paths before reserving legacy names."""
    from langflow.api.utils import knowledge_base_service

    monkeypatch.setattr(knowledge_base_service, "session_scope", database.sessions)
    monkeypatch.setattr(
        coordinator, "ensure_legacy_name_available", AsyncMock(side_effect=AssertionError("unsafe path inspected"))
    )
    with pytest.raises(ValueError, match="KB name"):
        await knowledge_base_service.create_record(user_id=database.user.id, name=name)
    assert await knowledge_base_service.get_by_user_and_name(database.user.id, name) is None


@pytest.mark.parametrize("entrypoint", ["service", "component"])
async def test_legacy_name_cannot_be_claimed_while_discovery_is_running(database, monkeypatch, entrypoint):
    """A create overlapping discovery must leave the original identity available for adoption."""
    from langflow.api.utils import knowledge_base_service

    monkeypatch.setattr(knowledge_base_service, "session_scope", database.sessions)
    source = storage_tests.native_source(database)
    identity = uuid4()
    (source / "embedding_metadata.json").write_text(
        json.dumps({"id": str(identity), "name": "fixture-l2", "embedding_model": "text-embedding-3-small"})
    )
    original = maintenance.tree_fingerprint(source)
    started, release = threading.Event(), threading.Event()
    fingerprint = coordinator.tree_fingerprint

    def paused_discovery(path):
        if path == source and not started.is_set():
            started.set()
            assert release.wait(timeout=10)
        return fingerprint(path)

    monkeypatch.setattr(coordinator, "tree_fingerprint", paused_discovery)
    discovery = asyncio.create_task(coordinator.run_pending())
    assert await asyncio.to_thread(started.wait, 5)
    try:
        if entrypoint == "service":
            creation = knowledge_base_service.create_record(user_id=database.user.id, name="fixture-l2")
        else:
            component = KnowledgeComponent()
            creation = component._create_knowledge_base_record(
                user_id=database.user.id,
                name="fixture-l2",
                model_selection=[{"name": "text-embedding-3-small", "provider": "OpenAI"}],
                backend_type="sqlite",
                backend_config={},
            )
        with pytest.raises(runtime.StorageUnavailableError, match="held by data from a previous version"):
            await creation
        assert await knowledge_base_service.get_by_user_and_name(database.user.id, "fixture-l2") is None
    finally:
        release.set()
        await discovery
    adopted = await read_kb(database, identity)
    assert (adopted.storage_state, adopted.backend_type, adopted.chunks) == ("ready", "sqlite", 239)
    assert maintenance.tree_fingerprint(source) == original
    assert coordinator.inventory_status()["issues"] == 0


@pytest.mark.parametrize("action", ["duplicate", "reroute"])
async def test_knowledge_component_embeds_without_lock_and_rechecks_before_write(database, monkeypatch, action):
    """Concurrent reads/writes stay available, and changes during embedding are respected."""
    from langflow.api.utils import knowledge_base_service

    monkeypatch.setattr(knowledge_base_service, "session_scope", database.sessions)
    row = await make_kb(database, backend="sqlite")
    reader = await runtime.backend_for_record(row, create=True)
    await reader.ensure_ready()
    started, release = asyncio.Event(), asyncio.Event()

    async def embed(_texts):
        started.set()
        await release.wait()
        return [[1.0, 2.0]]

    component = KnowledgeComponent(_user_id=str(row.user_id))
    component.set(knowledge_base=row.name, allow_duplicates=False)
    writing = asyncio.create_task(
        component._create_vector_store(
            pd.DataFrame({"text": ["overlapping document"]}),
            [{"column_name": "text", "vectorize": True, "identifier": True}],
            SimpleNamespace(aembed_documents=embed),
        )
    )
    await asyncio.wait_for(started.wait(), 1)
    try:
        assert await asyncio.wait_for(reader.count(), 1) == 0
        if action == "duplicate":
            doc_hash = hashlib.sha256(b"overlapping document").hexdigest()
            await asyncio.wait_for(
                reader.add_embedded_documents(
                    [IngestedDocument("winning concurrent write", {"_id": doc_hash}, [1.0, 2.0], id="winner")]
                ),
                1,
            )
        else:
            async with runtime.operation(row), database.sessions() as session:
                current = await session.get(KnowledgeBaseRecord, row.id)
                current.storage_generation += 1
                await session.commit()
    finally:
        release.set()
        if action == "reroute":
            with pytest.raises(runtime.StorageUnavailableError, match="storage changed"):
                await writing
        else:
            await writing
        await reader.teardown()
    original = SQLiteBackend(row.name, storage_context=SQLiteStorageContext(database.root, row.user_id, row.id))
    try:
        assert await original.count() == (1 if action == "duplicate" else 0)
    finally:
        await original.teardown()


@pytest.mark.usefixtures("database")
async def test_inventory_does_not_disable_ordinary_service_readiness(monkeypatch):
    monkeypatch.setattr(coordinator, "_inventory_complete", False)
    monkeypatch.setattr(coordinator, "_inventory_scanned", True)
    assert await coordinator.readiness(require_storage_ready=False)
    assert not await coordinator.readiness(require_storage_ready=True)


async def test_ordinary_readiness_stays_available_during_first_scan_with_issues(database, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    original = coordinator.reconcile_legacy_inventory
    source = database.root / database.user.username / "unregistered"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"retained source")
    monkeypatch.setattr(coordinator, "_inventory_scanned", False)

    async def paused_scan():
        started.set()
        await release.wait()
        await original()

    monkeypatch.setattr(coordinator, "reconcile_legacy_inventory", paused_scan)
    task = asyncio.create_task(coordinator.run_pending())
    await started.wait()
    try:
        assert await coordinator.readiness(require_storage_ready=False)
    finally:
        release.set()
        await task
    assert coordinator.inventory_status()["issues"] == 1
    assert await coordinator.readiness(require_storage_ready=False)
    assert not await coordinator.readiness(require_storage_ready=True)


@pytest.mark.parametrize("state", ["needs_attention", "detached"])
@pytest.mark.parametrize("backend_type", ["sqlite", "chroma"])
async def test_unavailable_record_deletion_erases_owned_sqlite_generations(database, state, backend_type):
    row = await make_kb(database, backend=backend_type)
    run = KnowledgeBaseStorageMigration(kb_id=row.id, source_generation=1, target_generation=2)
    async with database.sessions() as db:
        db.add(run)
        current = await db.get(KnowledgeBaseRecord, row.id)
        current.storage_state = state
        current.active_migration_id = run.id
        await db.commit()
    source = database.root / database.user.username / row.name
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"original retained source")
    generations = [1, 2] if backend_type == "sqlite" else [2]
    sentinel = b"unavailable-store-private-document"
    for generation in generations:
        context = SQLiteStorageContext(database.root, row.user_id, row.id, generation)
        target = SQLiteBackend(row.name, backend_config={"metric": "cosine"}, storage_context=context, create=True)
        await target.add_embedded_documents([IngestedDocument(sentinel.decode(), {}, [1.0, 2.0])])
        await target.teardown()
    await runtime.delete_storage_for_record(await read_kb(database, row.id))
    assert (await read_kb(database, row.id)).storage_state == "deleted"
    assert (source / "chroma.sqlite3").read_bytes() == b"original retained source"
    for generation in generations:
        context = SQLiteStorageContext(database.root, row.user_id, row.id, generation)
        assert sentinel not in b"".join(path.read_bytes() for path in context.database_path.parent.iterdir())
        reader = SQLiteBackend(row.name, backend_config={"metric": "cosine"}, storage_context=context)
        with pytest.raises(BackendConfigurationError, match="deleted"):
            await reader.ensure_ready()
        await reader.teardown()


async def test_unavailable_sqlite_erasure_failure_keeps_routing_retryable(database, monkeypatch):
    row = await make_kb(database, backend="sqlite")
    context = SQLiteStorageContext(database.root, row.user_id, row.id)
    target = SQLiteBackend(row.name, storage_context=context, create=True)
    await target.add_embedded_documents([IngestedDocument("private-document", {}, [1.0, 2.0])])
    await target.teardown()
    async with database.sessions() as db:
        current = await db.get(KnowledgeBaseRecord, row.id)
        current.storage_state = "needs_attention"
        await db.commit()
    original = SQLiteBackend.delete_collection
    monkeypatch.setattr(SQLiteBackend, "delete_collection", AsyncMock(side_effect=OSError("disk unavailable")))
    with pytest.raises(OSError, match="disk unavailable"):
        await runtime.delete_storage_for_record(await read_kb(database, row.id))
    assert (await read_kb(database, row.id)).storage_state == "needs_attention"
    monkeypatch.setattr(SQLiteBackend, "delete_collection", original)
    await runtime.delete_storage_for_record(await read_kb(database, row.id))
    assert (await read_kb(database, row.id)).storage_state == "deleted"


async def test_detach_and_delete_retire_real_legacy_source_across_restart(database, monkeypatch):
    monkeypatch.setattr(cleanup, "session_scope", database.sessions)
    source = database.root / database.user.username / "knowledge"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"retained legacy data")
    row = await make_kb(database)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await read_kb(database, row.id)
    migration_id = current.active_migration_id
    await cleanup.detach_attention_store(row.id, expected_generation=current.storage_generation)
    await coordinator.run_pending()
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}
    await runtime.delete_storage_for_record(await read_kb(database, row.id))
    async with database.sessions() as db:
        await db.delete(await db.get(KnowledgeBaseRecord, row.id))
        await db.commit()
        assert await db.get(KnowledgeBaseStorageMigration, migration_id) is not None
    await coordinator.run_pending()
    assert coordinator.inventory_status()["complete"]
    assert (source / "chroma.sqlite3").read_bytes() == b"retained legacy data"
    replacement = await make_kb(database, backend="sqlite")
    assert replacement.id != row.id


def test_unchanged_retired_source_uses_stat_inventory_and_detects_content_changes(database, monkeypatch):
    source = database.root / "owner" / "knowledge"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"original")
    relative = "owner/knowledge"
    coordinator._write_source_binding(relative, maintenance.tree_fingerprint(source), uuid4())
    full_hash = coordinator.tree_fingerprint
    monkeypatch.setattr(coordinator, "tree_fingerprint", lambda _path: pytest.fail("Unchanged source was re-hashed"))
    assert coordinator._is_retired_source(relative)
    monkeypatch.setattr(coordinator, "tree_fingerprint", full_hash)
    (source / "chroma.sqlite3").write_bytes(b"modified")
    with pytest.raises(maintenance.MaintenanceRequiredError, match="source changed"):
        coordinator._is_retired_source(relative)


async def test_backend_construction_overlaps_an_existing_shared_reader(database):
    row = await make_kb(database, backend="sqlite")
    created = await runtime.backend_for_record(row, create=True)
    await created.ensure_ready()
    await created.teardown()

    async def prepare_reader():
        backend = await runtime.backend_for_record(row)
        await backend.ensure_ready()
        assert await backend.count() == 0
        return backend

    async with runtime.operation(row, shared=True):
        backend = await asyncio.wait_for(asyncio.create_task(prepare_reader()), 1)
    await backend.teardown()


async def test_collection_deletion_erases_plaintext_and_preserves_generation_tombstone(tmp_path):
    context = SQLiteStorageContext(tmp_path, uuid4(), uuid4())
    backend = SQLiteBackend("private", storage_context=context, create=True)
    sentinel = "private-document-deletion-sentinel"
    await backend.add_embedded_documents(
        [IngestedDocument(sentinel + str(i) + "x" * 2000, {}, [1.0, 2.0], id=str(i)) for i in range(100)]
    )
    original_size = context.database_path.stat().st_size
    await backend.delete_collection()
    assert context.database_path.stat().st_size < original_size
    assert sentinel.encode() not in b"".join(path.read_bytes() for path in context.database_path.parent.iterdir())
    with pytest.raises(ValueError, match="deleted"):
        await backend.count()
    await backend.delete_collection()


async def test_embeddings_do_not_hold_storage_lease_and_stale_routing_refuses_write(database):
    row = await make_kb(database, backend="sqlite")
    started, release = asyncio.Event(), asyncio.Event()

    async def embed(_texts):
        started.set()
        await release.wait()
        return [[1.0, 2.0]]

    native = SQLiteBackend(
        "knowledge",
        storage_context=SQLiteStorageContext(database.root, row.user_id, row.id),
        embedding_function=SimpleNamespace(aembed_documents=embed),
        create=True,
    )
    guarded = runtime._GuardedMethods(native, row)
    writing = asyncio.create_task(guarded.add_documents([Document(page_content="computed outside lock")]))
    await asyncio.wait_for(started.wait(), 1)
    async with runtime.operation(row), database.sessions() as db:
        current = await db.get(KnowledgeBaseRecord, row.id)
        current.storage_state = "detached"
        await db.commit()
    release.set()
    with pytest.raises(runtime.StorageUnavailableError, match="detached"):
        await writing
    assert not native.storage_context.database_path.exists()


async def test_extension_ingestion_without_preembedded_write_keeps_guard_and_source_callback(database):
    row = await make_kb(database, backend="sqlite")
    started, release = asyncio.Event(), asyncio.Event()
    written = []

    class LegacyExtension(BaseVectorStoreBackend):
        async def _build_vector_store(self):
            message = "Legacy add_documents should handle its own ingestion"
            raise AssertionError(message)

        async def add_documents(self, docs):
            started.set()
            await release.wait()
            written.extend(docs)

    callback = AsyncMock()
    extension = LegacyExtension(row.name)
    guarded = runtime._GuardedMethods(extension, row, before_write=callback)
    document = Document(page_content="extension-owned ingestion")
    writing = asyncio.create_task(guarded.add_documents([document]))
    await asyncio.wait_for(started.wait(), 1)
    callback.assert_awaited_once()
    acquired = asyncio.Event()

    async def competing_delete():
        async with runtime.operation(row):
            acquired.set()

    deleting = asyncio.create_task(competing_delete())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(acquired.wait(), 0.05)
    finally:
        release.set()
        await writing
        await deleting
    assert written == [document]


@pytest.mark.parametrize("exited", [True, False])
def test_denied_same_user_process_is_rechecked_for_exit(monkeypatch, exited):
    import psutil

    denied = SimpleNamespace(
        cmdline=lambda: (_ for _ in ()).throw(psutil.AccessDenied(123)),
        status=lambda: psutil.STATUS_RUNNING,
        username=lambda: "application",
        is_running=lambda: not exited,
    )
    monkeypatch.setattr(maintenance.psutil, "Process", lambda: SimpleNamespace(username=lambda: "application"))
    pauses = []
    monkeypatch.setattr(maintenance.time, "sleep", pauses.append)
    if exited:
        assert not maintenance._legacy_process(denied)
        assert pauses == [0.01]
    else:
        with pytest.raises(maintenance.MaintenanceRequiredError, match="application account"):
            maintenance._legacy_process(denied)
        assert pauses == [0.01] * 3


async def test_fenced_session_purge_is_durable_and_replayed_before_retrieval(database, monkeypatch):
    monkeypatch.setattr(ingestion, "session_scope", database.sessions)
    # Include the normal history tables for the real deletion transaction.
    async with database.sessions() as db, db.bind.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    row = await make_kb(database)
    async with database.sessions() as db:
        current = await db.get(KnowledgeBaseRecord, row.id)
        current.storage_state = "needs_attention"
        memory = MemoryBase(name="memory", flow_id=uuid4(), user_id=row.user_id, kb_name=row.name)
        db.add(memory)
        await db.commit()
        tracking = MemoryBaseSession(memory_base_id=memory.id, session_id="deleted-session", total_processed=4)
        db.add(tracking)
        await db.commit()
    assert await ingestion.purge_session_data(user_id=row.user_id, session_ids=[tracking.session_id]) == 1
    async with database.sessions() as db:
        pending = await db.get(MemoryBaseSession, tracking.id)
        assert pending.purge_pending
        assert pending.total_processed == 0
        assert pending.cursor_id is None
    target = SimpleNamespace(delete_by=AsyncMock())
    await ingestion.apply_pending_session_purges(row, target)
    target.delete_by.assert_awaited_once_with({"session_id": "deleted-session"})
    async with database.sessions() as db:
        assert await db.get(MemoryBaseSession, tracking.id) is None


@pytest.mark.usefixtures("export_helper")
async def test_migration_replays_pending_purge_and_crash_retry_keeps_valid_manifest(database, monkeypatch):
    monkeypatch.setattr(ingestion, "session_scope", database.sessions)
    row = await make_kb(database)
    frozen_source(database, monkeypatch)
    memory = MemoryBase(name="memory", flow_id=uuid4(), user_id=row.user_id, kb_name=row.name)
    tracking = MemoryBaseSession(memory_base_id=memory.id, session_id="s", purge_pending=True)
    async with database.sessions() as db:
        db.add_all([memory, tracking])
        await db.commit()
    replay = ingestion.apply_pending_session_purges

    async def interrupted_before_removing_intent(_record, target):
        await target.delete_by({"session_id": "s"})
        msg = "Interrupted after vector deletion"
        raise OSError(msg)

    monkeypatch.setattr(ingestion, "apply_pending_session_purges", interrupted_before_removing_intent)
    await coordinator.migrate_one(row.id)
    assert (await read_kb(database, row.id)).storage_state == "needs_attention"
    monkeypatch.setattr(ingestion, "apply_pending_session_purges", replay)
    await coordinator.migrate_one(row.id)
    current = await read_kb(database, row.id)
    assert current.storage_state == "ready"
    assert current.chunks == 1
    backend = await runtime.backend_for_record(current)
    assert [doc.id async for batch in backend.iter_documents() for doc in batch] == ["b"]
    async with database.sessions() as db:
        assert await db.get(MemoryBaseSession, tracking.id) is None


@pytest.mark.parametrize("runner", ["opensearch", "importer", "helper", "coordinator", "runtime"])
async def test_failed_worker_cannot_replace_received_cancellation(runner):
    from langflow.services.knowledge_base_storage import helper
    from lfx.base.knowledge_bases.backends.opensearch import _drained_worker
    from lfx.base.knowledge_bases.migration.importer import _run_worker

    started, release = threading.Event(), threading.Event()

    def fail_after_release():
        started.set()
        assert release.wait(5)
        msg = "Worker failed after cancellation"
        raise OSError(msg)

    runners = {
        "opensearch": _drained_worker,
        "importer": _run_worker,
        "helper": helper._disk_call,
        "coordinator": coordinator._worker,
    }
    if runner == "runtime":
        task = asyncio.create_task(runtime._drain_cleanup(asyncio.to_thread(fail_after_release)))
    else:
        task = asyncio.create_task(runners[runner](fail_after_release))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.parametrize(
    "command",
    [
        ["journalctl", "-fu", "langflow"],
        ["python", "logs.py", "-m", "langflow"],
        ["systemctl", "status", "langflow"],
        ["docker", "logs", "-f", "langflow"],
        ["less", "/var/log/langflow"],
        [
            "uv",
            "run",
            "python",
            "-m",
            "langflow.services.knowledge_base_storage.controller",
            "--",
            "python",
            "-m",
            "langflow",
            "run",
        ],
        [
            "python",
            "-m",
            "langflow.services.knowledge_base_storage.controller",
            "--",
            "python",
            "-m",
            "langflow",
            "run",
        ],
    ],
)
def test_controller_scanner_ignores_operator_tools_and_its_launch_arguments(command):
    assert not maintenance._legacy_process(SimpleNamespace(cmdline=lambda: command))


@pytest.mark.parametrize(
    "command",
    [
        ["langflow", "run"],
        ["python", "-m", "langflow", "run"],
        ["uvicorn", "langflow.main:app"],
        ["python", "-m", "uvicorn", "langflow.main:app"],
        ["python", "-W", "ignore", "-m", "langflow", "run"],
    ],
)
def test_controller_scanner_still_identifies_real_entry_points(command):
    assert maintenance._legacy_process(SimpleNamespace(cmdline=lambda: command))


async def test_accepted_retry_replays_failures_from_an_active_batch(monkeypatch):
    first_started, finish_first = asyncio.Event(), asyncio.Event()
    calls = []

    async def pending():
        calls.append(True)
        coordinator._inventory_scanned = True
        if len(calls) == 1:
            first_started.set()
            await finish_first.wait()

    monkeypatch.setattr(coordinator, "run_pending", pending)
    monkeypatch.setattr(coordinator, "_tasks", set())
    monkeypatch.setattr(coordinator, "_inventory_complete", True)
    monkeypatch.setattr(coordinator, "_inventory_scanned", True)
    monkeypatch.setattr(coordinator, "_retry_requested", False)
    task = coordinator.schedule_upgrade()
    await first_started.wait()
    assert coordinator.schedule_upgrade(retry=True) is task
    assert await coordinator.readiness(require_storage_ready=False)
    finish_first.set()
    await asyncio.wait_for(task, 1)
    assert len(calls) == 2


async def test_configurable_remote_coordination_pool_supports_more_than_four_callers(monkeypatch):
    import os

    from .test_storage_runtime_locks import FakeAdvisoryEngine

    engine = FakeAdvisoryEngine()
    engine.capacity = asyncio.Semaphore(8)
    url = f"postgresql+psycopg://test/{uuid4().hex}"
    monkeypatch.setattr(runtime, "get_db_service", lambda: SimpleNamespace(database_url=url, _get_connect_args=dict))
    monkeypatch.setattr(
        runtime,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(knowledge_base_storage_pool_size=8)),
    )
    configured = []

    def create_engine(_url, **kwargs):
        configured.append(kwargs)
        return engine

    monkeypatch.setattr(runtime, "create_async_engine", create_engine)
    entered, release = asyncio.Event(), asyncio.Event()
    count = 0

    async def reader():
        nonlocal count
        async with runtime._remote_lock(uuid4(), shared=True):
            count += 1
            if count == 6:
                entered.set()
            await release.wait()

    tasks = [asyncio.create_task(reader()) for _ in range(6)]
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert configured[0]["pool_size"] == 8
        assert configured[0]["max_overflow"] == 0
    finally:
        release.set()
        await asyncio.gather(*tasks)
        runtime._coordination_engines.pop((os.getpid(), url, asyncio.get_running_loop()), None)


async def test_kernel_process_identity_survives_a_wall_clock_step(monkeypatch):
    process = SimpleNamespace(pid=10, create_time=lambda: 2000)
    identity = {"pid": 10, "created": 1000, "start_ticks": 123, "boot_id": "same-boot"}
    monkeypatch.setattr(maintenance, "process_identity", lambda _process: {**identity, "created": 2000})
    assert maintenance.identity_matches(process, identity)
    assert not maintenance.identity_matches(process, {**identity, "start_ticks": 124})
    assert not maintenance.identity_matches(process, {**identity, "boot_id": "another-boot"})


async def test_partial_deletion_erases_content_without_deleting_other_documents(tmp_path):
    context = SQLiteStorageContext(tmp_path, uuid4(), uuid4())
    backend = SQLiteBackend("private", storage_context=context, create=True)
    sentinel = "private-partial-deletion-sentinel"
    await backend.add_embedded_documents(
        [
            IngestedDocument(sentinel + "x" * 4096, {"session": "removed"}, [1.0, 2.0], id="deleted"),
            IngestedDocument("retained document", {"session": "retained"}, [1.0, 2.0], id="retained"),
        ]
    )
    await backend.delete_by({"session": "removed"})
    assert await backend.count() == 1
    assert sentinel.encode() not in b"".join(path.read_bytes() for path in context.database_path.parent.iterdir())
    await backend.teardown()


def test_configured_root_symlink_is_supported_but_child_symlinks_are_rejected(tmp_path, monkeypatch):
    target = tmp_path / "actual"
    target.mkdir()
    root = tmp_path / "configured"
    root.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(
        runtime, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace(knowledge_bases_dir=root))
    )
    assert runtime.storage_root() == target.resolve()
    child = target / "sqlite"
    child.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(runtime.StorageUnavailableError, match="symbolic links"):
        runtime.private_directory(runtime.storage_root() / "sqlite" / "new")


@pytest.mark.parametrize("username", ["sqlite", ".hidden"])
async def test_legacy_inventory_does_not_skip_previously_valid_usernames(database, username, monkeypatch):
    async with database.sessions() as db:
        owner = await db.get(type(database.user), database.user.id)
        owner.username = username
        db.add(owner)
        await db.commit()
    source = database.root / username / "knowledge"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"legacy data")
    row = await make_kb(database)
    fingerprint = Mock(wraps=coordinator.tree_fingerprint)
    monkeypatch.setattr(coordinator, "tree_fingerprint", fingerprint)
    await coordinator.reconcile_legacy_inventory()
    fingerprint.assert_any_call(source)
    assert coordinator.inventory_status() == {"complete": True, "issues": 0}
    monkeypatch.setattr(maintenance, "_process_matches", lambda _identity: False)
    monkeypatch.setattr(maintenance, "remaining_legacy_workers", list)
    receipt = database.root.parent / "receipt.json"
    maintenance.create_receipt(
        root=database.root, database=database.path, receipt=receipt, previous_workers=[{"pid": 999999, "created": 1}]
    )
    import json

    assert json.loads(receipt.read_bytes())["sources"] == {
        f"{username}/knowledge": maintenance.tree_fingerprint(source)
    }
    assert (await read_kb(database, row.id)).id == row.id


@pytest.mark.parametrize("failure", ["inventory", "size", "receipt_sync"])
async def test_failed_receipt_creation_cleans_owned_artifacts_and_can_retry(database, monkeypatch, failure):
    """Failure after backup creation must not leave a retry-blocking or incomplete receipt."""
    source = database.root / database.user.username / "legacy"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"retained legacy data")
    original = maintenance.tree_fingerprint(source)
    receipt = database.root.parent / "retryable-receipt.json"
    backup = receipt.with_suffix(".metadata.sqlite3")
    monkeypatch.setattr(maintenance, "_process_matches", lambda _identity: False)
    monkeypatch.setattr(maintenance, "remaining_legacy_workers", list)
    options = {
        "root": database.root,
        "database": database.path,
        "receipt": receipt,
        "previous_workers": [{"pid": 999999, "created": 1}],
    }
    with monkeypatch.context() as failing:
        if failure == "inventory":
            failing.setattr(maintenance, "tree_fingerprint", Mock(side_effect=OSError("inventory failed")))
        elif failure == "size":
            failing.setattr(maintenance, "MAX_RECEIPT_BYTES", 1)
        else:
            sync = maintenance._fsync_directory
            calls = 0

            def fail_receipt_sync(directory):
                nonlocal calls
                calls += 1
                if calls == 2:
                    msg = "receipt sync failed"
                    raise OSError(msg)
                sync(directory)

            failing.setattr(maintenance, "_fsync_directory", fail_receipt_sync)
        with pytest.raises((OSError, maintenance.MaintenanceRequiredError)):
            maintenance.create_receipt(**options)
    assert not receipt.exists()
    assert not backup.exists()
    assert maintenance.tree_fingerprint(source) == original
    maintenance.create_receipt(**options)
    assert receipt.is_file()
    assert backup.is_file()
    assert json.loads(receipt.read_bytes())["sources"] == {f"{database.user.username}/legacy": original}


@pytest.mark.parametrize("existing", ["backup", "receipt"])
async def test_receipt_creation_preserves_preexisting_artifacts(database, monkeypatch, existing):
    """Exclusive-create failures cannot remove another attempt's recovery artifacts."""
    database.root.mkdir(parents=True, exist_ok=True)
    receipt = database.root.parent / "existing-receipt.json"
    artifact = receipt if existing == "receipt" else receipt.with_suffix(".metadata.sqlite3")
    artifact.write_bytes(b"previous attempt must remain")
    monkeypatch.setattr(maintenance, "_process_matches", lambda _identity: False)
    monkeypatch.setattr(maintenance, "remaining_legacy_workers", list)
    with pytest.raises((FileExistsError, maintenance.MaintenanceRequiredError)):
        maintenance.create_receipt(
            root=database.root,
            database=database.path,
            receipt=receipt,
            previous_workers=[{"pid": 999999, "created": 1}],
        )
    assert artifact.read_bytes() == b"previous attempt must remain"


async def test_real_postgres_coordination_allows_more_than_four_callers(monkeypatch):
    import os

    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")
    monkeypatch.setattr(runtime, "get_db_service", lambda: SimpleNamespace(database_url=url, _get_connect_args=dict))
    monkeypatch.setattr(
        runtime,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(knowledge_base_storage_pool_size=8)),
    )
    entered, release = asyncio.Event(), asyncio.Event()
    count = 0

    async def reader():
        nonlocal count
        async with runtime._remote_lock(uuid4(), shared=True):
            count += 1
            if count == 6:
                entered.set()
            await release.wait()

    tasks = [asyncio.create_task(reader()) for _ in range(6)]
    try:
        await asyncio.wait_for(entered.wait(), 5)
    finally:
        release.set()
        await asyncio.gather(*tasks)
        await runtime.close_coordination_pools()


@pytest.mark.usefixtures("database")
async def test_admin_inventory_reads_the_shared_completed_scan(monkeypatch):
    coordinator._publish_inventory_status()
    monkeypatch.setattr(coordinator, "_inventory_complete", False)
    monkeypatch.setattr(coordinator, "_inventory_issue_count", 100)
    assert await coordinator.published_inventory_status() == {"complete": True, "issues": 0}


@pytest.mark.parametrize("backend_type", ["postgres", "opensearch"])
async def test_admin_can_abandon_an_unreachable_ready_remote_without_provider_calls(
    database, monkeypatch, backend_type
):
    row = await make_kb(database, backend=backend_type)
    monkeypatch.setattr(cleanup, "session_scope", database.sessions)
    monkeypatch.setattr(
        runtime, "_raw_backend", lambda *_args, **_kwargs: pytest.fail("Detached storage contacted provider")
    )
    await cleanup.detach_attention_store(row.id, expected_generation=row.storage_generation)
    assert (await read_kb(database, row.id)).storage_state == "detached"
    await runtime.delete_storage_for_record(await read_kb(database, row.id))
    assert (await read_kb(database, row.id)).storage_state == "deleted"


async def test_ingestion_snapshot_cannot_follow_a_reused_knowledge_base_name(database):
    from langflow.api.utils.kb_helpers import backend_for_name

    original = await make_kb(database, backend="sqlite")
    async with database.sessions() as db:
        await db.delete(await db.get(KnowledgeBaseRecord, original.id))
        await db.commit()
    replacement = await make_kb(database, backend="sqlite")
    with pytest.raises(runtime.StorageUnavailableError):
        await backend_for_name(original.user_id, original.name, expected_record=original)
    assert replacement.id != original.id
