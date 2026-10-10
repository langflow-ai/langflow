"""Application routing, operation fences and recoverable automatic upgrade."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sqlite3
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import psutil
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
from langflow.services.database.models.user.model import User
from langflow.services.knowledge_base_storage import application_backup, coordinator, maintenance, runtime
from lfx.base.knowledge_bases.backends.base import IngestedDocument
from lfx.base.knowledge_bases.migration import ExportHeader, write_export
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
async def database(tmp_path, monkeypatch):
    """Provide an isolated application database and owner-scoped vector directory."""
    root = tmp_path / "vectors"
    root.mkdir()
    path = tmp_path / "metadata.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    tables = [
        User.__table__,
        Flow.__table__,
        KnowledgeBaseRecord.__table__,
        KnowledgeBaseStorageMigration.__table__,
        MemoryBase.__table__,
        MemoryBaseSession.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=tables))

    @asynccontextmanager
    async def sessions():
        """Open a session against the fixture database without expiring committed rows."""
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    settings = SimpleNamespace(settings=SimpleNamespace(knowledge_bases_dir=str(root)))
    service = SimpleNamespace(database_url=f"sqlite+aiosqlite:///{path}", engine=engine)
    monkeypatch.setattr(runtime, "session_scope", sessions)
    monkeypatch.setattr(coordinator, "session_scope", sessions)
    monkeypatch.setattr(runtime, "get_settings_service", lambda: settings)
    monkeypatch.setattr(runtime, "get_db_service", lambda: service)
    monkeypatch.setattr(coordinator, "get_db_service", lambda: service)
    monkeypatch.setattr(coordinator, "get_settings_service", lambda: settings)
    monkeypatch.setattr(application_backup, "session_scope", sessions)
    monkeypatch.setattr(application_backup, "get_db_service", lambda: service)
    monkeypatch.setattr(application_backup, "get_settings_service", lambda: settings)
    monkeypatch.setattr(coordinator, "check_local_upgrade", lambda *_args: None)
    monkeypatch.setattr(coordinator, "_inventory_complete", True)
    monkeypatch.setattr(coordinator, "_inventory_scanned", False)
    monkeypatch.setattr(coordinator, "_inventory_issue_count", 0)
    monkeypatch.delenv("LANGFLOW_KB_UPGRADE_RECEIPT", raising=False)
    user = User(username="owner", password=uuid4().hex, is_active=True)
    async with sessions() as session:
        session.add(user)
        await session.commit()
    yield SimpleNamespace(root=root, path=path, sessions=sessions, user=user, settings=settings)
    await engine.dispose()


def created_now() -> str:
    """When a 1.11 sidecar records its base was created: after its owner's account, as the create endpoint did."""
    return datetime.now(timezone.utc).isoformat()


async def make_kb(database, *, backend="chroma", config=None):
    """Persist a knowledge base owned by the fixture user with the requested backend."""
    row = KnowledgeBaseRecord(
        user_id=database.user.id,
        name="knowledge",
        backend_type=backend,
        backend_config=config or {},
        model_selection={"provider": "test", "name": "fixed"},
    )
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    return row


async def read_kb(database, kb_id):
    """Reload the persisted storage state after a migration or deletion operation."""
    async with database.sessions() as session:
        return await session.get(KnowledgeBaseRecord, kb_id)


async def test_pending_batch_skips_disappeared_identity_and_continues(database, monkeypatch):
    """Continue queued migrations when an earlier knowledge base has been deleted."""
    first = await make_kb(database, config={"mode": "cloud"})
    second = KnowledgeBaseRecord(
        user_id=database.user.id,
        name="another-knowledge-base",
        backend_type="chroma",
        backend_config={"mode": "cloud"},
    )
    async with database.sessions() as session:
        session.add(second)
        await session.commit()
    await coordinator.fence_legacy_records()
    original_migrate = coordinator.migrate_one
    attempts = []

    async def remove_first_queued_identity(kb_id):
        """Delete the first queued record before attempting its captured migration."""
        attempts.append(kb_id)
        if len(attempts) == 1:
            # The inventory already captured this row. This is also the state
            # left by an owner deletion cascading away that queued KB.
            async with database.sessions() as session:
                await session.delete(await session.get(KnowledgeBaseRecord, kb_id))
                await session.commit()
        await original_migrate(kb_id)

    monkeypatch.setattr(coordinator, "migrate_one", remove_first_queued_identity)
    await coordinator.run_pending()
    assert set(attempts) == {first.id, second.id}
    assert await read_kb(database, attempts[0]) is None
    survivor = await read_kb(database, attempts[1])
    assert survivor.storage_state == "needs_attention"
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, survivor.active_migration_id)
    assert run.error_code == "remote_source_requires_migration"


async def test_pending_batch_keeps_existing_identity_lock_failure_visible(database, monkeypatch):
    """Keep a surviving record fenced when its storage lease cannot be acquired."""
    row = await make_kb(database)
    await coordinator.fence_legacy_records()

    @asynccontextmanager
    async def broken_lock(*_args, **_kwargs):
        """Fail lease entry before yielding access to an invalid storage path."""
        msg = "Invalid storage lock path"
        raise runtime.StorageUnavailableError(msg)
        yield  # pragma: no cover -- async context manager with a failing entry

    monkeypatch.setattr(coordinator, "operation", broken_lock)
    with pytest.raises(runtime.StorageUnavailableError, match="Invalid storage lock path"):
        await coordinator.run_pending()
    assert (await read_kb(database, row.id)).storage_state == "migrating"
    assert not await coordinator.readiness()


@pytest.fixture
def export_helper(monkeypatch):
    """Replace the managed exporter with a deterministic two-document export."""
    calls = []

    async def export(snapshot, output, **kwargs):
        """Validate the frozen source and write vectors with their original metadata."""
        assert (snapshot / "index.bin").read_bytes() == b"native-index"
        calls.append(kwargs)
        header = ExportHeader(
            source_id=kwargs["source_id"],
            source_fingerprint=kwargs["source_fingerprint"],
            source_version="chroma-rust-1.5.9",
            count=2,
            dimensions=2,
            metric="l2",
            model_fingerprint=kwargs["model_fingerprint"],
        )
        documents = [
            IngestedDocument(
                id="a", content="first", metadata={"_id": "different", "session_id": "s"}, embedding=[1.0, 2.0]
            ),
            IngestedDocument(
                id="b", content="second", metadata={"nested": {"keep": [True, None]}}, embedding=[3.0, 4.0]
            ),
        ]
        with output.open("wb") as stream:
            write_export(stream, header=header, documents=documents)
        return header

    monkeypatch.setattr(coordinator.helper, "export_snapshot", export)
    return calls


def frozen_source(database, monkeypatch):
    """Create a fingerprinted source approved by the fixture controller receipt."""
    source = database.root / database.user.username / "knowledge"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"frozen-database")
    (source / "index.bin").write_bytes(b"native-index")
    fingerprint = maintenance.tree_fingerprint(source)
    monkeypatch.setenv("LANGFLOW_KB_UPGRADE_RECEIPT", str(database.root.parent / "receipt.json"))
    monkeypatch.setattr(
        coordinator, "validate_receipt", lambda **_kwargs: {"sources": {"owner/knowledge": fingerprint}}
    )
    return source, fingerprint


async def test_automatic_migration_preserves_identity_vectors_and_retries(database, monkeypatch, export_helper):
    """Preserve identity and vectors, make retries idempotent and fence stale routing."""
    row = await make_kb(database)
    source, fingerprint = frozen_source(database, monkeypatch)
    await coordinator.fence_legacy_records()
    assert not await coordinator.readiness()
    await coordinator.run_pending()
    current = await read_kb(database, row.id)
    assert (current.id, current.user_id, current.name) == (row.id, row.user_id, row.name)
    assert (current.backend_type, current.storage_generation, current.storage_state, current.chunks) == (
        "sqlite",
        2,
        "ready",
        2,
    )
    assert maintenance.tree_fingerprint(source) == fingerprint
    assert await coordinator.readiness()
    backend = await runtime.backend_for_record(current)
    documents = [doc async for batch in backend.iter_documents(include_embeddings=True) for doc in batch]
    assert [(doc.id, doc.embedding) for doc in documents] == [("a", [1.0, 2.0]), ("b", [3.0, 4.0])]
    assert documents[0].metadata["_id"] == "different"
    await coordinator.migrate_one(row.id)
    assert len(export_helper) == 1
    with pytest.raises(runtime.StorageUnavailableError):
        await runtime.backend_for_record(row)


async def test_restart_without_receipt_ignores_retained_migrated_source(database, monkeypatch, export_helper):
    """Avoid adopting retained sources after successful migration or record deletion."""
    row = await make_kb(database)
    source, _ = frozen_source(database, monkeypatch)
    await coordinator.migrate_one(row.id)
    assert source.exists()
    monkeypatch.delenv("LANGFLOW_KB_UPGRADE_RECEIPT")
    await coordinator.run_pending()
    assert await coordinator.readiness()
    assert len(export_helper) == 1
    # Deleting the KB row must not make its retained source adoptable again.
    current = await read_kb(database, row.id)
    await runtime.delete_storage_for_record(current)
    async with database.sessions() as session:
        await session.delete(await session.get(KnowledgeBaseRecord, row.id))
        await session.commit()
    await coordinator.run_pending()
    assert await coordinator.readiness()
    assert await read_kb(database, row.id) is None


async def test_retry_after_complete_export_reuses_generation(database, monkeypatch, export_helper):
    """Reuse the durable migration identity after a target import failure."""
    row = await make_kb(database)
    frozen_source(database, monkeypatch)
    original = coordinator.import_qualified_export

    async def crash(*_args, **_kwargs):
        """Interrupt import after the exporter has written a complete artifact."""
        raise OSError

    monkeypatch.setattr(coordinator, "import_qualified_export", crash)
    await coordinator.migrate_one(row.id)
    before = await read_kb(database, row.id)
    assert before.storage_state == "needs_attention"
    monkeypatch.setattr(coordinator, "import_qualified_export", original)
    await coordinator.migrate_one(row.id)
    after = await read_kb(database, row.id)
    assert after.storage_state == "ready"
    assert after.active_migration_id == before.active_migration_id
    assert len(export_helper) == 2


async def test_corrupt_retired_binding_keeps_inventory_unready(database, monkeypatch):
    """Expose corrupt retirement evidence instead of silently adopting its source."""
    frozen_source(database, monkeypatch)
    monkeypatch.delenv("LANGFLOW_KB_UPGRADE_RECEIPT")
    binding = coordinator._binding_path("owner/knowledge")
    binding.parent.mkdir(parents=True)
    binding.write_text("corrupt")
    await coordinator.run_pending()
    assert not await coordinator.readiness()
    assert not coordinator.inventory_status()["complete"]


async def test_automatic_adoption_requires_controller_inventory_and_known_owner(database, monkeypatch, export_helper):
    """Adopt inventoried disk data under its original identity and known owner."""
    source, _ = frozen_source(database, monkeypatch)
    identity = uuid4()
    (source / "embedding_metadata.json").write_text(
        json.dumps(
            {
                "id": str(identity),
                "name": "knowledge",
                "embedding_provider": "test",
                "embedding_model": "fixed",
                "created_at": created_now(),
            }
        )
    )
    fingerprint = maintenance.tree_fingerprint(source)
    monkeypatch.setattr(
        coordinator, "validate_receipt", lambda **_kwargs: {"sources": {"owner/knowledge": fingerprint}}
    )
    await coordinator.run_pending()
    row = await read_kb(database, identity)
    assert row is not None
    assert (row.user_id, row.backend_type, row.storage_state) == (database.user.id, "sqlite", "ready")
    assert len(export_helper) == 1


async def test_cancelled_snapshot_drains_worker_before_releasing_operation(database, monkeypatch, export_helper):
    """Hold the storage lease until a cancelled snapshot worker stops writing."""
    row = await make_kb(database)
    frozen_source(database, monkeypatch)
    started = threading.Event()
    release = threading.Event()
    original = coordinator.snapshot_source

    def blocked(*args):
        """Pause snapshot work until the test releases the cancellation barrier."""
        started.set()
        release.wait(timeout=10)
        return original(*args)

    monkeypatch.setattr(coordinator, "snapshot_source", blocked)
    task = asyncio.create_task(coordinator.migrate_one(row.id))
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await read_kb(database, row.id)).storage_state == "needs_attention"
    assert not export_helper


async def test_deletion_retry_after_tombstone_and_missing_file(database):
    """Finish deletion after a native tombstone or an absent target directory."""
    row = await make_kb(database, backend="sqlite")
    backend = await runtime.backend_for_record(row, create=True)
    await backend.ensure_ready()
    await backend.delete_collection()
    # Simulate loss of the final metadata update after the native tombstone.
    async with database.sessions() as session:
        current = await session.get(KnowledgeBaseRecord, row.id)
        current.storage_state = "deleting"
        await session.commit()
    await runtime.delete_storage_for_record(row)
    assert (await read_kb(database, row.id)).storage_state == "deleted"
    async with database.sessions() as session:
        await session.delete(await session.get(KnowledgeBaseRecord, row.id))
        await session.commit()
    await runtime.delete_orphaned_storage(row)

    absent = await make_kb(database, backend="sqlite")
    await runtime.delete_storage_for_record(absent)
    assert (await read_kb(database, absent.id)).storage_state == "deleted"


async def test_missing_source_persists_fence_without_calling_helper(database, export_helper):
    """Keep missing legacy data fenced and expose a durable recovery requirement."""
    row = await make_kb(database)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await read_kb(database, row.id)
    assert (current.backend_type, current.storage_state) == ("chroma", "needs_attention")
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
    assert run.error_code == "legacy_source_missing"
    assert run.source_identity is None
    assert not export_helper
    with pytest.raises(runtime.StorageUnavailableError):
        await runtime.backend_for_record(current)


async def test_crash_after_routing_cas_recovers_target_without_reexport(database, monkeypatch, export_helper):
    """Recover an activated target after completion bookkeeping fails."""
    row = await make_kb(database)
    frozen_source(database, monkeypatch)
    original = coordinator._complete

    async def crash(*_args):
        """Interrupt completion after the new storage route has been persisted."""
        msg = "simulated process failure"
        raise OSError(msg)

    monkeypatch.setattr(coordinator, "_complete", crash)
    await coordinator.migrate_one(row.id)
    current = await read_kb(database, row.id)
    assert (current.backend_type, current.storage_state) == ("sqlite", "needs_attention")
    monkeypatch.setattr(coordinator, "_complete", original)
    await coordinator.migrate_one(row.id)
    current = await read_kb(database, row.id)
    assert (current.backend_type, current.storage_state) == ("sqlite", "ready")
    assert len(export_helper) == 1


async def test_failed_export_does_not_activate_or_delete_source(database, monkeypatch):
    """Retain original routing and source bytes when export validation fails."""
    row = await make_kb(database)
    source, fingerprint = frozen_source(database, monkeypatch)

    async def failed(*_args, **_kwargs):
        """Reject the native source before a target can be activated."""
        msg = "corrupt native store"
        raise ValueError(msg)

    monkeypatch.setattr(coordinator.helper, "export_snapshot", failed)
    await coordinator.migrate_one(row.id)
    current = await read_kb(database, row.id)
    assert (current.backend_type, current.storage_generation, current.storage_state) == ("chroma", 1, "needs_attention")
    assert maintenance.tree_fingerprint(source) == fingerprint


async def test_remote_chroma_blocked_without_local_root(database):
    """Report remote Chroma recovery without requiring a local vector directory."""
    row = await make_kb(database, config={"mode": "cloud"})
    database.settings.settings.knowledge_bases_dir = None
    await coordinator.migrate_one(row.id)
    current = await read_kb(database, row.id)
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
    assert run.error_code == "remote_source_requires_migration"


async def test_lock_reentrant_but_child_task_waits_and_stale_backend_is_fenced(database):
    """Allow task-local reentry while fencing child tasks and deleted backends."""
    row = await make_kb(database, backend="sqlite")
    backend = await runtime.backend_for_record(row, create=True)
    await backend.ensure_ready()
    started = asyncio.Event()

    async def child():
        """Record when a separate task obtains the parent-held storage lease."""
        async with runtime.operation(row):
            started.set()

    async with runtime.operation(row):
        assert await backend.count() == 0
        task = asyncio.create_task(child())
        await asyncio.sleep(0.1)
        assert not started.is_set()
    await task
    await runtime.delete_storage_for_record(row)
    with pytest.raises(runtime.StorageUnavailableError):
        await backend.count()
    assert (await read_kb(database, row.id)).storage_state == "deleted"


async def test_remote_guard_does_not_require_local_vector_root(database):
    """Acquire remote storage leases independently of local directory configuration."""
    row = await make_kb(database, backend="postgres")
    database.settings.settings.knowledge_bases_dir = None
    async with runtime.operation(row), runtime.operation(row):
        pass


def test_snapshot_rejects_changes_and_symlinks(tmp_path):
    """Require stable source bytes and refuse symbolic links during snapshotting."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "index").write_bytes(b"before")
    digest = maintenance.tree_fingerprint(source)
    destination = tmp_path / "snapshot"
    maintenance.snapshot_source(source, destination, digest)
    assert maintenance.tree_fingerprint(destination) == digest
    (source / "index").write_bytes(b"after")
    with pytest.raises(maintenance.MaintenanceRequiredError, match="changed"):
        maintenance.snapshot_source(source, destination, digest)
    (source / "link").symlink_to(tmp_path)
    with pytest.raises(maintenance.MaintenanceRequiredError, match="symbolic"):
        maintenance.tree_fingerprint(source)


def test_receipt_rejects_live_workers_and_backup_corruption(tmp_path, monkeypatch):
    """Require stopped legacy workers and an intact managed upgrade backup."""
    root = tmp_path / "vectors"
    root.mkdir()
    database = tmp_path / "metadata.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE identity (id TEXT)")
    receipt = tmp_path / "upgrade.json"
    process = psutil.Process()
    with pytest.raises(maintenance.MaintenanceRequiredError, match="stop"):
        maintenance.create_receipt(
            root=root,
            database=database,
            receipt=receipt,
            previous_workers=[{"pid": os.getpid(), "created": process.create_time()}],
        )
    monkeypatch.setattr(maintenance.psutil, "process_iter", list)
    maintenance.create_receipt(
        root=root, database=database, receipt=receipt, previous_workers=[{"pid": 999999999, "created": 1.0}]
    )
    payload = maintenance.validate_receipt(root=root, database=database, receipt=receipt)
    assert payload["scope"] == "managed-single-host"
    from pathlib import Path

    Path(payload["backup"]).write_bytes(b"corrupt")
    with pytest.raises(maintenance.MaintenanceRequiredError, match="backup"):
        maintenance.validate_receipt(root=root, database=database, receipt=receipt)


def test_application_migration_fences_legacy_rows_and_preserves_remote_routing(monkeypatch):
    """Fence legacy rows idempotently while preserving remote routes and aware timestamps."""
    migration = importlib.import_module("langflow.alembic.versions.c91d2e3f4a50_knowledge_base_storage_upgrade")
    create_table = migration.op.create_table
    ledger_columns = {}

    def capture_create_table(name, *columns, **kwargs):
        """Capture emitted ledger columns for PostgreSQL timestamp type assertions."""
        if name == "knowledge_base_storage_migration":
            ledger_columns.update({column.name: column for column in columns})
        return create_table(name, *columns, **kwargs)

    monkeypatch.setattr(migration.op, "create_table", capture_create_table)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE knowledge_base (id CHAR(32) PRIMARY KEY, backend_type VARCHAR NOT NULL)")
        )
        connection.execute(sa.text("INSERT INTO knowledge_base VALUES ('local', 'chroma'), ('remote', 'postgres')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        rows = connection.execute(
            sa.text("SELECT id, storage_state, storage_generation FROM knowledge_base ORDER BY id")
        )
        assert list(rows) == [("local", "migrating", 1), ("remote", "ready", 1)]
        assert "knowledge_base_storage_migration" in sa.inspect(connection).get_table_names()
        # SQLite reflection discards timezone information. Check the emitted
        # PostgreSQL types as well: a naive migrated column silently shifts
        # aware ORM values when the PostgreSQL session is not configured to UTC.
        from sqlalchemy.dialects import postgresql

        for name in ("created_at", "updated_at"):
            expected = KnowledgeBaseStorageMigration.__table__.c[name].type.compile(dialect=postgresql.dialect())
            assert ledger_columns[name].type.compile(dialect=postgresql.dialect()) == expected
            assert expected == "TIMESTAMP WITH TIME ZONE"
    engine.dispose()


async def test_deleted_migrated_source_cannot_be_reimported_by_disk_backfill(database, monkeypatch, export_helper):
    """Honor retired source bindings when per-user or global backfill runs later."""
    from langflow.api.utils import knowledge_base_service

    monkeypatch.setattr(knowledge_base_service, "session_scope", database.sessions)
    row = await make_kb(database)
    source, _ = frozen_source(database, monkeypatch)
    (source / "embedding_metadata.json").write_text(
        json.dumps(
            {
                "id": str(row.id),
                "name": row.name,
                "embedding_provider": "test",
                "embedding_model": "fixed",
            }
        )
    )
    fingerprint = maintenance.tree_fingerprint(source)
    monkeypatch.setattr(
        coordinator, "validate_receipt", lambda **_kwargs: {"sources": {"owner/knowledge": fingerprint}}
    )
    await coordinator.migrate_one(row.id)
    assert (await read_kb(database, row.id)).backend_type == "sqlite"
    await knowledge_base_service.delete_record(row.id)
    assert await read_kb(database, row.id) is None
    assert (source / "embedding_metadata.json").is_file()
    for dry_run in (True, False):
        assert (
            await knowledge_base_service.backfill_from_disk(
                user_id=database.user.id,
                kb_user_root=source.parent,
                dry_run=dry_run,
            )
            == 0
        )
        assert (
            await knowledge_base_service.backfill_all_users_from_disk(
                kb_root=database.root,
                dry_run=dry_run,
            )
            == 0
        )
    assert await read_kb(database, row.id) is None
    assert len(export_helper) == 1


def native_source(database, name="fixture-l2", version="1.5.9"):
    """Install a synthetic store produced by the real native Chroma SDK."""
    import tarfile
    from pathlib import Path

    archive = (
        Path(__file__).resolve().parents[6]
        / f"src/lfx/tests/unit/base/knowledge_bases/fixtures/chroma-{version}-local.tar.gz"
    )
    source = database.root / database.user.username / name
    source.mkdir(parents=True)
    with tarfile.open(archive) as fixture:
        for member in fixture:
            if not member.name.startswith("source/"):
                continue
            relative = Path(member.name).relative_to("source")
            assert member.isfile()
            assert ".." not in relative.parts
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with fixture.extractfile(member) as stream:
                destination.write_bytes(stream.read())
    return source


@pytest.mark.parametrize("version", ["1.5.9", "0.5.23"])
async def test_first_start_native_migration_without_receipt_docker_or_embeddings(database, monkeypatch, version):
    """Migrate real legacy vectors on startup without Docker or embedding calls."""
    source = native_source(database, version=version)
    original = maintenance.tree_fingerprint(source)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()

    async def unavailable_helper(*_args, **_kwargs):
        """Fail the test if automatic migration invokes the managed Docker helper."""
        pytest.fail("Automatic migration must not call the Docker helper")

    monkeypatch.setattr(coordinator.helper, "export_snapshot", unavailable_helper)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await read_kb(database, row.id)
    assert current.storage_state == "ready"
    assert current.backend_type == "sqlite"
    assert current.id == row.id
    assert current.chunks == 239
    backend = await runtime.backend_for_record(current)
    documents = {doc.id: doc async for batch in backend.iter_documents(include_embeddings=True) for doc in batch}
    assert documents["doc-2"].content == "Updated document"
    assert documents["doc-2"].embedding == [0.5, 1.0, 2.0, 3.0]
    assert documents["pending-doc"].embedding == [1.0, 2.0, 3.0, 4.0]
    assert "doc-5" not in documents
    assert "doc-9" not in documents
    assert maintenance.tree_fingerprint(source) == original
    backups = database.root / ".migration" / str(row.id) / str(current.active_migration_id)
    assert (backups / "routing-before-upgrade.json").is_file()
    reference = json.loads((backups / "application-backup.json").read_text())
    # The pass that finished the upgrade no longer needs the application backup, so it deleted it.
    assert reference["backup"].startswith("application-backups/application-before-upgrade-")
    assert not (database.root / ".migration" / reference["backup"]).exists()
    await coordinator.run_pending()
    assert (await read_kb(database, row.id)).storage_generation == 2
    await backend.teardown()


async def test_background_copy_keeps_other_bases_usable_and_resumes_on_restart(database, monkeypatch):
    """Keep other stores usable while interrupted background migration resumes durably."""
    source = native_source(database)
    fingerprint = maintenance.tree_fingerprint(source)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    available = await make_kb(database, backend="sqlite")
    backend = await runtime.backend_for_record(available, create=True)
    await backend.ensure_ready()
    entered, release = threading.Event(), threading.Event()
    export = coordinator.export_local_snapshot

    def paused_export(*args, **kwargs):
        """Pause native export so availability and interruption can be observed."""
        entered.set()
        assert release.wait(timeout=10)
        return export(*args, **kwargs)

    monkeypatch.setattr(coordinator, "export_local_snapshot", paused_export)
    await coordinator.fence_legacy_records()
    task = coordinator.schedule_upgrade()
    assert await asyncio.to_thread(entered.wait, 5)
    assert await coordinator.readiness(require_storage_ready=False)
    assert await backend.count() == 0
    with pytest.raises(runtime.StorageUnavailableError, match="upgrading automatically"):
        await asyncio.wait_for(runtime.backend_for_record(await read_kb(database, row.id)), timeout=1)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    interrupted = await read_kb(database, row.id)
    assert interrupted.storage_state == "needs_attention"
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, interrupted.active_migration_id)
    assert run.error_code == "interrupted"
    monkeypatch.setattr(coordinator, "export_local_snapshot", export)
    # A new startup schedules the same durable migration automatically.
    await coordinator.schedule_upgrade()
    resumed = await read_kb(database, row.id)
    assert resumed.storage_state == "ready"
    assert resumed.active_migration_id == interrupted.active_migration_id
    assert resumed.storage_generation == 2
    assert resumed.chunks == 239
    assert maintenance.tree_fingerprint(source) == fingerprint
    await backend.teardown()


async def test_multi_worker_upgrade_retains_source_and_reports_recovery(database, monkeypatch):
    """Require managed recovery for multiple workers without altering legacy data."""
    from langflow.services.knowledge_base_storage.automatic import check_local_upgrade

    source = native_source(database)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    database.settings.settings.workers = 2
    monkeypatch.setattr(coordinator, "check_local_upgrade", check_local_upgrade)
    await coordinator.migrate_one(row.id)
    current = await read_kb(database, row.id)
    assert current.backend_type == "chroma"
    assert current.storage_state == "needs_attention"
    assert source.exists()
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
    assert run.error_code == "single_host_required"


@pytest.mark.parametrize(
    ("embedding_metadata", "selection"),
    [
        ({"embedding_provider": "test", "embedding_model": "fixed"}, {"provider": "test", "name": "fixed"}),
        ({"embedding_model": "text-embedding-3-small"}, {"provider": "OpenAI", "name": "text-embedding-3-small"}),
    ],
)
async def test_automatic_upgrade_adopts_disk_only_base_with_original_identity(database, embedding_metadata, selection):
    """Recover disk-only bases with their original identity and embedding selection."""
    source = native_source(database)
    identity = uuid4()
    (source / "embedding_metadata.json").write_text(
        json.dumps({"id": str(identity), "name": "fixture-l2", "created_at": created_now(), **embedding_metadata})
    )
    original = maintenance.tree_fingerprint(source)
    await coordinator.run_pending()
    current = await read_kb(database, identity)
    assert current is not None
    assert current.storage_state == "ready"
    assert current.user_id == database.user.id
    assert current.name == "fixture-l2"
    assert current.model_selection == selection
    assert current.chunks == 239
    assert maintenance.tree_fingerprint(source) == original


async def test_fresh_install_without_storage_directory_has_no_upgrade_warning(database):
    """Treat an absent legacy storage directory as a healthy fresh installation."""
    database.root.rmdir()
    await coordinator.run_pending()
    assert await coordinator.published_inventory_status() == {"complete": True, "issues": 0}
    assert await coordinator.readiness()


async def test_disk_only_cloud_base_preserves_remote_routing_and_original_source(database, monkeypatch):
    """Preserve remote configuration despite a residual local directory."""
    source = native_source(database)
    identity = uuid4()
    config = {"mode": "cloud", "collection": "remote-original", "url_variable": "CHROMA_URL"}
    (source / "embedding_metadata.json").write_text(
        json.dumps(
            {
                "id": str(identity),
                "name": "fixture-l2",
                "backend_type": "chroma",
                "backend_config": config,
                "created_at": created_now(),
            }
        )
    )
    original = maintenance.tree_fingerprint(source)

    def unexpected_local_copy(*_args, **_kwargs):
        """Fail if a cloud base is mistaken for a migratable local source."""
        pytest.fail("Cloud routing must not be replaced by a residual local directory")

    monkeypatch.setattr(coordinator, "export_local_snapshot", unexpected_local_copy)
    await coordinator.run_pending()
    current = await read_kb(database, identity)
    assert current.backend_type == "chroma"
    assert current.backend_config == config
    assert current.storage_state == "needs_attention"
    assert maintenance.tree_fingerprint(source) == original
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
    assert run.error_code == "remote_source_requires_migration"
