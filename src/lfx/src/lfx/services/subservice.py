"""Generic sub-service discovery and registration helpers.

Sub-services are service-scoped plugin registries (e.g. deployment adapters for
the deployment router service). Discovery sources intentionally mirror the
existing ServiceManager plugin model:

1. Entry points (lowest priority)
2. Decorator registration
3. Config files (highest priority)
"""

from __future__ import annotations

import importlib
import threading
from pathlib import Path
from typing import Any

from lfx.log.logger import logger

_decorator_subservice_registry: dict[str, dict[str, type[Any]]] = {}
_subservice_registries: dict[str, SubServiceRegistry] = {}
_subservice_registries_lock = threading.Lock()


def register_sub_service(namespace: str, key: str, *, override: bool = True):
    """Decorator to register a sub-service class for a namespace."""

    def decorator(sub_service_class: type[Any]) -> type[Any]:
        registry = _decorator_subservice_registry.setdefault(namespace, {})
        if key in registry and not override:
            logger.debug(
                f"Skipped sub-service registration for namespace='{namespace}' key='{key}' (override={override})."
            )
            return sub_service_class

        registry[key] = sub_service_class
        logger.debug(
            f"Registered sub-service via decorator: namespace='{namespace}' key='{key}' "
            f"class='{sub_service_class.__name__}'"
        )
        return sub_service_class

    return decorator


class SubServiceRegistry:
    """Registry for sub-services under a parent service namespace."""

    def __init__(
        self,
        *,
        namespace: str,
        entry_point_group: str,
        config_section_path: tuple[str, ...],
    ) -> None:
        self.namespace = namespace
        self.entry_point_group = entry_point_group
        self.config_section_path = config_section_path
        self.sub_service_classes: dict[str, type[Any]] = {}
        self._discovered = False
        self._lock = threading.RLock()

    def register_sub_service_class(self, key: str, sub_service_class: type[Any], *, override: bool = True) -> None:
        """Register a sub-service class under a key."""
        if key in self.sub_service_classes and not override:
            logger.debug(
                f"Skipped sub-service registration for namespace='{self.namespace}' key='{key}' (override={override})."
            )
            return

        self.sub_service_classes[key] = sub_service_class
        logger.debug(
            f"Registered sub-service: namespace='{self.namespace}' key='{key}' class='{sub_service_class.__name__}'"
        )

    def get_sub_service_class(self, key: str) -> type[Any] | None:
        """Return sub-service class by key if available."""
        return self.sub_service_classes.get(key)

    def list_sub_service_keys(self) -> list[str]:
        """Return sorted list of registered sub-service keys."""
        return sorted(self.sub_service_classes.keys())

    def discover_sub_services(self, config_dir: Path | None = None) -> None:
        """Discover and register sub-services from all supported sources."""
        with self._lock:
            if self._discovered:
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
        decorator_entries = _decorator_subservice_registry.get(self.namespace, {})
        for key, sub_service_class in decorator_entries.items():
            self.register_sub_service_class(key, sub_service_class, override=True)

    def _discover_from_config(self, config_dir: Path | None = None) -> None:
        config_dir = Path.cwd() if config_dir is None else Path(config_dir)
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
                f"Invalid sub-service path for namespace='{self.namespace}' key='{key}': "
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
                f"Failed to register sub-service namespace='{self.namespace}' key='{key}' from '{import_path}': {exc}"
            )


def get_sub_service_registry(
    *,
    namespace: str,
    entry_point_group: str,
    config_section_path: tuple[str, ...],
) -> SubServiceRegistry:
    """Get or create a singleton sub-service registry for a namespace."""
    with _subservice_registries_lock:
        if namespace not in _subservice_registries:
            _subservice_registries[namespace] = SubServiceRegistry(
                namespace=namespace,
                entry_point_group=entry_point_group,
                config_section_path=config_section_path,
            )
        return _subservice_registries[namespace]


def _get_nested_section(config: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Safely resolve nested section dictionaries in TOML payloads."""
    node: Any = config
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node
