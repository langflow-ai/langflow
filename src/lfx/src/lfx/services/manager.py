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
                # Recursively create dependency if not exists
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

        Discovery order (last wins):
        1. Entry points (installed packages)
        2. Config files (lfx.toml / pyproject.toml)
        3. Decorator-registered services (already in self.service_classes)

        Args:
            config_dir: Directory to search for config files.
                       If None, tries to use settings_service.settings.config_dir,
                       then falls back to current working directory.

        Note:
            The settings service cannot be overridden via plugins and is always
            created using the built-in factory.
        """
        if self._plugins_discovered:
            logger.debug("Plugins already discovered, skipping...")
            return

        # Get config_dir from settings service if not provided
        if config_dir is None and ServiceType.SETTINGS_SERVICE in self.services:
            settings_service = self.services[ServiceType.SETTINGS_SERVICE]
            if hasattr(settings_service, "settings") and settings_service.settings.config_dir:
                config_dir = Path(settings_service.settings.config_dir)

        logger.debug(f"Starting plugin discovery (config_dir: {config_dir or 'cwd'})...")

        # 1. Discover from entry points
        self._discover_from_entry_points()

        # 2. Discover from config files
        self._discover_from_config(config_dir)

        self._plugins_discovered = True
        logger.debug(f"Plugin discovery complete. Registered services: {list(self.service_classes.keys())}")

    def _discover_from_entry_points(self) -> None:
        """Discover services from Python entry points."""
        from importlib.metadata import entry_points

        eps = entry_points(group="lfx.services")

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

    def _discover_from_config(self, config_dir: Path | None = None) -> None:
        """Discover services from config files (lfx.toml / pyproject.toml)."""
        config_dir = Path.cwd() if config_dir is None else Path(config_dir)

        # Try lfx.toml first
        lfx_config = config_dir / "lfx.toml"
        if lfx_config.exists():
            self._load_config_file(lfx_config)
            return

        # Try pyproject.toml with [tool.lfx.services]
        pyproject_config = config_dir / "pyproject.toml"
        if pyproject_config.exists():
            self._load_pyproject_config(pyproject_config)

    def _load_config_file(self, config_path: Path) -> None:
        """Load services from lfx.toml config file."""
        try:
            import tomllib as tomli  # Python 3.11+
        except ImportError:
            import tomli  # Python 3.10

        try:
            with config_path.open("rb") as f:
                config = tomli.load(f)

            services = config.get("services", {})
            for service_key, service_path in services.items():
                self._register_service_from_path(service_key, service_path)

            logger.debug(f"Loaded {len(services)} services from {config_path}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load config from {config_path}: {exc}")

    def _load_pyproject_config(self, config_path: Path) -> None:
        """Load services from pyproject.toml [tool.lfx.services] section."""
        try:
            import tomllib as tomli  # Python 3.11+
        except ImportError:
            import tomli  # Python 3.10

        try:
            with config_path.open("rb") as f:
                config = tomli.load(f)

            services = config.get("tool", {}).get("lfx", {}).get("services", {})
            for service_key, service_path in services.items():
                self._register_service_from_path(service_key, service_path)

            if services:
                logger.debug(f"Loaded {len(services)} services from {config_path}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to load config from {config_path}: {exc}")

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

        try:
            # Parse module:class format
            if ":" not in service_path:
                logger.warning(f"Invalid service path '{service_path}' - must be 'module:class' format")
                return

            module_path, class_name = service_path.split(":", 1)
            module = importlib.import_module(module_path)
            service_class = getattr(module, class_name)

            self.register_service_class(service_type, service_class, override=True)
            logger.debug(f"Registered service from config: {service_key} -> {service_path}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to register service {service_key} from {service_path}: {exc}")


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
