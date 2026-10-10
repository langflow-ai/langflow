"""Verify the managed upgrade's stopped-worker barrier and preserve rollback data.

The deployment manager stops its previous process family before invoking this
module. This verifier never terminates processes. Distributed workers and a
PostgreSQL metadata database require their deployment-specific controller and
are not accepted by this single-host proof format.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import stat
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psutil

MAX_RECEIPT_BYTES = 4 * 1024 * 1024
MAX_SOURCE_FILES = 200_000
_PROCESS_TIME_TOLERANCE = 0.01


class MaintenanceRequiredError(ValueError):
    """The managed old-writer barrier or rollback backup is not established."""


def _fsync_directory(path: Path) -> None:
    """Flush directory metadata after publishing a durable maintenance artifact."""
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def file_sha256(path: Path) -> str:
    """Hash a file's contents for receipt and backup integrity checks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_fingerprint(path: Path) -> str:
    """Hash every regular source file, including WAL, logs and native indexes."""
    if path.is_symlink() or not path.is_dir():
        msg = "Source directory is unavailable or is a symbolic link"
        raise MaintenanceRequiredError(msg)
    digest = hashlib.sha256()
    count = 0
    for directory, directories, files in os.walk(path, followlinks=False):
        for name in sorted(directories):
            if (Path(directory) / name).is_symlink():
                msg = "Source contains a symbolic link"
                raise MaintenanceRequiredError(msg)
        for name in sorted(files):
            candidate = Path(directory) / name
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode):
                msg = "Source contains a symbolic link or special file"
                raise MaintenanceRequiredError(msg)
            if info.st_nlink != 1:
                msg = "Source contains a hard link outside its storage boundary"
                raise MaintenanceRequiredError(msg)
            count += 1
            if count > MAX_SOURCE_FILES:
                msg = "Source file inventory exceeds the upgrade bound"
                raise MaintenanceRequiredError(msg)
            relative = candidate.relative_to(path).as_posix().encode()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(info.st_size.to_bytes(8, "big"))
            digest.update(bytes.fromhex(file_sha256(candidate)))
        directories.sort()
    return digest.hexdigest()


def tree_stat_fingerprint(path: Path) -> str:
    """Detect source changes without rereading retained document/index contents."""
    if path.is_symlink() or not path.is_dir():
        msg = "Source directory is unavailable or is a symbolic link"
        raise MaintenanceRequiredError(msg)
    digest = hashlib.sha256()
    count = 0
    for directory, directories, files in os.walk(path, followlinks=False):
        for name in sorted((*directories, *files)):
            candidate = Path(directory) / name
            info = candidate.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or (
                info.st_nlink != 1 and stat.S_ISREG(info.st_mode)
            ):
                msg = "Source contains a link or special file"
                raise MaintenanceRequiredError(msg)
            count += 1
            if count > MAX_SOURCE_FILES:
                msg = "Source file inventory exceeds the upgrade bound"
                raise MaintenanceRequiredError(msg)
            digest.update(
                json.dumps(
                    [
                        candidate.relative_to(path).as_posix(),
                        info.st_ino,
                        info.st_size,
                        info.st_mtime_ns,
                        info.st_ctime_ns,
                    ],
                    separators=(",", ":"),
                ).encode()
            )
        directories.sort()
    return digest.hexdigest()


def _legacy_process(process: psutil.Process) -> bool:
    """Identify a process that may still be using the legacy local store."""
    try:
        command = process.cmdline()
        if not command:
            return False
        executable = Path(command[0]).name.lower()
        if executable in ("langflow", "langflow.exe"):
            return True
        if executable.startswith("python"):
            index = 1
            while index < len(command):
                argument = command[index]
                if argument in ("-W", "-X", "--check-hash-based-pycs"):
                    index += 2
                    continue
                if argument == "-m":
                    if index + 1 >= len(command):
                        return False
                    module = command[index + 1]
                    return module in ("langflow", "langflow.__main__") or (
                        module in ("uvicorn", "gunicorn")
                        and any(part.startswith("langflow.main:") for part in command[index + 2 :])
                    )
                if argument in ("-c", "--"):
                    return False
                if not argument.startswith("-"):
                    script = Path(argument).name
                    return script == "langflow" or (
                        script in ("uvicorn", "gunicorn")
                        and any(part.startswith("langflow.main:") for part in command[index + 1 :])
                    )
                index += 1
            return False
        return executable in ("uvicorn", "gunicorn") and any(part.startswith("langflow.main:") for part in command[1:])
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied as exc:
        try:
            # Windows protects SYSTEM process tokens from ordinary accounts.
            # Only a confirmed application-account identity may fence us.
            username = process.username()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        if username != psutil.Process().username():
            return False
        try:
            if process.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                return False
            # macOS can deny cmdline() briefly while a same-user process exits.
            for _attempt in range(3):
                time.sleep(0.01)
                if not process.is_running() or process.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                    return False
        except psutil.NoSuchProcess:
            return False
        except psutil.AccessDenied:
            pass
        msg = "Cannot inspect a process belonging to the application account"
        raise MaintenanceRequiredError(msg) from exc


def process_identity(process: psutil.Process) -> dict:
    """Bind Linux processes to kernel start ticks and boot identity, independent of clock steps."""
    identity = {"pid": process.pid, "created": process.create_time()}
    if sys.platform == "linux":
        try:
            fields = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()
            identity.update(
                start_ticks=int(fields[19]), boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            )
        except (FileNotFoundError, ProcessLookupError) as exc:
            raise psutil.NoSuchProcess(process.pid) from exc
    return identity


def identity_matches(process: psutil.Process, identity: dict) -> bool:
    """Use stable kernel identity when present, with compatibility for older receipts."""
    if "start_ticks" in identity or "boot_id" in identity:
        if type(identity.get("start_ticks")) is not int or not isinstance(identity.get("boot_id"), str):
            msg = "Invalid kernel process identity"
            raise MaintenanceRequiredError(msg)
        current = process_identity(process)
        return current.get("start_ticks") == identity["start_ticks"] and current.get("boot_id") == identity["boot_id"]
    return abs(process.create_time() - identity["created"]) < _PROCESS_TIME_TOLERANCE


def _process_matches(identity: dict) -> bool:
    """Compare a live process against the captured maintenance identity."""
    if (
        not isinstance(identity, dict)
        or type(identity.get("pid")) is not int
        or not isinstance(identity.get("created"), (float, int))
    ):
        msg = "Invalid previous-worker identity"
        raise MaintenanceRequiredError(msg)
    try:
        process = psutil.Process(identity["pid"])
        # A retained zombie/dead process cannot write. Some container init
        # implementations defer reaping orphaned workers after their exit.
        return process.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD) and identity_matches(
            process, identity
        )
    except psutil.NoSuchProcess:
        return False


def remaining_legacy_workers(*, excluded_pids: set[int] | None = None) -> list[int]:
    """Report actual unselected Langflow entry points before and after downtime."""
    excluded = {os.getpid(), *(excluded_pids or set())}
    return [
        process.pid for process in psutil.process_iter() if process.pid not in excluded and _legacy_process(process)
    ]


def create_receipt(*, root: Path, database: Path, receipt: Path, previous_workers: list[dict]) -> None:
    """Verify registered workers already exited, back up, inventory and attest.

    The deployment controller supplies identities it recorded before stopping
    the previous supervised process family, including API and background workers.
    Unregistered matching workers fail the barrier. This applies only to a
    managed single-host instance whose supervisor has also been stopped.
    """
    root = root.resolve(strict=True)
    database = database.resolve(strict=True)
    if not previous_workers or any(_process_matches(item) for item in previous_workers):
        msg = "The deployment manager must stop all previous workers first"
        raise MaintenanceRequiredError(msg)
    if remaining := remaining_legacy_workers():
        msg = f"Langflow workers remain (PIDs {remaining}). Use their deployment manager to stop them"
        raise MaintenanceRequiredError(msg)
    receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if receipt.exists() or receipt.is_symlink():
        msg = "Use a new receipt path for each managed upgrade"
        raise MaintenanceRequiredError(msg)
    backup = receipt.with_suffix(".metadata.sqlite3")
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    receipt_created = False
    try:
        os.close(descriptor)
        with (
            closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as source,
            closing(sqlite3.connect(backup)) as target,
        ):
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                msg = "Application metadata backup failed integrity validation"
                raise MaintenanceRequiredError(msg)
        with backup.open("rb") as stream:
            os.fsync(stream.fileno())
        _fsync_directory(backup.parent)
        sources = {}
        for owner in sorted(root.iterdir()):
            if owner.is_symlink():
                msg = "Legacy owner directory is a symbolic link"
                raise MaintenanceRequiredError(msg)
            if not owner.is_dir():
                continue
            for candidate in sorted(owner.iterdir()):
                if candidate.is_dir() and (candidate / "chroma.sqlite3").is_file():
                    sources[candidate.relative_to(root).as_posix()] = tree_fingerprint(candidate)
        payload = {
            "version": 1,
            "scope": "managed-single-host",
            "host": socket.gethostname(),
            "root": str(root),
            "database": str(database),
            "backup": str(backup.resolve()),
            "backup_sha256": file_sha256(backup),
            "stopped_processes": previous_workers,
            "sources": sources,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        if len(encoded) > MAX_RECEIPT_BYTES:
            msg = "Upgrade inventory exceeds the receipt bound"
            raise MaintenanceRequiredError(msg)
        descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        receipt_created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_directory(receipt.parent)

    except BaseException:
        # Only remove artifacts created by this attempt. Existing backups and
        # receipts belong to earlier attempts and must remain untouched.
        if receipt_created:
            receipt.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)
        raise


def validate_receipt(*, root: Path, database: Path, receipt: Path) -> dict:
    """Check controller identity, terminated processes and retained rollback data."""
    if receipt.is_symlink():
        msg = "Invalid upgrade receipt"
        raise MaintenanceRequiredError(msg)
    info = receipt.stat()
    if info.st_size > MAX_RECEIPT_BYTES or not stat.S_ISREG(info.st_mode):
        msg = "Invalid upgrade receipt"
        raise MaintenanceRequiredError(msg)
    if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        msg = "Upgrade receipt must be private and owned by the application account"
        raise MaintenanceRequiredError(msg)
    payload = json.loads(receipt.read_bytes())
    if (
        payload.get("version") != 1
        or payload.get("scope") != "managed-single-host"
        or payload.get("host") != socket.gethostname()
        or payload.get("root") != str(root.resolve())
        or payload.get("database") != str(database.resolve())
    ):
        msg = "Upgrade receipt does not belong to this managed instance"
        raise MaintenanceRequiredError(msg)
    identities = payload.get("stopped_processes")
    if not isinstance(identities, list) or not identities or any(_process_matches(item) for item in identities):
        msg = "Previous application workers have not stopped"
        raise MaintenanceRequiredError(msg)
    backup = Path(payload["backup"])
    if backup.is_symlink() or file_sha256(backup) != payload.get("backup_sha256"):
        msg = "The pre-upgrade metadata backup is unavailable or changed"
        raise MaintenanceRequiredError(msg)
    return payload


def snapshot_source(source: Path, destination: Path, expected_fingerprint: str) -> None:
    """Copy the entire frozen source, retaining the pristine copy on retry."""
    if tree_fingerprint(source) != expected_fingerprint:
        msg = "Source changed after the stopped-worker barrier"
        raise MaintenanceRequiredError(msg)
    if destination.exists():
        if tree_fingerprint(destination) != expected_fingerprint:
            msg = "Retained source snapshot failed verification"
            raise MaintenanceRequiredError(msg)
        return
    required = sum(path.stat().st_size for path in source.rglob("*") if path.is_file())
    if shutil.disk_usage(destination.parent).free < required * 4 + 64 * 1024 * 1024:
        msg = "Insufficient disk space for source snapshot and verified import"
        raise MaintenanceRequiredError(msg)
    temporary = destination.with_name("snapshot.incomplete")
    if temporary.exists():
        if temporary.is_symlink():
            msg = "Invalid incomplete snapshot path"
            raise MaintenanceRequiredError(msg)
        shutil.rmtree(temporary)
    shutil.copytree(source, temporary)
    if tree_fingerprint(source) != expected_fingerprint or tree_fingerprint(temporary) != expected_fingerprint:
        msg = "Source changed during snapshot"
        raise MaintenanceRequiredError(msg)
    for path in temporary.rglob("*"):
        if path.is_file():
            with path.open("r+b") as stream:
                os.fsync(stream.fileno())
    temporary.rename(destination)
    _fsync_directory(destination.parent)


def main() -> None:
    """Create or validate the stopped-worker maintenance receipt from CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--previous-workers", required=True, type=Path, help="Controller's JSON array of pid/create-time identities"
    )
    args = parser.parse_args()
    if args.previous_workers.stat().st_size > MAX_RECEIPT_BYTES:
        msg = "Previous-worker inventory is too large"
        raise MaintenanceRequiredError(msg)
    create_receipt(
        root=args.root,
        database=args.database,
        receipt=args.receipt,
        previous_workers=json.loads(args.previous_workers.read_bytes()),
    )


if __name__ == "__main__":
    main()
