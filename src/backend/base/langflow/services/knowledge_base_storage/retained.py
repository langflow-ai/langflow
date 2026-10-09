"""Pre-upgrade copies of a local Chroma store that the automatic SQLite upgrade keeps for rollback.

An upgrade run leaves the original ``<owner>/<name>`` directory and a pristine snapshot under
``.migration/<kb_id>/<run_id>/source``. A run that failed after exporting also leaves its
``export.jsonl``. Nothing reads these once the SQLite generation is published, and deleting the base
keeps them, but they still hold every chunk. Chroma's files cannot be edited safely in place, and an
edit would also break the source binding's fingerprint, so an erase removes a copy whole.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing, suppress
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from uuid import uuid4

from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError

if TYPE_CHECKING:
    from uuid import UUID

MIGRATION_DIRECTORY = ".migration"
END_USER_KEY = "end_user_id"
# Removal renames a copy here first. The inventory scan looks only for ``<owner>/<name>/chroma.sqlite3``,
# so it never sees a half-deleted source, and an interrupted removal is finished by the next one.
_ERASED_DIRECTORY = "erased"
_DATABASE_FILES = ("chroma.sqlite3", "chroma.sqlite3-wal", "chroma.sqlite3-journal")
_READ_CHUNK = 1024 * 1024
_SOURCE_PATH_PARTS = 2  # <owner>/<name>


def retained_source(root: Path, source_identity: str) -> Path:
    """The original ``<owner>/<name>`` directory an upgrade run read and kept."""
    parts = PurePosixPath(source_identity).parts
    if len(parts) != _SOURCE_PATH_PARTS or any(part in ("", ".", "..") or "\\" in part for part in parts):
        msg = "Invalid retained source identity"
        raise MaintenanceRequiredError(msg)
    return root.joinpath(*parts)


def retained_copies(root: Path, *, kb_id: UUID, run_id: UUID, source_identity: str) -> tuple[Path, Path]:
    """The original directory and the snapshot that one upgrade run retained."""
    return retained_source(root, source_identity), run_directory(root, kb_id=kb_id, run_id=run_id) / "source"


def run_directory(root: Path, *, kb_id: UUID, run_id: UUID) -> Path:
    return root / MIGRATION_DIRECTORY / str(kb_id) / str(run_id)


def _patterns(value: str) -> set[bytes]:
    """Byte forms of an end-user stamp, never the bare id, so a short id cannot match chunk text.

    SQLite stores a row's ``key`` and ``string_value`` columns back to back, in the table and in its
    index. Chroma's log and the upgrade's export store JSON, with either separator and either escaping.
    """
    key = END_USER_KEY.encode()
    patterns = {key + value.encode()}
    for form in {value.encode(), json.dumps(value)[1:-1].encode()}:
        for separator in (b":", b": "):
            patterns.add(b'"' + key + b'"' + separator + b'"' + form + b'"')
    return patterns


def file_mentions(path: Path, value: str) -> bool:
    """Whether a file's bytes carry an end-user stamp for ``value``, read in bounded chunks."""
    patterns = _patterns(value)
    overlap = max(len(pattern) for pattern in patterns) - 1
    tail = b""
    with path.open("rb") as stream:
        while chunk := stream.read(_READ_CHUNK):
            window = tail + chunk
            if any(pattern in window for pattern in patterns):
                return True
            tail = window[-overlap:]
    return False


def copy_mentions(copy: Path, value: str) -> bool:
    """Whether a retained Chroma copy may hold chunks stamped with ``value`` as their end user.

    This errs toward yes: removing a copy that did not need it costs a rollback point, while keeping
    one that did leaves the person's data behind. The byte scan finds rows that Chroma deleted but
    left in free pages and journals. The SQL read finds values that SQLite split across overflow pages.
    """
    files = [copy / name for name in _DATABASE_FILES if (copy / name).is_file()]
    if not files:
        return False
    if any(file_mentions(path, value) for path in files):
        return True
    return _database_mentions(copy / "chroma.sqlite3", value)


def _database_mentions(database: Path, value: str) -> bool:
    # ``immutable`` opens without creating a -shm file, so the copy and its fingerprint stay untouched.
    try:
        with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            if connection.execute(
                "SELECT 1 FROM embedding_metadata WHERE key = ? AND string_value = ? LIMIT 1", (END_USER_KEY, value)
            ).fetchone():
                return True
            rows = connection.execute("SELECT metadata FROM embeddings_queue WHERE metadata IS NOT NULL")
            return any(_log_entry_mentions(metadata, value) for (metadata,) in rows)
    except sqlite3.Error:
        return True


def _log_entry_mentions(metadata: str | bytes, value: str) -> bool:
    try:
        entry = json.loads(metadata)
    except (TypeError, ValueError):
        return True
    return not isinstance(entry, dict) or entry.get(END_USER_KEY) == value


def _check_path(path: Path, root: Path) -> None:
    if not path.is_relative_to(root) or path == root:
        msg = "Retained storage escapes its configured root"
        raise MaintenanceRequiredError(msg)
    for candidate in (path, *path.parents):
        if candidate == root:
            return
        if candidate.is_symlink():
            msg = "Retained storage cannot use symbolic links"
            raise MaintenanceRequiredError(msg)


def _delete_tree(path: Path) -> None:
    # Another worker that took over the request may be deleting the same entry.
    with suppress(FileNotFoundError):
        shutil.rmtree(path)


def _erased_directory(root: Path) -> Path:
    erased = root / MIGRATION_DIRECTORY / _ERASED_DIRECTORY
    _check_path(erased, root)
    erased.mkdir(parents=True, exist_ok=True, mode=0o700)
    return erased


def remove_copy(copy: Path, root: Path) -> None:
    """Delete a retained copy without following a symbolic link out of the storage root."""
    _check_path(copy, root)
    erased = _erased_directory(root)
    for leftover in erased.iterdir():
        _delete_tree(leftover)
    if not copy.is_dir():
        return
    target = erased / uuid4().hex
    copy.rename(target)
    _delete_tree(target)


def remove_file(path: Path, root: Path) -> None:
    """Delete a retained file, such as a failed run's export, inside the storage root."""
    _check_path(path, root)
    path.unlink(missing_ok=True)


def remove_upgrade_evidence(root: Path, kb_id: UUID) -> None:
    """Delete every run's snapshot, export and routing backup for one knowledge base."""
    remove_copy(root / MIGRATION_DIRECTORY / str(kb_id), root)
