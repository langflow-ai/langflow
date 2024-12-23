import pickle
from datetime import datetime, timezone
from uuid import UUID

from apscheduler.job import Job as APSJob
from apscheduler.jobstores.base import BaseJobStore, JobLookupError
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from sqlmodel import select

from langflow.services.database.models.job import Job
from langflow.services.deps import session_scope


class AsyncSQLModelJobStore(BaseJobStore):
    """A job store that uses SQLModel to store jobs in the Langflow database.

    Currently only supports one-off tasks.
    """

    def __init__(self):
        super().__init__()
        self._jobs = {}

    async def get_all_jobs(self) -> list[Job]:
        """Get all jobs in the store."""
        async with session_scope() as session:
            stmt = select(Job)
            tasks = (await session.exec(stmt)).all()

            jobs = []
            for task in tasks:
                try:
                    job_state = pickle.loads(task.job_state)  # noqa: S301
                    job = self._reconstitute_job(job_state)
                    self._jobs[job.id] = job
                    jobs.append(job)
                except Exception:  # noqa: BLE001
                    logger.exception(f"Unable to restore job {task.id}")
                    await session.delete(task)

            await session.commit()
            return jobs

    async def lookup_job(self, job_id: str, user_id: UUID | None = None) -> APSJob | None:
        """Get job by ID."""
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == job_id)
            if user_id:
                if isinstance(user_id, str):
                    user_id = UUID(user_id)
                stmt = stmt.where(Job.user_id == user_id)
            db_job = (await session.exec(stmt)).first()
            if not db_job:
                return None

            try:
                job: APSJob = self._reconstitute_job(db_job.job_state)
                self._jobs[job_id] = job
            except Exception:  # noqa: BLE001
                logger.exception(f"Unable to restore job {job_id}")
                await session.delete(db_job)
                await session.commit()
                return None
            return job

    async def get_due_jobs(self, now: datetime) -> list[Job]:
        """Get all jobs that should be run at the given time."""
        async with session_scope() as session:
            stmt = select(Job).where(
                Job.next_run_time <= now,
                Job.is_active == True,  # noqa: E712
            )
            tasks = (await session.exec(stmt)).all()

            jobs = []
            for task in tasks:
                try:
                    job_state = pickle.loads(task.job_state)  # noqa: S301
                    job = self._reconstitute_job(job_state)
                    self._jobs[job.id] = job
                    jobs.append(job)
                except Exception:  # noqa: BLE001
                    logger.exception(f"Unable to restore job {task.id}")
                    await session.delete(task)

            await session.commit()
            return jobs

    async def get_next_run_time(self) -> datetime | None:
        """Get the earliest timestamp of all scheduled jobs."""
        async with session_scope() as session:
            stmt = (
                select(Job)
                .where(Job.is_active == True)  # noqa: E712
                .order_by(Job.next_run_time)
            )
            task = (await session.exec(stmt)).first()
            return task.next_run_time if task else None

    async def add_job(self, job: APSJob) -> None:
        """Add a one-off job."""
        if not isinstance(job.trigger, DateTrigger):
            msg = "Only one-off tasks are supported"
            raise TypeError(msg)

        job_state = pickle.dumps(job.__getstate__())

        async with session_scope() as session:
            if "flow" not in job.kwargs or "api_key_user" not in job.kwargs:
                msg = f"Job invalid: {job}"
                raise ValueError(msg)

            flow = job.kwargs.get("flow")
            api_key_user = job.kwargs.get("api_key_user")

            # Check for ids
            if not isinstance(flow.id, UUID) or not isinstance(api_key_user.id, UUID):
                msg = f"Job invalid: {job}"
                raise TypeError(msg)

            try:
                task = Job(
                    id=job.id,
                    name=job.name,
                    flow_id=job.kwargs.get("flow").id,
                    user_id=job.kwargs.get("api_key_user").id,
                    is_active=True,
                    next_run_time=job.next_run_time,
                    job_state=job_state,
                )

                session.add(task)
                await session.commit()
                await session.refresh(task)
                self._jobs[job.id] = job
            except Exception as exc:
                logger.exception(f"Unable to add job {job.id}")
                msg = f"Job invalid: {job}"
                raise ValueError(msg) from exc

    async def update_job(self, job: APSJob) -> None:
        """Update a job in the store."""
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == job.id)
            task = (await session.exec(stmt)).first()
            if not task:
                raise JobLookupError(job.id)

            job_state = job.__getstate__()
            task.name = job.name
            task.next_run_time = job.next_run_time
            task.job_state = job_state
            task.updated_at = datetime.now(timezone.utc)

            session.add(task)
            await session.commit()
            await session.refresh(task)
            self._jobs[job.id] = job

    async def remove_job(self, job_id: str) -> None:
        """Remove a job."""
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == job_id)
            task = (await session.exec(stmt)).first()
            if not task:
                raise JobLookupError(job_id)

            await session.delete(task)
            await session.commit()
            self._jobs.pop(job_id, None)

    async def remove_all_jobs(self) -> None:
        """Remove all jobs."""
        async with session_scope() as session:
            stmt = select(Job)
            tasks = (await session.exec(stmt)).all()
            for task in tasks:
                await session.delete(task)
            await session.commit()
            self._jobs.clear()

    async def get_user_jobs(self, user_id: UUID, pending: bool | None = None) -> list[Job]:
        """Get all jobs for a specific user."""
        async with session_scope() as session:
            stmt = select(Job).where(Job.user_id == user_id)
            tasks = (await session.exec(stmt)).all()

            jobs = []
            for task in tasks:
                try:
                    job_state = pickle.loads(task.job_state)  # noqa: S301
                    job = self._reconstitute_job(job_state)
                    if pending is not None and job.pending != pending:
                        continue
                    self._jobs[job.id] = job
                    jobs.append(job)
                except Exception:  # noqa: BLE001
                    logger.exception(f"Unable to restore job {task.id}")
                    await session.delete(task)

            await session.commit()
            return jobs

    def _reconstitute_job(self, job_state):
        """Reconstitute a job from its serialized state."""
        job_state_dict = job_state if isinstance(job_state, dict) else pickle.loads(job_state)  # noqa: S301
        job_state_dict["jobstore"] = self
        job = APSJob.__new__(APSJob)
        job.__setstate__(job_state_dict)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias
        return job
