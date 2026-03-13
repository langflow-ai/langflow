"""ServiceManager with pluggable service discovery.

Supports multiple discovery mechanisms:
1. Decorator-based registration (@register_service)
2. Config file (lfx.toml / pyproject.toml)
3. Entry points (Python packages)
4. Fallback to noop/minimal implementations
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.config_discovery import (
    get_nested_section,
    get_preferred_config_source,
    load_object_from_import_path,
    load_toml_config,
    resolve_config_dir,
)
from lfx.services.schema import ServiceType
from lfx.utils.concurrency import KeyedMemoryLockManager

if TYPE_CHECKING:
    from lfx.services.base import Service
    from lfx.services.factory import ServiceFactory


class NoFactoryRegisteredError(Exception):
    """Raised when no factory is registered for a service type."""


class NoServiceRegisteredError(Exception):
    """Raised when no service or factory is registered for a service type."""


class ServiceManager:
    """Manages the creation of different services with pluggable discovery."""

    def __init__(self) -> None:
        """Initialize the service manager with empty service and factory registries."""
        self.services: dict[str, Service] = {}
        self.factories: dict[str, ServiceFactory] = {}
        self.service_classes: dict[ServiceType, type[Service]] = {}  # New: direct service class registry
        self._lock = threading.RLock()
        self.keyed_lock = KeyedMemoryLockManager()
        self.factory_registered = False
        self._plugins_discovered = False

        # Always register settings service
        from lfx.services.settings.factory import SettingsServiceFactory

        self.register_factory(SettingsServiceFactory())

    def register_factories(self, factories: list[ServiceFactory] | None = None) -> None:
        """Register all available service factories."""
        if factories is None:
            return
        for factory in factories:
            try:
                self.register_factory(factory)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error initializing {factory}")
        self.set_factory_registered()

    def are_factories_registered(self) -> bool:
        """Check if the factory is registered."""
        return self.factory_registered

    def set_factory_registered(self) -> None:
        """Set the factory registered flag."""
        self.factory_registered = True

    def register_service_class(
        self,
        service_type: ServiceType,
        service_class: type[Service],
        *,
        override: bool = True,
    ) -> None:
        """Register a service class directly (without factory).

        Args:
            service_type: The service type enum value
            service_class: The service class to register
            override: Whether to override existing registration (default: True)

        Raises:
            ValueError: If attempting to register the settings service (not allowed)
        """
        # Settings service cannot be overridden via plugins
        if service_type == ServiceType.SETTINGS_SERVICE:
            msg = "Settings service cannot be registered via plugins. It is always created using the built-in factory."
            logger.warning(msg)
            raise ValueError(msg)

        if service_type in self.service_classes and not override:
            logger.warning(f"Service {service_type.value} already registered. Use override=True to replace it.")
            return

        if service_type in self.service_classes:
            logger.debug(f"Overriding service registration for {service_type.value}")

        self.service_classes[service_type] = service_class
        logger.debug(f"Registered service class: {service_type.value} -> {service_class.__name__}")

    def register_factory(
        self,
        service_factory: ServiceFactory,
    ) -> None:
        """Registers a new factory with dependencies."""
        service_name = service_factory.service_class.name
        self.factories[service_name] = service_factory

    def get(self, service_name: ServiceType, default: ServiceFactory | None = None) -> Service:
        """Get (or create) a service by its name."""
        with self.keyed_lock.lock(service_name):
            if service_name not in self.services:
                self._create_service(service_name, default)
            return self.services[service_name]

    def _create_service(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Create a new service given its name, handling dependencies."""
        logger.debug(f"Create service {service_name}")

        # Settings service is special - always use factory, never from plugins
        if service_name == ServiceType.SETTINGS_SERVICE:
            self._create_service_from_factory(service_name, default)
            return

        # Try plugin discovery first (if not already done)
        if not self._plugins_discovered:
            # Get config_dir from settings service if available
            config_dir = None
            if ServiceType.SETTINGS_SERVICE in self.services:
                settings_service = self.services[ServiceType.SETTINGS_SERVICE]
                if hasattr(settings_service, "settings") and settings_service.settings.config_dir:
                    config_dir = Path(settings_service.settings.config_dir)

            self.discover_plugins(config_dir)

        # Check if we have a direct service class registration (new system)
        if service_name in self.service_classes:
            self._create_service_from_class(service_name)
            return

        # Fall back to factory-based creation (old system)
        self._create_service_from_factory(service_name, default)

    def _create_service_from_class(self, service_name: ServiceType) -> None:
        """Create a service from a registered service class (new plugin system)."""
        service_class = self.service_classes[service_name]
        logger.debug(f"Creating service from class: {service_name.value} -> {service_class.__name__}")

        # Inspect __init__ to determine dependencies
        init_signature = inspect.signature(service_class.__init__)
        dependencies = {}

        for param_name, param in init_signature.parameters.items():
            if param_name == "self":
                continue

            # Try to resolve dependency from type hint first
            dependency_type = None
            if param.annotation != inspect.Parameter.empty:
                dependency_type = self._resolve_service_type_from_annotation(param.annotation)

            # If type hint didn't work, try to resolve from parameter name
            # E.g., param name "settings_service" -> ServiceType.SETTINGS_SERVICE
            if not dependency_type:
                try:
                    dependency_type = ServiceType(param_name)
                except ValueError:
                    # Not a valid service type - skip this parameter if it has a default
                    # Otherwise let it fail during instantiation
                    if param.default == inspect.Parameter.empty:
                        # No default, can't resolve - will fail during instantiation
                        pass
                    continue

            if dependency_type:
                # Check for circular dependency (service depending on itself)
                if dependency_type == service_name:
                    msg = f"Circular dependency detected: {service_name.value} depends on itself"
                    raise RuntimeError(msg)
                # Recursively create dependency if not exists
                # Note: Thread safety is handled by the caller's keyed lock context
                if dependency_type not in self.services:
                    self._create_service(dependency_type)
                dependencies[param_name] = self.services[dependency_type]

        # Create the service instance
        try:
            service_instance = service_class(**dependencies)
            # Don't call set_ready() here - let the service control its own ready state
            self.services[service_name] = service_instance
            logger.debug(f"Service created successfully: {service_name.value}")
        except Exception as exc:
            logger.exception(f"Failed to create service {service_name.value}: {exc}")
            raise

    def _resolve_service_type_from_annotation(self, annotation) -> ServiceType | None:
        """Resolve a ServiceType from a type annotation.

        Args:
            annotation: The type annotation from __init__ signature

        Returns:
            ServiceType if resolvable, None otherwise
        """
        # Handle string annotations (forward references)
        annotation_name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", None)

        if not annotation_name:
            return None

        # Try to match service class name to ServiceType
        # E.g., "SettingsService" -> ServiceType.SETTINGS_SERVICE
        for service_type in ServiceType:
            # Check if registered service class matches
            if service_type in self.service_classes:
                registered_class = self.service_classes[service_type]
                if registered_class.__name__ == annotation_name:
                    return service_type

            # Check if annotation name matches expected pattern
            # E.g., "SettingsService" -> "settings_service"
            expected_name = annotation_name.replace("Service", "").lower() + "_service"
            if service_type.value == expected_name:
                return service_type

        return None

    def _create_service_from_factory(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Create a service from a factory (old system)."""
        self._validate_service_creation(service_name, default)

        if service_name == ServiceType.SETTINGS_SERVICE:
            from lfx.services.settings.factory import SettingsServiceFactory

            factory = SettingsServiceFactory()
            if factory not in self.factories:
                self.register_factory(factory)
        else:
            factory = self.factories.get(service_name)

        # Create dependencies first
        if factory is None and default is not None:
            self.register_factory(default)
            factory = default
        if factory is None:
            msg = f"No factory registered for {service_name}"
            raise NoFactoryRegisteredError(msg)
        for dependency in factory.dependencies:
            if dependency not in self.services:
                self._create_service(dependency)

        # Collect the dependent services
        dependent_services = {dep.value: self.services[dep] for dep in factory.dependencies}

        # Create the actual service
        self.services[service_name] = self.factories[service_name].create(**dependent_services)
        self.services[service_name].set_ready()

    def _validate_service_creation(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Validate whether the service can be created."""
        if service_name == ServiceType.SETTINGS_SERVICE:
            return
        if service_name not in self.factories and default is None:
            msg = f"No factory registered for the service class '{service_name.name}'"
            raise NoFactoryRegisteredError(msg)

    def update(self, service_name: ServiceType) -> None:
        """Update a service by its name."""
        if service_name in self.services:
            logger.debug(f"Update service {service_name}")
            self.services.pop(service_name, None)
            self.get(service_name)

    async def teardown(self) -> None:
        """Teardown all the services."""
        for service in list(self.services.values()):
            if service is None:
                continue
            logger.debug(f"Teardown service {service.name}")
            try:
                teardown_result = service.teardown()
                if asyncio.iscoroutine(teardown_result):
                    await teardown_result
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Error in teardown of {service.name}", exc_info=exc)

        # Adapter registries own singleton adapter instances and must also be cleaned up.
        try:
            from lfx.services.adapters.registry import teardown_all_adapter_registries

            await teardown_all_adapter_registries()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error during adapter registry teardown: {exc}", exc_info=True)

        self.services = {}
        self.factories = {}

    @classmethod
    def get_factories(cls) -> list[ServiceFactory]:
        """Auto-discover and return all service factories."""
        from lfx.services.factory import ServiceFactory
        from lfx.services.schema import ServiceType

        service_names = [ServiceType(service_type).value.replace("_service", "") for service_type in ServiceType]
        base_module = "lfx.services"
        factories = []

        for name in service_names:
            try:
                module_name = f"{base_module}.{name}.factory"
                module = importlib.import_module(module_name)

                # Find all classes in the module that are subclasses of ServiceFactory
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if isinstance(obj, type) and issubclass(obj, ServiceFactory) and obj is not ServiceFactory:
                        factories.append(obj())
                        break

            except Exception:  # noqa: BLE001, S110
                # This is expected during initial service discovery - some services
                # may not have factories yet or depend on settings service being ready first
                # Intentionally suppressed to avoid startup noise - not an error condition
                pass

        return factories

    def discover_plugins(self, config_dir: Path | None = None) -> None:
        """Discover and register service plugins from multiple sources.

        Decorator-registered services are already in ``service_classes``
        at this point (they register at import time via ``@register_service``).

        This method discovers two additional sources:

        1. Entry points (``override=False`` — won't overwrite decorators)
        2. Config files (``override=True`` — will overwrite decorators)

        Effective precedence: config files > decorators > entry points.

        Args:
            config_dir: Directory to search for config files.
                       If None, tries to use settings_service.settings.config_dir,
                       then falls back to current working directory.

        Note:
            The settings service cannot be overridden via plugins and is always
            created using the built-in factory.
        """
        with self._lock:
            if self._plugins_discovered:
                logger.debug("Plugins already discovered, skipping...")
                return

            settings_service = self.services.get(ServiceType.SETTINGS_SERVICE)
            config_dir = resolve_config_dir(config_dir, settings_service=settings_service)

            logger.debug(f"Starting plugin discovery (config_dir: {config_dir})...")

            # 1. Discover from entry points
            self._discover_from_entry_points()

            # 2. Discover from config files
            self._discover_from_config(config_dir)

            self._plugins_discovered = True
            logger.debug(f"Plugin discovery complete. Registered services: {list(self.service_classes.keys())}")

    def _discover_from_entry_points(self) -> None:
        """Discover services from Python entry points."""
        from importlib.metadata import entry_points

        try:
            eps = entry_points(group="lfx.services")
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to enumerate entry points for group='lfx.services'. "
                "Entry-point-based service discovery will be skipped."
            )
            return

        for ep in eps:
            try:
                service_class = ep.load()
                # Entry point name should match ServiceType enum value
                service_type = ServiceType(ep.name)
                self.register_service_class(service_type, service_class, override=False)
                logger.debug(f"Loaded service from entry point: {ep.name}")
            except (ValueError, AttributeError) as exc:
                logger.warning(f"Failed to load entry point {ep.name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Error loading entry point {ep.name}: {exc}")

    def _discover_from_config(self, config_dir: Path) -> None:
        """Discover services from config files (lfx.toml / pyproject.toml)."""
        source = get_preferred_config_source(
            config_dir,
            lfx_root_path=("services",),
            pyproject_root_path=("tool", "lfx", "services"),
        )
        if source is None:
            return
        self._load_services_from_config(*source)

    def _load_services_from_config(self, config_path: Path, root_path: tuple[str, ...]) -> None:
        """Load service registrations from config section."""
        config = load_toml_config(config_path)
        if config is None:
            return

        services = get_nested_section(config, root_path) or {}
        for service_key, service_path in services.items():
            self._register_service_from_path(service_key, service_path)

        if config_path.name == "lfx.toml" or services:
            logger.debug(f"Loaded {len(services)} services from {config_path}")

    def _register_service_from_path(self, service_key: str, service_path: str) -> None:
        """Register a service from a module:class path string.

        Args:
            service_key: ServiceType enum value (e.g., "database_service")
            service_path: Import path (e.g., "langflow.services.database.service:DatabaseService")
        """
        try:
            # Validate service_key matches ServiceType enum
            service_type = ServiceType(service_key)
        except ValueError:
            logger.warning(f"Invalid service key '{service_key}' - must match ServiceType enum value")
            return

        service_class = load_object_from_import_path(
            service_path,
            object_kind="service",
            object_key=service_key,
        )
        if service_class is None:
            return

        self.register_service_class(service_type, service_class, override=True)
        logger.debug(f"Registered service from config: {service_key} -> {service_path}")


# Global variables for lazy initialization
_service_manager: ServiceManager | None = None
_service_manager_lock = threading.Lock()


def get_service_manager() -> ServiceManager:
    """Get or create the service manager instance using lazy initialization.

    This function ensures thread-safe lazy initialization of the service manager,
    preventing automatic service creation during module import.

    Returns:
        ServiceManager: The singleton service manager instance.
    """
    global _service_manager  # noqa: PLW0603
    if _service_manager is None:
        with _service_manager_lock:
            if _service_manager is None:
                _service_manager = ServiceManager()
    return _service_manager
