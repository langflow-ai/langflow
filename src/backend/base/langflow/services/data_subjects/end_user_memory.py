"""End-user erase: the person's chunks inside each Memory Base vector collection, one Memory Base per call."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from lfx.base.knowledge_bases.backends import create_backend
from sqlmodel import col, select

from langflow.api.utils.kb_helpers import _coerce_backend_config_value, resolve_local_store_path
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext

CURSOR_KEY = "memory_vectors_after"
DEFAULT_BACKEND = "chroma"


async def _next_memory_base(session: AsyncSession, ctx: EraseContext) -> MemoryBase | None:
    stmt = select(MemoryBase).order_by(col(MemoryBase.id)).limit(1)
    if ctx.scope_flow_ids:
        stmt = stmt.where(col(MemoryBase.flow_id).in_(ctx.scope_flow_ids))
    if after := ctx.cursor.get(CURSOR_KEY):
        stmt = stmt.where(col(MemoryBase.id) > UUID(after))
    return (await session.exec(stmt)).first()


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
    backend_type = (record.backend_type if record else None) or DEFAULT_BACKEND
    backend_config = _coerce_backend_config_value(record.backend_config) if record else {}
    owner = await session.get(User, memory_base.user_id)
    kb_path = None
    if owner is not None:
        kb_path = resolve_local_store_path(
            memory_base.kb_name, owner.username, backend_type=backend_type, backend_config=backend_config
        )
    local_store_missing = kb_path is not None and not kb_path.exists()
    if not local_store_missing:
        backend = create_backend(
            backend_type,
            kb_name=memory_base.kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            user_id=memory_base.user_id,
        )
        await backend.delete_by({"end_user_id": ctx.end_user.raw_id})
    ctx.cursor[CURSOR_KEY] = str(memory_base.id)
    return 1
