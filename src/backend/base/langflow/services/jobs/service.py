"""Job service for managing workflow job status and tracking."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from langflow.services.base import Service
from langflow.services.database.models.jobs.crud import (
    get_job_by_job_id,
    get_jobs_by_flow_id,
    get_latest_jobs_by_asset_ids,
    update_job_status,
)
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import session_scope


class JobService(Service):
    """Service for managing workflow jobs."""

    name = "jobs_service"

    def __init__(self):
        """Initialize the job service."""
        self.set_ready()

    async def get_jobs_by_flow_id(self, flow_id: UUID | str, page: int = 1, page_size: int = 10) -> list[Job]:
        """Get jobs for a specific flow with pagination.

        Args:
            flow_id: The flow ID to filter jobs by
            page: Page number (1-indexed)
            page_size: Number of jobs per page

        Returns:
            List of Job objects for the specified flow
        """
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        async with session_scope() as session:
            return await get_jobs_by_flow_id(session, flow_id, page=page, size=page_size)

    async def get_job_by_job_id(self, job_id: UUID | str) -> Job | None:
        """Get job for a specific job ID.

        Args:
            job_id: The job ID to filter jobs by

        Returns:
            Job object for the specified job ID
        """
        if isinstance(job_id, str):
            job_id = UUID(job_id)

        async with session_scope() as session:
            return await get_job_by_job_id(session, job_id)

    async def create_job(
        self,
        job_id: UUID,
        flow_id: UUID,
        job_type: JobType = JobType.WORKFLOW,
        asset_id: UUID | None = None,
        asset_type: str | None = None,
    ) -> Job:
        """Create a new job record with QUEUED status.

        Args:
            job_id: The job ID
            flow_id: The flow ID
            job_type: The job type
            asset_id: The asset ID
            asset_type: The asset type

        Returns:
            Created Job object
        """
        if isinstance(job_id, str):
            job_id = UUID(job_id)

        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=flow_id,
                status=JobStatus.QUEUED,
                type=job_type,
                asset_id=asset_id,
                asset_type=asset_type,
            )
            session.add(job)
            await session.flush()
            return job

    async def update_job_status(
        self, job_id: UUID, status: JobStatus, *, finished_timestamp: bool = False
    ) -> Job | None:
        """Update job status and optionally set finished timestamp.

        Args:
            job_id: The job ID to update
            status: New status value
            finished_timestamp: If True, set finished_timestamp to current time

        Returns:
            Updated Job object or None if not found
        """
        async with session_scope() as session:
            job = await update_job_status(session, job_id, status)
            if job and finished_timestamp:
                job.finished_timestamp = datetime.now(timezone.utc)
                session.add(job)
                await session.flush()
            return job

    async def get_latest_jobs_by_asset_ids(self, asset_ids: Sequence[UUID | str]) -> dict[UUID, Job]:
        """Get the latest job for each asset ID in a single batch query.

        Args:
            asset_ids: List of asset IDs (UUID or string) to fetch jobs for

        Returns:
            Dictionary mapping asset_id (UUID) to the latest Job object
        """
        # Convert all asset_ids to UUID
        uuid_asset_ids = [UUID(aid) if isinstance(aid, str) else aid for aid in asset_ids]

        async with session_scope() as session:
            return await get_latest_jobs_by_asset_ids(session, uuid_asset_ids)

    async def execute_with_status(self, job_id: UUID, run_coro_func, *args, **kwargs):
        """Wrapper that manages job status lifecycle around a coroutine.

        This function:
        1. Updates status to IN_PROGRESS before execution
        2. Executes the wrapped function
        3. Updates status to COMPLETED on success or FAILED on error
        4. Sets finished_timestamp when done

        Args:
            job_id: The job ID
            run_coro_func: The coroutine function to wrap
            *args: Positional arguments to pass to run_coro_func
            **kwargs: Keyword arguments to pass to run_coro_func

        Returns:
            The result from run_coro_func

        Raises:
            Exception: Re-raises any exception from run_coro_func after updating status
        """
        from lfx.log import logger

        await logger.ainfo(f"Starting job execution: job_id={job_id}")

        try:
            # Update to IN_PROGRESS
            await logger.adebug(f"Updating job {job_id} status to IN_PROGRESS")
            await self.update_job_status(job_id, JobStatus.IN_PROGRESS)

            # Execute the wrapped function
            await logger.ainfo(f"Executing job function for job_id={job_id}")
            result = await run_coro_func(*args, **kwargs)

        except AssertionError as e:
            # Handle missing required arguments
            await logger.aerror(f"Job {job_id} failed with AssertionError: {e}")
            await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise

        except asyncio.TimeoutError as e:
            # Handle timeout specifically
            await logger.aerror(f"Job {job_id} timed out: {e}")
            await self.update_job_status(job_id, JobStatus.TIMED_OUT, finished_timestamp=True)
            raise

        except asyncio.CancelledError as exc:
            # Check the message code to determine if this was user-initiated or system-initiated
            if exc.args and exc.args[0] == "LANGFLOW_USER_CANCELLED":
                # User-initiated cancellation, update status to CANCELLED
                await logger.awarning(f"Job {job_id} was cancelled by user")
                await self.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)
            else:
                # System-initiated cancellation - update status to FAILED
                await logger.aerror(f"Job {job_id} was cancelled by system")
                await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise

        except Exception as e:
            # Handle any other error
            await logger.aexception(f"Job {job_id} failed with unexpected error: {e}")
            await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise
        else:
            # Update to COMPLETED
            await logger.ainfo(f"Job {job_id} completed successfully")
            await self.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
            return result
