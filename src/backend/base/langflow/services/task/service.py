from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent, JobExecutionEvent
from apscheduler.schedulers.base import SchedulerAlreadyRunningError
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from sqlmodel import select

from langflow.services.base import Service
from langflow.services.database.models.job.model import Job
from langflow.services.deps import session_scope
from langflow.services.scheduler.jobstore import AsyncSQLModelJobStore
from langflow.services.task.scheduler import AsyncScheduler

if TYPE_CHECKING:
    from collections.abc import Callable

    from apscheduler.job import Job as APSJob

    from langflow.services.settings.service import SettingsService


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskService(Service):
    """Service for managing tasks and scheduled flows."""

    name = "task_service"

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.scheduler = AsyncScheduler()
        self.job_store = AsyncSQLModelJobStore()
        self.scheduler.add_jobstore(self.job_store, "default")

        # Add event listeners
        self.scheduler.add_listener(self._handle_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._handle_job_error, EVENT_JOB_ERROR)
        self._started = False

    async def _ensure_scheduler_running(self):
        """Ensure the scheduler is running."""
        if not self._started:
            try:
                await self.scheduler.start(paused=False)
                self._started = True
            except SchedulerAlreadyRunningError:
                pass

    async def _handle_job_executed(self, event: JobExecutionEvent) -> None:
        """Handle job executed event."""
        await self._ensure_scheduler_running()
        # JobExecutionEvent has retval
        await event.job_store.update_job(event.job_id, TaskStatus.COMPLETED)

    async def _handle_job_error(self, event: JobEvent) -> None:
        """Handle job error event."""
        await self._ensure_scheduler_running()
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == event.job_id)
            task = (await session.exec(stmt)).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error = str(event.exception)
                session.add(task)
                await session.commit()

    async def create_task(
        self,
        task_func: str | Callable[..., Any],
        run_at: datetime | None = None,
        name: str | None = None,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """Create a new task."""
        await self._ensure_scheduler_running()
        task_id = str(uuid4())
        try:
            if run_at is None:
                run_at = datetime.now(timezone.utc) + timedelta(seconds=1)

            await self.scheduler.add_job(
                task_func,
                trigger=DateTrigger(run_date=run_at),
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

    async def get_task(self, task_id: str, user_id: UUID | None = None) -> APSJob | None:
        """Get task information."""
        await self._ensure_scheduler_running()
        try:
            job = await self.job_store.lookup_job(task_id, user_id)
        except Exception as exc:
            logger.error(f"Error getting task {task_id}: {exc}")
            raise
        return job

    async def cancel_task(self, task_id: str, user_id: UUID | None = None) -> bool:
        """Cancel a task."""
        await self._ensure_scheduler_running()
        try:
            # Get the job from jobstore
            job = await self.job_store.lookup_job(task_id, user_id)
            if not job:
                return False

            # Remove from scheduler if not yet executed
            scheduler_job = await self.scheduler.get_job(task_id)
            if scheduler_job is not None:
                await self.scheduler.remove_job(task_id)

        except Exception as exc:
            logger.error(f"Error cancelling task {task_id}: {exc}")
            raise
        return True

    async def get_tasks(
        self,
        user_id: UUID | None = None,
        pending: bool | None = None,
    ) -> list[dict]:
        """Get tasks with optional filters."""
        await self._ensure_scheduler_running()
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
