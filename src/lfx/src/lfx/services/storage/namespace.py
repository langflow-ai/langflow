"""Storage namespaces: the per-flow or per-user folder every stored file lives under."""

from __future__ import annotations

import shutil
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def validate_namespace(namespace: str) -> str:
    """Return a canonical raw or ``user-``/``flow-`` typed UUID namespace."""
    value = str(namespace)
    scope_type, separator, principal_id = value.partition("-")
    try:
        if separator and scope_type in {"user", "flow"}:
            return f"{scope_type}-{uuid.UUID(principal_id)}"
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        msg = "Storage namespace must be a UUID"
        raise ValueError(msg) from exc


def remove_namespace_tree(root: Path, namespace: str) -> int:
    """Delete ``root/<namespace>`` with everything under it and return how many files were removed."""
    validated = validate_namespace(namespace)
    resolved_root = root.resolve()
    folder = (resolved_root / validated).resolve()
    if not folder.is_relative_to(resolved_root) or folder == resolved_root:
        msg = "Invalid namespace: path escapes the storage root"
        raise ValueError(msg)
    if not folder.is_dir():
        return 0
    removed = sum(1 for entry in folder.rglob("*") if entry.is_file())
    shutil.rmtree(folder)
    return removed
