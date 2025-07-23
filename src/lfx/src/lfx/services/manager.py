"""ServiceManager extracted from langflow for lfx package.

This maintains the same API and most of the functionality, but removes
langflow-specific auto-discovery to break dependencies.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from lfx.services.base import Service
    from lfx.services.factory import ServiceFactory
    from lfx.services.schema import ServiceType


class NoFactoryRegisteredError(Exception):
    pass


class ServiceManager:
    """Manages the creation of different services."""

    def __init__(self) -> None:
        self.services: dict[str, Service] = {}
        self.factories: dict[str, ServiceFactory] = {}
        self._lock = threading.RLock()

    def register_factories(self, factories: list[ServiceFactory] | None = None) -> None:
        """Register all available service factories."""
        if factories is None:
            return
        for factory in factories:
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
        with self._lock:
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
        for service in list(self.services.values()):
            if service is None:
                continue
            logger.debug(f"Teardown service {service.name}")
            try:
                await service.teardown()
            except Exception as exc:  # noqa: BLE001
                logger.exception(exc)
        self.services = {}
        self.factories = {}


# Global service manager instance
service_manager = ServiceManager()


def get_settings_service():
    """Get settings service with fallback for lfx package.

    This is a stub implementation that returns None since lfx
    doesn't have full service infrastructure like langflow.
    Components should handle None gracefully with fallback values.
    """
    return
