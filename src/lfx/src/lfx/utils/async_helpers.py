import asyncio
import threading
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import anyio

from lfx.log.logger import logger

_F = TypeVar("_F", bound=Callable[..., Any])

# Dunder-named so ``unittest.mock`` objects report it missing instead of inventing a value.
_ASYNC_DELEGATE_ATTR = "__lfx_async_delegate__"

if hasattr(asyncio, "timeout"):

    @asynccontextmanager
    async def timeout_context(timeout_seconds):
        with asyncio.timeout(timeout_seconds) as ctx:
            yield ctx

else:

    @asynccontextmanager
    async def timeout_context(timeout_seconds):
        try:
            yield await asyncio.wait_for(asyncio.Future(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            msg = f"Operation timed out after {timeout_seconds} seconds"
            raise TimeoutError(msg) from e


def run_until_complete(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # If there's no event loop, create a new one and run the coroutine
        return asyncio.run(coro)
    # If there's already a running event loop, we can't call run_until_complete on it.
    # Instead, run the coroutine in a new thread with a new event loop. Propagate the
    # caller's contextvars context so request-scoped state (e.g. lfx serve request
    # variables and the no-env-fallback flag) stays visible inside the worker thread;
    # a bare ThreadPoolExecutor would otherwise reset every ContextVar to its default.
    import concurrent.futures
    import contextvars

    ctx = contextvars.copy_context()

    def run_in_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            try:
                # Like asyncio.run: close async generators on this loop so
                # resources bound to it (such as a per-loop database engine)
                # are released on the loop that owns them.
                new_loop.run_until_complete(new_loop.shutdown_asyncgens())
            finally:
                new_loop.close()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(ctx.run, run_in_new_loop)
        return future.result()


def delegates_to(async_name: str) -> Callable[[_F], _F]:
    """Mark a sync method as a thin wrapper around the coroutine method ``async_name``.

    The wrapper body should be ``return run_until_complete(self.<async_name>(...))``. Callers
    that already run on an event loop look the marker up with ``async_delegate_target`` and
    await the coroutine directly, instead of pushing the wrapper to a worker thread where
    ``run_until_complete`` has to start yet another event loop.

    A subclass that overrides the sync method does not inherit the marker, so async callers
    fall back to running that override in a thread. The class that owns the coroutine must
    implement it natively: a marked wrapper whose coroutine calls back into the wrapper would
    recurse forever. File-loader sync wrappers should run from plain threads; a coroutine
    should await the corresponding async method to avoid blocking its event loop.
    """

    def decorator(func: _F) -> _F:
        setattr(func, _ASYNC_DELEGATE_ATTR, async_name)
        return func

    return decorator


def async_delegate_target(obj: object, method_name: str) -> Callable[..., Awaitable[Any]] | None:
    """Return the bound coroutine method behind ``obj.<method_name>``, if it is a marked wrapper.

    Returns ``None`` when the method is missing, unmarked, or overridden (on the class or the
    instance) by something that is not itself a ``delegates_to`` wrapper.
    """
    method = getattr(obj, method_name, None)
    async_name = getattr(method, _ASYNC_DELEGATE_ATTR, None)
    if not isinstance(async_name, str):
        return None
    return getattr(obj, async_name)


async def acquire_thread_lock(lock: threading.Lock) -> None:
    """Acquire a ``threading.Lock`` from a coroutine without blocking the event loop.

    Use this for state that both coroutines and plain threads (or coroutines on other event
    loops) must serialize on, where an ``asyncio.Lock`` bound to one loop cannot work.

    The uncontended case takes the lock inline. Under contention, poll without occupying a
    worker thread needed by the lock holder. Cancellation cannot acquire an orphaned lock.
    """
    delay = 0.001
    while not lock.acquire(blocking=False):
        await asyncio.sleep(delay)
        delay = min(delay * 2, 0.05)


# How long a stream whose client went away waits for its cancelled run to unwind. Far above
# cooperative cleanup (a job row's FAILED write, a component closing its client), so it only
# bites when a component swallows its cancellation; that run then finishes unobserved.
RUN_CANCEL_GRACE_SECONDS = 30.0


async def cancel_and_wait(task: asyncio.Task[Any], *, grace_seconds: float | None) -> None:
    """Cancel ``task`` once and wait up to ``grace_seconds`` for it to finish unwinding.

    For a consumer tearing down a producer task it owns, typically in the ``finally`` of a
    streaming generator. A bare ``task.cancel(); await task`` is unsafe there in two ways:

    * Starlette streams a response inside an AnyIO cancel scope and cancels that scope when
      the client disconnects. AnyIO cancellation is level-triggered: until the waiting task
      leaves the cancelled scope it is cancelled again on every event-loop tick, and asyncio
      forwards each of those cancels to the task it is awaiting. ``task`` then gets a cancel
      per tick, which cuts its cleanup short at the next ``await``. An
      ``anyio.CancelScope(shield=True)`` inside ``task`` does not help: it holds off AnyIO's
      own delivery, not a native ``Task.cancel()``.
    * A task that swallows its cancellation never finishes, so the caller waits forever.

    So the wait runs in a shielded scope, through ``asyncio.wait``, which neither forwards a
    cancel to ``task`` nor cancels it when the grace period runs out: ``task`` receives
    exactly this one cancel. A cancel aimed straight at the caller still ends the wait early
    without reaching ``task``.

    The bound is a trade-off. Past ``grace_seconds`` the caller moves on and ``task``
    finishes on its own, unobserved; nothing can force-stop a task that ignores
    cancellation, so the bound frees the caller, not the work. Keep ``grace_seconds`` well
    above how long cooperative cleanup takes (a few writes, closing a client), or the caller
    stops waiting on cleanup that is still running. ``None`` waits for as long as ``task``
    takes.

    Re-raises the task's exception, other than its cancellation, as ``await task`` would. A
    task that outlives the wait has a late failure logged rather than dropped.
    """
    if not task.done():
        task.cancel()
    try:
        with anyio.CancelScope(shield=True):
            await asyncio.wait({task}, timeout=grace_seconds)
    finally:
        # Also reached when the wait itself is cancelled: either way nobody awaits ``task`` now.
        if not task.done():
            task.add_done_callback(_log_late_failure)
    if not task.done():
        # Not awaited: past the shield the caller may sit in a cancelled scope again,
        # and an awaited log call would be the first thing cancelled.
        logger.warning(
            "Task %s was still running %ss after it was cancelled; no longer waiting for it",
            task.get_name(),
            grace_seconds,
        )
        return
    if not task.cancelled():
        task.result()


def _log_late_failure(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("Task %s failed after its caller stopped waiting for it", task.get_name(), exc_info=exc)
