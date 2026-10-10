"""Safety checks and rollback metadata for first-start local storage upgrades."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import psutil

from langflow.services.knowledge_base_storage.application_backup import backup_path
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
    "fakeowner",  # Docker Desktop's local VirtioFS passthrough
    "tmpfs",
    "ntfs",
    "NTFS",
    "fuseblk",
}


class AutomaticUpgradeUnavailableError(MaintenanceRequiredError):
    """A supported single-host maintenance window has not been established."""

    def __init__(self, code: str):
        """Retain the safe recovery code used to explain an unsupported automatic upgrade."""
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
    # Our supervisor and same-interpreter listener children are current-release
    # processes. Other children and independently running apps remain fenced.
    from langflow.services.triggers.listeners.subprocess_host import listener_command

    current = psutil.Process()
    excluded = {process.pid for process in current.parents()}
    for child in current.children(recursive=True):
        try:
            if child.cmdline() == list(listener_command()):
                excluded.add(child.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
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
        backup = backup_path(backup_directory, database)
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
                    # One snapshot step cannot restart indefinitely under normal
                    # traffic. WAL writers continue while this background copy runs.
                    source.backup(destination, pages=-1)
                    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        msg = "Application backup failed verification"
                        raise MaintenanceRequiredError(msg)
                with temporary.open("r+b") as stream:
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
