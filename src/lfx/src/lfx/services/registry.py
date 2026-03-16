"""Service registration decorator for pluggable services.

Allows services to self-register with the service manager using a decorator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.services.base import Service
    from lfx.services.schema import ServiceType

ServiceT = TypeVar("ServiceT", bound="Service")


def register_service(service_type: ServiceType, *, override: bool = True):
    """Decorator to register a service class with the service manager.

    Usage:
        @register_service(ServiceType.DATABASE_SERVICE)
        class DatabaseService(Service):
            name = "database_service"
            ...

    Args:
        service_type: The ServiceType enum value for this service
        override: Whether to override existing registrations (default: True)

    Returns:
        Decorator function that registers the service class
    """

    def decorator(service_class: type[ServiceT]) -> type[ServiceT]:
        """Register the service class and return it unchanged."""
        try:
            from lfx.services.manager import get_service_manager

            service_manager = get_service_manager()
            service_manager.register_service_class(service_type, service_class, override=override)
            logger.debug(f"Registered service via decorator: {service_type.value} -> {service_class.__name__}")
        except ValueError:
            # Re-raise ValueError (used for settings service protection)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to register service {service_type.value} from decorator: {exc}")

        return service_class

    return decorator
