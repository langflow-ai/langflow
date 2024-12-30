from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent, JobExecutionEvent
from apscheduler.schedulers.base import SchedulerAlreadyRunningError
from apscheduler.triggers.date import DateTrigger
from fastapi.encoders import jsonable_encoder
from loguru import logger
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.job.model import Job, JobStatus
from langflow.services.deps import session_scope
from langflow.services.task.jobstore import AsyncSQLModelJobStore
from langflow.services.task.scheduler import AsyncScheduler

if TYPE_CHECKING:
    from collections.abc import Callable

    from apscheduler.job import Job as APSJob

    from langflow.services.database.service import DatabaseService
    from langflow.services.settings.service import SettingsService


class TaskService(Service):
    """Service for managing tasks and scheduled flows."""

    name = "task_service"

    def __init__(self, settings_service: SettingsService, database_service: DatabaseService):
        self.settings_service = settings_service
        self._started = False
        self.scheduler: AsyncScheduler | None = None
        self.job_store: AsyncSQLModelJobStore | None = None
        self.database_service = database_service

    async def setup(self):
        """Initialize the scheduler."""
        self.scheduler = AsyncScheduler()
        await self.scheduler.configure()
        self.job_store = AsyncSQLModelJobStore()
        await self.scheduler.add_jobstore(self.job_store, "default")

        # Add event listeners
        await self.scheduler.add_listener(self._handle_job_executed, EVENT_JOB_EXECUTED)
        await self.scheduler.add_listener(self._handle_job_error, EVENT_JOB_ERROR)

    async def _ensure_scheduler_running(self):
        """Ensure the scheduler is running."""
        if not self._started:
            if self.scheduler is None:
                await self.setup()
            try:
                await self.scheduler.start(paused=False)
                self._started = True
            except SchedulerAlreadyRunningError:
                pass

    async def _handle_job_executed(self, event: JobExecutionEvent) -> None:
        """Handle job executed event."""
        await self._ensure_scheduler_running()
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == event.job_id)
            job = (await session.exec(stmt)).first()
            if job:
                job.status = JobStatus.COMPLETED
                try:
                    serialized_result = jsonable_encoder(
                        event.retval, custom_encoder={datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}
                    )
                except (TypeError, ValueError) as e:
                    logger.error("Error serializing result: %s", str(e))
                    serialized_result = {"output": str(event.retval)}
                job.result = serialized_result if isinstance(serialized_result, dict) else {"output": str(event.retval)}
                session.add(job)
                await session.commit()

    async def _handle_job_error(self, event: JobEvent) -> None:
        """Handle job error event."""
        await self._ensure_scheduler_running()
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == event.job_id)
            job = (await session.exec(stmt)).first()
            if job:
                job.status = JobStatus.FAILED
                job.error = str(event.exception)
                session.add(job)
                await session.commit()

    async def create_job(
        self,
        task_func: str | Callable[..., Any],
        run_at: datetime | None = None,
        name: str | None = None,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """Create a new job."""
        await self._ensure_scheduler_running()
        if self.scheduler is None or self.job_store is None:
            msg = "Scheduler or job store not initialized"
            logger.error(msg)
            raise ValueError(msg)
        task_id = str(uuid4())
        try:
            trigger = DateTrigger(run_date=run_at) if run_at is not None else None

            await self.scheduler.add_job(
                task_func,
                trigger=trigger,
                args=args or [],
                kwargs=kwargs or {},
                id=task_id,
                name=name or f"task_{task_id}",
                misfire_grace_time=None,  # Run immediately when missed
                coalesce=True,  # Only run once if multiple are due
                max_instances=1,  # Only one instance at a time
                replace_existing=True,
            )

        except Exception as exc:
            logger.error(f"Error creating task: {exc}")
            raise
        return task_id

    async def get_job(self, job_id: str, user_id: UUID | None = None) -> APSJob | None:
        """Get job information."""
        await self._ensure_scheduler_running()
        if self.job_store is None:
            msg = "Job store not initialized"
            logger.error(msg)
            raise ValueError(msg)
        try:
            job = await self.job_store.lookup_job(job_id, user_id)
        except Exception as exc:
            logger.error(f"Error getting job {job_id}: {exc}")
            raise
        return job

    async def cancel_job(self, job_id: str, user_id: UUID | None = None) -> bool:
        """Cancel a job."""
        await self._ensure_scheduler_running()
        if self.scheduler is None or self.job_store is None:
            msg = "Scheduler or job store not initialized"
            logger.error(msg)
            raise ValueError(msg)
        try:
            # Get the job from jobstore
            job = await self.job_store.lookup_job(job_id, user_id)
            if not job:
                return False

            # Remove from scheduler if not yet executed
            scheduler_job = await self.scheduler.get_job(job_id)
            if scheduler_job is not None:
                await self.scheduler.remove_job(job_id)

        except Exception as exc:
            logger.error(f"Error cancelling job {job_id}: {exc}")
            raise
        return True

    async def get_jobs(
        self,
        user_id: UUID | None = None,
        pending: bool | None = None,
    ) -> list[dict]:
        """Get tasks with optional filters."""
        await self._ensure_scheduler_running()
        if self.job_store is None:
            msg = "Job store not initialized"
            logger.error(msg)
            raise ValueError(msg)
        try:
            if user_id:
                return await self.job_store.get_user_jobs(user_id, pending)
            # For other filters, we'll need to implement corresponding methods in the jobstore
            # For now, we'll just get all jobs if no user_id is provided
            return await self.job_store.get_all_jobs()
        except Exception as exc:
            logger.error(f"Error getting tasks: {exc}")
            raise

    async def get_user_jobs(self, user_id: UUID) -> list[dict]:
        """Get all jobs for a specific user."""
        await self._ensure_scheduler_running()
        if self.job_store is None:
            msg = "Job store not initialized"
            logger.error(msg)
            raise ValueError(msg)
        try:
            return await self.job_store.get_user_jobs(user_id)
        except Exception as exc:
            logger.error(f"Error getting jobs for user {user_id}: {exc}")
            raise

    async def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Task scheduler stopped")
