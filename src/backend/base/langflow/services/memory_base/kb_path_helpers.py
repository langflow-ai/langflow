"""KB path resolution and username helpers for MemoryBase.

Extracted from MemoryBaseService to keep single-responsibility per file.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends import create_backend
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils.kb_helpers import KBStorageHelper
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    import uuid
    from pathlib import Path

    from sqlmodel.ext.asyncio.session import AsyncSession


def validate_kb_path(kb_root: Path, kb_path: Path) -> None:
    """Assert that kb_path is contained within kb_root (path traversal guard).

    Prevents crafted usernames with '..' segments from escaping the KB root directory.
    Follows the same pattern as services/storage/local.py:save_file.
    """
    kb_root_resolved = kb_root.resolve()
    kb_path_resolved = kb_path.resolve()
    if not kb_path_resolved.is_relative_to(kb_root_resolved):
        msg = "KB path escapes root directory"
        raise ValueError(msg)


def hash_session_id(session_id: str) -> str:
    """Return a truncated SHA-256 hash for safe logging of session IDs."""
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


def sanitize_kb_name(name: str) -> str:
    """Lowercase, replace spaces/hyphens with underscores, strip non-alphanum."""
    sanitized = name.strip().lower()
    sanitized = re.sub(r"[\s\-]+", "_", sanitized)
    sanitized = re.sub(r"[^\w]", "", sanitized)
    return sanitized or "memory"


async def resolve_kb_username(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Look up the username for a user_id within an existing DB session."""
    from langflow.services.database.models.user.model import User

    stmt = select(User.username).where(User.id == user_id)
    result = await db.exec(stmt)
    username = result.first()
    if not username:
        msg = f"User {user_id} not found"
        raise ValueError(msg)
    return username


async def resolve_kb_username_by_user_id(user_id: uuid.UUID) -> str:
    """Look up the username for a user_id using a fresh DB session."""
    async with session_scope() as db:
        return await resolve_kb_username(db, user_id)


async def initialize_kb(
    *,
    kb_name: str,
    kb_username: str,
    user_id: uuid.UUID | None = None,
    backend_type: str = "chroma",
    backend_config: dict | None = None,
) -> None:
    """Provision a Memory Base's vector-store collection.

    Memory Bases are DB-driven: their identity, embedding config, backend, and
    cached stats all live on the ``knowledge_base`` row (written by the caller via
    ``_create_kb_record_for_memory_base``). This function only touches the vector
    store — it no longer writes an on-disk ``embedding_metadata.json`` sidecar, so
    a Memory Base provisioned on a remote backend needs no local disk at all and
    works identically across replicas.

    Collection setup goes through ``create_backend`` so a Memory Base can be
    provisioned on any registered backend. For a local-Chroma backend the Chroma
    client creates its own persistence directory; for remote backends nothing
    touches the local filesystem. Best-effort throughout: every backend creates the
    collection lazily on first write anyway, so a provisioning failure here must not
    block Memory Base creation.
    """
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        await logger.awarning("KB root path not configured — Memory Base collection will not be pre-provisioned.")
        return

    kb_path: Path = kb_root / kb_username / kb_name
    validate_kb_path(kb_root, kb_path)

    # Touch the collection so it exists before the first ingestion. Best-effort:
    # every backend creates the collection lazily on write anyway, so a failure
    # here (including a missing/unwritable local dir on a remote-backed KB) must
    # not block Memory Base creation.
    backend = create_backend(
        backend_type,
        kb_name=kb_name,
        kb_path=kb_path,
        backend_config=backend_config or {},
        user_id=user_id,
    )
    try:
        await backend.ensure_ready()
        _ = backend.vector_store
    except Exception as exc:  # noqa: BLE001 — provisioning is best-effort
        await logger.awarning("Initial %s setup for %s failed: %s", backend_type, kb_name, exc)
    finally:
        await backend.teardown()


async def delete_kb(*, kb_name: str, kb_username: str) -> None:
    """Remove the KB directory from disk. Logs on failure, does not raise."""
    if not kb_name:
        return
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        return
    kb_path = kb_root / kb_username / kb_name
    validate_kb_path(kb_root, kb_path)
    try:
        await asyncio.to_thread(KBStorageHelper.delete_storage, kb_path, kb_name)
    except (OSError, ValueError):
        await logger.awarning("Could not delete KB '%s' from disk after Memory Base deletion.", kb_name, exc_info=True)
