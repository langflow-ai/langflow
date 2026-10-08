"""Which end users own a SaveToFile folder under ``config_dir``.

SaveToFile encodes the complete raw id into a filesystem-safe folder name. Legacy folders used a
lossy sanitizer, and unrelated folders may already occupy a name, so the writer records ownership
and erasure deletes a folder only when this record names exactly the person being erased.

The registry lives in a dot-folder, which neither the encoded nor legacy folder names can address.
"""

from __future__ import annotations

import json
import os
import tempfile
from base64 import b32encode
from pathlib import Path

from filelock import FileLock

REGISTRY_DIR_NAME = ".save_file_end_users"
# 145 bytes encode to 232 characters. The prefix and registry temporary-file suffix
# then fit within the common 255-byte filesystem name limit without truncation.
_MAX_END_USER_ID_BYTES = 145


def end_user_folder_segment(end_user_id: str) -> str:
    """Encode the full UTF-8 identity, preserving distinctions even on case-insensitive filesystems.

    Raises:
        ValueError: If the identity is empty or too long for the folder and registry filenames.
    """
    raw = end_user_id.encode("utf-8")
    if not raw or len(raw) > _MAX_END_USER_ID_BYTES:
        msg = f"End-user file storage requires an identity of 1 to {_MAX_END_USER_ID_BYTES} UTF-8 bytes."
        raise ValueError(msg)
    return "end_user-" + b32encode(raw).decode("ascii").rstrip("=").lower()


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


def record_end_user_folder(config_dir: Path, segment: str, end_user_id: str, *, exclusive: bool = False) -> None:
    """Record ownership, rejecting unowned or shared existing folders when an exclusive save is required."""
    with end_user_folder_lock(config_dir, segment):
        owners = end_user_folder_owners(config_dir, segment)
        if exclusive and owners is not None and owners != frozenset({end_user_id}):
            msg = "Cannot save to an end-user folder owned by another identity."
            raise ValueError(msg)
        folder = Path(config_dir) / segment
        if owners is None:
            try:
                folder.mkdir()
            except FileExistsError:
                if exclusive:
                    msg = "Cannot save to an end-user folder without verified ownership."
                    raise ValueError(msg) from None
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
