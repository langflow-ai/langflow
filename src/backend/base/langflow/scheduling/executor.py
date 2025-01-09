import sys

from apscheduler.executors.base import BaseExecutor, MaxInstancesReachedError, run_coroutine_job, run_job
from apscheduler.util import iscoroutinefunction_partial


class AsyncIOExecutor(BaseExecutor):
    """Runs jobs in the default executor of the event loop.

    If the job function is a native coroutine function, it is scheduled to be run directly in the
    event loop as soon as possible. All other functions are run in the event loop's default
    executor which is usually a thread pool.

    Plugin alias: ``asyncio``
    """

    def start(self, scheduler, alias):
        super().start(scheduler, alias)
        self._eventloop = scheduler._eventloop
        self._pending_futures = set()

    def shutdown(self, *, wait=True):  # noqa: ARG002
        # There is no way to honor wait=True without converting this method into a coroutine method
        for f in self._pending_futures:
            if not f.done():
                f.cancel()

        self._pending_futures.clear()

    async def _do_submit_job(self, job, run_times):
        if iscoroutinefunction_partial(job.func):
            coro = run_coroutine_job(job, job._jobstore_alias, run_times, self._logger.name)
            f = self._eventloop.create_task(coro)
        else:
            f = self._eventloop.run_in_executor(None, run_job, job, job._jobstore_alias, run_times, self._logger.name)

        try:
            events = await f
            await self._run_job_success(job.id, events)
        except BaseException:  # noqa: BLE001
            await self._run_job_error(job.id, *sys.exc_info()[1:])
        finally:
            self._pending_futures.discard(f)

    async def submit_job(self, job, run_times):
        """Submits job for execution.

        :param Job job: job to execute
        :param list[datetime] run_times: list of datetimes specifying
            when the job should have been run
        :raises MaxInstancesReachedError: if the maximum number of
            allowed instances for this job has been reached

        """
        if self._lock is None:
            msg = "This executor has not been started yet"
            raise RuntimeError(msg)
        async with self._lock:
            if self._instances[job.id] >= job.max_instances:
                raise MaxInstancesReachedError(job)

            await self._do_submit_job(job, run_times)
            self._instances[job.id] += 1

    async def _run_job_success(self, job_id, events):
        """Called by the executor with the list of generated events.

        Called when :func:`run_job` has been successfully called.
        """
        async with self._lock:
            self._instances[job_id] -= 1
            if self._instances[job_id] == 0:
                del self._instances[job_id]

        for event in events:
            await self._scheduler._dispatch_event(event)

    async def _run_job_error(self, job_id, exc, traceback=None):
        """Called by the executor with the exception if there is an error calling `run_job`."""
        async with self._lock:
            self._instances[job_id] -= 1
            if self._instances[job_id] == 0:
                del self._instances[job_id]

        exc_info = (exc.__class__, exc, traceback)
        self._logger.error("Error running job %s", job_id, exc_info=exc_info)
