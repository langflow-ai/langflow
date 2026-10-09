"""End-user erase: one person's rows inside the customer's flows; the flows keep working."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import true
from sqlmodel import and_, col, select

from langflow.services.data_subjects.batching import delete_batch, delete_job_batch, delete_trace_batch
from langflow.services.data_subjects.end_user_memory import erase_memory_base_vectors
from langflow.services.data_subjects.transactions import end_user_transactions
from langflow.services.database.models.jobs.model import Job
from langflow.services.database.models.memory_base.model import (
    MemoryBase,
    MemoryBasePreprocessingOutput,
    MemoryBaseSession,
    MemoryBaseWorkflowRun,
    MessageIngestionRecord,
)
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext
    from langflow.services.data_subjects.identity import EndUserKeys

    Step = Callable[[AsyncSession, EraseContext], Awaitable[int]]

LIKE_ESCAPE = "\\"


def _keys(ctx: EraseContext) -> EndUserKeys:
    if ctx.end_user is None:
        msg = "end-user step called without end-user keys"
        raise RuntimeError(msg)
    return ctx.end_user


def _in_scope(flow_column, ctx: EraseContext) -> ColumnElement[bool]:
    if not ctx.scope_flow_ids:
        return true()
    return col(flow_column).in_(ctx.scope_flow_ids)


def _session_matches(session_column, ctx: EraseContext) -> ColumnElement[bool]:
    return col(session_column).like(_keys(ctx).session_like_pattern, escape=LIKE_ESCAPE)


def _end_user_jobs(ctx: EraseContext):
    return select(Job.job_id).where(
        col(Job.job_metadata)["end_user_id"].as_string() == _keys(ctx).raw_id,
        _in_scope(Job.flow_id, ctx),
    )


def _scoped_memory_bases(ctx: EraseContext):
    return select(MemoryBase.id).where(_in_scope(MemoryBase.flow_id, ctx))


async def erase_vertex_builds(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(
        session,
        VertexBuildTable,
        col(VertexBuildTable.job_id).in_(_end_user_jobs(ctx)),
        pk=VertexBuildTable.build_id,
    )


async def erase_messages(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(
        session,
        MessageTable,
        MessageTable.user_id == _keys(ctx).message_owner_id,
        _session_matches(MessageTable.session_id, ctx),
        _in_scope(MessageTable.flow_id, ctx),
    )


async def erase_traces(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_trace_batch(
        session, _session_matches(TraceTable.session_id, ctx), _in_scope(TraceTable.flow_id, ctx)
    )


async def erase_transactions(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(session, TransactionTable, end_user_transactions(_keys(ctx), ctx.scope_flow_ids))


def _memory_rows(model) -> Step:
    async def step(session: AsyncSession, ctx: EraseContext) -> int:
        return await delete_batch(
            session,
            model,
            and_(_session_matches(model.session_id, ctx), col(model.memory_base_id).in_(_scoped_memory_bases(ctx))),
        )

    return step


async def erase_jobs(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_job_batch(session, col(Job.job_id).in_(_end_user_jobs(ctx)))


END_USER_STEPS: tuple[tuple[str, Step], ...] = (
    ("vertex_builds", erase_vertex_builds),
    ("messages", erase_messages),
    ("traces", erase_traces),
    ("transactions", erase_transactions),
    ("memory_ingestion_records", _memory_rows(MessageIngestionRecord)),
    ("memory_preprocessing_outputs", _memory_rows(MemoryBasePreprocessingOutput)),
    ("memory_workflow_runs", _memory_rows(MemoryBaseWorkflowRun)),
    ("memory_sessions", _memory_rows(MemoryBaseSession)),
    ("memory_vectors", erase_memory_base_vectors),
    ("jobs", erase_jobs),
)
