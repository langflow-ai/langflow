"""Builder erase: knowledge bases, one per call, including their remote collection and local directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.utils.util_strings import escape_like_pattern
from sqlmodel import col, select

from langflow.services.data_subjects.batching import delete_batch
from langflow.services.data_subjects.export import LIKE_ESCAPE
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.knowledge_base_storage_migration import KnowledgeBaseStorageMigration
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_job_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext


async def erase_knowledge_bases(session: AsyncSession, ctx: EraseContext) -> int:
    # The KB delete route's own path: drain writers, fence and delete the store, then the row.
    # A store that cannot be reached raises, so the step is retried and holds the request open.
    from langflow.api.utils import knowledge_base_service
    from langflow.api.v1 import knowledge_bases as kb_routes

    record = (
        await session.exec(
            select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.user_id == ctx.subject_user_id).limit(1)
        )
    ).first()
    if record is None:
        return 0
    await kb_routes._cancel_inflight_ingestion_for_kb(  # noqa: SLF001
        kb_name=record.name, asset_id=record.id, job_service=get_job_service()
    )
    await knowledge_base_service.delete_record(record.id)
    return 1


async def erase_knowledge_base_upgrades(session: AsyncSession, ctx: EraseContext) -> int:
    # Ledger rows outlive their knowledge base and name it by its `<username>/<name>` directory.
    owner = await session.get(User, ctx.subject_user_id)
    if owner is None:
        return 0
    prefix = f"{escape_like_pattern(owner.username)}/%"
    return await delete_batch(
        session,
        KnowledgeBaseStorageMigration,
        col(KnowledgeBaseStorageMigration.source_identity).like(prefix, escape=LIKE_ESCAPE),
    )
