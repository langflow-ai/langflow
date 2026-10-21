"""Reclaim a flow's Memory Bases with durable, retryable storage deletion.

The flow transaction removes Memory rows and marks backing KBs deleting. Their
routing records remain until the post-commit cleanup drains writers and
successfully tombstones or drops storage. Failures retain the deleting record
for retry, so a dead provider never loses the information needed for cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy import delete, update
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import _coerce_backend_config_value
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBasePreprocessingOutput,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
    MessageIngestionRecord,
)
from langflow.services.database.models.user.model import User
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError
from langflow.services.memory_base.ingestion import cancel_active_jobs
from langflow.services.memory_base.kb_path_helpers import delete_kb

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class FlowMemoryBaseCleanup:
    """External resources of one deleted Memory Base, captured before its rows go.

    The backing KB row remains fenced until storage deletion succeeds. This
    snapshot also preserves immutable storage identity when a concurrent owner
    deletion removes that row through a database cascade.
    """

    kb_name: str
    user_id: UUID
    # ``None`` when the owning user could not be resolved (e.g. the user is being
    # deleted in the same transaction). This only affects residual legacy
    # directory cleanup. SQLite cleanup uses the captured immutable UUIDs.
    kb_username: str | None
    backend_type: str
    backend_config: dict = field(default_factory=dict)
    kb_record_id: UUID | None = None
    storage_record: KnowledgeBaseRecord | None = None


async def purge_flow_memory_bases(session: AsyncSession, flow_id: UUID) -> list[FlowMemoryBaseCleanup]:
    """Delete the DB rows for every Memory Base owned by ``flow_id``.

    Runs on the caller's session so the deletions commit (or roll back) together
    with the flow deletion. Removes the ``memory_base`` rows, their child rows
    (sessions, workflow runs, ingestion records, preprocessing outputs). Backing
    KB rows are retained in the deleting state until storage cleanup succeeds.
    The child deletes are explicit because
    SQLite does not honor ``ON DELETE CASCADE`` unless ``PRAGMA foreign_keys`` is
    on — matching the surrounding ``cascade_delete_flow`` convention.

    Returns one :class:`FlowMemoryBaseCleanup` per Memory Base so the caller can
    run :func:`finalize_flow_memory_base_cleanup` after the transaction commits.
    No external I/O happens here.
    """
    memory_bases = list((await session.exec(select(MemoryBase).where(MemoryBase.flow_id == flow_id))).all())
    if not memory_bases:
        return []

    # Resolve each owner's username once for residual legacy directory cleanup.
    username_cache: dict[UUID, str | None] = {}

    async def _resolve_username(user_id: UUID) -> str | None:
        if user_id not in username_cache:
            username_cache[user_id] = (await session.exec(select(User.username).where(User.id == user_id))).first()
        return username_cache[user_id]

    handles: list[FlowMemoryBaseCleanup] = []
    for mb in memory_bases:
        # Retain and fence routing for post-commit cleanup, and capture a trusted
        # snapshot for the owner-deletion case where an FK cascade removes it.
        kb_record = (
            await session.exec(
                select(KnowledgeBaseRecord)
                .where(KnowledgeBaseRecord.user_id == mb.user_id)
                .where(KnowledgeBaseRecord.name == mb.kb_name)
            )
        ).first()
        if kb_record is not None:
            backend_type = kb_record.backend_type or "chroma"
            backend_config = _coerce_backend_config_value(kb_record.backend_config)
            if kb_record.storage_state != "detached":
                if backend_type == "chroma" or kb_record.storage_state not in ("ready", "deleting", "deleted"):
                    msg = "Memory Base storage requires upgrade recovery before deleting its flow"
                    raise StorageUnavailableError(msg)
                if kb_record.storage_state == "ready":
                    changed = await session.exec(
                        update(KnowledgeBaseRecord)
                        .where(KnowledgeBaseRecord.id == kb_record.id)
                        .where(KnowledgeBaseRecord.storage_generation == kb_record.storage_generation)
                        .where(KnowledgeBaseRecord.backend_type == kb_record.backend_type)
                        .where(KnowledgeBaseRecord.storage_state == "ready")
                        .values(storage_state="deleting")
                        .execution_options(synchronize_session=False)
                    )
                    if changed.rowcount != 1:
                        msg = "Memory Base storage changed during flow deletion. Retry after upgrade recovery."
                        raise StorageUnavailableError(msg)
                    await session.refresh(kb_record)
            session.add(kb_record)
        else:
            # No row to resolve a remote backend from; treat as local so the
            # only cleanup attempted is the on-disk directory (a no-op if absent).
            backend_type = "chroma"
            backend_config = {}

        handles.append(
            FlowMemoryBaseCleanup(
                kb_name=mb.kb_name,
                user_id=mb.user_id,
                kb_username=await _resolve_username(mb.user_id),
                backend_type=backend_type,
                backend_config=backend_config,
                kb_record_id=kb_record.id if kb_record is not None else None,
                storage_record=kb_record.model_copy(deep=True) if kb_record is not None else None,
            )
        )

    memory_base_ids = [mb.id for mb in memory_bases]

    # Validate every backing store before cancelling any running jobs.
    for mb in memory_bases:
        try:
            await cancel_active_jobs(memory_base_id=mb.id, db=session)
        except Exception as exc:  # noqa: BLE001 - job teardown is best-effort
            await logger.awarning(
                "Could not cancel ingestion jobs for Memory Base %s during flow deletion: %s", mb.id, exc
            )

    # Children first (explicit — SQLite may not enforce FK cascades), then the
    # Memory rows. Backing KB rows remain available for storage cleanup retries.
    await session.exec(
        delete(MessageIngestionRecord).where(col(MessageIngestionRecord.memory_base_id).in_(memory_base_ids))
    )
    await session.exec(
        delete(MemoryBaseWorkflowRun).where(col(MemoryBaseWorkflowRun.memory_base_id).in_(memory_base_ids))
    )
    await session.exec(
        delete(MemoryBasePreprocessingOutput).where(
            col(MemoryBasePreprocessingOutput.memory_base_id).in_(memory_base_ids)
        )
    )
    await session.exec(delete(MemoryBaseSession).where(col(MemoryBaseSession.memory_base_id).in_(memory_base_ids)))
    await session.exec(delete(MemoryBase).where(col(MemoryBase.id).in_(memory_base_ids)))

    return handles


async def finalize_flow_memory_base_cleanup(handles: list[FlowMemoryBaseCleanup]) -> None:
    """Finish storage deletion after the flow transaction commits.

    A failure retains the fenced routing row and does not abort later handles.
    """
    for handle in handles:
        try:
            if handle.storage_record is not None and handle.storage_record.storage_state == "detached":
                continue  # Preserve detached routing, ledger and source for operator recovery.
            await _drop_remote_collection(handle)
            # Only after storage cleanup succeeds, remove residual legacy
            # directories. A failed or incomplete upgrade leaves them intact.
            if handle.kb_username is not None:
                await delete_kb(kb_name=handle.kb_name, kb_username=handle.kb_username)
        except Exception:  # noqa: BLE001 — one handle's failure must never orphan the rest of the batch
            await logger.aexception(
                "Memory Base cleanup failed for kb_name=%s; it may need manual cleanup.", handle.kb_name
            )


async def _drop_remote_collection(handle: FlowMemoryBaseCleanup) -> None:
    """Drain writers and delete storage before removing its routing record."""
    from langflow.api.utils import knowledge_base_service
    from langflow.services.knowledge_base_storage.runtime import (
        StorageUnavailableError,
        delete_orphaned_storage,
    )

    if handle.kb_record_id is None:
        return
    record = await knowledge_base_service.get_by_id(handle.kb_record_id)
    if record is None:
        if handle.storage_record is not None and handle.storage_record.backend_type == "sqlite":
            await delete_orphaned_storage(handle.storage_record)
        elif handle.backend_type == "chroma":
            msg = "Legacy storage lost its routing record. Preserve its migration source for administrator recovery."
            raise StorageUnavailableError(msg)
        elif handle.storage_record is not None:
            await logger.awarning(
                "Storage routing for deleted Memory Base %s was removed with its owner. "
                "The remote collection requires administrator cleanup.",
                handle.kb_name,
            )
        return
    await knowledge_base_service.delete_record(record.id)
