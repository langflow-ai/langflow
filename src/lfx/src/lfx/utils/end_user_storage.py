"""Which end users own a SaveToFile folder under ``config_dir``.

SaveToFile names an identified end user's folder after their sanitized id, so the folder name alone
cannot prove ownership: the sanitizing is lossy (``a@b`` and ``a_b`` share ``a_b``) and an unrelated
folder may carry the same name. The writer records every raw id it saves for here, and erasure deletes a
folder only when this record names exactly the person being erased.

The registry lives in a dot-folder, which a sanitized id can never be named (leading dots are stripped).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock

REGISTRY_DIR_NAME = ".save_file_end_users"


def _entry(config_dir: Path, segment: str) -> Path:
    return Path(config_dir) / REGISTRY_DIR_NAME / f"{segment}.json"


def end_user_folder_lock(config_dir: Path, segment: str) -> FileLock:
    """Serialize owner changes and erasure across workers sharing this directory.

    Lock files remain after erasure so a waiting writer cannot acquire a different lock inode.
    """
    entry = _entry(config_dir, segment)
    entry.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(entry.parent / f".{segment}.lock", timeout=10)


def end_user_folder_owners(config_dir: Path, segment: str) -> frozenset[str] | None:
    """The raw end-user ids recorded for ``config_dir/<segment>``, or ``None`` when nothing was recorded."""
    entry = _entry(config_dir, segment)
    try:
        payload = json.loads(entry.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    owners = payload.get("end_user_ids") if isinstance(payload, dict) else None
    if not isinstance(owners, list):
        return None
    return frozenset(str(owner) for owner in owners)


def record_end_user_folder(config_dir: Path, segment: str, end_user_id: str) -> None:
    """Record an owner without claiming a pre-existing folder whose contents cannot be attributed."""
    with end_user_folder_lock(config_dir, segment):
        owners = end_user_folder_owners(config_dir, segment)
        folder = Path(config_dir) / segment
        if owners is None:
            try:
                folder.mkdir()
            except FileExistsError:
                return
        owners = owners or frozenset()
        if end_user_id in owners:
            return
        entry = _entry(config_dir, segment)
        payload = json.dumps({"end_user_ids": sorted({*owners, end_user_id})})
        fd, tmp = tempfile.mkstemp(dir=entry.parent, prefix=f".{segment}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            Path(tmp).replace(entry)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def forget_end_user_folder(config_dir: Path, segment: str) -> None:
    _entry(config_dir, segment).unlink(missing_ok=True)
