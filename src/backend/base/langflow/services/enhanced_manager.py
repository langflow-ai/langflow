"""Enhanced ServiceManager that extends lfx's ServiceManager with langflow features."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

from lfx.services.manager import NoFactoryRegisteredError
from lfx.services.manager import ServiceManager as BaseServiceManager
from loguru import logger

from langflow.utils.concurrency import KeyedMemoryLockManager

if TYPE_CHECKING:
    from langflow.services.base import Service
    from langflow.services.factory import ServiceFactory
    from langflow.services.schema import ServiceType


__all__ = ["NoFactoryRegisteredError", "ServiceManager"]


class ServiceManager(BaseServiceManager):
    """Enhanced ServiceManager with langflow factory system and dependency injection."""

    def __init__(self) -> None:
        super().__init__()
        self.register_factories()
        self.keyed_lock = KeyedMemoryLockManager()

    def register_factories(self, factories: list[ServiceFactory] | None = None) -> None:
        """Register all available service factories."""
        for factory in factories or self.get_factories():
            try:
                self.register_factory(factory)
            except Exception:  # noqa: BLE001
                logger.exception(f"Error initializing {factory}")

    def get(self, service_name: ServiceType, default: ServiceFactory | None = None) -> Service:
        """Get (or create) a service by its name with keyed locking."""
        with self.keyed_lock.lock(service_name):
            return super().get(service_name, default)

    @classmethod
    def get_factories(cls) -> list[ServiceFactory]:
        """Auto-discover and return all service factories."""
        from langflow.services.factory import ServiceFactory
        from langflow.services.schema import ServiceType

        service_names = [ServiceType(service_type).value.replace("_service", "") for service_type in ServiceType]
        base_module = "langflow.services"
        factories = []

        for name in service_names:
            try:
                base_module = "lfx.services" if name == "settings" else "langflow.services"
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
