import pickle
from datetime import datetime, timezone
from uuid import UUID

from apscheduler.job import Job as APSJob
from apscheduler.jobstores.base import BaseJobStore, JobLookupError
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from sqlmodel import col, select

from langflow.services.database.models.job.model import Job, JobStatus
from langflow.services.deps import session_scope


class AsyncSQLModelJobStore(BaseJobStore):
    """An asynchronous job store that uses SQLModel to store jobs in the Langflow database.

    This jobstore is designed to work with async/await operations and uses SQLModel for database operations.
    All database operations are performed asynchronously using session_scope context manager.

    Currently only supports one-off tasks with DateTrigger.

    Attributes:
        _jobs (dict): A dictionary that caches job instances for quick lookup
    """

    def __init__(self):
        """Initialize the async job store."""
        super().__init__()
        self._jobs = {}

    async def start(self, scheduler, alias):
        """Start the job store asynchronously.

        This method is called when the scheduler starts up. It loads all existing jobs
        from the database into memory.

        Args:
            scheduler: The scheduler instance that this job store is associated with
            alias: The alias of this job store as known to the scheduler
        """
        super().start(scheduler, alias)
        # Load all jobs from the database
        await self.get_all_jobs()

    async def shutdown(self):
        """Shut down the job store asynchronously.

        This method is called when the scheduler is shut down. It clears the job cache
        and performs any necessary cleanup.
        """
        await super().shutdown()
        self._jobs.clear()

    async def get_all_jobs(self) -> list[Job]:
        """Get all jobs from the database asynchronously.

        Retrieves all jobs from the database and reconstitutes them into Job objects.
        Failed jobs are removed from the database.

        Returns:
            list[Job]: A list of all active jobs in the store

        Note:
            This method will remove any jobs that cannot be properly reconstituted
            from their serialized state.
        """
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
        """Look up a job by its ID asynchronously.

        Args:
            job_id (str): The identifier of the job to look up
            user_id (UUID | None): Optional user ID to filter jobs by owner

        Returns:
            APSJob | None: The job if found and successfully reconstituted, None otherwise

        Note:
            If the job exists but cannot be reconstituted, it will be removed from the database.
        """
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
        """Get all jobs that are due to run asynchronously.

        Retrieves all active jobs that should be run at or before the given time.

        Args:
            now (datetime): The current time to check against

        Returns:
            list[Job]: A list of jobs that are due to run

        Note:
            Jobs that cannot be reconstituted will be removed from the database.
        """
        async with session_scope() as session:
            stmt = select(Job).where(
                col(Job.next_run_time).isnot(None),
                col(Job.next_run_time) <= now,
                col(Job.is_active) == True,  # noqa: E712
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
        """Get the earliest timestamp of all scheduled jobs asynchronously.

        Returns:
            datetime | None: The earliest run time of all active jobs,
                           or None if there are no active jobs.
        """
        async with session_scope() as session:
            stmt = (
                select(Job)
                .where(Job.is_active == True)  # noqa: E712
                .order_by(Job.next_run_time)
            )
            task = (await session.exec(stmt)).first()
            return task.next_run_time if task else None

    async def add_job(self, job: APSJob) -> None:
        """Add a new job to the store asynchronously.

        Args:
            job (APSJob): The job to add

        Raises:
            TypeError: If the job's trigger is not a DateTrigger
            ValueError: If the job is missing required fields or is invalid

        Note:
            Currently only supports one-off tasks using DateTrigger.
            The job must include 'flow' and 'api_key_user' in its kwargs.
        """
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

            flow_id = flow.get("id") if isinstance(flow, dict) else flow.id
            if isinstance(flow_id, str):
                flow_id = UUID(flow_id)

            api_key_user_id = api_key_user.get("id") if isinstance(api_key_user, dict) else api_key_user.id

            if isinstance(api_key_user_id, str):
                api_key_user_id = UUID(api_key_user_id)

            # Check for ids
            if not isinstance(flow_id, UUID) or not isinstance(api_key_user_id, UUID):
                msg = f"Job invalid: {job}"
                raise TypeError(msg)

            try:
                task = Job(
                    id=job.id,
                    name=job.name,
                    flow_id=flow_id,
                    user_id=api_key_user_id,
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
        """Update an existing job in the store asynchronously.

        Args:
            job (APSJob): The job to update

        Raises:
            JobLookupError: If the job does not exist in the store
        """
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
        """Mark a job as completed in the store asynchronously.

        Args:
            job_id (str): The identifier of the job to mark as completed

        Raises:
            JobLookupError: If the job does not exist in the store
        """
        async with session_scope() as session:
            stmt = select(Job).where(Job.id == job_id)
            task = (await session.exec(stmt)).first()
            if not task:
                raise JobLookupError(job_id)

            task.status = JobStatus.COMPLETED
            task.is_active = False
            task.updated_at = datetime.now(timezone.utc)

            session.add(task)
            await session.commit()
            self._jobs.pop(job_id, None)

    async def remove_all_jobs(self) -> None:
        """Remove all jobs from the store asynchronously.

        This method removes all jobs from both the database and the in-memory cache.
        """
        async with session_scope() as session:
            stmt = select(Job)
            tasks = (await session.exec(stmt)).all()
            for task in tasks:
                await session.delete(task)
            await session.commit()
            self._jobs.clear()

    async def get_user_jobs(
        self, user_id: UUID, pending: bool | None = None, status: JobStatus | None = None
    ) -> list[Job]:
        """Get all jobs for a specific user asynchronously.

        Args:
            user_id (UUID): The ID of the user whose jobs to retrieve
            pending (bool | None): If set, only return jobs with matching pending status
            status (JobStatus | None): If set, only return jobs with matching status
        Returns:
            list[Job]: A list of jobs belonging to the specified user

        Note:
            Jobs that cannot be reconstituted will be removed from the database.
        """
        async with session_scope() as session:
            stmt = select(Job).where(Job.user_id == user_id)
            if status:
                stmt = stmt.where(Job.status == status)
            tasks = (await session.exec(stmt)).all()

            jobs = []
            for task in tasks:
                try:
                    job_state = pickle.loads(task.job_state)  # noqa: S301
                    job: APSJob = self._reconstitute_job(job_state)
                    if pending is not None and job.pending != pending:
                        continue
                    self._jobs[job.id] = job
                    jobs.append(job)
                except Exception:  # noqa: BLE001
                    logger.exception(f"Unable to restore job {task.id}")
                    await session.delete(task)

            await session.commit()
            return jobs

    def _reconstitute_job(self, job_state) -> APSJob:
        """Reconstitute a job from its serialized state.

        This method creates a new Job instance from a serialized job state.

        Args:
            job_state: The serialized job state (either a dict or pickled data)

        Returns:
            APSJob: The reconstituted job instance

        Note:
            This is an internal method used by other methods to restore jobs from their
            serialized state in the database.
        """
        job_state_dict = job_state if isinstance(job_state, dict) else pickle.loads(job_state)  # noqa: S301
        job_state_dict["jobstore"] = self
        job = APSJob.__new__(APSJob)
        job.__setstate__(job_state_dict)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias
        return job
