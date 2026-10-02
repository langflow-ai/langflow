"""Safety checks and rollback metadata for first-start local storage upgrades."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import psutil

from langflow.services.knowledge_base_storage.maintenance import (
    MaintenanceRequiredError,
    _fsync_directory,
    remaining_legacy_workers,
)

_ORCHESTRATORS = (
    "KUBERNETES_SERVICE_HOST",
    "ECS_CONTAINER_METADATA_URI",
    "ECS_CONTAINER_METADATA_URI_V4",
    "NOMAD_ALLOC_ID",
)
_LOCAL_FILESYSTEMS = {
    "apfs",
    "hfs",
    "ext2",
    "ext3",
    "ext4",
    "xfs",
    "btrfs",
    "zfs",
    "overlay",
    "virtiofs",
    "tmpfs",
    "ntfs",
    "NTFS",
    "fuseblk",
}


class AutomaticUpgradeUnavailableError(MaintenanceRequiredError):
    """A supported single-host maintenance window has not been established."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def check_local_upgrade(root: Path, settings) -> None:
    """Require one local worker and a local filesystem before touching migration state."""
    if not getattr(settings, "knowledge_base_auto_migrate", True):
        msg = "automatic_upgrade_disabled"
        raise AutomaticUpgradeUnavailableError(msg)
    if getattr(settings, "workers", 1) != 1 or any(os.environ.get(key) for key in _ORCHESTRATORS):
        msg = "single_host_required"
        raise AutomaticUpgradeUnavailableError(msg)
    # The current CLI/supervisor may appear in the process listing. Exclude
    # only this process's ancestors, never another independently running app.
    excluded = {process.pid for process in psutil.Process().parents()}
    if remaining_legacy_workers(excluded_pids=excluded):
        msg = "legacy_workers_running"
        raise AutomaticUpgradeUnavailableError(msg)
    mounts = [
        partition for partition in psutil.disk_partitions(all=True) if root.is_relative_to(Path(partition.mountpoint))
    ]
    if (
        not mounts
        or max(mounts, key=lambda partition: len(Path(partition.mountpoint).parts)).fstype not in _LOCAL_FILESYSTEMS
    ):
        msg = "local_filesystem_required"
        raise AutomaticUpgradeUnavailableError(msg)


def preserve_routing(directory: Path, row, database: Path | None, *, backup_directory: Path) -> None:
    """Keep private pre-upgrade routing, plus a consistent SQLite app DB backup."""
    path = directory / "routing-before-upgrade.json"
    if not path.exists():
        temporary = directory / f"routing-backup-{uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(row.model_dump(mode="json"), stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    elif path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        msg = "Invalid routing backup path"
        raise MaintenanceRequiredError(msg)
    if database is not None:
        identity = hashlib.sha256(str(database).encode()).hexdigest()
        backup = backup_directory / f"application-before-upgrade-{identity}.sqlite3"
        if not backup.exists():
            # Back up the app database once for the whole upgrade. Each KB still
            # keeps its own source snapshot and pre-upgrade routing record.
            required = database.stat().st_size
            wal = database.with_name(f"{database.name}-wal")
            if wal.exists():
                required += wal.stat().st_size
            if shutil.disk_usage(backup_directory).free < required * 2 + 64 * 1024 * 1024:
                msg = "Insufficient disk space for the application backup"
                raise MaintenanceRequiredError(msg)
            temporary = backup.with_suffix(".incomplete")
            if temporary.exists() or temporary.is_symlink():
                info = temporary.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    msg = "Invalid incomplete application backup"
                    raise MaintenanceRequiredError(msg)
                temporary.unlink()
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(descriptor)
            try:
                with (
                    closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as source,
                    closing(sqlite3.connect(temporary)) as destination,
                ):
                    # Release the source read lock between page batches so a
                    # large rollback backup does not hold up normal app writes.
                    source.backup(destination, pages=128)
                    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        msg = "Application backup failed verification"
                        raise MaintenanceRequiredError(msg)
                with temporary.open("rb") as stream:
                    os.fsync(stream.fileno())
                temporary.replace(backup)
                _fsync_directory(backup_directory)
            finally:
                temporary.unlink(missing_ok=True)
        elif backup.is_symlink() or not backup.is_file() or backup.stat().st_nlink != 1:
            msg = "Invalid application backup path"
            raise MaintenanceRequiredError(msg)
        reference = directory / "application-backup.json"
        if not reference.exists():
            temporary = directory / f"application-reference-{uuid4().hex}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump({"backup": str(backup.relative_to(directory.parents[1]))}, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(reference)
            finally:
                temporary.unlink(missing_ok=True)
        elif reference.is_symlink() or not reference.is_file() or reference.stat().st_nlink != 1:
            msg = "Invalid application backup reference"
            raise MaintenanceRequiredError(msg)
    _fsync_directory(directory)
