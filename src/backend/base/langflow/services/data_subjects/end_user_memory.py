"""End-user erase: the person's chunks inside each Memory Base vector collection, one Memory Base per call."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from lfx.base.knowledge_bases.backends import is_local_chroma
from lfx.base.knowledge_bases.backends.chroma import ChromaMigrationRequiredError
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import _coerce_backend_config_value, resolve_local_store_path
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.knowledge_base_storage.runtime import backend_for_record
from langflow.services.memory_base.ingestion import refresh_metrics_after_purge

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

CURSOR_KEY = "memory_vectors_after"
DEFAULT_BACKEND = "chroma"
# A tombstoned store can no longer be opened, so it has nothing left to erase. A store still
# ``deleting`` may hold chunks after a failed teardown, so it raises and is retried like an outage.
DELETED_STATE = "deleted"


async def _next_memory_base(session: AsyncSession, ctx: EraseContext) -> MemoryBase | None:
    stmt = select(MemoryBase).order_by(col(MemoryBase.id)).limit(1)
    if ctx.scope_flow_ids:
        stmt = stmt.where(col(MemoryBase.flow_id).in_(ctx.scope_flow_ids))
    if after := ctx.cursor.get(CURSOR_KEY):
        stmt = stmt.where(col(MemoryBase.id) > UUID(after))
    return (await session.exec(stmt)).first()


async def _local_store_missing(
    session: AsyncSession, memory_base: MemoryBase, record: KnowledgeBaseRecord | None
) -> bool:
    """A legacy local Chroma directory that was never written holds none of the person's chunks."""
    backend_type = (record.backend_type if record else None) or DEFAULT_BACKEND
    backend_config = _coerce_backend_config_value(record.backend_config) if record else {}
    if not is_local_chroma(backend_type, backend_config):
        return False
    if record is not None and await _upgrade_captured_source(session, record):
        return False
    owner = await session.get(User, memory_base.user_id)
    if owner is None:
        return False
    kb_path = resolve_local_store_path(
        memory_base.kb_name, owner.username, backend_type=backend_type, backend_config=backend_config
    )
    return kb_path is not None and not kb_path.exists()


async def _upgrade_captured_source(session: AsyncSession, record: KnowledgeBaseRecord) -> bool:
    # The SQLite upgrade fingerprints the source just before it snapshots and imports it into an
    # unpublished generation, so once it has, a missing directory no longer means the chunks are gone.
    # A directory that was never written fails before that point and leaves the fingerprint unset.
    if record.active_migration_id is None:
        return False
    run = await session.get(KnowledgeBaseStorageMigration, record.active_migration_id)
    return run is not None and run.source_fingerprint is not None


async def _erase_from_store(record: KnowledgeBaseRecord | None, end_user_id: str) -> None:
    if record is None:
        # Without a row, only a legacy Chroma directory can hold chunks, and it must be upgraded first.
        raise ChromaMigrationRequiredError
    if record.storage_state == DELETED_STATE:
        return
    # The storage runtime routes SQLite to its owned generation and fences migrations. A store it
    # cannot serve raises, so the engine retries instead of finishing with the chunks still there.
    backend = await backend_for_record(record)
    try:
        await backend.delete_by({"end_user_id": end_user_id})
        await refresh_metrics_after_purge(user_id=record.user_id, kb_name=record.name, backend=backend)
    finally:
        await backend.teardown()


async def erase_memory_base_vectors(session: AsyncSession, ctx: EraseContext) -> int:
    if ctx.end_user is None:
        return 0
    memory_base = await _next_memory_base(session, ctx)
    if memory_base is None:
        return 0
    record = (
        await session.exec(
            select(KnowledgeBaseRecord).where(
                KnowledgeBaseRecord.user_id == memory_base.user_id,
                KnowledgeBaseRecord.name == memory_base.kb_name,
            )
        )
    ).first()
    if not await _local_store_missing(session, memory_base, record):
        await _erase_from_store(record, ctx.end_user.raw_id)
    ctx.cursor[CURSOR_KEY] = str(memory_base.id)
    return 1
