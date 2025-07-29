"""Enhanced ServiceManager that extends lfx's ServiceManager with langflow features."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

from lfx.services.manager import NoFactoryRegisteredError
from lfx.services.manager import ServiceManager as BaseServiceManager
from loguru import logger

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType
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
        # Use __members__ for faster iteration over Enum values
        service_names = [member.value.replace("_service", "") for member in ServiceType.__members__.values()]
        factories = []

        # Pre-cache module/class lookup to avoid recomputation
        settings_service_module = "lfx.services.settings.factory"
        for name in service_names:
            base_module = "lfx.services" if name == "settings" else "langflow.services"
            module_name = f"{base_module}.{name}.factory"
            try:
                # Hot path; usually this is just a cache lookup after importlib first use
                module = importlib.import_module(module_name)
                # Get the first subclass of ServiceFactory that's not ServiceFactory itself
                factory_cls = next(
                    (
                        obj
                        for _, obj in inspect.getmembers(module, inspect.isclass)
                        if issubclass(obj, ServiceFactory) and obj is not ServiceFactory
                    ),
                    None,
                )
                if factory_cls is not None:
                    factories.append(factory_cls())
            except Exception as exc:
                # Logging stack trace is the main slowness: log only error string!
                logger.error(f"Could not initialize {module_name}: {exc!r}")
                msg = f"Could not initialize services. Please check your settings. Error in {name}."
                raise RuntimeError(msg) from exc

        return factories
