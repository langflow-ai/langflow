"""Eval Suite authoring and immutable evaluation records."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from lfx.projects.evaluations import EvalSuiteConfig, scorer_baseline
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import col, select
from starlette.concurrency import run_in_threadpool

from langflow.api.utils import CurrentActiveUser
from langflow.services.authorization import FlowAction, ProjectAction, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.flow_bindings import _authorize
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.jobs.model import Job, JobType
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.evaluations.configuration import scorer_choices
from langflow.services.evaluations.runner import present_run, run_suite

router = APIRouter(prefix="/projects/{project_id}/evaluations", tags=["Projects"])


async def eval_project(session, caller, project_id, *, write=False):
    project = await authorized_or_owner_scoped(
        session, Folder, id_column=Folder.id, resource_id=project_id, owner_column=Folder.user_id, owner_id=caller.id
    )
    if project is None:
        raise HTTPException(404, "Evaluation project not found.")
    try:
        await ensure_project_permission(
            caller,
            ProjectAction.WRITE if write else ProjectAction.READ,
            project_id=project.id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, "Evaluation project not found.") from exc
    if project.project_type != "eval-suite":
        raise HTTPException(422, "Choose an Eval Suite project.")
    return project


@router.get("")
async def read_suite(project_id: UUID, current_user: CurrentActiveUser):
    async with session_scope() as session:
        project = await eval_project(session, current_user, project_id)
        suite = EvalSuiteConfig.model_validate(project.project_config or {})
        flows = (
            await session.exec(select(Flow).where(Flow.folder_id == project_id, col(Flow.is_component).is_(False)))
        ).all()
        scorers = []
        for flow in flows:
            try:
                scorers.extend(await scorer_choices(session, current_user, flow))
            except (HTTPException, ValueError, KeyError, TypeError):
                continue
        targets = []
        for identity, mount in get_settings_service().settings.harness_candidate_mounts.items():
            if not mount.enabled:
                continue
            try:
                flow = await _authorize(session, current_user, str(identity), FlowAction.EXECUTE)
                targets.append({"workflow_id": str(identity), "name": flow.name, "candidate_digest": mount.digest})
            except HTTPException:
                continue
    return {"config": suite.model_dump(mode="json"), "revision": suite.revision, "scorers": scorers, "targets": targets}


@router.post("/scorer-baseline")
async def prepare_scorer(project_id: UUID, current_user: CurrentActiveUser):
    async with session_scope() as session:
        await eval_project(session, current_user, project_id, write=True)
    return await run_in_threadpool(scorer_baseline)


class EvalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_candidate_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/runs", status_code=202)
async def execute_suite(project_id: UUID, body: EvalRunRequest, request: Request, current_user: CurrentActiveUser):
    async with session_scope() as session:
        project = await eval_project(session, current_user, project_id, write=True)
        suite = EvalSuiteConfig.model_validate(project.project_config or {})
    try:
        return await run_suite(
            project, suite, current_user, request, body.run_id, body.expected_revision, body.expected_candidate_digest
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/runs")
async def list_evaluations(project_id: UUID, current_user: CurrentActiveUser):
    async with session_scope() as session:
        await eval_project(session, current_user, project_id)
        rows = (
            await session.exec(
                select(Job)
                .where(Job.asset_id == project_id, Job.type == JobType.EVALUATION, Job.user_id == current_user.id)
                .order_by(col(Job.created_timestamp).desc())
                .limit(20)
            )
        ).all()
        return [present_run(job) for job in rows]


@router.get("/runs/{run_id}")
async def read_evaluation(project_id: UUID, run_id: UUID, current_user: CurrentActiveUser):
    async with session_scope() as session:
        await eval_project(session, current_user, project_id)
        job = await session.get(Job, run_id)
        if (
            job is None
            or job.user_id != current_user.id
            or job.asset_id != project_id
            or job.type != JobType.EVALUATION
        ):
            raise HTTPException(404, "Evaluation not found.")
        return present_run(job)


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel_evaluation(project_id: UUID, run_id: UUID, current_user: CurrentActiveUser):
    from langflow.services.deps import get_background_execution_service, get_job_service
    from langflow.services.evaluations.state import ACTIVE, save_progress

    async with session_scope() as session:
        await eval_project(session, current_user, project_id, write=True)
    jobs = get_job_service()
    for _ in range(10):
        job = await jobs.get_job_by_job_id(run_id)
        if (
            job is None
            or job.user_id != current_user.id
            or job.asset_id != project_id
            or job.type != JobType.EVALUATION
        ):
            raise HTTPException(404, "Evaluation not found.")
        if job.status not in ACTIVE or (job.result or {}).get("cancel_requested"):
            return present_run(job)
        if (job.job_metadata or {}).get("evaluation_format") != 1:
            raise HTTPException(409, "This legacy evaluation does not support cancellation.")
        progress = {**job.result, "cancel_requested": True, "pending_approval": None}
        if await save_progress(job, progress, job.status):
            await get_background_execution_service().start()
            return present_run(await jobs.get_job_by_job_id(run_id))
    raise HTTPException(409, "Evaluation progress changed. Refresh its status and retry cancellation.")
