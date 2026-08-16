"""KB path resolution and username helpers for MemoryBase.

Extracted from MemoryBaseService to keep single-responsibility per file.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends import BackendType, create_backend
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils.kb_helpers import KBStorageHelper
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    import uuid
    from pathlib import Path

    from sqlmodel.ext.asyncio.session import AsyncSession


class BackendProvisioningError(ValueError):
    """Raised when a non-local vector-store backend fails its create-time check.

    A remote backend (OpenSearch / Chroma Cloud / Mongo / Astra / Postgres) with
    a bad URL or wrong credentials would otherwise be swallowed and produce a
    Memory Base that only errors later on every ingest and retrieval. Surfacing
    it here lets the create path reject the misconfiguration up front.
    """


def _is_local_chroma(backend_type: str, backend_config: dict | None) -> bool:
    """True for the default local-Chroma backend (on-disk, lazily created)."""
    return backend_type == BackendType.CHROMA.value and (backend_config or {}).get("mode") != "cloud"


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
    provisioned on any registered backend.

    Failure handling depends on the backend:

    * **Local Chroma (default):** best-effort. The Chroma client creates its own
      persistence directory and the collection is created lazily on first write,
      so a provisioning hiccup here must not block Memory Base creation — it is
      logged and swallowed.
    * **Remote backends (OpenSearch / Chroma Cloud / Mongo / Astra / Postgres):**
      a bad URL or wrong credentials is a real misconfiguration that would make
      the Memory Base silently dead — every later ingest and retrieval would
      fail with no link back to create. So an explicit connectivity check runs
      here and a failure raises :class:`BackendProvisioningError`, rejecting the
      create up front.
    """
    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        await logger.awarning("KB root path not configured — Memory Base collection will not be pre-provisioned.")
        return

    kb_path: Path = kb_root / kb_username / kb_name
    validate_kb_path(kb_root, kb_path)

    is_local_chroma = _is_local_chroma(backend_type, backend_config)
    backend = create_backend(
        backend_type,
        kb_name=kb_name,
        kb_path=kb_path,
        backend_config=backend_config or {},
        user_id=user_id,
    )
    try:
        if is_local_chroma:
            # Touch the collection so it exists before the first ingestion.
            # Best-effort: it is created lazily on write anyway.
            await backend.ensure_ready()
            _ = backend.vector_store
        else:
            # Validate connectivity up front so a bad remote config fails the
            # create instead of producing a Memory Base that only errors later.
            result = await backend.test_connection()
            if not result.ok:
                msg = f"Could not connect to the '{backend_type}' vector store: {result.message}"
                raise BackendProvisioningError(msg)
    except BackendProvisioningError:
        raise
    except Exception as exc:
        await logger.awarning("Initial %s setup for %s failed: %s", backend_type, kb_name, exc)
        if not is_local_chroma:
            msg = f"Could not initialize the '{backend_type}' vector store for this Memory Base: {exc}"
            raise BackendProvisioningError(msg) from exc
    finally:
        await backend.teardown()


async def delete_kb_remote_collection(*, kb_name: str, kb_username: str, user_id: uuid.UUID) -> None:
    """Drop the remote vector-store collection backing a Memory Base.

    Must run *before* the ``knowledge_base`` row is deleted: the row holds the
    ``backend_type`` / ``backend_config`` needed to reach the remote store, so
    dropping the row first would strand the OpenSearch index / Chroma Cloud
    collection with no way to clean it up. Best-effort — a stale credential or
    an unreachable cluster must not block Memory Base deletion, so failures are
    logged and swallowed.

    Local Chroma is skipped: its vectors live inside the KB directory and are
    removed by :func:`delete_kb`. Every other backend (OpenSearch, Chroma Cloud,
    Astra, Mongo, Postgres) stores off-box and needs an explicit
    ``delete_collection`` call.
    """
    from lfx.base.knowledge_bases.backends import BackendType, create_backend

    from langflow.api.utils.kb_helpers import resolve_backend_selection

    kb_root = KBStorageHelper.get_root_path()
    if not kb_root:
        return
    kb_path = kb_root / kb_username / kb_name  # only consumed by local backends
    try:
        backend_type, backend_config = await resolve_backend_selection(
            user_id=user_id, kb_name=kb_name, kb_path=kb_path
        )
    except ValueError as exc:
        # No row and no sidecar — nothing we can resolve a backend from.
        await logger.awarning("Could not resolve backend for Memory Base kb_name=%s: %s", kb_name, exc)
        return

    # Local Chroma keeps everything on disk; ``delete_kb`` handles it.
    if backend_type == BackendType.CHROMA.value and (backend_config or {}).get("mode") != "cloud":
        return

    backend = create_backend(
        backend_type,
        kb_name=kb_name,
        kb_path=kb_path,
        backend_config=backend_config,
        user_id=user_id,
    )
    try:
        await backend.ensure_ready()
        await backend.delete_collection()
    except Exception as exc:  # noqa: BLE001 — best-effort remote cleanup
        await logger.awarning(
            "Could not delete remote %s collection for Memory Base kb_name=%s: %s — "
            "the remote collection may need manual cleanup.",
            backend_type,
            kb_name,
            exc,
        )
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
