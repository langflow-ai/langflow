"""Builder erase for Evals: children first, because SQLite does not enforce the FK cascades."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, update
from sqlmodel import col, select

from langflow.services.data_subjects.batching import BATCH_SIZE, delete_batch
from langflow.services.database.models.evaluation import (
    Dataset,
    DatasetItem,
    Evaluation,
    EvaluationResult,
    EvaluationRun,
)
from langflow.services.database.models.traces.model import SpanTable, TraceTable

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext


def _owned_evaluation_ids(user_id: UUID):
    return select(Evaluation.id).where(Evaluation.user_id == user_id)


def _owned_run_ids(user_id: UUID):
    return select(EvaluationRun.id).where(col(EvaluationRun.evaluation_id).in_(_owned_evaluation_ids(user_id)))


def _trace_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def erase_evaluation_traces(session: AsyncSession, ctx: EraseContext) -> int:
    """Row traces are filed under the evaluated flow, which may belong to someone else: delete them by the results' ids.

    Each processed result's trace id is cleared, so the step ends once no result still points at a trace.
    """
    rows = (
        await session.exec(
            select(EvaluationResult.id, EvaluationResult.trace_id)
            .where(col(EvaluationResult.run_id).in_(_owned_run_ids(ctx.subject_user_id)))
            .where(col(EvaluationResult.trace_id).is_not(None))
            .limit(BATCH_SIZE)
        )
    ).all()
    if not rows:
        return 0
    trace_ids = [trace_id for _, raw in rows if (trace_id := _trace_uuid(raw)) is not None]
    if trace_ids:
        await session.exec(delete(SpanTable).where(col(SpanTable.trace_id).in_(trace_ids)))
        await session.exec(delete(TraceTable).where(col(TraceTable.id).in_(trace_ids)))
    result_ids = [row_id for row_id, _ in rows]
    await session.exec(update(EvaluationResult).where(col(EvaluationResult.id).in_(result_ids)).values(trace_id=None))
    return len(rows)


async def erase_evaluation_results(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(
        session, EvaluationResult, col(EvaluationResult.run_id).in_(_owned_run_ids(ctx.subject_user_id))
    )


async def erase_evaluation_runs(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(
        session,
        EvaluationRun,
        col(EvaluationRun.evaluation_id).in_(_owned_evaluation_ids(ctx.subject_user_id)),
    )


async def reassign_started_runs(session: AsyncSession, ctx: EraseContext) -> int:
    """Runs the subject started on someone else's evaluation stay with that evaluation's owner."""
    owner = select(Evaluation.user_id).where(Evaluation.id == EvaluationRun.evaluation_id).scalar_subquery()
    result = await session.exec(
        update(EvaluationRun).where(EvaluationRun.user_id == ctx.subject_user_id).values(user_id=owner)
    )
    return result.rowcount or 0


async def erase_evaluations(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(session, Evaluation, Evaluation.user_id == ctx.subject_user_id)


async def erase_dataset_items(session: AsyncSession, ctx: EraseContext) -> int:
    owned = select(Dataset.id).where(Dataset.user_id == ctx.subject_user_id)
    return await delete_batch(session, DatasetItem, col(DatasetItem.dataset_id).in_(owned))


async def erase_datasets(session: AsyncSession, ctx: EraseContext) -> int:
    return await delete_batch(session, Dataset, Dataset.user_id == ctx.subject_user_id)


EVALUATION_STEPS = (
    ("evaluation_traces", erase_evaluation_traces),
    ("evaluation_results", erase_evaluation_results),
    ("evaluation_runs", erase_evaluation_runs),
    ("evaluation_run_starters", reassign_started_runs),
    ("evaluations", erase_evaluations),
    ("dataset_items", erase_dataset_items),
    ("datasets", erase_datasets),
)
