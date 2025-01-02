from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser
from langflow.api.v1.endpoints import simple_run_flow_task
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.job.model import Job, JobRead, JobStatus
from langflow.services.deps import get_jobs_service, session_scope
from langflow.services.jobs.service import JobsService

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class CreateJobRequest(BaseModel):
    """Request model for creating a job.

    Attributes:
        name (Optional[str]): An optional user-defined name for the job.
        input_request (SimplifiedAPIRequest): The payload containing all necessary data
            to run the specified flow. This includes input parameters, stream flags, and other
            relevant options.
    """

    name: str | None = None
    input_request: SimplifiedAPIRequest = Field(..., description="Input request for the flow")


@router.post("/{flow_id_or_name}", response_model=str)
async def create_job(
    request: CreateJobRequest,
    user: CurrentActiveUser,
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
) -> str:
    """Create a new job for a given flow.

    This endpoint schedules a background job to run the specified flow, using
    the provided input data and job name. The newly created job will be stored
    in the job repository and processed asynchronously.

    Args:
        request (CreateJobRequest): The job creation request parameters, including
            a flow input and an optional job name.
        user (CurrentActiveUser): The currently authenticated user.
        flow (Flow): The flow object identified by ID or name, obtained via dependency injection.

    Returns:
        str: The unique identifier (UUID string) of the newly created job.

    Raises:
        HTTPException: If the job creation fails for any reason, it returns a 500 status code.
    """
    try:
        jobs_service = get_jobs_service()
        return await jobs_service.create_job(
            task_func=simple_run_flow_task,
            run_at=None,
            name=request.name,
            kwargs={
                "flow": flow,
                "input_request": request.input_request,
                "stream": False,
                "api_key_user": user,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    user: CurrentActiveUser,
) -> JobRead:
    """Retrieve details for a specific job by its unique identifier.

    This endpoint fetches the job data from the database, verifying ownership by the
    currently authenticated user. If the job does not exist or the user does not own the job,
    a 404 is raised.

    Args:
        job_id (str): The unique identifier of the job to retrieve.
        user (CurrentActiveUser): The currently authenticated user.

    Returns:
        JobRead: The job details, including status, name, and timestamps.

    Raises:
        HTTPException:
            - 404 if the job does not exist or is not owned by the current user.
    """
    task_service: JobsService = get_jobs_service()
    task = await task_service.get_job(job_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"Job: {task}")
    async with session_scope() as session:
        if not user.id:
            msg = "User not found"
            raise HTTPException(status_code=404, detail=msg)
        stmt = select(Job).where(Job.id == job_id, Job.user_id == user.id)
        return (await session.exec(stmt)).first()


@router.get("/", response_model=list[JobRead])
async def get_jobs(
    user: CurrentActiveUser,
    task_service: Annotated[JobsService, Depends(get_jobs_service)],
    pending: bool | None = None,
    status: JobStatus | None = None,
) -> list[JobRead]:
    """Retrieve a list of jobs associated with the current user.

    This endpoint allows filtering jobs based on their 'pending' state (an APSJob.job_state attribute)
    and/or their status in the database. If 'pending' is not provided, it will simply return all
    available jobs for the user, optionally filtered by a specified status.

    Args:
        user (CurrentActiveUser): The currently authenticated user.
        task_service (JobsService): The service used to perform job-related operations.
        pending (Optional[bool]): When provided, filters jobs by whether they are pending.
        status (Optional[JobStatus]): When provided, filters jobs by a specific status
            (e.g., PENDING, COMPLETED, FAILED, etc.).

    Returns:
        list[JobRead]: A list of job records matching the given criteria.
    """
    if pending is not None:
        jobs = await task_service.get_jobs(user_id=user.id, pending=pending, status=status)
        ids = [job.id for job in jobs]
        async with session_scope() as session:
            stmt = select(Job).where(col(Job.id).in_(ids))
            return (await session.exec(stmt)).all()
    else:
        async with session_scope() as session:
            stmt = select(Job).where(Job.user_id == user.id)
            if status is not None:
                stmt = stmt.where(Job.status == status)
            return (await session.exec(stmt)).all()


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    user: CurrentActiveUser,
    task_service: Annotated[JobsService, Depends(get_jobs_service)],
) -> bool:
    """Cancel a specific job and remove it from the scheduler.

    This endpoint attempts to cancel the job corresponding to the provided job ID. If successful,
    it returns True. If the job does not exist or is not owned by the current user, a 404 is raised.

    Args:
        job_id (str): The unique identifier of the job to cancel.
        user (CurrentActiveUser): The currently authenticated user.
        task_service (JobsService): A reference to the job service handling cancellation logic.

    Returns:
        bool: True if the job was successfully canceled.

    Raises:
        HTTPException:
            - 404 if the job is not found.
    """
    success = await task_service.cancel_job(job_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return True
