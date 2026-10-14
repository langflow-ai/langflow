"""First-start portability and restart regressions from the latest review."""

import json
import logging
import os
from types import SimpleNamespace

import psutil
import pytest
import structlog
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.knowledge_base_storage import automatic, coordinator, maintenance
from lfx.base.knowledge_bases.migration.protocol import AutomaticMigrationLimitError

from . import test_storage_upgrade as storage_tests

pytestmark = pytest.mark.no_blockbuster
database = storage_tests.database


@pytest.mark.parametrize("denied_method", ["username", "status"])
def test_uninspectable_system_process_does_not_block_local_upgrade(denied_method):
    """Windows SYSTEM processes are not confirmed application-account writers."""

    def denied():
        raise psutil.AccessDenied(600, "csrss.exe")

    process = SimpleNamespace(cmdline=denied, username=lambda: "SYSTEM", status=lambda: psutil.STATUS_RUNNING)
    setattr(process, denied_method, denied)
    assert not maintenance._legacy_process(process)


def _started_by_this_run(pid: int) -> bool:
    """Whether this test run started the process: xdist gives its workers the id of the run, and a child inherits it."""
    run = os.environ.get("PYTEST_XDIST_TESTRUNUID")
    try:
        return run is not None and psutil.Process(pid).environ().get("PYTEST_XDIST_TESTRUNUID") == run
    except psutil.NoSuchProcess:
        return True
    except psutil.AccessDenied:
        return False


async def test_native_first_start_with_real_platform_checks(database, monkeypatch):
    """Exercise the actual process, mount and durability checks, including on Windows CI."""
    source = storage_tests.native_source(database)
    original = maintenance.tree_fingerprint(source)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    monkeypatch.setattr(coordinator, "check_local_upgrade", automatic.check_local_upgrade)
    # Other tests of this run start `python -m langflow` commands, and the scan takes each one for a worker.
    scan = automatic.remaining_legacy_workers
    monkeypatch.setattr(
        automatic,
        "remaining_legacy_workers",
        lambda *, excluded_pids: [pid for pid in scan(excluded_pids=excluded_pids) if not _started_by_this_run(pid)],
    )
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await storage_tests.read_kb(database, row.id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)
    assert maintenance.tree_fingerprint(source) == original


@pytest.mark.parametrize("sidecar", [False, True])
async def test_never_ingested_legacy_record_becomes_empty_sqlite(database, sidecar):
    """Known empty legacy rows should not demand manual recovery."""
    row = await storage_tests.make_kb(database)
    source = database.root / database.user.username / row.name
    source.mkdir(parents=True)
    if sidecar:
        (source / "embedding_metadata.json").write_text(json.dumps({"name": row.name}))
    before = maintenance.tree_fingerprint(source)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await storage_tests.read_kb(database, row.id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 0)
    assert maintenance.tree_fingerprint(source) == before


async def test_post_routing_crash_recovers_without_phantom_inventory_issue(database, monkeypatch):
    """A verified ledger binds the source during interrupted activation."""
    source = storage_tests.native_source(database)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    complete = coordinator._complete

    async def stopped(*_args):
        msg = "simulated crash after routing CAS"
        raise RuntimeError(msg)

    monkeypatch.setattr(coordinator, "_complete", stopped)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await storage_tests.read_kb(database, row.id)
    assert (current.backend_type, current.storage_state) == ("sqlite", "needs_attention")
    monkeypatch.setattr(coordinator, "_complete", complete)
    monkeypatch.setattr(coordinator, "_inventory_scanned", False)
    await coordinator.run_pending()
    assert (await storage_tests.read_kb(database, row.id)).storage_state == "ready"
    assert (await coordinator.published_inventory_status())["issues"] == 0
    assert await coordinator.readiness()
    assert source.is_dir()


@pytest.mark.parametrize("exception_class", [FileNotFoundError, AutomaticMigrationLimitError])
async def test_failure_diagnostic_retains_phase_and_class_without_sensitive_payload(
    database, monkeypatch, exception_class
):
    """Operator diagnostics explain where to investigate without storing exception text."""
    warning_logger = structlog.make_filtering_bound_logger(logging.WARNING)(structlog.ReturnLogger(), [], {})
    monkeypatch.setattr(coordinator, "logger", warning_logger)
    storage_tests.native_source(database)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()

    def unavailable(*_args, **_kwargs):
        msg = "/private/path?password=secret"
        raise exception_class(msg)

    monkeypatch.setattr(coordinator, "export_local_snapshot", unavailable)
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await storage_tests.read_kb(database, row.id)
    async with database.sessions() as session:
        run = await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
    assert run.validation["diagnostic"] == {"phase": "exporting", "exception_type": exception_class.__name__}
    assert run.error_code == (
        "automatic_reader_limit" if exception_class is AutomaticMigrationLimitError else "migration_failed"
    )
    assert "secret" not in json.dumps(run.validation)


@pytest.mark.parametrize("controlled", [True, False])
def test_preflight_excludes_only_current_listener_children(tmp_path, monkeypatch, controlled):
    """A current listener is safe, but unrelated child Langflow servers remain writers."""
    from langflow.services.triggers.listeners.subprocess_host import listener_command

    command = list(listener_command()) if controlled else ["langflow", "run"]
    child = SimpleNamespace(pid=123, cmdline=lambda: command)
    parent = SimpleNamespace(parents=list, children=lambda **_kwargs: [child])
    monkeypatch.setattr(automatic.psutil, "Process", lambda: parent)
    monkeypatch.setattr(
        automatic, "remaining_legacy_workers", lambda *, excluded_pids: [] if 123 in excluded_pids else [child]
    )
    monkeypatch.setattr(
        automatic.psutil,
        "disk_partitions",
        lambda **_kwargs: [SimpleNamespace(mountpoint=str(tmp_path), fstype="fakeowner")],
    )
    for key in automatic._ORCHESTRATORS:
        monkeypatch.delenv(key, raising=False)
    if controlled:
        automatic.check_local_upgrade(tmp_path, SimpleNamespace(workers=1))
    else:
        with pytest.raises(automatic.AutomaticUpgradeUnavailableError) as failure:
            automatic.check_local_upgrade(tmp_path, SimpleNamespace(workers=1))
        assert failure.value.code == "legacy_workers_running"


@pytest.mark.skipif(os.name == "nt", reason="Windows CI checks actual fsync instead")
async def test_native_migration_flushes_files_using_writable_handles(database, monkeypatch):
    """Model Windows FlushFileBuffers permissions on every migration fsync."""
    import fcntl
    import stat

    source = storage_tests.native_source(database)
    original = maintenance.tree_fingerprint(source)
    fsync = os.fsync

    def require_writable(descriptor):
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            assert fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY
        fsync(descriptor)

    monkeypatch.setattr(os, "fsync", require_writable)
    row = KnowledgeBaseRecord(user_id=database.user.id, name="fixture-l2", backend_type="chroma")
    async with database.sessions() as session:
        session.add(row)
        await session.commit()
    await coordinator.fence_legacy_records()
    await coordinator.run_pending()
    current = await storage_tests.read_kb(database, row.id)
    assert (current.backend_type, current.storage_state, current.chunks) == ("sqlite", "ready", 239)
    assert maintenance.tree_fingerprint(source) == original
