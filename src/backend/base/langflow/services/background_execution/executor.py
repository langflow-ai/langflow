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
import time
from collections.abc import Awaitable, Callable

from lfx.log.logger import logger
from lfx.observability import _root_error_type, application_span
from opentelemetry import trace
from opentelemetry.trace import Link, SpanContext, SpanKind

CoroFactory = Callable[[], Awaitable[None]]


class InProcessExecutor:
    """A bounded worker pool over an asyncio.Queue."""

    def __init__(self, max_concurrency: int = 5) -> None:
        self._max_concurrency = max(int(max_concurrency), 1)
        self._queue: asyncio.Queue[tuple[str, CoroFactory, int, SpanContext | None]] = asyncio.Queue()
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
        span_context = trace.get_current_span().get_span_context()
        origin = span_context if span_context.is_valid else None
        await self._queue.put((key, coro_factory, time.time_ns(), origin))

    async def cancel(self, key: str) -> bool:
        """Cancel the in-flight task for ``key``. Returns False if not in flight."""
        task = self._in_flight.get(key)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    @staticmethod
    async def _await_task(task: asyncio.Task) -> None:
        # A bare ``await task`` relies on the task's own wakeup of its awaiter. On
        # Python 3.10, when stop() cancels this worker while the job task is also
        # finishing, that wakeup is lost: the job task completes but the worker is
        # never rescheduled, so the event loop idles forever in select(None) — a
        # hard deadlock in stop(). A done-callback + Event is immune (it is the
        # same mechanism stop()'s own asyncio.gather uses, which never hangs), and
        # task.result() re-raises CancelledError/exception exactly like await task.
        done = asyncio.Event()
        task.add_done_callback(lambda _t: done.set())
        await done.wait()
        task.result()

    async def _worker(self, worker_id: int) -> None:
        while True:
            try:
                key, coro_factory, enqueued_at, origin = await self._queue.get()
            except asyncio.CancelledError:
                return
            links = [Link(origin)] if origin is not None else None
            attributes = {
                "messaging.system": "langflow",
                "messaging.destination.name": "workflow.jobs",
                "langflow.job.id": key,
                "langflow.job.type": "workflow",
                "langflow.job.backend": "in_process",
            }
            with application_span(
                "langflow.job.queue_wait",
                {**attributes, "messaging.operation.type": "settle", "langflow.phase": "job.queue_wait"},
                links=links,
                root=True,
                start_time=enqueued_at,
            ):
                pass
            with application_span(
                "langflow.job.dequeue",
                {**attributes, "messaging.operation.type": "receive", "langflow.phase": "job.dequeue"},
                kind=SpanKind.CONSUMER,
                links=links,
                root=True,
            ):
                pass
            with application_span(
                "langflow.job.execute",
                {
                    **attributes,
                    "messaging.operation.type": "process",
                    "langflow.phase": "job.execute",
                    "langflow.worker.id": worker_id,
                },
                kind=SpanKind.CONSUMER,
                links=links,
                root=True,
            ) as execute_span:
                task = asyncio.create_task(coro_factory())
                self._in_flight[key] = task
                try:
                    await self._await_task(task)
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
                    execute_span.set_attribute("langflow.job.status", "cancelled")
                    await logger.adebug(f"Background job {key} cancelled on worker {worker_id}")
                except Exception as exc:  # noqa: BLE001
                    execute_span.record_error(_root_error_type(exc))
                    await logger.aerror(f"Background job {key} failed on worker {worker_id}: {exc}", exc_info=True)
                finally:
                    if self._in_flight.get(key) is task:
                        self._in_flight.pop(key, None)
                    self._queue.task_done()
