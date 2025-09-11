from __future__ import annotations

import asyncio
import importlib
import inspect
from typing import TYPE_CHECKING

from langflow.logging.logger import logger
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
        import asyncio
        import time

        start_time = time.time()
        await logger.adebug(f"Starting teardown of {len(self.services)} services")

        for service in list(self.services.values()):
            if service is None:
                continue
            service_start = time.time()
            await logger.adebug(f"Teardown service {service.name}")
            try:
                # Add timeout to prevent individual service teardowns from hanging
                await asyncio.wait_for(service.teardown(), timeout=15.0)
                service_time = time.time() - service_start
                await logger.adebug(f"Service {service.name} teardown completed in {service_time:.2f}s")
            except asyncio.TimeoutError:
                await logger.aerror(f"Service {service.name} teardown timed out after 15s")
                # Try to force cleanup of common background resources
                await self._force_cleanup_service(service)
            except Exception as exc:  # noqa: BLE001
                await logger.aexception(f"Service {service.name} teardown failed: {exc}")

        services_time = time.time() - start_time
        await logger.adebug(f"All services teardown completed in {services_time:.2f}s")

        # Clean up all MCP session managers after regular service teardown
        mcp_start = time.time()
        await logger.adebug("Starting MCP session manager cleanup")
        try:
            from langflow.base.mcp.util import cleanup_all_mcp_session_managers

            await asyncio.wait_for(cleanup_all_mcp_session_managers(), timeout=10.0)
            mcp_time = time.time() - mcp_start
            await logger.adebug(f"MCP session manager cleanup completed in {mcp_time:.2f}s")
        except asyncio.TimeoutError:
            await logger.aerror("MCP session manager cleanup timed out after 10s")
        except Exception as exc:  # noqa: BLE001
            await logger.aexception(f"Error cleaning up MCP session managers: {exc}")

        total_time = time.time() - start_time
        await logger.adebug(f"Total teardown completed in {total_time:.2f}s")

        self.services = {}
        self.factories = {}

    async def _force_cleanup_service(self, service) -> None:
        """Force cleanup of service resources when normal teardown times out."""
        service_name = getattr(service, "name", str(type(service).__name__))
        await logger.awarning(f"Attempting force cleanup of {service_name}")

        # Try to cancel common background task attributes
        task_attrs = ["worker_task", "log_package_version_task", "_cleanup_task", "_task", "background_task"]
        for attr_name in task_attrs:
            if hasattr(service, attr_name):
                task = getattr(service, attr_name)
                if task and isinstance(task, asyncio.Task) and not task.done():
                    try:
                        task.cancel()
                        await logger.adebug(f"Cancelled {attr_name} for {service_name}")
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(f"Failed to cancel {attr_name} for {service_name}: {e}")

        # Try to close common connection attributes
        conn_attrs = ["client", "_client", "session", "_session"]
        for attr_name in conn_attrs:
            if hasattr(service, attr_name):
                conn = getattr(service, attr_name)
                if conn and hasattr(conn, "aclose"):
                    try:
                        await conn.aclose()
                        await logger.adebug(f"Closed {attr_name} for {service_name}")
                    except Exception as e:  # noqa: BLE001
                        await logger.awarning(f"Failed to close {attr_name} for {service_name}: {e}")

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
