"""Public entry points for the execution layer.

The execution coordinator and registry are owned by the :class:`ExecutorService`
(``lfx.services.executor``). The helpers below are thin convenience wrappers that
resolve the service through the standard service manager so callers do not need to
know about the service plumbing.
"""

from __future__ import annotations

import asyncio

from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.coordinator import Coordinator
from lfx.execution.executor import Executor
from lfx.execution.partitioner import identity_partition
from lfx.execution.registry import ExecutorNotFoundError, ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult, Unit


def _get_executor_service():
    from lfx.services.deps import get_service
    from lfx.services.schema import ServiceType

    service = get_service(ServiceType.EXECUTOR_SERVICE)
    if service is None:
        msg = "ExecutorService is not available; check earlier logs for the underlying init failure."
        raise RuntimeError(msg)
    return service


def get_default_registry() -> ExecutorRegistry:
    return _get_executor_service().registry


def get_default_coordinator() -> Coordinator:
    return _get_executor_service().coordinator


def _executor_service_exists() -> bool:
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    return ServiceType.EXECUTOR_SERVICE in get_service_manager().services


async def aget_default_coordinator() -> Coordinator:
    """Async-safe :func:`get_default_coordinator` -- builds the service off the event loop.

    The first access in a process constructs the :class:`ExecutorService`, whose ``__init__``
    enumerates the ``lfx.executors`` entry points and imports every plugin it finds. That is
    synchronous disk I/O plus module imports, and doing it from inside a running loop stalls
    the loop long enough to trip event-loop-block detectors (~0.1s locally, more on loaded
    CI runners). Off-load that cold build to a worker thread; once the service exists the
    lookup is a dict hit, so the fast path stays on the loop.
    """
    if _executor_service_exists():
        return get_default_coordinator()
    return await asyncio.to_thread(get_default_coordinator)


def set_default_coordinator(coordinator: Coordinator) -> None:
    _get_executor_service().set_coordinator(coordinator)


def reset_default_coordinator() -> None:
    """Drop the executor service so the next access rebuilds registry + coordinator. For tests."""
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    get_service_manager().update(ServiceType.EXECUTOR_SERVICE)


__all__ = [
    "Coordinator",
    "Executor",
    "ExecutorNotFoundError",
    "ExecutorRegistry",
    "InProcessExecutor",
    "RunComplete",
    "StepResult",
    "Unit",
    "aget_default_coordinator",
    "get_default_coordinator",
    "get_default_registry",
    "identity_partition",
    "reset_default_coordinator",
    "set_default_coordinator",
]
