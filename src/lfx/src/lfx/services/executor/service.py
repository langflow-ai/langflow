"""Executor service: owns the executor registry and the default coordinator."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from lfx.execution.backends.in_process import InProcessExecutor
from lfx.execution.coordinator import Coordinator
from lfx.execution.registry import ExecutorKindCollisionError, ExecutorRegistry
from lfx.log.logger import logger
from lfx.services.base import Service

if TYPE_CHECKING:
    from lfx.execution.executor import Executor
    from lfx.services.settings.service import SettingsService


ENTRY_POINT_GROUP = "lfx.executors"


class ExecutorService(Service):
    """Service that holds the executor registry and the default coordinator."""

    name = "executor_service"

    def __init__(self, settings_service: SettingsService) -> None:
        super().__init__()
        self._settings_service = settings_service
        self._registry = ExecutorRegistry()
        self._coordinator: Coordinator | None = None
        self._populate_registry()

    def register(self, executor: Executor) -> None:
        """Register an executor; replaces any prior registration for the same kind.

        Invalidates the cached coordinator so the next access rebuilds against the new
        registry contents. Direct mutation of the registry through other paths bypasses
        this invalidation -- always go through this method to register or replace.
        """
        self._registry.register(executor)
        self._coordinator = None

    def has(self, kind: str) -> bool:
        """Return True if an executor with the given kind is registered."""
        return self._registry.has(kind)

    def get(self, kind: str) -> Executor:
        """Return the executor registered under the given kind."""
        return self._registry.get(kind)

    @property
    def registry(self) -> ExecutorRegistry:
        """Return the underlying registry.

        Read access only. Mutating the registry directly (e.g. ``service.registry.register(...)``)
        bypasses the cached-coordinator invalidation done by :meth:`register`; always go through
        :meth:`register` for mutations.
        """
        return self._registry

    @property
    def coordinator(self) -> Coordinator:
        if self._coordinator is None:
            kind = self._settings_service.settings.executor_kind
            self._coordinator = Coordinator(registry=self._registry, executor_kind=kind)
        return self._coordinator

    def set_coordinator(self, coordinator: Coordinator) -> None:
        """Override the default coordinator (test/extension hook)."""
        self._coordinator = coordinator

    def _populate_registry(self) -> None:
        """Register the built-in executor and run plugin discovery."""
        self._registry.register(InProcessExecutor())
        self._discover_entry_points()

    def _discover_entry_points(self) -> None:
        try:
            eps = entry_points(group=ENTRY_POINT_GROUP)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to enumerate entry points for group=%r. Executor plugin discovery skipped.",
                ENTRY_POINT_GROUP,
            )
            return
        for ep in eps:
            kind: str = "<unknown>"
            try:
                obj = ep.load()
                executor = obj() if isinstance(obj, type) else obj
                kind = getattr(executor, "kind", "<unknown>")
                self._registry.register(executor, replace=False)
                logger.debug("Loaded executor from entry point: %s -> %s", ep.name, kind)
            except ExecutorKindCollisionError:
                logger.warning(
                    "Skipping entry point %r: an executor with kind=%r is already registered. "
                    "Entry-point discovery cannot replace existing executors; register the "
                    "executor explicitly via ExecutorService.register() if replacement is intended.",
                    ep.name,
                    kind,
                )
            except Exception:  # noqa: BLE001
                # Broad catch is intentional: a single broken plugin must not break discovery
                # of others. The full traceback is preserved via logger.exception.
                logger.exception("Failed to load executor entry point %s", ep.name)

    async def teardown(self) -> None:
        """Reset the service to its post-init state.

        ServiceManager.teardown() does not evict the cached service instance, so we must
        leave the registry usable: the built-in InProcessExecutor is re-registered and
        plugin discovery re-runs so a post-teardown access still returns a working
        coordinator.
        """
        self._coordinator = None
        self._registry = ExecutorRegistry()
        self._populate_registry()
