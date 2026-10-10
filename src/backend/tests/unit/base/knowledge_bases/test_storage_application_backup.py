"""The application database backup that the automatic storage upgrade keeps only while it runs."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.knowledge_base_storage import application_backup
from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError

pytestmark = pytest.mark.no_blockbuster


def test_should_remove_this_databases_backup_and_journals_but_count_another_databases(tmp_path):
    root = tmp_path / "knowledge"
    database = tmp_path / "app.sqlite3"
    directory = application_backup.backup_directory(root)
    directory.mkdir(parents=True)
    backup = application_backup.backup_path(directory, database)
    incomplete = backup.with_suffix(".incomplete")
    # A copy interrupted by a restart, and the journals SQLite leaves beside either file, hold rows too.
    own = [backup, incomplete, *(path.with_name(path.name + "-wal") for path in (backup, incomplete))]
    own.append(backup.with_name(backup.name + "-shm"))
    for path in own:
        path.write_bytes(b"application rows")
    # Another application database can share the storage root. Its upgrade is not this one's to finish.
    other = application_backup.backup_path(directory, tmp_path / "other.sqlite3")
    other.write_bytes(b"another application's rows")
    assert application_backup.retained_backups(root) == 2

    application_backup.remove_backups(root, database)

    assert [path for path in own if path.exists()] == []
    assert other.read_bytes() == b"another application's rows"
    assert application_backup.retained_backups(root) == 1


def test_should_count_and_create_nothing_when_no_upgrade_kept_a_backup(tmp_path):
    root = tmp_path / "knowledge"
    database = tmp_path / "app.sqlite3"

    assert application_backup.retained_backups(root) == 0
    application_backup.remove_backups(root, database)

    assert not root.exists()


def test_should_refuse_to_remove_through_a_symbolic_link(tmp_path):
    root = tmp_path / "knowledge"
    database = tmp_path / "app.sqlite3"
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = application_backup.backup_path(outside, database)
    victim.write_bytes(b"not part of this storage root")
    (root / ".migration").mkdir(parents=True)
    application_backup.backup_directory(root).symlink_to(outside, target_is_directory=True)

    with pytest.raises(MaintenanceRequiredError):
        application_backup.remove_backups(root, database)

    assert victim.exists()


def test_should_give_each_event_loop_its_own_upgrade_pass_lock():
    async def contend() -> None:
        lock = application_backup.upgrade_pass()
        assert application_backup.upgrade_pass() is lock
        async with lock:
            waiter = asyncio.create_task(lock.acquire())
            await asyncio.sleep(0)
            assert not waiter.done()
        await waiter
        lock.release()

    # A lock shared across loops would raise in the second, once the first had waited on it.
    asyncio.run(contend())
    asyncio.run(contend())
