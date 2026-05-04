"""Public entry points for the execution layer."""

from __future__ import annotations

from dataclasses import dataclass

from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.coordinator import Coordinator
from lfx.execution.executor import Executor
from lfx.execution.partitioner import identity_partition
from lfx.execution.registry import ExecutorNotFoundError, ExecutorRegistry
from lfx.execution.types import RunComplete, StepResult, Unit


@dataclass
class _Defaults:
    registry: ExecutorRegistry | None = None
    coordinator: Coordinator | None = None


_defaults = _Defaults()


def get_default_registry() -> ExecutorRegistry:
    if _defaults.registry is None:
        registry = ExecutorRegistry()
        registry.register(InProcessExecutor())
        _defaults.registry = registry
    return _defaults.registry


def get_default_coordinator() -> Coordinator:
    if _defaults.coordinator is None:
        _defaults.coordinator = Coordinator(registry=get_default_registry())
    return _defaults.coordinator


def set_default_coordinator(coordinator: Coordinator) -> None:
    _defaults.coordinator = coordinator


def reset_default_coordinator() -> None:
    """Drop the module-level singletons; next access rebuilds them. For tests."""
    _defaults.registry = None
    _defaults.coordinator = None


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
