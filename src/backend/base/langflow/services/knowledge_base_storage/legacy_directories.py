"""The ``<owner>/<name>`` directories that versions before the SQLite upgrade wrote under the storage root.

A directory keeps the username its owner had when it was written, so the folder name alone does not say
whose it is. What a directory holds, and the base id its sidecar records, are the evidence an erase reads.
Internal folders such as ``.migration`` start with a dot and are never one owner's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from langflow.services.knowledge_base_storage.retained import is_path_segment

if TYPE_CHECKING:
    from pathlib import Path

SIDECAR = "embedding_metadata.json"
MAX_SIDECAR_BYTES = 2 * 1024 * 1024
# Left by a deletion that removed the base's row but could not remove its files.
TOMBSTONE = ".kb_deleted"
_STORE_MARKERS = frozenset({"chroma.sqlite3", SIDECAR, TOMBSTONE})
_UNREADABLE = (OSError, RecursionError, TypeError, ValueError)


@dataclass(frozen=True)
class LegacyDirectories:
    """What a scan found, by ``<owner>/<name>`` source identity."""

    stores: frozenset[str] = frozenset()
    """Directories that hold a legacy store or a deleted one's leftovers, or nothing at all."""
    tombstones: frozenset[str] = frozenset()
    """Stores whose base was deleted, though its files were not."""
    recorded: dict[str, UUID] = field(default_factory=dict)
    """The knowledge base id that each sidecar records. Versions 1.8 to 1.11 wrote it, and adoption keeps it."""
    unreadable: frozenset[str] = frozenset()
    """Directories, and whole owner folders, that are symbolic links or could not be read."""

    def readable(self, source_identity: str) -> bool:
        owner = source_identity.partition("/")[0]
        return source_identity not in self.unreadable and owner not in self.unreadable


def is_owner_folder(value: str) -> bool:
    """Whether a value can name one owner's folder, rather than an internal one or a path."""
    return is_path_segment(value) and not value.startswith(".")


def scan_legacy_directories(root: Path) -> LegacyDirectories:
    """Survey every owner folder under ``root`` without following a symbolic link.

    Anything that cannot be read is reported as unreadable rather than skipped, so a caller never takes
    it for a directory without an owner. A failure to list ``root`` itself is raised.
    """
    stores: set[str] = set()
    tombstones: set[str] = set()
    recorded: dict[str, UUID] = {}
    unreadable: set[str] = set()
    owners = sorted(root.iterdir()) if root.is_dir() else []
    for owner in owners:
        if not is_owner_folder(owner.name):
            continue
        try:
            if owner.is_symlink():
                unreadable.add(owner.name)
                continue
            if not owner.is_dir():
                continue
            sources = sorted(owner.iterdir())
        except OSError:
            unreadable.add(owner.name)
            continue
        for source in sources:
            identity = f"{owner.name}/{source.name}"
            try:
                survey = _survey(source)
            except _UNREADABLE:
                unreadable.add(identity)
                continue
            if survey is None:
                continue
            names, kb_id = survey
            if not names or names & _STORE_MARKERS:
                stores.add(identity)
            if TOMBSTONE in names:
                tombstones.add(identity)
            if kb_id is not None:
                recorded[identity] = kb_id
    return LegacyDirectories(frozenset(stores), frozenset(tombstones), recorded, frozenset(unreadable))


def _survey(source: Path) -> tuple[set[str], UUID | None] | None:
    """What a directory holds, and the id its sidecar records. ``None`` for anything but a directory."""
    if source.is_symlink():
        msg = "Legacy directory is a symbolic link"
        raise ValueError(msg)
    if not source.is_dir():
        return None
    names = {path.name for path in source.iterdir()}
    return names, _sidecar_id(source / SIDECAR) if SIDECAR in names else None


def _sidecar_id(sidecar: Path) -> UUID | None:
    if sidecar.is_symlink() or sidecar.stat().st_size > MAX_SIDECAR_BYTES:
        msg = "Legacy sidecar is a symbolic link or too large"
        raise ValueError(msg)
    metadata = json.loads(sidecar.read_bytes())
    if not isinstance(metadata, dict):
        msg = "Legacy sidecar is not an object"
        raise TypeError(msg)
    return UUID(str(metadata["id"])) if metadata.get("id") else None
