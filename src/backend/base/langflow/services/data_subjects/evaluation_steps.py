"""Builder erase for Evals: children first, because SQLite does not enforce the FK cascades."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlmodel import col, select

from langflow.services.data_subjects.batching import delete_batch
from langflow.services.database.models.evaluation import (
    Dataset,
    DatasetItem,
    Evaluation,
    EvaluationResult,
    EvaluationRun,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.context import EraseContext


def _owned_evaluation_ids(user_id: UUID):
    return select(Evaluation.id).where(Evaluation.user_id == user_id)


def _owned_run_ids(user_id: UUID):
    return select(EvaluationRun.id).where(col(EvaluationRun.evaluation_id).in_(_owned_evaluation_ids(user_id)))


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
    ("evaluation_results", erase_evaluation_results),
    ("evaluation_runs", erase_evaluation_runs),
    ("evaluation_run_starters", reassign_started_runs),
    ("evaluations", erase_evaluations),
    ("dataset_items", erase_dataset_items),
    ("datasets", erase_datasets),
)
