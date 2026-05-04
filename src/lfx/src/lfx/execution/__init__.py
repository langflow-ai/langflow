"""Public entry points for the execution layer."""

from __future__ import annotations

from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.coordinator import Coordinator
from lfx.execution.executor import Executor
from lfx.execution.partitioner import identity_partition
from lfx.execution.registry import ExecutorNotFoundError, ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult, Unit

_default_registry: ExecutorRegistry | None = None
_default_coordinator: Coordinator | None = None


def get_default_registry() -> ExecutorRegistry:
    global _default_registry  # noqa: PLW0603
    if _default_registry is None:
        registry = ExecutorRegistry()
        registry.register(InProcessExecutor())
        _default_registry = registry
    return _default_registry


def get_default_coordinator() -> Coordinator:
    global _default_coordinator  # noqa: PLW0603
    if _default_coordinator is None:
        _default_coordinator = Coordinator(registry=get_default_registry())
    return _default_coordinator


def set_default_coordinator(coordinator: Coordinator) -> None:
    global _default_coordinator  # noqa: PLW0603
    _default_coordinator = coordinator


def reset_default_coordinator() -> None:
    """Drop the module-level singletons; next access rebuilds them. For tests."""
    global _default_registry, _default_coordinator  # noqa: PLW0603
    _default_registry = None
    _default_coordinator = None


__all__ = [
    "Coordinator",
    "Executor",
    "ExecutorNotFoundError",
    "ExecutorRegistry",
    "RunComplete",
    "StepResult",
    "Unit",
    "get_default_coordinator",
    "get_default_registry",
    "identity_partition",
    "reset_default_coordinator",
    "set_default_coordinator",
]
