import asyncio
import threading
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

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
