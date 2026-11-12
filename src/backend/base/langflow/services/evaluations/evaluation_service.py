"""Evaluation configs: create, edit, list and delete (runs live in ``run_service``)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, and_, delete, func, or_
from sqlmodel import col, select

from langflow.services.authorization import DatasetAction, FlowAction
from langflow.services.database.models.evaluation import Dataset, Evaluation, EvaluationResult, EvaluationRun
from langflow.services.database.models.flow.model import Flow
from langflow.services.evaluations.access import load_eval_dataset, load_eval_flow
from langflow.services.evaluations.errors import EvalsConflictError
from langflow.services.evaluations.run_reconcile import active_runs
from langflow.services.evaluations.schemas import EvaluationRead, EvaluationRunRead
from langflow.services.evaluations.versioning import release_unused_versions

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User
    from langflow.services.evaluations.schemas import EvaluationCreate, EvaluationUpdate

DEFAULT_NAME_PREFIX = "Evaluation of"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def to_run_read(run: EvaluationRun) -> EvaluationRunRead:
    return EvaluationRunRead.model_validate(run, from_attributes=True)


async def create_evaluation(session: AsyncSession, user: User, payload: EvaluationCreate) -> Evaluation:
    flow = await load_eval_flow(session, user, payload.flow_id, FlowAction.EXECUTE)
    dataset = await load_eval_dataset(session, user, payload.dataset_id, DatasetAction.READ)
    evaluation = Evaluation(
        user_id=user.id,
        project_id=flow.folder_id,
        flow_id=flow.id,
        dataset_id=dataset.id,
        name=(payload.name or "").strip() or f"{DEFAULT_NAME_PREFIX} {flow.name}"[:255],
        output_vertex_id=payload.output_vertex_id,
        scorers=[spec.model_dump() for spec in payload.scorers],
        pass_threshold=payload.pass_threshold,
    )
    session.add(evaluation)
    await session.flush()
    return evaluation


async def update_evaluation(
    session: AsyncSession, user: User, evaluation: Evaluation, payload: EvaluationUpdate
) -> Evaluation:
    fields = payload.model_fields_set
    if payload.name is not None:
        evaluation.name = payload.name.strip() or evaluation.name
    if payload.dataset_id is not None:
        evaluation.dataset_id = (await load_eval_dataset(session, user, payload.dataset_id, DatasetAction.READ)).id
    if "output_vertex_id" in fields:
        evaluation.output_vertex_id = payload.output_vertex_id
    if payload.scorers is not None:
        evaluation.scorers = [spec.model_dump() for spec in payload.scorers]
    if payload.pass_threshold is not None:
        evaluation.pass_threshold = payload.pass_threshold
    evaluation.updated_at = _now()
    session.add(evaluation)
    await session.flush()
    return evaluation


async def has_active_run(session: AsyncSession, evaluation_id: UUID) -> bool:
    return bool(await active_runs(session, EvaluationRun.evaluation_id == evaluation_id))


def in_project(project_id: UUID) -> ColumnElement[bool]:
    """An evaluation belongs to its flow's current project; only a flow-less one keeps the stored project."""
    return or_(
        Flow.folder_id == project_id,
        and_(col(Evaluation.flow_id).is_(None), Evaluation.project_id == project_id),
    )


async def delete_evaluation(session: AsyncSession, evaluation: Evaluation) -> None:
    if await has_active_run(session, evaluation.id):
        msg = "Cancel the running evaluation before deleting it."
        raise EvalsConflictError(msg)
    runs = (await session.exec(select(EvaluationRun).where(EvaluationRun.evaluation_id == evaluation.id))).all()
    run_ids = [run.id for run in runs]
    version_ids = {run.flow_version_id for run in runs if run.flow_version_id is not None}
    if run_ids:
        await session.exec(delete(EvaluationResult).where(col(EvaluationResult.run_id).in_(run_ids)))
        await session.exec(delete(EvaluationRun).where(col(EvaluationRun.id).in_(run_ids)))
    await session.delete(evaluation)
    await session.flush()
    await release_unused_versions(session, version_ids)


async def list_evaluations(
    session: AsyncSession,
    user: User,
    *,
    project_id: UUID | None,
    flow_id: UUID | None,
    page: int,
    size: int,
) -> tuple[list[Evaluation], int]:
    where = [Evaluation.user_id == user.id]
    if project_id is not None:
        where.append(in_project(project_id))
    if flow_id is not None:
        where.append(Evaluation.flow_id == flow_id)
    joined = select(Evaluation).outerjoin(Flow, col(Flow.id) == Evaluation.flow_id).where(*where)
    total = int((await session.exec(select(func.count()).select_from(joined.subquery()))).one())
    rows = (
        await session.exec(
            joined.order_by(col(Evaluation.updated_at).desc(), col(Evaluation.id)).offset((page - 1) * size).limit(size)
        )
    ).all()
    return list(rows), total


async def _names(session: AsyncSession, model: type[Flow | Dataset], ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    rows = (await session.exec(select(model.id, model.name).where(col(model.id).in_(list(ids))))).all()
    return dict(rows)


async def _flow_projects(session: AsyncSession, ids: set[UUID]) -> dict[UUID, UUID | None]:
    if not ids:
        return {}
    rows = (await session.exec(select(Flow.id, Flow.folder_id).where(col(Flow.id).in_(list(ids))))).all()
    return dict(rows)


async def _last_runs(session: AsyncSession, evaluation_ids: list[UUID]) -> dict[UUID, EvaluationRun]:
    if not evaluation_ids:
        return {}
    newest = (
        select(EvaluationRun.evaluation_id, func.max(EvaluationRun.created_at).label("created_at"))
        .where(col(EvaluationRun.evaluation_id).in_(evaluation_ids))
        .group_by(EvaluationRun.evaluation_id)
        .subquery()
    )
    rows = (
        await session.exec(
            select(EvaluationRun).join(
                newest,
                (newest.c.evaluation_id == EvaluationRun.evaluation_id)
                & (newest.c.created_at == EvaluationRun.created_at),
            )
        )
    ).all()
    return {run.evaluation_id: run for run in rows}


async def to_evaluation_reads(session: AsyncSession, evaluations: list[Evaluation]) -> list[EvaluationRead]:
    flow_ids = {e.flow_id for e in evaluations if e.flow_id is not None}
    flow_names = await _names(session, Flow, flow_ids)
    flow_projects = await _flow_projects(session, flow_ids)
    dataset_names = await _names(session, Dataset, {e.dataset_id for e in evaluations if e.dataset_id is not None})
    last_runs = await _last_runs(session, [e.id for e in evaluations])
    return [
        EvaluationRead(
            id=evaluation.id,
            name=evaluation.name,
            project_id=flow_projects.get(evaluation.flow_id, evaluation.project_id)
            if evaluation.flow_id
            else evaluation.project_id,
            flow_id=evaluation.flow_id,
            flow_name=flow_names.get(evaluation.flow_id) if evaluation.flow_id else None,
            dataset_id=evaluation.dataset_id,
            dataset_name=dataset_names.get(evaluation.dataset_id) if evaluation.dataset_id else None,
            output_vertex_id=evaluation.output_vertex_id,
            scorers=_public_scorers(evaluation.scorers),
            pass_threshold=evaluation.pass_threshold,
            last_run=to_run_read(last_runs[evaluation.id]) if evaluation.id in last_runs else None,
            created_at=evaluation.created_at,
            updated_at=evaluation.updated_at,
        )
        for evaluation in evaluations
    ]


def _public_scorers(scorers: list) -> list[dict]:
    return [spec for spec in scorers if isinstance(spec, dict)]
