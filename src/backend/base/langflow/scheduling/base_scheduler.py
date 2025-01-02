import inspect
import sys
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timedelta, timezone
from importlib.metadata import entry_points
from logging import getLogger
from pathlib import Path
from threading import TIMEOUT_MAX
from typing import TYPE_CHECKING, Any

import aiofiles
from apscheduler.events import (
    EVENT_ALL,
    EVENT_ALL_JOBS_REMOVED,
    EVENT_EXECUTOR_ADDED,
    EVENT_EXECUTOR_REMOVED,
    EVENT_JOB_ADDED,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MODIFIED,
    EVENT_JOB_REMOVED,
    EVENT_JOB_SUBMITTED,
    EVENT_JOBSTORE_ADDED,
    EVENT_JOBSTORE_REMOVED,
    EVENT_SCHEDULER_PAUSED,
    EVENT_SCHEDULER_RESUMED,
    EVENT_SCHEDULER_SHUTDOWN,
    EVENT_SCHEDULER_STARTED,
    JobEvent,
    JobSubmissionEvent,
    SchedulerEvent,
)
from apscheduler.executors.base import BaseExecutor, MaxInstancesReachedError
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job as APSJob
from apscheduler.jobstores.base import BaseJobStore, ConflictingIdError, JobLookupError
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers import SchedulerAlreadyRunningError, SchedulerNotRunningError
from apscheduler.triggers.base import BaseTrigger
from apscheduler.util import asbool, asint, maybe_ref, obj_to_ref, ref_to_obj, undefined

from .async_rlock import AsyncRLock

if TYPE_CHECKING:
    from traitlets import Callable

#: constant indicating a scheduler's stopped state
STATE_STOPPED = 0
#: constant indicating a scheduler's running state (started and processing jobs)
STATE_RUNNING = 1
#: constant indicating a scheduler's paused state (started but not processing jobs)
STATE_PAUSED = 2


class AsyncBaseScheduler(metaclass=ABCMeta):
    """Abstract base class for all schedulers.

    Takes the following keyword arguments:

    :param str|logging.Logger logger: logger to use for the scheduler's logging (defaults to
        apscheduler.scheduler)
    :param str|datetime.tzinfo timezone: the default time zone (defaults to the local timezone)
    :param int|float jobstore_retry_interval: the minimum number of seconds to wait between
        retries in the scheduler's main loop if the job store raises an exception when getting
        the list of due jobs
    :param dict job_defaults: default values for newly added jobs
    :param dict jobstores: a dictionary of job store alias -> job store instance or configuration
        dict
    :param dict executors: a dictionary of executor alias -> executor instance or configuration
        dict

    :ivar int state: current running state of the scheduler (one of the following constants from
        ``apscheduler.schedulers.base``: ``STATE_STOPPED``, ``STATE_RUNNING``, ``STATE_PAUSED``)

    .. seealso:: :ref:`scheduler-config`
    """

    # The `group=...` API is only available in the backport, used in <=3.7, and in std>=3.10.
    if (3, 8) <= sys.version_info < (3, 10):
        _trigger_plugins = {ep.name: ep for ep in entry_points()["apscheduler.triggers"]}
        _executor_plugins = {ep.name: ep for ep in entry_points()["apscheduler.executors"]}
        _jobstore_plugins = {ep.name: ep for ep in entry_points()["apscheduler.jobstores"]}
    else:
        _trigger_plugins = {ep.name: ep for ep in entry_points(group="apscheduler.triggers")}
        _executor_plugins = {ep.name: ep for ep in entry_points(group="apscheduler.executors")}
        _jobstore_plugins = {ep.name: ep for ep in entry_points(group="apscheduler.jobstores")}

    _trigger_classes: dict[str, type[Any]] = {}
    _executor_classes: dict[str, type[Any]] = {}
    _jobstore_classes: dict[str, type[Any]] = {}

    #
    # Public API
    #

    def __init__(self, gconfig: dict | None = None):
        if gconfig is None:
            gconfig = {}
        super().__init__()
        self._executors: dict[str, BaseExecutor] = {}
        self._executors_lock = self._create_lock()
        self._jobstores: dict[str, BaseJobStore] = {}
        self._jobstores_lock = self._create_lock()
        self._listeners: list[tuple[Callable[[JobEvent], None], int]] = []
        self._listeners_lock = self._create_lock()
        self._pending_jobs: list[tuple[APSJob, str, bool]] = []
        self.state = STATE_STOPPED

    def __getstate__(self):
        msg = (
            "Schedulers cannot be serialized. Ensure that you are not passing a "
            "scheduler instance as an argument to a job, or scheduling an instance "
            "method where the instance contains a scheduler as an attribute."
        )
        raise TypeError(msg)

    async def configure(self, gconfig=None, prefix="apscheduler.", **options):
        """Reconfigures the scheduler with the given options.

        Can only be done when the scheduler isn't running.

        :param dict gconfig: a "global" configuration dictionary whose values can be overridden by
            keyword arguments to this method
        :param str|unicode prefix: pick only those keys from ``gconfig`` that are prefixed with
            this string (pass an empty string or ``None`` to use all keys)
        :raises SchedulerAlreadyRunningError: if the scheduler is already running

        """
        if gconfig is None:
            gconfig = {}
        if self.state != STATE_STOPPED:
            raise SchedulerAlreadyRunningError

        # If a non-empty prefix was given, strip it from the keys in the
        # global configuration dict
        if prefix:
            prefixlen = len(prefix)
            gconfig = {key[prefixlen:]: value for key, value in gconfig.items() if key.startswith(prefix)}

        # Create a structure from the dotted options
        # (e.g. "a.b.c = d" -> {'a': {'b': {'c': 'd'}}})
        config = {}
        for config_key, value in gconfig.items():
            parts = config_key.split(".")
            parent = config
            current_key = parts.pop(0)
            while parts:
                parent = parent.setdefault(current_key, {})
                current_key = parts.pop(0)
            parent[current_key] = value

        # Override any options with explicit keyword arguments
        config.update(options)
        await self._configure(config)

    async def start(self, *, paused: bool = False):
        """Start the configured executors and job stores and begin processing scheduled jobs.

        :param bool paused: if ``True``, don't start job processing until :meth:`resume` is called
        :raises SchedulerAlreadyRunningError: if the scheduler is already running
        :raises RuntimeError: if running under uWSGI with threads disabled

        """
        if self.state != STATE_STOPPED:
            raise SchedulerAlreadyRunningError

        self._check_uwsgi()

        async with self._executors_lock:
            # Create a default executor if nothing else is configured
            if "default" not in self._executors:
                self.add_executor(self._create_default_executor(), "default")

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
                result = store.start(self, alias)
                if inspect.iscoroutine(result):
                    await result

            # Schedule all pending jobs
            for job, jobstore_alias, replace_existing in self._pending_jobs:
                await self._real_add_job(job, jobstore_alias, replace_existing)
            del self._pending_jobs[:]

        self.state = STATE_PAUSED if paused else STATE_RUNNING
        self._logger.info("Scheduler started")
        await self._dispatch_event(SchedulerEvent(EVENT_SCHEDULER_STARTED))

        if not paused:
            self.wakeup()

    @abstractmethod
    async def shutdown(self, *, wait: bool = True):
        """Shuts down the scheduler, along with its executors and job stores.

        Does not interrupt any currently running jobs.

        :param bool wait: ``True`` to wait until all currently executing jobs have finished
        :raises SchedulerNotRunningError: if the scheduler has not been started yet

        """
        if self.state == STATE_STOPPED:
            raise SchedulerNotRunningError

        self.state = STATE_STOPPED

        # Shut down all executors
        async with self._executors_lock, self._jobstores_lock:
            for executor in self._executors.values():
                result = executor.shutdown(wait)
                if inspect.iscoroutine(result):
                    await result

            # Shut down all job stores
            for jobstore in self._jobstores.values():
                result = jobstore.shutdown()
                if inspect.iscoroutine(result):
                    await result

        self._logger.info("Scheduler has been shut down")
        await self._dispatch_event(SchedulerEvent(EVENT_SCHEDULER_SHUTDOWN))

    async def pause(self):
        """Pause job processing in the scheduler.

        This will prevent the scheduler from waking up to do job processing until :meth:`resume`
        is called. It will not however stop any already running job processing.

        """
        if self.state == STATE_STOPPED:
            raise SchedulerNotRunningError
        if self.state == STATE_RUNNING:
            self.state = STATE_PAUSED
            self._logger.info("Paused scheduler job processing")
            await self._dispatch_event(SchedulerEvent(EVENT_SCHEDULER_PAUSED))

    async def resume(self):
        """Resume job processing in the scheduler."""
        if self.state == STATE_STOPPED:
            raise SchedulerNotRunningError
        if self.state == STATE_PAUSED:
            self.state = STATE_RUNNING
            self._logger.info("Resumed scheduler job processing")
            await self._dispatch_event(SchedulerEvent(EVENT_SCHEDULER_RESUMED))
            self.wakeup()

    @property
    def running(self):
        """Return ``True`` if the scheduler has been started.

        This is a shortcut for ``scheduler.state != STATE_STOPPED``.

        """
        return self.state != STATE_STOPPED

    async def add_executor(self, executor, alias="default", **executor_opts):
        """Add an executor to this scheduler.

        Any extra keyword arguments will be passed to the executor plugin's constructor, assuming
        that the first argument is the name of an executor plugin.

        :param str|unicode|apscheduler.executors.base.BaseExecutor executor: either an executor
            instance or the name of an executor plugin
        :param str|unicode alias: alias for the scheduler
        :raises ValueError: if there is already an executor by the given alias
        """
        async with self._executors_lock:
            if alias in self._executors:
                msg = f'This scheduler already has an executor by the alias of "{alias}"'
                raise ValueError(msg)

            if isinstance(executor, BaseExecutor):
                self._executors[alias] = executor
            elif isinstance(executor, str):
                self._executors[alias] = executor = self._create_plugin_instance("executor", executor, executor_opts)
            else:
                msg = self._create_executor_error_message(alias, executor)
                raise TypeError(msg)

            # Start the executor right away if the scheduler is running
            if self.state != STATE_STOPPED:
                result = executor.start(self, alias)
                if inspect.iscoroutine(result):
                    await result

        await self._dispatch_event(SchedulerEvent(EVENT_EXECUTOR_ADDED, alias))

    async def remove_executor(self, alias, *, shutdown: bool = True):
        """Removes the executor by the given alias from this scheduler.

        :param str|unicode alias: alias of the executor
        :param bool shutdown: ``True`` to shut down the executor after
            removing it

        """
        async with self._executors_lock:
            executor = await self._lookup_executor(alias)
            del self._executors[alias]

        if shutdown:
            result = executor.shutdown()
            if inspect.iscoroutine(result):
                await result

        await self._dispatch_event(SchedulerEvent(EVENT_EXECUTOR_REMOVED, alias))

    async def add_jobstore(self, jobstore, alias="default", **jobstore_opts):
        """Add a job store to this scheduler.

        Any extra keyword arguments will be passed to the job store plugin's constructor, assuming
        that the first argument is the name of a job store plugin.

        :param str|unicode|apscheduler.jobstores.base.BaseJobStore jobstore: job store to be added
        :param str|unicode alias: alias for the job store
        :raises ValueError: if there is already a job store by the given alias
        """
        async with self._jobstores_lock:
            if alias in self._jobstores:
                msg = f'This scheduler already has a job store by the alias of "{alias}"'
                raise ValueError(msg)

            if isinstance(jobstore, BaseJobStore):
                self._jobstores[alias] = jobstore
            elif isinstance(jobstore, str):
                self._jobstores[alias] = jobstore = self._create_plugin_instance("jobstore", jobstore, jobstore_opts)
            else:
                msg = self._create_jobstore_error_message(alias, jobstore)
                raise TypeError(msg)

            # Start the job store right away if the scheduler isn't stopped
            if self.state != STATE_STOPPED:
                result = jobstore.start(self, alias)
                if inspect.iscoroutine(result):
                    await result

        # Notify listeners that a new job store has been added
        await self._dispatch_event(SchedulerEvent(EVENT_JOBSTORE_ADDED, alias))

        # Notify the scheduler so it can scan the new job store for jobs
        if self.state != STATE_STOPPED:
            await self.wakeup()

    async def remove_jobstore(self, alias, *, shutdown: bool = True):
        """Removes the job store by the given alias from this scheduler.

        :param str|unicode alias: alias of the job store
        :param bool shutdown: ``True`` to shut down the job store after removing it

        """
        async with self._jobstores_lock:
            jobstore = self._lookup_jobstore(alias)
            del self._jobstores[alias]

        if shutdown:
            result = jobstore.shutdown()
            if inspect.iscoroutine(result):
                await result

        await self._dispatch_event(SchedulerEvent(EVENT_JOBSTORE_REMOVED, alias))

    async def add_listener(self, callback, mask=EVENT_ALL):
        """Add a listener for scheduler events.

        When a matching event occurs, ``callback`` is executed with the event object as its
        sole argument. If the ``mask`` parameter is not provided, the callback will receive events
        of all types.

        :param callback: any callable that takes one argument
        :param int mask: bitmask that indicates which events should be listened to

        .. seealso:: :mod:`apscheduler.events`
        .. seealso:: :ref:`scheduler-events`
        """
        async with self._listeners_lock:
            self._listeners.append((callback, mask))

    async def remove_listener(self, callback):
        """Removes a previously added event listener."""
        async with self._listeners_lock:
            for i, (cb, _) in enumerate(self._listeners):
                if callback == cb:
                    del self._listeners[i]

    async def add_job(
        self,
        func,
        trigger=None,
        args=None,
        kwargs=None,
        job_id=None,
        name=None,
        misfire_grace_time=undefined,
        coalesce=undefined,
        max_instances=undefined,
        next_run_time=undefined,
        jobstore="default",
        executor="default",
        *,
        replace_existing: bool = False,
        **trigger_args,
    ):
        """Add a job to the job list and wakes up the scheduler if it's already running.

        Any option that defaults to ``undefined`` will be replaced with the corresponding default
        value when the job is scheduled (which happens when the scheduler is started, or
        immediately if the scheduler is already running).

        The ``func`` argument can be given either as a callable object or a textual reference in
        the ``package.module:some.object`` format, where the first half (separated by ``:``) is an
        importable module and the second half is a reference to the callable object, relative to
        the module.

        The ``trigger`` argument can either be:
          #. the alias name of the trigger (e.g. ``date``, ``interval`` or ``cron``), in which case
            any extra keyword arguments to this method are passed on to the trigger's constructor
          #. an instance of a trigger class

        :param func: callable (or a textual reference to one) to run at the given time
        :param str|apscheduler.triggers.base.BaseTrigger trigger: trigger that determines when
            ``func`` is called
        :param list|tuple args: list of positional arguments to call func with
        :param dict kwargs: dict of keyword arguments to call func with
        :param str|unicode job_id: explicit identifier for the job (for modifying it later)
        :param str|unicode name: textual description of the job
        :param int misfire_grace_time: seconds after the designated runtime that the job is still
            allowed to be run (or ``None`` to allow the job to run no matter how late it is)
        :param bool coalesce: run once instead of many times if the scheduler determines that the
            job should be run more than once in succession
        :param int max_instances: maximum number of concurrently running instances allowed for this
            job
        :param datetime next_run_time: when to first run the job, regardless of the trigger (pass
            ``None`` to add the job as paused)
        :param str|unicode jobstore: alias of the job store to store the job in
        :param str|unicode executor: alias of the executor to run the job with
        :param bool replace_existing: ``True`` to replace an existing job with the same ``id``
            (but retain the number of runs from the existing one)
        :rtype: Job

        """
        job_kwargs = {
            "trigger": self._create_trigger(trigger, trigger_args),
            "executor": executor,
            "func": func,
            "args": tuple(args) if args is not None else (),
            "kwargs": dict(kwargs) if kwargs is not None else {},
            "id": job_id,
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
                self._logger.info(
                    "Adding job tentatively -- it will be properly scheduled when " "the scheduler starts"
                )
            else:
                await self._real_add_job(job, jobstore, replace_existing)

        return job

    def scheduled_job(
        self,
        trigger,
        args=None,
        kwargs=None,
        job_id=None,
        name=None,
        misfire_grace_time=undefined,
        coalesce=undefined,
        max_instances=undefined,
        next_run_time=undefined,
        jobstore="default",
        executor="default",
        **trigger_args,
    ):
        """Scheduled job decorator.

        A decorator version of :meth:`add_job`, except that ``replace_existing`` is always
        ``True``.

        .. important:: The ``id`` argument must be given if scheduling a job in a persistent job
        store. The scheduler cannot, however, enforce this requirement.

        """

        def inner(func):
            self.add_job(
                func,
                trigger,
                args,
                kwargs,
                job_id,
                name,
                misfire_grace_time,
                coalesce,
                max_instances,
                next_run_time,
                jobstore,
                executor,
                replace_existing=True,
                **trigger_args,
            )
            return func

        return inner

    async def modify_job(self, job_id: str, jobstore: str | None = None, **changes):
        """Modifies the properties of a single job.

        Modifications are passed to this method as extra keyword arguments.

        :param str|unicode job_id: the identifier of the job
        :param str|unicode jobstore: alias of the job store that contains the job
        :return Job: the relevant job instance

        """
        async with self._jobstores_lock:
            result = self._lookup_job(job_id, jobstore)
            if inspect.iscoroutine(result):
                job_result: tuple[APSJob, str] = await result
                job: APSJob = job_result[0]
                jobstore = job_result[1]
            else:
                job, jobstore = result
            job._modify(**changes)
            if jobstore:
                result = self._lookup_jobstore(jobstore).update_job(job)
                if inspect.iscoroutine(result):
                    await result

        await self._dispatch_event(JobEvent(EVENT_JOB_MODIFIED, job_id, jobstore))

        # Wake up the scheduler since the job's next run time may have been changed
        if self.state == STATE_RUNNING:
            self.wakeup()

        return job

    async def reschedule_job(self, job_id, jobstore=None, trigger=None, **trigger_args):
        """Constructs a new trigger for a job and updates its next run time.

        Extra keyword arguments are passed directly to the trigger's constructor.

        :param str|unicode job_id: the identifier of the job
        :param str|unicode jobstore: alias of the job store that contains the job
        :param trigger: alias of the trigger type or a trigger instance
        :return Job: the relevant job instance

        """
        trigger = self._create_trigger(trigger, trigger_args)
        now = datetime.now(self.timezone)
        next_run_time = trigger.get_next_fire_time(None, now)
        return await self.modify_job(job_id, jobstore, trigger=trigger, next_run_time=next_run_time)

    async def pause_job(self, job_id, jobstore=None):
        """Causes the given job not to be executed until it is explicitly resumed.

        :param str|unicode job_id: the identifier of the job
        :param str|unicode jobstore: alias of the job store that contains the job
        :return Job: the relevant job instance

        """
        return await self.modify_job(job_id, jobstore, next_run_time=None)

    async def resume_job(self, job_id, jobstore=None):
        """Resumes the schedule of the given job, or removes the job if its schedule is finished.

        :param str|unicode job_id: the identifier of the job
        :param str|unicode jobstore: alias of the job store that contains the job
        :return Job|None: the relevant job instance if the job was rescheduled, or ``None`` if no
            next run time could be calculated and the job was removed

        """
        async with self._jobstores_lock:
            job, jobstore = self._lookup_job(job_id, jobstore)
            now = datetime.now(self.timezone)
            next_run_time = job.trigger.get_next_fire_time(None, now)
            if next_run_time:
                return await self.modify_job(job_id, jobstore, next_run_time=next_run_time)
            await self.remove_job(job.id, jobstore)
            return None

    async def get_jobs(self, jobstore=None, pending=None):
        """Get a list of scheduled jobs.

        Returns a list of pending jobs (if the scheduler hasn't been started yet) and scheduled
        jobs, either from a specific job store or from all of them.

        If the scheduler has not been started yet, only pending jobs can be returned because the
        job stores haven't been started yet either.

        :param str|unicode jobstore: alias of the job store
        :param bool pending: **DEPRECATED**
        :rtype: list[Job]
        """
        if pending is not None:
            warnings.warn(
                'The "pending" option is deprecated -- get_jobs() always returns '
                "scheduled jobs if the scheduler has been started and pending jobs "
                "otherwise",
                DeprecationWarning,
                stacklevel=2,
            )

        async with self._jobstores_lock:
            jobs = []
            if self.state == STATE_STOPPED:
                for job, alias, _replace_existing in self._pending_jobs:
                    if jobstore is None or alias == jobstore:
                        jobs.append(job)
            else:
                for alias, store in self._jobstores.items():
                    if jobstore is None or alias == jobstore:
                        store_jobs = store.get_all_jobs()
                        if inspect.iscoroutine(store_jobs):
                            store_jobs = await store_jobs
                        jobs.extend(store_jobs)

            return jobs

    async def get_job(self, job_id, jobstore=None):
        """Returns the Job that matches the given ``job_id``.

        :param str|unicode job_id: the identifier of the job
        :param str|unicode jobstore: alias of the job store that most likely contains the job
        :return: the Job by the given ID, or ``None`` if it wasn't found
        :rtype: Job

        """
        async with self._jobstores_lock:
            try:
                result = self._lookup_job(job_id, jobstore)
                if inspect.iscoroutine(result):
                    job, _ = await result
                else:
                    job, _ = result
            except JobLookupError:
                return None
            return job

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
                            if inspect.iscoroutine(result):
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

        if self.state == STATE_RUNNING:
            self.wakeup()

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
                        if inspect.iscoroutine(result):
                            await result

        await self._dispatch_event(SchedulerEvent(EVENT_ALL_JOBS_REMOVED, jobstore))

    async def print_jobs(self, jobstore=None, out=None):
        """Print a textual listing of all jobs.

        Prints out a textual listing of all jobs currently scheduled on either all job stores or
        just a specific one.

        :param str|unicode jobstore: alias of the job store, ``None`` to list jobs from all stores
        :param file out: a file-like object to print to (defaults to **sys.stdout** if nothing is
            given)

        """
        out = out or sys.stdout
        async with self._jobstores_lock:
            if self.state == STATE_STOPPED:
                print("Pending jobs:", file=out)
                if self._pending_jobs:
                    for job, jobstore_alias, _replace_existing in self._pending_jobs:
                        if jobstore in (None, jobstore_alias):
                            print(f"    {job}", file=out)
                else:
                    print("    No pending jobs", file=out)
            else:
                for alias, store in sorted(self._jobstores.items()):
                    if jobstore in (None, alias):
                        print(f"Jobstore {alias}:", file=out)
                        jobs = store.get_all_jobs()
                        if inspect.iscoroutine(jobs):
                            jobs = await jobs
                        if jobs:
                            for job in jobs:
                                print(f"    {job}", file=out)
                        else:
                            print("    No scheduled jobs", file=out)

    async def export_jobs(self, outfile, jobstore=None):
        """Export stored jobs as JSON.

        :param outfile: either a file object opened in text write mode ("w"), or a path
            to the target file
        :param jobstore: alias of the job store to export jobs from (if omitted, export
            from all configured job stores)
        """
        import json
        import pickle
        from base64 import b64encode

        from apscheduler import version

        if self.state == STATE_STOPPED:
            msg = "the scheduler must have been started for job export to work"
            raise RuntimeError(msg)

        def encode_with_pickle(obj):
            return b64encode(pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)).decode("ascii")

        def json_default(obj):
            if hasattr(obj, "__getstate__") and hasattr(obj, "__setstate__"):
                state = obj.__getstate__()
                if isinstance(state, Mapping):
                    return {
                        "__apscheduler_class__": obj_to_ref(obj.__class__),
                        "__apscheduler_state__": state,
                    }

            return {"__apscheduler_pickle__": encode_with_pickle(obj)}

        async with self._jobstores_lock:
            all_jobs = [
                job
                for alias, store in self._jobstores.items()
                for job in store.get_all_jobs()
                if jobstore in (None, alias)
            ]

        if hasattr(outfile, "write"):
            json.dump(
                {
                    "version": 1,
                    "scheduler_version": version,
                    "jobs": [job.__getstate__() for job in all_jobs],
                },
                outfile,
                default=json_default,
            )
        else:
            async with aiofiles.open(Path(outfile), mode="w") as f:
                await f.write(
                    json.dumps(
                        {
                            "version": 1,
                            "scheduler_version": version,
                            "jobs": [job.__getstate__() for job in all_jobs],
                        },
                        default=json_default,
                    )
                )

    async def import_jobs(self, infile, jobstore="default"):
        """Import jobs previously exported via :meth:`export_jobs`.

        :param infile: either a file object opened in text read mode ("r") or a path to
            a JSON file containing previously exported jobs
        :param jobstore: the alias of the job store to import the jobs to

        .. warning:: This function uses pickle for deserialization, which can be unsafe
            when loading data from untrusted sources. Only load job data from trusted sources.
        """
        import json
        import pickle
        from base64 import b64decode

        def json_object_hook(dct):
            if pickle_data := dct.get("__apscheduler_pickle__"):
                try:
                    return pickle.loads(b64decode(pickle_data))  # noqa: S301
                except pickle.UnpicklingError as e:
                    msg = "Failed to unpickle job data"
                    raise ValueError(msg) from e

            if (obj_class := dct.get("__apscheduler_class__")) and (obj_state := dct.get("__apscheduler_state__")):
                obj_class = ref_to_obj(obj_class)
                obj = object.__new__(obj_class)
                obj.__setstate__(obj_state)
                return obj

            return dct

        jobstore = self._jobstores[jobstore]

        if hasattr(infile, "read"):
            data = json.load(infile, object_hook=json_object_hook)
        else:
            async with aiofiles.open(Path(infile)) as f:
                content = await f.read()
                data = json.loads(content, object_hook=json_object_hook)

        if not isinstance(data, dict):
            msg = "Invalid job data format"
            raise TypeError(msg)

        if (version := data.get("version", None)) != 1:
            msg = f"unrecognized version: {version}"
            raise ValueError(msg)

        for job_state in data["jobs"]:
            job = object.__new__(APSJob)
            job.__setstate__(job_state)
            jobstore.add_job(job)

    @abstractmethod
    def wakeup(self):
        """Notify the scheduler about jobs due for execution.

        Notifies the scheduler that there may be jobs due for execution.
        Triggers :meth:`_process_jobs` to be run in an implementation specific manner.
        """

    #
    # Private API
    #

    async def _configure(self, config):
        # Set general options
        self._logger = maybe_ref(config.pop("logger", None)) or getLogger("apscheduler.scheduler")
        self.timezone = timezone.utc  # This is the default timezone for the scheduler
        self.jobstore_retry_interval = float(config.pop("jobstore_retry_interval", 10))

        # Set the job defaults
        job_defaults = config.get("job_defaults", {})
        self._job_defaults = {
            "misfire_grace_time": asint(job_defaults.get("misfire_grace_time", 1)),
            "coalesce": asbool(job_defaults.get("coalesce", True)),
            "max_instances": asint(job_defaults.get("max_instances", 1)),
        }

        # Configure executors
        self._executors.clear()
        for alias, value in config.get("executors", {}).items():
            if isinstance(value, BaseExecutor):
                await self.add_executor(value, alias)
            elif isinstance(value, MutableMapping):
                executor_class = value.pop("class", None)
                plugin = value.pop("type", None)
                if plugin:
                    executor = self._create_plugin_instance("executor", plugin, value)
                elif executor_class:
                    cls = maybe_ref(executor_class)
                    executor = cls(**value)
                else:
                    msg = f'Cannot create executor "{alias}" -- either "type" or "class" must be defined'
                    raise ValueError(msg)

                await self.add_executor(executor, alias)
            else:
                msg = self._create_executor_error_message(alias, value)
                raise TypeError(msg)

        # Configure job stores
        self._jobstores.clear()
        for alias, value in config.get("jobstores", {}).items():
            if isinstance(value, BaseJobStore):
                await self.add_jobstore(value, alias)
            elif isinstance(value, MutableMapping):
                jobstore_class = value.pop("class", None)
                plugin = value.pop("type", None)
                if plugin:
                    jobstore = self._create_plugin_instance("jobstore", plugin, value)
                elif jobstore_class:
                    cls = maybe_ref(jobstore_class)
                    jobstore = cls(**value)
                else:
                    msg = f'Cannot create job store "{alias}" -- either "type" or "class" must be defined'
                    raise ValueError(msg)

                await self.add_jobstore(jobstore, alias)
            else:
                msg = self._create_jobstore_error_message(alias, value)
                raise TypeError(msg)

    def _create_default_executor(self):
        """Creates a default executor store, specific to the particular scheduler type."""
        return ThreadPoolExecutor()

    def _create_default_jobstore(self):
        """Creates a default job store, specific to the particular scheduler type."""
        return MemoryJobStore()

    async def _lookup_executor(self, alias):
        """Returns the executor instance by the given name.

        Returns the executor instance by the given name from the list of executors that were added
        to this scheduler.

        :type alias: str
        :raises KeyError: if no executor by the given alias is not found
        """
        try:
            return self._executors[alias]
        except KeyError as err:
            msg = f"No such executor: {alias}"
            raise KeyError(msg) from err

    def _lookup_jobstore(self, alias):
        """Returns the job store instance by the given name.

        Returns the job store instance by the given name from the list of job stores that were
        added to this scheduler.

        :type alias: str
        :raises KeyError: if no job store by the given alias is not found
        """
        try:
            return self._jobstores[alias]
        except KeyError as err:
            msg = f"No such job store: {alias}"
            raise KeyError(msg) from err

    async def _lookup_job(self, job_id, jobstore_alias):
        """Find a job by its ID.

        :type job_id: str
        :param str jobstore_alias: alias of a job store to look in
        :return tuple[Job, str]: a tuple of job, jobstore alias (jobstore alias is None in case of
            a pending job)
        :raises JobLookupError: if no job by the given ID is found.
        """
        if self.state == STATE_STOPPED:
            # Check if the job is among the pending jobs
            for job, _store_alias, _replace_existing in self._pending_jobs:
                if job.id == job_id:
                    return job, None
        else:
            # Look in all job stores
            for alias, store in self._jobstores.items():
                if jobstore_alias in (None, alias):
                    result = store.lookup_job(job_id)
                    if inspect.iscoroutine(result):
                        job = await result
                    else:
                        job = result
                    if job is not None:
                        return job, alias

        raise JobLookupError(job_id)

    async def _dispatch_event(self, event):
        """Dispatches the given event to interested listeners.

        :param SchedulerEvent event: the event to send

        """
        async with self._listeners_lock:
            listeners = tuple(self._listeners)

        for cb, mask in listeners:
            if event.code & mask:
                try:
                    result = cb(event)
                    if inspect.iscoroutine(result):
                        await result
                except BaseException:
                    self._logger.exception("Error notifying listener")

    def _check_uwsgi(self):
        """Check if we're running under uWSGI with threads disabled."""
        uwsgi_module = sys.modules.get("uwsgi")
        if not getattr(uwsgi_module, "has_threads", True):
            msg = (
                "The scheduler seems to be running under uWSGI, but threads have "
                "been disabled. You must run uWSGI with the --enable-threads "
                "option for the scheduler to work."
            )
            raise RuntimeError(msg)

    async def _real_add_job(self, job, jobstore_alias, replace_existing):
        """Add a job to the job store.

        :param Job job: the job to add
        :param bool replace_existing: ``True`` to use update_job() in case the job already exists
            in the store
        """
        # Fill in undefined values with defaults
        replacements = {key: value for key, value in self._job_defaults.items() if not hasattr(job, key)}

        # Calculate the next run time if there is none defined
        if not hasattr(job, "next_run_time"):
            now = datetime.now(self.timezone)
            replacements["next_run_time"] = job.trigger.get_next_fire_time(None, now)

        # Apply any replacements
        job._modify(**replacements)

        # Add the job to the given job store
        store = self._lookup_jobstore(jobstore_alias)
        try:
            result = store.add_job(job)
            if inspect.iscoroutine(result):
                await result
        except ConflictingIdError:
            if replace_existing:
                result = store.update_job(job)
                if inspect.iscoroutine(result):
                    await result
            else:
                raise

        # Mark the job as no longer pending
        job._jobstore_alias = jobstore_alias

        # Notify listeners that a new job has been added
        event = JobEvent(EVENT_JOB_ADDED, job.id, jobstore_alias)
        await self._dispatch_event(event)

        self._logger.info('Added job "%s" to job store "%s"', job.name, jobstore_alias)

        # Notify the scheduler about the new job
        if self.state == STATE_RUNNING:
            self.wakeup()

    def _create_plugin_instance(self, type_, alias, constructor_kwargs):
        """Create an instance of the given plugin type.

        Creates an instance of the given plugin type, loading the plugin first if necessary.
        """
        plugin_container, class_container, base_class = {
            "trigger": (self._trigger_plugins, self._trigger_classes, BaseTrigger),
            "jobstore": (self._jobstore_plugins, self._jobstore_classes, BaseJobStore),
            "executor": (self._executor_plugins, self._executor_classes, BaseExecutor),
        }[type_]

        try:
            plugin_cls = class_container[alias]
        except KeyError:
            if alias in plugin_container:
                plugin_cls = class_container[alias] = plugin_container[alias].load()
                if not issubclass(plugin_cls, base_class):
                    msg = f"The {type_} entry point does not point to a {type_} class"
                    raise TypeError(msg) from None
            else:
                msg = f'No {type_} by the name "{alias}" was found'
                raise LookupError(msg) from None

        return plugin_cls(**constructor_kwargs)

    def _create_trigger(self, trigger, trigger_args):
        if isinstance(trigger, BaseTrigger):
            return trigger
        if trigger is None:
            trigger = "date"
        elif not isinstance(trigger, str):
            msg = f"Expected a trigger instance or string, got {trigger.__class__.__name__} instead"
            raise TypeError(msg)

        # Use the scheduler's time zone if nothing else is specified
        trigger_args.setdefault("timezone", self.timezone)

        # Instantiate the trigger class
        return self._create_plugin_instance("trigger", trigger, trigger_args)

    def _create_lock(self):
        """Creates a reentrant lock object."""
        return AsyncRLock()

    async def _process_jobs(self):
        """Process due jobs and determine next wakeup time.

        Iterates through jobs in every jobstore, starts jobs that are due and figures out how long
        to wait for the next round.

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
                    if inspect.iscoroutine(due_jobs):
                        due_jobs = await due_jobs
                except (JobLookupError, ConflictingIdError, RuntimeError) as e:
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
                            if inspect.iscoroutine(result):
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
                            if inspect.iscoroutine(result):
                                await result
                        else:
                            await self.remove_job(job.id, jobstore_alias)

                # Set a new next wakeup time if there isn't one yet or
                # the jobstore has an even earlier one
                jobstore_next_run_time = jobstore.get_next_run_time()
                if inspect.iscoroutine(jobstore_next_run_time):
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

    def _create_executor_error_message(self, alias, value):
        """Create error message for invalid executor type."""
        cls_name = value.__class__.__name__
        msg_parts = [f"Expected executor instance or dict for executors['{alias}']", f"got {cls_name} instead"]
        return ", ".join(msg_parts)

    def _create_jobstore_error_message(self, alias, value):
        """Create error message for invalid job store type."""
        cls_name = value.__class__.__name__
        msg_parts = [f"Expected job store instance or dict for jobstores['{alias}']", f"got {cls_name} instead"]
        return ", ".join(msg_parts)
