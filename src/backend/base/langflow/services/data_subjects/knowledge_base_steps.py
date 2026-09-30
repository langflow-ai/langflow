"""Builder erase: knowledge bases, one per call, including their remote collection and local directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlmodel import select

from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_job_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext


class RemoteCollectionNotDeletedError(RuntimeError):
    """A remote vector collection survived; the row stays so the step can be retried."""


async def erase_knowledge_bases(session: AsyncSession, ctx: EraseContext) -> int:
    # The KB route owns backend routing; reusing its helpers keeps one deletion path.
    from langflow.api.utils.kb_helpers import KBStorageHelper
    from langflow.api.v1 import knowledge_bases as kb_routes

    record = (
        await session.exec(
            select(KnowledgeBaseRecord).where(KnowledgeBaseRecord.user_id == ctx.subject_user_id).limit(1)
        )
    ).first()
    if record is None:
        return 0
    owner = await session.get(User, ctx.subject_user_id)
    if owner is None:
        return 0
    backend_type, backend_config = kb_routes._backend_from_record(record)  # noqa: SLF001
    kb_path = kb_routes._resolve_kb_store_path(  # noqa: SLF001
        record.name, owner, backend_type=backend_type, backend_config=backend_config
    )
    await kb_routes._cancel_inflight_ingestion_for_kb(  # noqa: SLF001
        kb_name=record.name, asset_id=record.id, job_service=get_job_service()
    )
    warning = await kb_routes._delete_remote_backend_collection(  # noqa: SLF001
        kb_name=record.name,
        kb_path=kb_path,
        backend_type_value=backend_type,
        backend_config=backend_config,
        current_user=owner,
    )
    if warning:
        msg = f"Remote collection of knowledge base {record.id} could not be deleted"
        raise RemoteCollectionNotDeletedError(msg)
    await session.exec(delete(KnowledgeBaseRecord).where(KnowledgeBaseRecord.id == record.id))
    if kb_path is not None:
        KBStorageHelper.delete_storage(kb_path, record.name)
    return 1
