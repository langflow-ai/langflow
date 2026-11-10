"""Tests for the sync-wrapper markers and the loop-safe thread-lock helper in ``async_helpers``."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output
from lfx.utils.async_helpers import acquire_thread_lock, async_delegate_target, delegates_to, run_until_complete


class _Loader:
    @delegates_to("aload")
    def load(self) -> str:
        return run_until_complete(self.aload())

    async def aload(self) -> str:
        return "async"


class _SyncOverride(_Loader):
    def load(self) -> str:
        return "sync override"


class _AsyncOverride(_Loader):
    async def aload(self) -> str:
        return "async override"


class TestAsyncDelegateTarget:
    def test_marked_wrapper_resolves_to_bound_coroutine(self):
        loader = _Loader()

        target = async_delegate_target(loader, "load")

        assert target is not None
        assert target.__self__ is loader
        assert target.__func__ is _Loader.aload

    async def test_async_override_is_reached_through_inherited_wrapper(self):
        target = async_delegate_target(_AsyncOverride(), "load")

        assert target is not None
        assert await target() == "async override"

    def test_sync_override_on_subclass_is_not_a_wrapper(self):
        assert async_delegate_target(_SyncOverride(), "load") is None

    def test_instance_attribute_override_is_not_a_wrapper(self):
        loader = _Loader()
        loader.load = lambda: "instance override"

        assert async_delegate_target(loader, "load") is None

    def test_mock_override_is_not_mistaken_for_a_wrapper(self):
        loader = _Loader()
        loader.load = MagicMock(return_value="mocked")

        assert async_delegate_target(loader, "load") is None

    def test_missing_method_returns_none(self):
        assert async_delegate_target(_Loader(), "does_not_exist") is None

    def test_sync_wrapper_still_works_without_a_loop(self):
        assert _Loader().load() == "async"
        assert _AsyncOverride().load() == "async override"


# Supplying the code up front keeps construction independent of ``inspect.getsource``, which
# an earlier test in a full-suite run can leave unable to read this module.
_INLINE_COMPONENT_CODE = "# inline test component"


class _DelegatingOutputComponent(Component):
    outputs = [Output(display_name="Value", name="value", method="build_value")]

    @delegates_to("abuild_value")
    def build_value(self) -> str:
        msg = "graph output dispatch must await the coroutine, not run the sync wrapper"
        raise AssertionError(msg)

    async def abuild_value(self) -> str:
        return "awaited"


class _OverriddenOutputComponent(_DelegatingOutputComponent):
    def build_value(self) -> str:
        return f"sync override on {threading.current_thread().name}"


class TestOutputDispatch:
    async def test_output_backed_by_wrapper_awaits_its_coroutine(self):
        component = _DelegatingOutputComponent(_code=_INLINE_COMPONENT_CODE)

        result = await component._get_output_result(component._outputs_map["value"])

        assert result == "awaited"

    async def test_overridden_sync_output_still_runs_in_a_worker_thread(self):
        component = _OverriddenOutputComponent(_code=_INLINE_COMPONENT_CODE)
        loop_thread = threading.current_thread().name

        result = await component._get_output_result(component._outputs_map["value"])

        assert result.startswith("sync override on ")
        assert result != f"sync override on {loop_thread}"


class TestAcquireThreadLock:
    async def test_uncontended_lock_is_taken_inline(self):
        lock = threading.Lock()

        await acquire_thread_lock(lock)

        try:
            assert lock.locked()
        finally:
            lock.release()

    async def test_contended_acquire_keeps_the_loop_running(self):
        lock = threading.Lock()
        lock.acquire()
        waiter = asyncio.create_task(acquire_thread_lock(lock))

        # The loop must keep scheduling other work while the waiter is blocked.
        for _ in range(5):
            await asyncio.sleep(0.01)
        assert not waiter.done()

        lock.release()
        await asyncio.wait_for(waiter, timeout=2)
        try:
            assert lock.locked()
        finally:
            lock.release()

    async def test_cancelled_waiter_never_acquires_the_lock(self):
        lock = _RecordingLock()
        lock.acquire()
        waiter = asyncio.create_task(acquire_thread_lock(lock))  # type: ignore[arg-type]
        await asyncio.sleep(0.05)

        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

        lock.release()
        await asyncio.sleep(0.1)
        assert lock.acquired == 1
        assert lock.released == 1
        assert not lock.locked()


class _RecordingLock:
    """A ``threading.Lock`` stand-in that counts successful acquires and releases."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts = threading.Lock()
        self.acquired = 0
        self.released = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:  # noqa: FBT001, FBT002
        got = self._lock.acquire(blocking, timeout)
        if got:
            with self._counts:
                self.acquired += 1
        return got

    def release(self) -> None:
        with self._counts:
            self.released += 1
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()
