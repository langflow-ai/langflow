"""Generic adapter discovery and registration helpers.

Adapter registries are service-scoped plugin registries
that allow multiple adapters of the same service type
to be registered and used simultaneously.
Discovery sources mirror the existing ServiceManager
plugin model:

1. Decorator registration (immediate, at import time)
2. Entry points (during ``discover()``, ``override=False``)
3. Config files (during ``discover()``, ``override=True``)

Decorators register directly on the ``AdapterRegistry``
singleton (mirroring ``@register_service`` for top-level
services).  No intermediary staging dict is needed because
``get_adapter_registry`` derives ``entry_point_group`` and
``config_section_path`` from the ``AdapterType`` value by
convention.
"""

from __future__ import annotations

import asyncio
import importlib
import threading
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from lfx.services.adapters.schema import AdapterType

from lfx.log.logger import logger
from lfx.services.config_discovery import get_nested_section, get_preferred_config_source, load_toml_config

T = TypeVar("T")
AdapterT = TypeVar("AdapterT")

__all__ = [
    "AdapterRegistry",
    "AdapterRegistryConflictError",
    "get_adapter_registry",
    "register_adapter",
    "teardown_all_adapter_registries",
]


_adapter_registries: dict[AdapterType, AdapterRegistry[Any]] = {}
_adapter_registries_lock = threading.Lock()


class AdapterRegistryConflictError(ValueError):
    """Raised when a registry identity conflict is detected."""


def register_adapter(
    adapter_type: AdapterType,
    key: str,
    *,
    override: bool = True,
):
    """Decorator to register an adapter class for an adapter type.

    Registers immediately on the ``AdapterRegistry`` singleton (same
    pattern as ``@register_service`` for top-level services).
    """

    def decorator(adapter_class: type[AdapterT]) -> type[AdapterT]:
        registry = get_adapter_registry(adapter_type=adapter_type)
        registry.register_class(key, adapter_class, override=override)
        return adapter_class

    return decorator


class AdapterRegistry(Generic[T]):
    """Registry for adapters of a single AdapterType.

    Generic over ``T``, the adapter contract expected by callers
    (e.g. ``AdapterRegistry[DeploymentServiceProtocol]``).
    """

    def __init__(
        self,
        *,
        adapter_type: AdapterType,
        entry_point_group: str,
        config_section_path: tuple[str, ...],
    ) -> None:
        self.adapter_type = adapter_type
        self.entry_point_group = entry_point_group
        self.config_section_path = config_section_path
        self.adapter_classes: dict[str, type[T]] = {}
        self.adapter_instances: dict[str, T] = {}
        self._discovered = False
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        return (
            f"AdapterRegistry(adapter_type={self.adapter_type!r}, "
            f"keys={self.list_keys()}, discovered={self._discovered})"
        )

    def register_class(self, key: str, adapter_class: type[T], *, override: bool = True) -> None:
        """Register an adapter class under a key."""
        if key in self.adapter_classes and not override:
            logger.debug(
                f"Skipped adapter registration for adapter_type='{self.adapter_type.value}' "
                f"key='{key}' (override={override})."
            )
            return

        self.adapter_classes[key] = adapter_class
        logger.debug(
            f"Registered adapter: adapter_type='{self.adapter_type.value}' key='{key}' class='{adapter_class.__name__}'"
        )

    def get_class(self, key: str) -> type[T] | None:
        """Return adapter class by key if available."""
        return self.adapter_classes.get(key)

    def list_keys(self) -> list[str]:
        """Return sorted list of registered adapter keys."""
        return sorted(self.adapter_classes.keys())

    def get_instance(self, key: str, *, factory: Callable[[type[T]], T]) -> T | None:
        """Get or create a singleton adapter instance for a key.

        The registry is the owner of adapter instance lifecycle:
        - Instances are created lazily on first access per key.
        - A single instance is cached per key.
        - Cached instances are torn down via ``teardown_instances``.
        """
        with self._lock:
            if key in self.adapter_instances:
                return self.adapter_instances[key]

            adapter_class = self.get_class(key)
            if adapter_class is None:
                return None

            instance = factory(adapter_class)
            self.adapter_instances[key] = instance
            return instance

    async def teardown_instances(self) -> None:
        """Teardown and clear all cached adapter instances in this registry."""
        with self._lock:
            instances = list(self.adapter_instances.values())
            self.adapter_instances.clear()

        for instance in instances:
            teardown = getattr(instance, "teardown", None)
            if not callable(teardown):
                continue
            try:
                teardown_result = teardown()
                if asyncio.iscoroutine(teardown_result):
                    await teardown_result
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Failed to teardown adapter instance for adapter_type='{self.adapter_type.value}': {exc}"
                )

    def discover(self, config_dir: Path) -> None:
        """Discover and register adapters from all supported sources.

        Args:
            config_dir: Directory to search for ``lfx.toml`` / ``pyproject.toml``.
        """
        with self._lock:
            if self._discovered:
                logger.debug(
                    f"Adapter discovery for '{self.adapter_type.value}' already complete, "
                    f"ignoring call with config_dir='{config_dir}'."
                )
                return

            self._discover_from_entry_points()
            self._discover_from_config(config_dir=config_dir)
            self._discovered = True

    def _discover_from_entry_points(self) -> None:
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        for ep in eps:
            try:
                adapter_class = ep.load()
                self.register_class(ep.name, adapter_class, override=False)
            except (ValueError, AttributeError) as exc:
                logger.warning(
                    f"Failed to load adapter entry point group='{self.entry_point_group}' name='{ep.name}': {exc}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    f"Error loading adapter entry point group='{self.entry_point_group}' name='{ep.name}': {exc}"
                )

    def _discover_from_config(self, *, config_dir: Path) -> None:
        source = get_preferred_config_source(
            config_dir,
            lfx_root_path=self.config_section_path,
            pyproject_root_path=("tool", "lfx", *self.config_section_path),
        )
        if source is None:
            return
        config_path, root_path = source
        self._load_config_file(config_path=config_path, root_path=root_path)

    def _load_config_file(self, *, config_path: Path, root_path: tuple[str, ...]) -> None:
        config = load_toml_config(config_path)
        if config is None:
            return

        section = get_nested_section(config, root_path)
        if section is None:
            return

        for key, import_path in section.items():
            self._register_adapter_from_path(key=key, import_path=import_path)

        if config_path.name == "lfx.toml" or section:
            logger.debug(f"Loaded {len(section)} adapter(s) for '{self.adapter_type.value}' from {config_path}")

    def _register_adapter_from_path(self, *, key: str, import_path: Any) -> None:
        if not isinstance(import_path, str) or ":" not in import_path:
            logger.warning(
                f"Invalid adapter path for adapter_type='{self.adapter_type.value}' key='{key}': "
                f"'{import_path}'. Expected 'module:class'."
            )
            return

        try:
            module_path, class_name = import_path.split(":", 1)
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            self.register_class(key, adapter_class, override=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Failed to register adapter for adapter_type='{self.adapter_type.value}' "
                f"key='{key}' from '{import_path}': {exc}"
            )


def _default_entry_point_group(adapter_type: AdapterType) -> str:
    return f"lfx.{adapter_type.value}.adapters"


def _default_config_section_path(adapter_type: AdapterType) -> tuple[str, ...]:
    return (adapter_type.value, "adapters")


def get_adapter_registry(
    *,
    adapter_type: AdapterType,
    entry_point_group: str | None = None,
    config_section_path: tuple[str, ...] | None = None,
) -> AdapterRegistry[Any]:
    """Get or create a singleton adapter registry for an adapter type.

    ``entry_point_group`` and ``config_section_path`` are derived from
    ``adapter_type`` by convention when not provided explicitly:

    * ``entry_point_group`` → ``"lfx.<adapter_type>.adapters"``
    * ``config_section_path`` → ``("<adapter_type>", "adapters")``
    """
    resolved_epg = entry_point_group or _default_entry_point_group(adapter_type)
    resolved_csp = config_section_path or _default_config_section_path(adapter_type)

    with _adapter_registries_lock:
        if adapter_type in _adapter_registries:
            existing = _adapter_registries[adapter_type]
            if existing.entry_point_group != resolved_epg or existing.config_section_path != resolved_csp:
                msg = (
                    "get_adapter_registry called with conflicting parameters for existing "
                    f"adapter_type='{adapter_type.value}'. "
                    f"Existing: entry_point_group='{existing.entry_point_group}', "
                    f"config_section_path={existing.config_section_path}. "
                    f"Requested: entry_point_group='{resolved_epg}', "
                    f"config_section_path={resolved_csp}."
                )
                raise AdapterRegistryConflictError(msg)
            return existing

        registry = AdapterRegistry(
            adapter_type=adapter_type,
            entry_point_group=resolved_epg,
            config_section_path=resolved_csp,
        )
        _adapter_registries[adapter_type] = registry
        return registry


async def _reset_registries() -> None:
    """Reset all adapter registry state. For testing only.

    Tears down cached adapter instances before clearing registries so
    that resources held by adapters (connections, file handles, …) are
    released even in test-isolation scenarios.
    """
    await teardown_all_adapter_registries()
    with _adapter_registries_lock:
        _adapter_registries.clear()


async def teardown_all_adapter_registries() -> None:
    """Teardown all cached instances across all adapter registries."""
    with _adapter_registries_lock:
        registries = list(_adapter_registries.values())
    for registry in registries:
        await registry.teardown_instances()
