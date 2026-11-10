"""Builder erase: the flows the person owns, one flow at a time, largest tables in batches first."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlmodel import col, select

from langflow.api.utils.flow_utils import cascade_delete_flow
from langflow.services.data_subjects.batching import (
    BATCH_SIZE,
    delete_batch,
    delete_job_batch,
    delete_trace_batch,
)
from langflow.services.database.models.a2a.model import A2ATask
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext


async def _next_owned_flow(session: AsyncSession, user_id: UUID) -> UUID | None:
    return (await session.exec(select(Flow.id).where(Flow.user_id == user_id).limit(1))).first()


async def _delete_a2a_tasks(session: AsyncSession, flow_id: UUID) -> int:
    owners = list(
        (
            await session.exec(
                select(A2ATask.owner).where(col(A2ATask.owner).startswith(f"{flow_id}:")).limit(BATCH_SIZE)
            )
        ).all()
    )
    if not owners:
        return 0
    await session.exec(delete(A2ATask).where(col(A2ATask.owner).in_(owners)))
    return len(owners)


async def _drain_flow_history(session: AsyncSession, flow_id: UUID) -> int:
    """Delete one batch of the flow's high-volume rows; 0 once only the flow itself is left."""
    batches = (
        lambda: delete_batch(session, MessageTable, MessageTable.flow_id == flow_id),
        lambda: delete_batch(session, TransactionTable, TransactionTable.flow_id == flow_id),
        lambda: delete_batch(
            session, VertexBuildTable, VertexBuildTable.flow_id == flow_id, pk=VertexBuildTable.build_id
        ),
        lambda: delete_trace_batch(session, TraceTable.flow_id == flow_id),
        lambda: delete_job_batch(session, Job.flow_id == flow_id),
        lambda: _delete_a2a_tasks(session, flow_id),
    )
    for run in batches:
        deleted = await run()
        if deleted:
            return deleted
    return 0


async def erase_owned_flows(session: AsyncSession, ctx: EraseContext) -> int:
    """Process one batch for the next owned flow, then the flow row itself through ``cascade_delete_flow``."""
    flow_id = await _next_owned_flow(session, ctx.subject_user_id)
    if flow_id is None:
        return 0
    drained = await _drain_flow_history(session, flow_id)
    if drained:
        return drained
    await cascade_delete_flow(session, flow_id, memory_base_cleanups=ctx.memory_base_cleanups)
    return 1
