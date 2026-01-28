"""Job service for managing workflow job status and tracking."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from langflow.services.base import Service
from langflow.services.database.models.jobs.crud import get_job_by_job_id, get_jobs_by_flow_id

if TYPE_CHECKING:
    from langflow.services.database.models.jobs.model import Job, JobStatus


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
        from langflow.services.deps import session_scope

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
        from langflow.services.deps import session_scope

        if isinstance(job_id, str):
            job_id = UUID(job_id)

        async with session_scope() as session:
            return await get_job_by_job_id(session, job_id)

    async def create_job(self, job_id: UUID, flow_id: UUID) -> Job:
        """Create a new job record with QUEUED status.

        Args:
            job_id: The job ID
            flow_id: The flow ID

        Returns:
            Created Job object
        """
        from langflow.services.database.models.jobs.model import Job, JobStatus
        from langflow.services.deps import session_scope

        if isinstance(job_id, str):
            job_id = UUID(job_id)

        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        async with session_scope() as session:
            job = Job(job_id=job_id, flow_id=flow_id, status=JobStatus.QUEUED)
            session.add(job)
            await session.commit()
            await session.refresh(job)
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
        from datetime import datetime, timezone

        from langflow.services.database.models.jobs.crud import update_job_status
        from langflow.services.deps import session_scope

        async with session_scope() as session:
            job = await update_job_status(session, job_id, status)
            if job and finished_timestamp:
                job.finished_timestamp = datetime.now(timezone.utc)
                session.add(job)
                await session.commit()
                await session.refresh(job)
            return job

    async def with_status_updates(self, job_id: UUID, flow_id: UUID, run_graph_func, *args, **kwargs):
        """Wrapper that manages job status lifecycle around run_graph_internal.

        This function:
        1. Creates a job record with QUEUED status
        2. Updates status to IN_PROGRESS before execution
        3. Executes the wrapped function
        4. Updates status to COMPLETED on success or FAILED on error
        5. Sets finished_timestamp when done

        Args:
            job_id: The job ID
            flow_id: The flow ID
            run_graph_func: The function to wrap (typically run_graph_internal)
            *args: Positional arguments to pass to run_graph_func
            **kwargs: Keyword arguments to pass to run_graph_func

        Returns:
            The result from run_graph_func

        Raises:
            Exception: Re-raises any exception from run_graph_func after updating status
        """
        from langflow.services.database.models.jobs.model import JobStatus

        try:
            # Update to IN_PROGRESS
            await self.update_job_status(job_id, JobStatus.IN_PROGRESS)

            # Execute the wrapped function
            kwargs["flow_id"] = str(flow_id)
            result = await run_graph_func(*args, **kwargs)

        except AssertionError:
            # Handle missing required arguments
            await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise

        except asyncio.TimeoutError:
            # Handle timeout specifically
            await self.update_job_status(job_id, JobStatus.TIMED_OUT, finished_timestamp=True)
            raise

        except asyncio.CancelledError:
            # Handle cancellation
            await self.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)
            raise

        except Exception:
            # Handle any other error
            await self.update_job_status(job_id, JobStatus.FAILED, finished_timestamp=True)
            raise
        else:
            # Update to COMPLETED
            await self.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
            return result
