"""The application database backup that the automatic storage upgrade keeps only while it runs.

Before copying the first base, ``preserve_routing`` takes one consistent copy of a SQLite application
database. That copy holds every application row, and a data-subject erase deletes rows from the live
database only. Nothing reads the backup back: a retried base uses its own routing record and source
snapshot. So the backup is deleted once the upgrade has finished, in the sense that strict readiness
uses: discovery is complete and no base is still on Chroma, migrating or needing attention. A
coordinator pass checks this when it ends, and an erase checks it before it finishes. Until then, the
erase reports the backup as kept.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.service import get_sqlite_database_file_path
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError, _fsync_directory
from langflow.services.knowledge_base_storage.retained import MIGRATION_DIRECTORY
from langflow.services.knowledge_base_storage.runtime import storage_root

if TYPE_CHECKING:
    from pathlib import Path

    from sqlmodel.sql.expression import SelectOfScalar

BACKUP_DIRECTORY = "application-backups"
_BACKUP_PREFIX = "application-before-upgrade-"
# The journal files beside a SQLite database can hold its pages too, for example after an interrupted copy.
_SQLITE_FILES = ("", "-wal", "-shm", "-journal")
# An asyncio.Lock binds to the first loop that waits on it, so each event loop gets its own.
_passes: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()


def upgrade_pass() -> asyncio.Lock:
    """Held by each coordinator pass, the only place a backup is created.

    An erase that finds it held leaves the backup to that pass, rather than deleting it while a
    migration may be about to take it.
    """
    loop = asyncio.get_running_loop()
    lock = _passes.get(loop)
    if lock is None:
        lock = _passes[loop] = asyncio.Lock()
    return lock


def backup_directory(root: Path) -> Path:
    return root / MIGRATION_DIRECTORY / BACKUP_DIRECTORY


def backup_path(directory: Path, database: Path) -> Path:
    """The one backup of ``database`` that every run of the upgrade shares."""
    identity = hashlib.sha256(str(database).encode()).hexdigest()
    return directory / f"{_BACKUP_PREFIX}{identity}.sqlite3"


def _own_files(root: Path, database: Path) -> list[Path]:
    backup = backup_path(backup_directory(root), database)
    # A copy interrupted by a restart holds the same rows as a finished one.
    return [
        path.with_name(path.name + suffix)
        for path in (backup, backup.with_suffix(".incomplete"))
        for suffix in _SQLITE_FILES
    ]


def retained_backups(root: Path) -> int:
    """How many application backups are left under ``root``, for any database.

    Only the current database's backup is ever deleted. A backup of another database that shares the
    storage root, or one named after another spelling of this database's path, is still counted,
    since it may hold rows that an erase did not reach.
    """
    directory = backup_directory(root)
    try:
        if not directory.is_dir():
            return 0
        names = [path.name for path in directory.iterdir()]
    except OSError:
        # A directory that cannot be read may still hold a backup.
        return 1
    return len(
        {name.removeprefix(_BACKUP_PREFIX).split(".", 1)[0] for name in names if name.startswith(_BACKUP_PREFIX)}
    )


def remove_backups(root: Path, database: Path) -> None:
    """Delete the copies of ``database``, never following a symbolic link out of the storage root."""
    directory = backup_directory(root)
    for candidate in (directory.parent, directory):
        if candidate.is_symlink():
            msg = "Invalid application backup directory"
            raise MaintenanceRequiredError(msg)
    if not directory.is_dir():
        return
    for path in _own_files(root, database):
        path.unlink(missing_ok=True)
    _fsync_directory(directory)


def first_unfinished_base() -> SelectOfScalar:
    """A base the upgrade has not settled: still on Chroma and not detached, or migrating or failed."""
    return (
        select(KnowledgeBaseRecord.id)
        .where(
            ((KnowledgeBaseRecord.backend_type == "chroma") & (KnowledgeBaseRecord.storage_state != "detached"))
            | col(KnowledgeBaseRecord.storage_state).in_(("migrating", "needs_attention"))
        )
        .limit(1)
    )


def _backed_up_database() -> Path | None:
    if not get_settings_service().settings.knowledge_bases_dir:
        return None
    return get_sqlite_database_file_path(get_db_service().database_url)


async def discard_if_finished(*, inventory_complete: bool) -> int:
    """Delete this database's backup once the upgrade has finished; return how many backups remain.

    The caller holds ``upgrade_pass()``. A backup that cannot be deleted is logged and counted, and the
    next pass or erase tries again.
    """
    database = _backed_up_database()
    if database is None:
        return 0
    root = storage_root()
    if inventory_complete:
        async with session_scope() as session:
            finished = (await session.exec(first_unfinished_base())).first() is None
        if finished:
            try:
                await asyncio.to_thread(remove_backups, root, database)
            except (OSError, MaintenanceRequiredError) as exc:
                await logger.awarning(
                    "op=kb_storage_upgrade the application backup could not be removed: %s", type(exc).__name__
                )
    return await asyncio.to_thread(retained_backups, root)


async def discard_outside_pass() -> int:
    """For an erase: delete a finished upgrade's backup, and return how many backups it could not reach."""
    database = _backed_up_database()
    if database is None:
        return 0
    lock = upgrade_pass()
    if lock.locked():
        # The running pass deletes the backup itself if it finishes the upgrade.
        return await asyncio.to_thread(retained_backups, storage_root())
    # The coordinator imports this module, so load its shared discovery status only when it is due.
    from langflow.services.knowledge_base_storage.coordinator import published_inventory_status

    async with lock:
        inventory = await published_inventory_status()
        return await discard_if_finished(inventory_complete=inventory["complete"])
