"""Bounded in-process executor for background workflow jobs.

A small pool of worker tasks drains a single ``asyncio.Queue`` of submitted
jobs. Concurrency is capped at ``max_concurrency`` so background runs cannot
starve the request event loop. A job is a ``(key, coro_factory)`` pair: the
factory is invoked by the worker that picks it up, so the coroutine is created
at execution time (not submit time) and a queued job holds no live coroutine.

Cancellation is keyed: ``cancel(key)`` cancels the in-flight task for that key.
A still-queued job is cancelled cooperatively by the caller (the runner checks
the durable STOP signal before it starts emitting); the executor only owns
in-flight task cancellation.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable

from lfx.log.logger import logger

CoroFactory = Callable[[], Awaitable[None]]


class InProcessExecutor:
    """A bounded worker pool over an asyncio.Queue."""

    def __init__(self, max_concurrency: int = 5) -> None:
        self._max_concurrency = max(int(max_concurrency), 1)
        self._queue: asyncio.Queue[tuple[str, CoroFactory]] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        # Maps a job key to its in-flight task so cancel() can reach it.
        self._in_flight: dict[str, asyncio.Task] = {}
        self._closed = False

    async def start(self) -> None:
        if self._workers:
            return
        self._closed = False
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self._max_concurrency)]
        await logger.adebug(f"InProcessExecutor started with {self._max_concurrency} workers")

    async def stop(self) -> None:
        self._closed = True
        # Cancel the in-flight JOB tasks directly first, then await them. A job
        # that catches its cancel (a user-stop reconciles to CANCELLED) would
        # otherwise leave the worker's ``await task`` in cancellation limbo, so we
        # do not rely on cancellation propagating through the worker. Awaiting the
        # job tasks here lets each one's shielded terminal reconcile finish BEFORE
        # teardown — without it a reconcile write races a closing DB engine and a
        # "Task was destroyed but it is pending" warning is logged.
        # return_exceptions swallows the CancelledError each task raises so one
        # cancel cannot mask the others.
        # Cancel the in-flight JOB tasks directly first, then await them. A job
        # that catches its cancel (a user-stop reconciles to CANCELLED) would
        # otherwise leave the worker's ``await task`` in cancellation limbo, so we
        # do not rely on cancellation propagating through the worker. Awaiting the
        # job tasks here lets each one's shielded terminal reconcile finish BEFORE
        # teardown — without it a reconcile write races a closing DB engine and a
        # "Task was destroyed but it is pending" warning is logged.
        # return_exceptions swallows the CancelledError each task raises so one
        # cancel cannot mask the others.
        in_flight = list(self._in_flight.values())
        for task in in_flight:
            task.cancel()
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)
        self._in_flight.clear()
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._workers.clear()

    async def submit(self, key: str, coro_factory: CoroFactory) -> None:
        """Enqueue a job. A free worker picks it up and invokes the factory."""
        if self._closed:
            msg = "Executor is closed"
            raise RuntimeError(msg)
        await self._queue.put((key, coro_factory))

    async def cancel(self, key: str) -> bool:
        """Cancel the in-flight task for ``key``. Returns False if not in flight."""
        task = self._in_flight.get(key)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def _worker(self, worker_id: int) -> None:
        while True:
            try:
                key, coro_factory = await self._queue.get()
            except asyncio.CancelledError:
                return
            task = asyncio.create_task(coro_factory())
            self._in_flight[key] = task
            try:
                await task
            except asyncio.CancelledError:
                # A cancelled job must not take the worker down with it — but a
                # cancel aimed at the WORKER (stop()) must. ``Task.cancelling()``
                # is Python 3.11+; the project supports 3.10, so we distinguish
                # the two with an explicit ``_closed`` flag set by ``stop()``
                # rather than that version-specific API. When ``stop()`` ran, the
                # cancel targets the worker — re-raise to exit. Otherwise it was
                # a ``cancel(key)`` aimed at the job — swallow and keep serving.
                if self._closed:
                    raise
                await logger.adebug(f"Background job {key} cancelled on worker {worker_id}")
            except Exception as exc:  # noqa: BLE001
                await logger.aerror(f"Background job {key} failed on worker {worker_id}: {exc}", exc_info=True)
            finally:
                if self._in_flight.get(key) is task:
                    self._in_flight.pop(key, None)
                self._queue.task_done()
