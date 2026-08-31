import threading
from unittest.mock import patch

from lfx.execution import (
    Coordinator,
    aget_default_coordinator,
    get_default_coordinator,
    get_default_registry,
    set_default_coordinator,
)
from lfx.services.executor.service import ExecutorService
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType


def test_default_registry_has_in_process():
    assert get_default_registry().get("in-process").kind == "in-process"


def test_default_coordinator_uses_default_registry():
    c = get_default_coordinator()
    assert isinstance(c, Coordinator)


def test_set_default_coordinator_overrides_singleton():
    original = get_default_coordinator()
    custom = Coordinator(registry=get_default_registry())
    set_default_coordinator(custom)
    try:
        assert get_default_coordinator() is custom
    finally:
        # Restore the singleton so this override doesn't bleed into later tests.
        set_default_coordinator(original)


def test_default_coordinator_is_idempotent_within_a_test():
    a = get_default_coordinator()
    b = get_default_coordinator()
    assert a is b


async def test_aget_default_coordinator_builds_cold_service_off_the_loop():
    """The cold build imports entry-point plugins, so it must not run on the event loop."""
    service_manager = get_service_manager()
    service_manager.services.pop(ServiceType.EXECUTOR_SERVICE, None)

    loop_thread = threading.get_ident()
    build_thread: list[int] = []
    original_init = ExecutorService.__init__

    def recording_init(self, settings_service):
        build_thread.append(threading.get_ident())
        original_init(self, settings_service)

    with patch.object(ExecutorService, "__init__", recording_init):
        coordinator = await aget_default_coordinator()

    assert isinstance(coordinator, Coordinator)
    assert build_thread, "ExecutorService was never constructed"
    assert build_thread[0] != loop_thread


async def test_aget_default_coordinator_stays_on_the_loop_once_warm():
    """Once the service exists the lookup is a dict hit -- no thread hand-off needed."""
    warm = get_default_coordinator()

    with patch("lfx.execution.asyncio.to_thread") as to_thread:
        assert await aget_default_coordinator() is warm

    to_thread.assert_not_called()
