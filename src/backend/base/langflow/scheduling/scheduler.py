import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from apscheduler.events import EVENT_ALL_JOBS_REMOVED, EVENT_JOB_ADDED, EVENT_JOB_REMOVED, JobEvent, SchedulerEvent
from apscheduler.job import Job as APSJob
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.schedulers.asyncio import maybe_ref
from apscheduler.schedulers.base import (
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_SUBMITTED,
    EVENT_SCHEDULER_STARTED,
    STATE_PAUSED,
    STATE_RUNNING,
    STATE_STOPPED,
    TIMEOUT_MAX,
    JobLookupError,
    JobSubmissionEvent,
    MaxInstancesReachedError,
    SchedulerAlreadyRunningError,
)
from apscheduler.util import undefined
from loguru import logger

from .base_scheduler import AsyncBaseScheduler

if TYPE_CHECKING:
    from .jobstore import AsyncSQLModelJobStore


class AsyncScheduler(AsyncBaseScheduler):
    """An improved version of AsyncIOScheduler that supports async jobstores."""

    _eventloop: asyncio.AbstractEventLoop | None = None
    _timeout = None

    def __init__(self, *args, **kwargs):
        self.timezone = timezone.utc
        super().__init__(*args, **kwargs)

    async def shutdown(self, *, wait: bool = True):
        """Shut down the scheduler.

        :param wait: ``True`` to wait until all currently executing jobs have finished
        :type wait: bool
        """
        await super().shutdown(wait=wait)
        self._stop_timer()

    async def _configure(self, config):
        self._eventloop = maybe_ref(config.pop("event_loop", None))
        await super()._configure(config)

    def _start_timer(self, wait_seconds):
        self._stop_timer()
        if wait_seconds is not None:
            self._timeout = self._eventloop.call_later(wait_seconds, self.wakeup)

    def _stop_timer(self):
        if self._timeout:
            self._timeout.cancel()
            del self._timeout

    def _create_default_executor(self):
        from langflow.scheduling.executor import AsyncIOExecutor

        return AsyncIOExecutor()

    async def wakeup(self):
        self._stop_timer()
        wait_seconds = await self._process_jobs()
        self._start_timer(wait_seconds)

    async def start(self, *, paused: bool = False):
        """Start the scheduler.

        Args:
            paused (bool, optional): If True, start in paused state. Defaults to False.
        """
        self._eventloop = self._eventloop or asyncio.get_running_loop()
        await self._start(paused=paused)

    async def _start(self, *, paused: bool = False):
        """Start the configured executors and job stores and begin processing scheduled jobs.

        :param bool paused: if ``True``, don't start job processing until :meth:`resume` is called
        :raises SchedulerAlreadyRunningError: if the scheduler is already running
        :raises RuntimeError: if running under uWSGI with threads disabled

        """
        if self.state != STATE_STOPPED:  # type: ignore[has-type]
            raise SchedulerAlreadyRunningError

        self._check_uwsgi()

        async with self._executors_lock:
            # Create a default executor if nothing else is configured
            if "default" not in self._executors:
                await self.add_executor(self._create_default_executor(), "default")

            # Start all the executors
            for alias, executor in self._executors.items():
                result = executor.start(self, alias)
                if inspect.iscoroutine(result):
                    await result

        async with self._jobstores_lock:
            # Create a default job store if nothing else is configured
            if "default" not in self._jobstores:
                await self.add_jobstore(self._create_default_jobstore(), "default")

            # Start all the job stores
            for alias, store in self._jobstores.items():
                result = await store.start(self, alias)
                if asyncio.iscoroutine(result):
                    await result

            # Schedule all pending jobs
            for job, jobstore_alias, replace_existing in self._pending_jobs:
                await self._real_add_job(job, jobstore_alias, replace_existing)
            del self._pending_jobs[:]

        self.state = STATE_PAUSED if paused else STATE_RUNNING
        self._logger.info("Scheduler started")
        await self._dispatch_event(SchedulerEvent(EVENT_SCHEDULER_STARTED))

        if not paused:
            await self.wakeup()

    async def _process_jobs(self):
        """Iterates through jobs in every jobstore.

        Starts jobs that are due and figures out how long to wait for the next round.

        If the ``get_due_jobs()`` call raises an exception, a new wakeup is scheduled in at least
        ``jobstore_retry_interval`` seconds.
        """
        if self.state == STATE_PAUSED:
            self._logger.debug("Scheduler is paused -- not processing jobs")
            return None

        self._logger.debug("Looking for jobs to run")
        now = datetime.now(self.timezone)
        next_wakeup_time = None
        events = []

        async with self._jobstores_lock:
            for jobstore_alias, jobstore in self._jobstores.items():
                try:
                    due_jobs = jobstore.get_due_jobs(now)
                    if asyncio.iscoroutine(due_jobs):
                        due_jobs = await due_jobs
                except Exception as e:  # noqa: BLE001
                    # Schedule a wakeup at least in jobstore_retry_interval seconds
                    self._logger.warning(
                        "Error getting due jobs from job store %r: %s",
                        jobstore_alias,
                        e,
                    )
                    retry_wakeup_time = now + timedelta(seconds=self.jobstore_retry_interval)
                    if not next_wakeup_time or next_wakeup_time > retry_wakeup_time:
                        next_wakeup_time = retry_wakeup_time

                    continue

                for job in due_jobs:
                    # Look up the job's executor
                    try:
                        executor = await self._lookup_executor(job.executor)
                    except BaseException:
                        self._logger.exception(
                            'Executor lookup ("%s") failed for job "%s" -- removing it from the ' "job store",
                            job.executor,
                            job,
                        )
                        await self.remove_job(job.id, jobstore_alias)
                        continue

                    run_times = job._get_run_times(now)
                    run_times = run_times[-1:] if run_times and job.coalesce else run_times
                    if run_times:
                        try:
                            result = executor.submit_job(job, run_times)
                            if asyncio.iscoroutine(result):
                                await result
                        except MaxInstancesReachedError:
                            self._logger.warning(
                                'Execution of job "%s" skipped: maximum number of running ' "instances reached (%d)",
                                job,
                                job.max_instances,
                            )
                            event = JobSubmissionEvent(
                                EVENT_JOB_MAX_INSTANCES,
                                job.id,
                                jobstore_alias,
                                run_times,
                            )
                            events.append(event)
                        except BaseException:
                            self._logger.exception(
                                'Error submitting job "%s" to executor "%s"',
                                job,
                                job.executor,
                            )
                        else:
                            event = JobSubmissionEvent(EVENT_JOB_SUBMITTED, job.id, jobstore_alias, run_times)
                            events.append(event)

                        # Update the job if it has a next execution time.
                        # Otherwise remove it from the job store.
                        job_next_run = job.trigger.get_next_fire_time(run_times[-1], now)
                        if job_next_run:
                            job._modify(next_run_time=job_next_run)
                            result = jobstore.update_job(job)
                            if asyncio.iscoroutine(result):
                                await result
                        else:
                            await self.remove_job(job.id, jobstore_alias)

                # Set a new next wakeup time if there isn't one yet or
                # the jobstore has an even earlier one
                jobstore_next_run_time = jobstore.get_next_run_time()
                if asyncio.iscoroutine(jobstore_next_run_time):
                    jobstore_next_run_time = await jobstore_next_run_time
                if jobstore_next_run_time and (next_wakeup_time is None or jobstore_next_run_time < next_wakeup_time):
                    next_wakeup_time = jobstore_next_run_time.astimezone(self.timezone)

        # Dispatch collected events
        for event in events:
            await self._dispatch_event(event)

        # Determine the delay until this method should be called again
        if self.state == STATE_PAUSED:
            wait_seconds = None
            self._logger.debug("Scheduler is paused; waiting until resume() is called")
        elif next_wakeup_time is None:
            wait_seconds = None
            self._logger.debug("No jobs; waiting until a job is added")
        else:
            now = datetime.now(self.timezone)
            wait_seconds = min(max((next_wakeup_time - now).total_seconds(), 0), TIMEOUT_MAX)
            self._logger.debug(
                "Next wakeup is due at %s (in %f seconds)",
                next_wakeup_time,
                wait_seconds,
            )

        return wait_seconds

    async def remove_job(self, job_id, jobstore=None):
        """Removes a job, preventing it from being run any more.

        :param str|unicode job_id: the identifier of the job
        :param str|unicode jobstore: alias of the job store that contains the job
        :raises JobLookupError: if the job was not found

        """
        jobstore_alias = None
        async with self._jobstores_lock:
            # Check if the job is among the pending jobs
            if self.state == STATE_STOPPED:
                for i, (job, alias, _replace_existing) in enumerate(self._pending_jobs):
                    if job.id == job_id and jobstore in (None, alias):
                        del self._pending_jobs[i]
                        jobstore_alias = alias
                        break
            else:
                # Otherwise, try to remove it from each store until it succeeds or we run out of
                # stores to check
                for alias, store in self._jobstores.items():
                    if jobstore in (None, alias):
                        try:
                            result = store.remove_job(job_id)
                            if asyncio.iscoroutine(result):
                                await result
                            jobstore_alias = alias
                            break
                        except JobLookupError:
                            continue

        if jobstore_alias is None:
            raise JobLookupError(job_id)

        # Notify listeners that a job has been removed
        event = JobEvent(EVENT_JOB_REMOVED, job_id, jobstore_alias)
        await self._dispatch_event(event)

        self._logger.info("Removed job %s", job_id)

    async def remove_all_jobs(self, jobstore=None):
        """Removes all jobs from the specified job store, or all job stores if none is given.

        :param str|unicode jobstore: alias of the job store

        """
        async with self._jobstores_lock:
            if self.state == STATE_STOPPED:
                if jobstore:
                    self._pending_jobs = [pending for pending in self._pending_jobs if pending[1] != jobstore]
                else:
                    self._pending_jobs = []
            else:
                for alias, store in self._jobstores.items():
                    if jobstore in (None, alias):
                        result = store.remove_all_jobs()
                        if asyncio.iscoroutine(result):
                            await result

        await self._dispatch_event(SchedulerEvent(EVENT_ALL_JOBS_REMOVED, jobstore))

    async def _real_add_job(self, job, jobstore_alias, replace_existing):
        """Override to make async-compatible."""
        # Fill in undefined values with defaults
        replacements = {key: value for key, value in self._job_defaults.items() if not hasattr(job, key)}

        # Calculate the next run time if there is none defined
        if not hasattr(job, "next_run_time"):
            now = datetime.now(timezone.utc)
            replacements["next_run_time"] = job.trigger.get_next_fire_time(None, now)

        # Apply any replacements
        job._modify(**replacements)

        # Add the job to the given job store
        store: AsyncSQLModelJobStore = self._lookup_jobstore(jobstore_alias)
        try:
            await store.add_job(job)
        except ConflictingIdError:
            if replace_existing:
                await store.update_job(job)
            else:
                raise

        # Mark the job as no longer pending
        job._jobstore_alias = jobstore_alias

        # Notify listeners that a new job has been added
        event = JobEvent(EVENT_JOB_ADDED, job.id, jobstore_alias)
        await self._dispatch_event(event)

        logger.info(f"Added job {job.name} to job store {jobstore_alias}")

        # Notify the scheduler about the new job
        if self.state == STATE_RUNNING:
            await self.wakeup()

    async def add_job(
        self,
        func,
        trigger=None,
        args=None,
        kwargs=None,
        id=None,  # noqa: A002
        name=None,
        misfire_grace_time=undefined,
        coalesce=undefined,
        max_instances=undefined,
        next_run_time=undefined,
        jobstore="default",
        executor="default",
        *,
        replace_existing=False,
        **trigger_args,
    ):
        """Add a job to the scheduler.

        Any option that defaults to undefined will be replaced with the corresponding default
        value when the job is scheduled.
        """
        job_kwargs = {
            "trigger": self._create_trigger(trigger, trigger_args),
            "executor": executor,
            "func": func,
            "args": tuple(args) if args is not None else (),
            "kwargs": dict(kwargs) if kwargs is not None else {},
            "id": id,
            "name": name,
            "misfire_grace_time": misfire_grace_time,
            "coalesce": coalesce,
            "max_instances": max_instances,
            "next_run_time": next_run_time,
        }
        job_kwargs = {key: value for key, value in job_kwargs.items() if value is not undefined}
        job = APSJob(self, **job_kwargs)

        # Don't really add jobs to job stores before the scheduler is up and running
        async with self._jobstores_lock:
            if self.state == STATE_STOPPED:
                self._pending_jobs.append((job, jobstore, replace_existing))
                logger.info("Adding job tentatively -- it will be properly scheduled when the scheduler starts")
            else:
                await self._real_add_job(job, jobstore, replace_existing)

        return job
