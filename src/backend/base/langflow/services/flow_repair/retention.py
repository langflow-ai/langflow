"""Protected recovery entries also mark flows that require reviewed graph saves."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

REPAIR_RETENTION_REASON = "admin-upgrade-repair"


async def requires_reviewed_graph_save(session: AsyncSession, flow_id: UUID) -> bool:
    from sqlmodel import select

    from langflow.services.database.models.flow_version.model import FlowVersion

    statement = (
        select(FlowVersion.id)
        .where(FlowVersion.flow_id == flow_id, FlowVersion.retained_reason == REPAIR_RETENTION_REASON)
        .limit(1)
    )
    return (await session.exec(statement)).first() is not None
