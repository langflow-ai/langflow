"""Authenticated upgrade progress and exceptional retry controls."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from lfx.log.logger import logger
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_
from sqlmodel import col, select

from langflow.api.utils import DbSession
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.knowledge_base_storage.cleanup import retry_pending_cleanup
from langflow.services.knowledge_base_storage.coordinator import inventory_status, schedule_upgrade
from langflow.services.knowledge_base_storage.runtime import StorageUnavailableError

router = APIRouter(prefix="/knowledge-base-storage", tags=["Knowledge Base Upgrade"])

_GUIDANCE = {
    "maintenance_required": "Use the managed upgrade controller to establish the stopped-worker receipt and backup.",
    "remote_source_requires_migration": "Migrate the remote collection to a configured pgVector or OpenSearch store.",
    "validation_failed": "The copy failed validation. Preserve the original source and inspect the upgrade logs.",
    "storage_changed": "Routing changed during upgrade. Inspect the authoritative KB record before retrying.",
    "interrupted": "The upgrade was interrupted. Retry resumes the unpublished generation safely.",
    "migration_failed": "Verify helper availability, source compatibility and free disk space, then retry.",
}


class CleanupRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_generation: int = Field(gt=0, strict=True)


@router.get("/inventory")
async def get_inventory(_admin: Annotated[User, Depends(get_current_active_superuser)]):
    return inventory_status()


@router.get("/pending-cleanup")
async def pending_cleanup(session: DbSession, _admin: Annotated[User, Depends(get_current_active_superuser)]):
    rows = (
        await session.exec(
            select(KnowledgeBaseRecord)
            .where(col(KnowledgeBaseRecord.storage_state).in_(("deleting", "deleted")))
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


@router.get("/migrations")
async def list_migrations(session: DbSession, _admin: Annotated[User, Depends(get_current_active_superuser)]):
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
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.post("/migrations/{migration_id}/retry", status_code=202)
async def retry_migration(
    migration_id: UUID, session: DbSession, _admin: Annotated[User, Depends(get_current_active_superuser)]
):
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
    schedule_upgrade()
    return {"id": run.id, "status": "scheduled"}
