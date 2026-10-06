import asyncio
import inspect
import threading
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

# Dunder-named so ``unittest.mock`` objects report it missing instead of inventing a value.
_ASYNC_DELEGATE_ATTR = "__lfx_async_delegate__"
_ASYNC_DELEGATE_OWNER_ATTR = "__lfx_async_delegate_owner__"

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
    """Mark a synchronous method as having an equivalent async implementation.

    The decorator only attaches metadata; it does not wrap or call the method.
    A marked method may bridge to its async counterpart or keep a parallel
    synchronous implementation. Async callers use ``async_delegate_target``
    to await the counterpart directly, avoiding a blocking sync-to-async bridge.

    An unmarked subclass/instance override must still execute its own behavior,
    so callers run it in a worker thread. Mark only equivalent implementations:
    bypassing custom validation or calling back into the sync method from its
    async counterpart can respectively skip behavior or recurse forever.
    """

    def decorator(func: _F) -> _F:
        setattr(func, _ASYNC_DELEGATE_ATTR, async_name)
        # functools.wraps copies function attributes. A wrapper must retain its
        # own behavior rather than inherit permission to skip straight to async.
        setattr(func, _ASYNC_DELEGATE_OWNER_ATTR, func)
        return func

    return decorator


def async_delegate_target(obj: object, method_name: str) -> Callable[..., Awaitable[Any]] | None:
    """Return the bound coroutine method behind ``obj.<method_name>``, if it is a marked wrapper.

    Returns ``None`` when the method is missing, unmarked, or overridden (on the class or the
    instance) by something that is not itself a ``delegates_to`` wrapper. Copied
    attributes from ``functools.wraps`` do not authorize skipping the wrapper.
    """
    method = getattr(obj, method_name, None)
    async_name = getattr(method, _ASYNC_DELEGATE_ATTR, None)
    if not isinstance(async_name, str):
        return None
    receiver = getattr(method, "__self__", None)
    if receiver is not None and receiver is not obj:
        # A supplied bound method must keep its original receiver/configuration.
        return None
    function = getattr(method, "__func__", method)
    if getattr(function, _ASYNC_DELEGATE_OWNER_ATTR, None) is not function:
        return None
    return getattr(obj, async_name)


async def async_call_method(obj: object, method_name: str, *args, **kwargs) -> Any:
    """Call a component method without bypassing a synchronous customization.

    Prefer a verified delegate, then a coroutine override. Otherwise use
    ``to_thread``, which copies request context variables (including credential
    fallback settings). Thread fallback protects loop progress; cancelling it
    cannot stop an already running sync extension. Native lookups remain fully
    cancellable on the caller loop.
    """
    method = async_delegate_target(obj, method_name)
    if method is not None:
        return await method(*args, **kwargs)
    method = getattr(obj, method_name)
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)
    return await asyncio.to_thread(method, *args, **kwargs)


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
