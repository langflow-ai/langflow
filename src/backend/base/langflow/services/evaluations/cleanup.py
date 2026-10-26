"""Keep evaluations consistent when the flow or project they point at is deleted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, update
from sqlmodel import col, select

from langflow.services.database.models.evaluation import Evaluation, EvaluationResult, EvaluationRun
from langflow.services.database.models.evaluation.evaluation import TERMINAL_RUN_STATUSES
from langflow.services.database.models.flow_version.model import FlowVersion

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def detach_flow(session: AsyncSession, flow_id: UUID) -> None:
    """Past results stay readable after the flow is gone; Re-run is then refused (no flow)."""
    await session.exec(update(Evaluation).where(Evaluation.flow_id == flow_id).values(flow_id=None))
    version_ids = select(FlowVersion.id).where(FlowVersion.flow_id == flow_id)
    await session.exec(
        update(EvaluationRun).where(col(EvaluationRun.flow_version_id).in_(version_ids)).values(flow_version_id=None)
    )


async def delete_project_evaluations(session: AsyncSession, project_id: UUID) -> None:
    from langflow.services.evaluations.runner import cancel_local_run

    evaluation_ids = list((await session.exec(select(Evaluation.id).where(Evaluation.project_id == project_id))).all())
    if not evaluation_ids:
        return
    runs = (
        await session.exec(
            select(EvaluationRun.id, EvaluationRun.status).where(col(EvaluationRun.evaluation_id).in_(evaluation_ids))
        )
    ).all()
    for run_id, status in runs:
        if status not in TERMINAL_RUN_STATUSES:
            cancel_local_run(run_id)
    run_ids = [run_id for run_id, _ in runs]
    if run_ids:
        await session.exec(delete(EvaluationResult).where(col(EvaluationResult.run_id).in_(run_ids)))
        await session.exec(delete(EvaluationRun).where(col(EvaluationRun.id).in_(run_ids)))
    await session.exec(delete(Evaluation).where(col(Evaluation.id).in_(evaluation_ids)))
