"""Start, cancel and read evaluation runs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, update
from sqlmodel import col, select

from langflow.services.authorization import DatasetAction, FlowAction
from langflow.services.database.models.evaluation import EvaluationResult, EvaluationRun
from langflow.services.database.models.evaluation.evaluation import TERMINAL_RUN_STATUSES
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import get_job_service, get_settings_service, get_task_service
from langflow.services.evaluations.access import load_eval_dataset, load_eval_flow
from langflow.services.evaluations.dataset_service import count_items
from langflow.services.evaluations.errors import EvalsConflictError, EvalsNotFoundError, EvalsValidationError
from langflow.services.evaluations.estimate import estimate_run
from langflow.services.evaluations.evaluation_service import has_active_run
from langflow.services.evaluations.flow_checks import check_flow, resolve_output_vertex
from langflow.services.evaluations.runner import cancel_local_run, run_evaluation
from langflow.services.evaluations.summary import build_summary
from langflow.services.evaluations.versioning import pin_history_version, pin_latest

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.evaluation import Evaluation
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.user.model import User

WORKER_LOST_ERROR = "The server stopped while this run was in progress. Finished rows are kept."
ACTIVE_STATUSES = ("queued", "running")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FlowCheckFailedError(EvalsValidationError):
    def __init__(self, issues: list[dict[str, Any]]) -> None:
        super().__init__("; ".join(issue["message"] for issue in issues))
        self.issues = issues


async def _pin_version(
    session: AsyncSession, flow: Flow, user: User, version_id: UUID | None
) -> tuple[FlowVersion, str]:
    if version_id is None:
        return await pin_latest(session, flow, user.id), "latest"
    return await pin_history_version(session, flow.id, version_id), "history"


async def start_evaluation_run(
    session: AsyncSession, user: User, evaluation: Evaluation, flow_version_id: UUID | None
) -> EvaluationRun:
    if evaluation.flow_id is None:
        msg = "The flow of this evaluation was deleted."
        raise EvalsValidationError(msg)
    if evaluation.dataset_id is None:
        msg = "The dataset of this evaluation was deleted. Choose another dataset."
        raise EvalsValidationError(msg)
    flow = await load_eval_flow(session, user, evaluation.flow_id, FlowAction.EXECUTE)
    dataset = await load_eval_dataset(session, user, evaluation.dataset_id, DatasetAction.READ)
    if await has_active_run(session, evaluation.id):
        msg = "This evaluation is already running."
        raise EvalsConflictError(msg)
    items = await count_items(session, dataset.id)
    max_items = get_settings_service().settings.evals_max_items
    if items == 0:
        msg = "The dataset has no items."
        raise EvalsValidationError(msg)
    if items > max_items:
        msg = f"The dataset has {items} items; the limit per run is {max_items}."
        raise EvalsValidationError(msg)
    version, source = await _pin_version(session, flow, user, flow_version_id)
    report = check_flow(version.data, evaluation.output_vertex_id)
    if report.blocking:
        raise FlowCheckFailedError([issue.model_dump() for issue in report.blocking])
    estimate = await estimate_run(
        session,
        flow_id=flow.id,
        flow_data=version.data,
        dataset_id=dataset.id,
        scorers=evaluation.scorers,
        judge_max_output_tokens=get_settings_service().settings.evals_judge_max_output_tokens,
    )
    run = EvaluationRun(
        evaluation_id=evaluation.id,
        user_id=user.id,
        flow_id=flow.id,
        flow_name=flow.name,
        flow_version_id=version.id,
        flow_version_number=version.version_number,
        flow_version_source=source,
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        dataset_revision=dataset.revision,
        config={
            "scorers": evaluation.scorers,
            "pass_threshold": evaluation.pass_threshold,
            "output_vertex_id": resolve_output_vertex(version.data or {}, evaluation.output_vertex_id),
        },
        status="queued",
        total_items=items,
        estimate=estimate.model_dump(),
    )
    session.add(run)
    await session.flush()
    job_id = uuid.uuid4()
    run.job_id = job_id
    session.add(run)
    # The coordinator reads the run in its own session, so it must be committed before launch.
    await session.commit()
    await _launch_coordinator(job_id, run.id, flow.id, user.id)
    return run


async def _launch_coordinator(job_id: UUID, run_id: UUID, flow_id: UUID, user_id: UUID) -> None:
    job_service = get_job_service()
    await job_service.create_job(
        job_id=job_id,
        flow_id=flow_id,
        job_type=JobType.EVALUATION,
        asset_id=run_id,
        asset_type="evaluation_run",
        user_id=user_id,
        heartbeat=True,
    )
    await get_task_service().fire_and_forget_task(
        job_service.execute_with_status,
        job_id=job_id,
        run_coro_func=run_evaluation,
        run_id=run_id,
        keep_alive=True,
    )


async def cancel_evaluation_run(session: AsyncSession, run: EvaluationRun) -> EvaluationRun:
    if run.status in TERMINAL_RUN_STATUSES:
        msg = f"The run already finished ({run.status})."
        raise EvalsConflictError(msg)
    await session.exec(
        update(EvaluationRun)
        .where(EvaluationRun.id == run.id, col(EvaluationRun.status).in_(ACTIVE_STATUSES))
        .values(status="cancelled", finished_at=_now())
    )
    await session.commit()
    cancel_local_run(run.id)
    await session.refresh(run)
    return run


async def reconcile_runs(session: AsyncSession, runs: list[EvaluationRun]) -> None:
    """Fail active runs whose job is gone or finished: the process that ran them stopped."""
    active = [run for run in runs if run.status in ACTIVE_STATUSES]
    job_ids = [run.job_id for run in active if run.job_id is not None]
    if not active:
        return
    jobs = {job.job_id: job for job in (await session.exec(select(Job).where(col(Job.job_id).in_(job_ids)))).all()}
    lost = [
        run
        for run in active
        if run.job_id not in jobs or jobs[run.job_id].status not in (JobStatus.QUEUED, JobStatus.IN_PROGRESS)
    ]
    if not lost:
        return
    await session.exec(
        update(EvaluationRun)
        .where(col(EvaluationRun.id).in_([run.id for run in lost]), col(EvaluationRun.status).in_(ACTIVE_STATUSES))
        .values(status="failed", error=WORKER_LOST_ERROR, finished_at=_now())
    )
    await session.commit()
    for run in lost:
        await session.refresh(run)


async def get_run(session: AsyncSession, user: User, run_id: UUID) -> EvaluationRun:
    run = (
        await session.exec(select(EvaluationRun).where(EvaluationRun.id == run_id, EvaluationRun.user_id == user.id))
    ).first()
    if run is None:
        msg = "Evaluation run not found"
        raise EvalsNotFoundError(msg)
    await reconcile_runs(session, [run])
    return run


async def list_runs(
    session: AsyncSession, evaluation_id: UUID, *, page: int, size: int
) -> tuple[list[EvaluationRun], int]:
    where = [EvaluationRun.evaluation_id == evaluation_id]
    total = int((await session.exec(select(func.count()).select_from(EvaluationRun).where(*where))).one())
    runs = list(
        (
            await session.exec(
                select(EvaluationRun)
                .where(*where)
                .order_by(col(EvaluationRun.created_at).desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()
    )
    await reconcile_runs(session, runs)
    return runs, total


async def list_results(
    session: AsyncSession, run_id: UUID, *, passed: bool | None, page: int, size: int
) -> tuple[list[EvaluationResult], int]:
    where = [EvaluationResult.run_id == run_id]
    if passed is not None:
        where.append(EvaluationResult.passed == passed)
    total = int((await session.exec(select(func.count()).select_from(EvaluationResult).where(*where))).one())
    rows = (
        await session.exec(
            select(EvaluationResult)
            .where(*where)
            .order_by(col(EvaluationResult.position))
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return list(rows), total


async def live_summary(session: AsyncSession, run: EvaluationRun) -> dict[str, Any] | None:
    """Aggregates over the rows finished so far, for a run still in progress; never persisted."""
    if run.status not in ACTIVE_STATUSES or run.summary is not None:
        return run.summary
    results = list((await session.exec(select(EvaluationResult).where(EvaluationResult.run_id == run.id))).all())
    if not results:
        return None
    return build_summary(results, [spec["name"] for spec in run.config.get("scorers", [])])
