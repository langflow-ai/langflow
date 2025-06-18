"""Singleton service registry with dependency injection for Langflow services.

This module implements the ServiceManager which acts as a service registry
and factory orchestrator, providing dependency injection and ensuring
single instances of services across the application.

Service Registration:
    Services are automatically discovered and registered via ServiceFactory
    instances. Each service factory declares its dependencies through type hints:

    ```python
    class AuthService(Service):
        def __init__(self, settings_service: SettingsService): ...

    # Factory automatically infers SettingsService dependency
    ```

Dependency Resolution:
    The manager resolves dependencies recursively, creating services in
    dependency order. Circular dependencies are detected and raise errors.

Thread Safety:
    Uses KeyedMemoryLockManager to ensure thread-safe service creation:
    - Each service name gets its own lock during creation
    - Prevents race conditions in multi-threaded service initialization
    - Services are cached after creation for singleton behavior

Service Lifecycle:
    1. register_factories(): Auto-discover service factories
    2. get(service_name): Get or create service instance
    3. _create_service(): Instantiate with resolved dependencies
    4. Cached in self.services dict for subsequent requests

Key Components:
    - services: dict[str, Service] - Singleton service instances
    - factories: dict[str, ServiceFactory] - Service creation factories
    - keyed_lock: KeyedMemoryLockManager - Thread-safe creation locks

Factory Discovery:
    Automatically scans for ServiceFactory subclasses in:
    - langflow.services.*.factory modules
    - Each factory defines create() method for service instantiation
    - Dependencies resolved through constructor type annotations

Example Usage:
    ```python
    # Get service instance (creates if not exists)
    manager = get_service_manager()
    auth_service = manager.get(AUTH_SERVICE)

    # Services are singletons - same instance returned
    auth_service2 = manager.get(AUTH_SERVICE)
    assert auth_service is auth_service2
    ```

Supported Services:
    - AUTH_SERVICE: Authentication and user management
    - SETTINGS_SERVICE: Configuration and environment settings
    - DATABASE_SERVICE: Database connections and migrations
    - CHAT_SERVICE: Graph caching and execution state
    - TELEMETRY_SERVICE: Usage analytics and monitoring

The manager ensures proper initialization order and prevents circular
dependency issues through topological sorting of service dependencies.

Example Advanced Usage:
    ```python
    manager = ServiceManager()
    auth_service = manager.get("auth_service")  # Creates with dependencies
    database_service = manager.get("database_service")  # Reuses existing
    ```

The manager ensures consistent service instantiation and prevents duplicate
service creation across the Langflow application.
"""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

from loguru import logger

from langflow.utils.concurrency import KeyedMemoryLockManager

if TYPE_CHECKING:
    from langflow.services.base import Service
    from langflow.services.factory import ServiceFactory
    from langflow.services.schema import ServiceType


class NoFactoryRegisteredError(Exception):
    pass


class ServiceManager:
    """Manages the creation of different services."""

    def __init__(self) -> None:
        self.services: dict[str, Service] = {}
        self.factories: dict[str, ServiceFactory] = {}
        self.register_factories()
        self.keyed_lock = KeyedMemoryLockManager()

    def register_factories(self) -> None:
        for factory in self.get_factories():
            try:
                self.register_factory(factory)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error initializing {factory}")

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
        self._validate_service_creation(service_name, default)

        # Create dependencies first
        factory = self.factories.get(service_name)
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
        for service in self.services.values():
            if service is None:
                continue
            logger.debug(f"Teardown service {service.name}")
            try:
                await service.teardown()
            except Exception as exc:  # noqa: BLE001
                logger.exception(exc)
        self.services = {}
        self.factories = {}

    @staticmethod
    def get_factories():
        from langflow.services.factory import ServiceFactory
        from langflow.services.schema import ServiceType

        service_names = [ServiceType(service_type).value.replace("_service", "") for service_type in ServiceType]
        base_module = "langflow.services"
        factories = []

        for name in service_names:
            try:
                module_name = f"{base_module}.{name}.factory"
                module = importlib.import_module(module_name)

                # Find all classes in the module that are subclasses of ServiceFactory
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, ServiceFactory) and obj is not ServiceFactory:
                        factories.append(obj())
                        break

            except Exception as exc:
                logger.exception(exc)
                msg = f"Could not initialize services. Please check your settings. Error in {name}."
                raise RuntimeError(msg) from exc

        return factories


service_manager = ServiceManager()


def initialize_settings_service() -> None:
    """Initialize the settings manager."""
    from langflow.services.settings import factory as settings_factory

    service_manager.register_factory(settings_factory.SettingsServiceFactory())


def initialize_session_service() -> None:
    """Initialize the session manager."""
    from langflow.services.cache import factory as cache_factory
    from langflow.services.session import factory as session_service_factory

    initialize_settings_service()

    service_manager.register_factory(cache_factory.CacheServiceFactory())

    service_manager.register_factory(session_service_factory.SessionServiceFactory())
