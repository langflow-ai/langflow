"""KB path resolution and username helpers for MemoryBase.

Extracted from MemoryBaseService to keep single-responsibility per file.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.backends import BackendType, create_backend
from lfx.base.knowledge_bases.validation import MAX_LOCAL_COLLECTION_NAME_LENGTH
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils.kb_helpers import KBStorageHelper, validate_kb_path
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    import uuid

    from sqlmodel.ext.asyncio.session import AsyncSession


class BackendProvisioningError(ValueError):
    """Raised when a vector-store backend fails a non-retryable create-time check.

    A remote backend (OpenSearch / Chroma Cloud / Mongo / Astra / Postgres) with
    a bad URL or wrong credentials would otherwise be swallowed and produce a
    Memory Base that only errors later on every ingest and retrieval. Surfacing
    it here lets the create path reject the misconfiguration up front. Local
    Chroma validation failures are surfaced for the same reason.
    """


# Re-exported for this module's long-standing importers. The guard itself lives in
# ``kb_helpers`` (the lower-level module) so the import graph stays acyclic.
__all__ = [
    "BackendProvisioningError",
    "delete_kb",
    "delete_kb_remote_collection",
    "hash_session_id",
    "initialize_kb",
    "resolve_kb_username",
    "resolve_kb_username_by_user_id",
    "sanitize_kb_name",
    "validate_kb_path",
]


def hash_session_id(session_id: str) -> str:
    """Return a truncated SHA-256 hash for safe logging of session IDs."""
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


_KB_NAME_SUFFIX_LENGTH = 9  # underscore + 8 hex characters, added by MemoryBaseService
_MAX_KB_NAME_PREFIX_LENGTH = MAX_LOCAL_COLLECTION_NAME_LENGTH - _KB_NAME_SUFFIX_LENGTH


def sanitize_kb_name(name: str) -> str:
    """Return an ASCII-safe prefix for a generated Memory Base collection name."""
    sanitized = name.strip().lower()
    sanitized = re.sub(r"[\s\-]+", "_", sanitized)
    sanitized = re.sub(r"[^\w]", "", sanitized, flags=re.ASCII).lstrip("_")
    return sanitized[:_MAX_KB_NAME_PREFIX_LENGTH] or "memory"


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
    kb_username: str,  # noqa: ARG001 - retained for saved callers
    user_id: uuid.UUID | None = None,
    backend_type: str = "sqlite",
    backend_config: dict | None = None,
) -> None:
    """Validate a provider before creating the Memory Base's backing KB row.

    The row creation helper initializes SQLite after assigning its UUID. Remote
    providers are probed here without allocating any local storage.
    """
    # SQLite initialization requires the UUID identity assigned by create_record,
    # which initializes it atomically with the create workflow immediately after
    # this preflight. Remote providers can validate connectivity without a row.
    if backend_type == BackendType.SQLITE.value:
        return
    if backend_type == BackendType.CHROMA.value:
        msg = "Chroma is retired. Choose SQLite, pgVector, or OpenSearch."
        raise BackendProvisioningError(msg)
    backend = create_backend(backend_type, kb_name=kb_name, backend_config=backend_config or {}, user_id=user_id)
    try:
        result = await backend.test_connection()
        if not result.ok:
            msg = f"Could not connect to the '{backend_type}' vector store: {result.message}"
            raise BackendProvisioningError(msg)
    except BackendProvisioningError:
        raise
    except Exception as exc:
        msg = f"Could not initialize the '{backend_type}' vector store for this Memory Base: {exc}"
        raise BackendProvisioningError(msg) from exc
    finally:
        await backend.teardown()


async def delete_kb_remote_collection(*, kb_name: str, user_id: uuid.UUID) -> None:
    """Fence and delete the backing store while its routing row still exists.

    The historical name is retained for callers. SQLite and remote providers
    use the same durable deletion protocol, and failures remain retryable.
    """
    from langflow.api.utils import knowledge_base_service
    from langflow.services.knowledge_base_storage.runtime import delete_storage_for_record

    record = await knowledge_base_service.get_by_user_and_name(user_id, kb_name)
    if record is not None:
        await delete_storage_for_record(record)


async def delete_kb(*, kb_name: str, kb_username: str) -> None:
    """Remove a local-Chroma Memory Base's directory from disk.

    Runs *after* the ``knowledge_base`` row has been dropped, so it cannot resolve
    the backend to check whether this KB ever had local storage. It doesn't need
    to: a remote-backed Memory Base simply has no directory, and the absence is
    the answer rather than an error.

    Deliberately tolerant of an unconfigured or unusable KB root. A deployment
    that serves only remote vector stores may have no local storage at all, and
    Memory Base deletion must not fail there. Logs on failure, never raises.
    """
    if not kb_name:
        return
    try:
        kb_root = KBStorageHelper.get_root_path()
    except ValueError:
        # No local storage configured — nothing on disk to remove.
        return
    kb_path = kb_root / kb_username / kb_name
    try:
        validate_kb_path(kb_root, kb_path)
        if not await asyncio.to_thread(kb_path.exists):
            return
        await asyncio.to_thread(KBStorageHelper.delete_storage, kb_path, kb_name)
    except (OSError, ValueError):
        await logger.awarning("Could not delete KB '%s' from disk after Memory Base deletion.", kb_name, exc_info=True)
