"""Queries over a flow's history rows and checkpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.model import FlowVersion

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def anchors_of(flow_id: UUID):
    """Select the checkpoints of a flow that replay may start from."""
    return select(FlowVersion).where(
        FlowVersion.flow_id == flow_id,
        col(FlowVersion.operation_revision).is_not(None),
        col(FlowVersion.graph_hash).is_not(None),
        col(FlowVersion.view_only).is_(False),
    )


async def latest_anchor_at_or_before(session: AsyncSession, flow_id: UUID, revision: int) -> FlowVersion | None:
    """Return the newest checkpoint whose graph is at or before ``revision``."""
    statement = (
        anchors_of(flow_id)
        .where(col(FlowVersion.operation_revision) <= revision)
        .order_by(col(FlowVersion.operation_revision).desc(), col(FlowVersion.created_at).desc())
        .limit(1)
    )
    return (await session.exec(statement)).first()


async def has_anchor(session: AsyncSession, flow_id: UUID) -> bool:
    """Return whether the flow's history has started, which its revision-0 system checkpoint marks.

    Only a system checkpoint counts: a saved version can be deleted or pruned,
    so it may shorten replay but never be the anchor history depends on.
    """
    statement = (
        anchors_of(flow_id)
        .where(col(FlowVersion.operation_revision) == 0, col(FlowVersion.version_number).is_(None))
        .limit(1)
    )
    return (await session.exec(statement)).first() is not None


async def rows_covering(session: AsyncSession, flow_id: UUID, *, after: int, through: int) -> list[FlowOperation]:
    """Return the rows holding revisions ``after + 1`` through ``through``, in order."""
    statement = (
        select(FlowOperation)
        .where(
            FlowOperation.flow_id == flow_id,
            col(FlowOperation.end_revision) > after,
            col(FlowOperation.start_revision) <= through,
        )
        .order_by(col(FlowOperation.start_revision))
    )
    return list((await session.exec(statement)).all())
