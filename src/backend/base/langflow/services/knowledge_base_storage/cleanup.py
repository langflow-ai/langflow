"""Explicit recovery of already-requested KB storage deletions."""

from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import delete, exists
from sqlmodel import col, select

from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.deps import session_scope
from langflow.services.knowledge_base_storage.runtime import (
    StorageUnavailableError,
    delete_storage_for_record,
    operation,
)


async def detach_attention_store(kb_id: UUID, *, expected_generation: int) -> None:
    """Disable a failed store while retaining its source, routing and migration ledger.

    Linked Memory Bases remain unavailable until explicitly deleted. Detachment
    never invokes a retired backend or removes a local or remote source.
    """
    async with operation(kb_id, allowed_states=("ready", "needs_attention", "deleting")) as record:
        if record.storage_state == "ready" and record.backend_type == "sqlite":
            msg = "Delete a ready local store through its owner API so its data is erased."
            raise StorageUnavailableError(msg)
        if record.storage_generation != expected_generation:
            msg = "Storage generation changed. Refresh migration status before detaching."
            raise StorageUnavailableError(msg)
        async with session_scope() as session:
            current = await session.get(KnowledgeBaseRecord, kb_id)
            if (
                current is None
                or current.storage_generation != expected_generation
                or current.storage_state not in ("ready", "needs_attention", "deleting")
            ):
                msg = "Storage changed. Refresh migration status before detaching."
                raise StorageUnavailableError(msg)
            from langflow.services.knowledge_base_storage.coordinator import retire_legacy_source

            await retire_legacy_source(record)
            current.storage_state = "detached"
            if current.active_migration_id:
                run = await session.get(KnowledgeBaseStorageMigration, current.active_migration_id)
                if run is not None:
                    run.phase = "detached"
            await session.commit()


if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.engine import CursorResult


async def retry_pending_cleanup(kb_id: UUID, *, expected_generation: int) -> bool:
    """Finish one pending deletion, retaining its UUID fence through metadata removal.

    A missing UUID is an idempotent success. A live Memory Base must be deleted
    through its existing service so its ingestion jobs and history stay linked.
    Neither a name nor a path supplied by a caller selects the storage target.
    """
    async with session_scope() as session:
        record = await session.get(KnowledgeBaseRecord, kb_id)
    if record is None:
        return False
    if record.storage_generation != expected_generation:
        msg = "Storage generation changed. Refresh pending cleanup before retrying."
        raise StorageUnavailableError(msg)
    try:
        async with operation(record, allowed_states=("deleting", "deleted")) as current:
            memory_reference = exists(
                select(MemoryBase.id).where(
                    MemoryBase.user_id == current.user_id,
                    MemoryBase.kb_name == current.name,
                )
            )
            async with session_scope() as session:
                if await session.scalar(select(memory_reference)):
                    msg = "This KB still backs a Memory Base. Retry the linked Memory Base deletion instead."
                    raise StorageUnavailableError(msg)
            await delete_storage_for_record(current)
            async with session_scope() as session:
                # The exact identity/generation and its completed storage fence
                # must still match. A name reused by another KB is never deleted.
                result = cast(
                    "CursorResult[Any]",
                    await session.execute(
                        delete(KnowledgeBaseRecord).where(
                            col(KnowledgeBaseRecord.id) == kb_id,
                            col(KnowledgeBaseRecord.user_id) == current.user_id,
                            col(KnowledgeBaseRecord.storage_generation) == expected_generation,
                            col(KnowledgeBaseRecord.backend_type) == current.backend_type,
                            col(KnowledgeBaseRecord.storage_state) == "deleted",
                            ~memory_reference,
                        )
                    ),
                )
                if result.rowcount != 1:
                    if await session.get(KnowledgeBaseRecord, kb_id) is None:
                        return False
                    msg = "Storage identity or Memory linkage changed during cleanup. Refresh pending cleanup."
                    raise StorageUnavailableError(msg)
                await session.commit()
            return True
    except StorageUnavailableError:
        # A concurrent successful retry can remove the row while this request
        # waits for its lock. Only confirmed absence may turn that into success.
        async with session_scope() as session:
            if await session.get(KnowledgeBaseRecord, kb_id) is None:
                return False
        raise
