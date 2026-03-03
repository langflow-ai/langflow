"""Generic sub-service discovery and registration helpers.

Sub-services are service-scoped plugin registries
that allow multiple adapters of the same service type
to be registered and used simultaneously.
Discovery sources intentionally mirror the
existing ServiceManager plugin model:

1. Entry points (lowest priority)
2. Decorator registration
3. Config files (highest priority)
"""

from __future__ import annotations

import importlib
import threading
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from pathlib import Path

    from lfx.services.schema import SubServiceType

from lfx.log.logger import logger

T = TypeVar("T")
SubServiceT = TypeVar("SubServiceT")

__all__ = [
    "SubServiceRegistry",
    "SubServiceRegistryConflictError",
    "get_sub_service_registry",
    "register_sub_service",
]


_decorator_subservice_registry: dict[SubServiceType, dict[str, tuple[type[Any], bool]]] = {}
_decorator_lock = threading.Lock()
_subservice_registries: dict[SubServiceType, SubServiceRegistry[Any]] = {}
_subservice_registries_lock = threading.Lock()


class SubServiceRegistryConflictError(ValueError):
    """Raised when a registry identity conflict is detected."""


def register_sub_service(
    sub_service_type: SubServiceType,
    key: str,
    *,
    override: bool = True,
):
    """Decorator to register a sub-service class for a sub-service type."""

    def decorator(sub_service_class: type[SubServiceT]) -> type[SubServiceT]:
        with _decorator_lock:
            registry = _decorator_subservice_registry.setdefault(sub_service_type, {})
            if key in registry and not override:
                logger.debug(
                    f"Skipped sub-service registration for sub_service_type='{sub_service_type.value}' "
                    f"key='{key}' (override={override})."
                )
                return sub_service_class

            registry[key] = (sub_service_class, override)
            logger.debug(
                f"Registered sub-service via decorator: sub_service_type='{sub_service_type.value}' key='{key}' "
                f"class='{sub_service_class.__name__}'"
            )
        return sub_service_class

    return decorator


class SubServiceRegistry(Generic[T]):
    """Registry for sub-services under a parent service namespace.

    Generic over ``T``, the adapter contract expected by callers
    (e.g. ``SubServiceRegistry[DeploymentServiceProtocol]``).
    """

    def __init__(
        self,
        *,
        sub_service_type: SubServiceType,
        entry_point_group: str,
        config_section_path: tuple[str, ...],
    ) -> None:
        self.sub_service_type = sub_service_type
        self.entry_point_group = entry_point_group
        self.config_section_path = config_section_path
        self.sub_service_classes: dict[str, type[T]] = {}
        self._discovered = False
        self._lock = threading.RLock()

    def register_sub_service_class(self, key: str, sub_service_class: type[T], *, override: bool = True) -> None:
        """Register a sub-service class under a key.

        Not internally locked — callers are responsible for synchronisation.
        During discovery this is called under ``self._lock``, matching the
        ``ServiceManager.register_service_class`` pattern.
        """
        if key in self.sub_service_classes and not override:
            logger.debug(
                f"Skipped sub-service registration for sub_service_type='{self.sub_service_type.value}' "
                f"key='{key}' (override={override})."
            )
            return

        self.sub_service_classes[key] = sub_service_class
        logger.debug(
            f"Registered sub-service: sub_service_type='{self.sub_service_type.value}' "
            f"key='{key}' class='{sub_service_class.__name__}'"
        )

    def get_sub_service_class(self, key: str) -> type[T] | None:
        """Return sub-service class by key if available."""
        return self.sub_service_classes.get(key)

    def list_sub_service_keys(self) -> list[str]:
        """Return sorted list of registered sub-service keys."""
        return sorted(self.sub_service_classes.keys())

    def discover_sub_services(self, config_dir: Path) -> None:
        """Discover and register sub-services from all supported sources.

        Args:
            config_dir: Directory to search for ``lfx.toml`` / ``pyproject.toml``.
        """
        with self._lock:
            if self._discovered:
                logger.debug(
                    f"Sub-service discovery for '{self.sub_service_type.value}' already complete, "
                    f"ignoring call with config_dir='{config_dir}'."
                )
                return

            self._discover_from_entry_points()
            self._discover_from_decorators()
            self._discover_from_config(config_dir=config_dir)
            self._discovered = True

    def _discover_from_entry_points(self) -> None:
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        for ep in eps:
            try:
                sub_service_class = ep.load()
                self.register_sub_service_class(ep.name, sub_service_class, override=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Failed to load sub-service entry point group='{self.entry_point_group}' name='{ep.name}': {exc}"
                )

    def _discover_from_decorators(self) -> None:
        with _decorator_lock:
            decorator_entries = dict(_decorator_subservice_registry.get(self.sub_service_type, {}))
        for key, (sub_service_class, override) in decorator_entries.items():
            self.register_sub_service_class(key, sub_service_class, override=override)

    def _discover_from_config(self, *, config_dir: Path) -> None:
        lfx_config = config_dir / "lfx.toml"
        pyproject_config = config_dir / "pyproject.toml"

        if lfx_config.exists():
            self._load_config_file(config_path=lfx_config, root_path=self.config_section_path)
            return

        if pyproject_config.exists():
            root_path = ("tool", "lfx", *self.config_section_path)
            self._load_config_file(config_path=pyproject_config, root_path=root_path)

    def _load_config_file(self, *, config_path: Path, root_path: tuple[str, ...]) -> None:
        try:
            import tomllib as tomli  # Python 3.11+
        except ImportError:
            import tomli  # Python 3.10

        try:
            with config_path.open("rb") as file_handle:
                config = tomli.load(file_handle)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load sub-service config from '{config_path}': {exc}")
            return

        section = _get_nested_section(config, root_path)
        if not isinstance(section, dict):
            return

        for key, import_path in section.items():
            self._register_sub_service_from_path(key=key, import_path=import_path)

    def _register_sub_service_from_path(self, *, key: str, import_path: Any) -> None:
        if not isinstance(import_path, str) or ":" not in import_path:
            logger.warning(
                f"Invalid sub-service path for sub_service_type='{self.sub_service_type.value}' key='{key}': "
                f"'{import_path}'. Expected 'module:class'."
            )
            return

        try:
            module_path, class_name = import_path.split(":", 1)
            module = importlib.import_module(module_path)
            sub_service_class = getattr(module, class_name)
            self.register_sub_service_class(key, sub_service_class, override=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Failed to register sub-service sub_service_type='{self.sub_service_type.value}' "
                f"key='{key}' from '{import_path}': {exc}"
            )


def get_sub_service_registry(
    *,
    sub_service_type: SubServiceType,
    entry_point_group: str,
    config_section_path: tuple[str, ...],
) -> SubServiceRegistry[Any]:
    """Get or create a singleton sub-service registry for a sub-service type."""
    with _subservice_registries_lock:
        if sub_service_type in _subservice_registries:
            existing = _subservice_registries[sub_service_type]
            if existing.entry_point_group != entry_point_group or existing.config_section_path != config_section_path:
                msg = (
                    "get_sub_service_registry called with conflicting parameters for existing "
                    f"sub_service_type='{sub_service_type.value}'. "
                    f"Existing: entry_point_group='{existing.entry_point_group}', "
                    f"config_section_path={existing.config_section_path}. "
                    f"Requested: entry_point_group='{entry_point_group}', "
                    f"config_section_path={config_section_path}."
                )
                raise SubServiceRegistryConflictError(msg)
            return existing

        registry = SubServiceRegistry(
            sub_service_type=sub_service_type,
            entry_point_group=entry_point_group,
            config_section_path=config_section_path,
        )
        _subservice_registries[sub_service_type] = registry
        return registry


def _reset_registries() -> None:
    """Reset all sub-service registry state. For testing only."""
    with _decorator_lock, _subservice_registries_lock:
        _decorator_subservice_registry.clear()
        _subservice_registries.clear()


def _get_nested_section(config: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Safely resolve nested section dictionaries in TOML payloads."""
    node: Any = config
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node
