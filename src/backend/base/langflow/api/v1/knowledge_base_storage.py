"""Authenticated upgrade progress and exceptional retry controls."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from lfx.log.logger import logger
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.authorization import KnowledgeBaseAction, filter_visible_resources
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.knowledge_base_storage.cleanup import detach_attention_store, retry_pending_cleanup
from langflow.services.knowledge_base_storage.coordinator import (
    published_inventory_status,
    schedule_upgrade,
    upgrade_in_progress,
)
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError

router = APIRouter(prefix="/knowledge-base-storage", tags=["Knowledge Base Upgrade"])

_GUIDANCE = {
    "maintenance_required": "Check storage access and free disk space, then retry. Your original data is preserved.",
    "legacy_source_missing": (
        "No directory from the previous version could be tied to this base. If its owner was renamed, "
        "move its directory to <owner's current username>/<base name> in the knowledge base directory, then retry."
    ),
    "legacy_source_ambiguous": (
        "More than one directory from the previous version could hold this base, or another base may hold its "
        "directory. Leave only its own directory at <owner's current username>/<base name>, move any other copy "
        "out of the knowledge base directory, detach a base of the same name whose data is gone, then retry. "
        "Your original data is preserved."
    ),
    "automatic_upgrade_disabled": (
        "Enable LANGFLOW_KNOWLEDGE_BASE_AUTO_MIGRATE and restart Langflow to upgrade local data."
    ),
    "single_host_required": (
        "Stop all old instances, then run one Langflow worker on the host with the original "
        "local data. Distributed deployments need administrator recovery."
    ),
    "legacy_workers_running": "Stop the other Langflow instance using this data, then retry the upgrade.",
    "local_filesystem_required": (
        "Copy the original data to a local filesystem and run one Langflow worker there. "
        "Shared filesystems require administrator recovery."
    ),
    "remote_source_requires_migration": "Migrate the remote collection to a configured pgVector or OpenSearch store.",
    "validation_failed": "The copy failed validation. Preserve the original source and inspect the upgrade logs.",
    "automatic_reader_limit": (
        "This store exceeds the automatic reader's resource limits. Preserve the source and use the "
        "managed controller with a qualified signed helper, or export it from an isolated old-release environment."
    ),
    "storage_changed": "Routing changed during upgrade. Inspect the authoritative KB record before retrying.",
    "interrupted": "The upgrade was interrupted. Retry resumes the unpublished generation safely.",
    "migration_failed": (
        "Check storage access, source compatibility and free disk space, then retry. Your original data is preserved."
    ),
}


@router.get("/status")
async def storage_status(session: DbSession, current_user: CurrentActiveUser):
    """Show users their own availability and administrators the recovery queue.

    Paths, embedding credentials and other users' resources never appear in
    regular-user responses. Progress is joined to the active migration only.
    """
    statement = (
        select(KnowledgeBaseRecord, KnowledgeBaseStorageMigration)
        .outerjoin(
            KnowledgeBaseStorageMigration,
            KnowledgeBaseRecord.active_migration_id == KnowledgeBaseStorageMigration.id,
        )
        .where(
            col(KnowledgeBaseRecord.storage_state).in_(("migrating", "needs_attention"))
            | col(KnowledgeBaseRecord.active_migration_id).is_not(None)
        )
    )
    if not current_user.is_superuser:
        statement = statement.where(KnowledgeBaseRecord.user_id == current_user.id)
    rows = (
        await session.exec(
            statement.order_by(
                (col(KnowledgeBaseRecord.storage_state) != "ready").desc(),
                col(KnowledgeBaseStorageMigration.updated_at).desc(),
            ).limit(500)
        )
    ).all()
    if not current_user.is_superuser:
        rows = await filter_visible_resources(
            current_user,
            resource_type="knowledge_base",
            candidates=rows,
            key=lambda item: item[0].id,
            owner_extractor=lambda item: item[0].user_id,
            act=KnowledgeBaseAction.READ,
        )
    memory_names = {}
    if rows:
        references = (
            await session.exec(
                select(KnowledgeBaseRecord.id, MemoryBase.name)
                .join(
                    MemoryBase,
                    and_(
                        MemoryBase.user_id == KnowledgeBaseRecord.user_id,
                        MemoryBase.kb_name == KnowledgeBaseRecord.name,
                    ),
                )
                .where(col(KnowledgeBaseRecord.id).in_([record.id for record, _ in rows]))
                .order_by(MemoryBase.id)
            )
        ).all()
        for kb_id, name in references:
            memory_names.setdefault(kb_id, name)
    return {
        "stores": [
            {
                "kb_id": record.id,
                "name": memory_names.get(record.id, record.name),
                "kind": "memory" if record.id in memory_names else "knowledge",
                "storage_state": record.storage_state,
                "migration_id": run.id if run else None,
                "phase": run.phase if run else "discovered",
                "error_code": run.error_code if run else None,
                "guidance": _GUIDANCE.get(run.error_code or "") if run else None,
                "can_retry": bool(current_user.is_superuser and run and record.storage_state == "needs_attention"),
            }
            for record, run in rows
            if record.storage_state in ("migrating", "needs_attention")
        ],
        "revision": max((run.updated_at.isoformat() for _, run in rows if run and run.phase == "complete"), default=""),
        "running": any(record.storage_state == "migrating" for record, _ in rows)
        or (current_user.is_superuser and upgrade_in_progress()),
        "inventory": await published_inventory_status() if current_user.is_superuser else None,
        "is_admin": bool(current_user.is_superuser),
    }


class CleanupRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_generation: int = Field(gt=0, strict=True)


@router.get("/inventory")
async def get_inventory(_admin: Annotated[User, Depends(get_current_active_superuser)]):
    """Report whether legacy storage discovery completed and requires recovery."""
    return await published_inventory_status()


@router.get("/pending-cleanup")
async def pending_cleanup(
    session: DbSession,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List pending deletions with the linked Memory Bases that own their history."""
    rows = (
        await session.exec(
            select(KnowledgeBaseRecord)
            .where(col(KnowledgeBaseRecord.storage_state).in_(("deleting", "deleted")))
            .order_by(KnowledgeBaseRecord.id)
            .offset(offset)
            .limit(500)
        )
    ).all()
    memory_ids: dict[UUID, list[UUID]] = {}
    if rows:
        references = (
            await session.exec(
                select(KnowledgeBaseRecord.id, MemoryBase.id)
                .join(
                    MemoryBase,
                    and_(
                        col(MemoryBase.user_id) == KnowledgeBaseRecord.user_id,
                        col(MemoryBase.kb_name) == KnowledgeBaseRecord.name,
                    ),
                )
                .where(col(KnowledgeBaseRecord.id).in_([row.id for row in rows]))
            )
        ).all()
        for kb_id, memory_id in references:
            memory_ids.setdefault(kb_id, []).append(memory_id)
    return [
        {
            "kb_id": row.id,
            "storage_generation": row.storage_generation,
            "state": row.storage_state,
            "memory_base_ids": sorted(memory_ids.get(row.id, []), key=str),
            "guidance": (
                "Retry deletion of the linked Memory Base to finish its storage and history cleanup."
                if row.id in memory_ids
                else "Retry this pending cleanup with its KB UUID and expected storage generation."
            ),
        }
        for row in rows
    ]


@router.post("/pending-cleanup/{kb_id}/retry")
async def retry_cleanup(
    kb_id: UUID,
    request: CleanupRetryRequest,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
):
    """Retry deletion only for the UUID and generation confirmed by the administrator."""
    try:
        removed = await retry_pending_cleanup(kb_id, expected_generation=request.expected_generation)
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        await logger.awarning("Pending knowledge base cleanup failed for %s", kb_id)
        raise HTTPException(
            status_code=503,
            detail="Storage cleanup could not finish. Resolve storage access or provider availability, then retry.",
        ) from exc
    return {"kb_id": kb_id, "status": "deleted" if removed else "already_absent"}


@router.post("/attention/{kb_id}/detach")
async def detach_storage(
    kb_id: UUID,
    request: CleanupRetryRequest,
    _admin: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
):
    """Abandon a failed migration without deleting its source or recovery evidence."""
    if await session.get(KnowledgeBaseRecord, kb_id) is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    try:
        await detach_attention_store(kb_id, expected_generation=request.expected_generation)
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"kb_id": kb_id, "status": "detached", "source_preserved": True}


@router.get("/migrations")
async def list_migrations(session: DbSession, _admin: Annotated[User, Depends(get_current_active_superuser)]):
    """Return bounded, credential-free migration status and operator guidance."""
    rows = (
        await session.exec(
            select(KnowledgeBaseStorageMigration)
            .order_by(col(KnowledgeBaseStorageMigration.created_at).desc())
            .limit(500)
        )
    ).all()
    return [
        {
            "id": row.id,
            "kb_id": row.kb_id,
            "phase": row.phase,
            "source_generation": row.source_generation,
            "target_generation": row.target_generation,
            "attempts": row.attempts,
            "error_code": row.error_code,
            "guidance": _GUIDANCE.get(row.error_code or ""),
            "count": row.validation.get("count"),
            "diagnostic": row.validation.get("diagnostic"),
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.post("/migrations/{migration_id}/retry", status_code=202)
async def retry_migration(
    migration_id: UUID, session: DbSession, _admin: Annotated[User, Depends(get_current_active_superuser)]
):
    """Schedule recovery of the migration still bound to the current KB record."""
    run = await session.get(KnowledgeBaseStorageMigration, migration_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Storage migration not found")
    record = await session.get(KnowledgeBaseRecord, run.kb_id)
    if (
        record is None
        or record.active_migration_id != run.id
        or record.storage_state not in ("migrating", "needs_attention")
    ):
        raise HTTPException(status_code=409, detail="This storage migration cannot be retried")
    # Scheduling does not remove the durable fence. The worker serializes with
    # every other attempt and revalidates the source snapshot and target ledger.
    schedule_upgrade(retry=True)
    return {"id": run.id, "status": "scheduled"}
