"""ServiceManager extracted from langflow for lfx package.

This maintains the same API and most of the functionality, but removes
langflow-specific auto-discovery to break dependencies.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import threading
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.base import Service
    from lfx.services.factory import ServiceFactory


class NoFactoryRegisteredError(Exception):
    pass


class ServiceManager:
    """Manages the creation of different services."""

    def __init__(self) -> None:
        self.services: dict[str, Service] = {}
        self.factories: dict[str, ServiceFactory] = {}
        self._lock = threading.RLock()
        self.factory_registered = False
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

    def register_factory(
        self,
        service_factory: ServiceFactory,
    ) -> None:
        """Registers a new factory with dependencies."""
        service_name = service_factory.service_class.name
        self.factories[service_name] = service_factory

    def get(self, service_name: ServiceType, default: ServiceFactory | None = None) -> Service:
        """Get (or create) a service by its name."""
        with self._lock:
            if service_name not in self.services:
                self._create_service(service_name, default)
            return self.services[service_name]

    def _create_service(self, service_name: ServiceType, default: ServiceFactory | None = None) -> None:
        """Create a new service given its name, handling dependencies."""
        logger.debug(f"Create service {service_name}")
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
                    if issubclass(obj, ServiceFactory) and obj is not ServiceFactory:
                        factories.append(obj())
                        break

            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    f"Could not initialize services. Please check your settings. Error in {name}.", exc_info=exc
                )

        return factories


# Global service manager instance
_service_manager = None


def get_service_manager():
    global _service_manager  # noqa: PLW0603
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager
