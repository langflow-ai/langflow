"""Concrete ServiceFactory with dependency inference for Langflow services."""

from __future__ import annotations

import importlib
import inspect
from typing import get_type_hints

from cachetools import LRUCache, cached
from lfx.log.logger import logger
from lfx.services.base import Service
from lfx.services.factory import ServiceFactory as LfxServiceFactory
from lfx.services.schema import ServiceType

# Services owned by LFX (not this package).
_LFX_OWNED = frozenset({"mcp_composer", "executor", "extension_events", "settings"})


class ServiceFactory(LfxServiceFactory):
    """Langflow concrete factory with dependency inference."""

    def __init__(self, service_class: type[Service] | None = None) -> None:
        if service_class is None:
            msg = "service_class is required"
            raise ValueError(msg)
        super().__init__(service_class)
        self.dependencies = infer_service_types(self, import_all_services_into_a_dict())

    def create(self, *args, **kwargs) -> Service:
        return self.service_class(*args, **kwargs)


def hash_factory(factory: ServiceFactory) -> str:
    return factory.service_class.__name__


def hash_dict(d: dict) -> str:
    return str(d)


def hash_infer_service_types_args(factory: ServiceFactory, available_services=None) -> str:
    factory_hash = hash_factory(factory)
    services_hash = hash_dict(available_services)
    return f"{factory_hash}_{services_hash}"


@cached(cache=LRUCache(maxsize=10), key=hash_infer_service_types_args)
def infer_service_types(factory: ServiceFactory, available_services=None) -> list[ServiceType]:
    create_method = factory.create
    type_hints = get_type_hints(create_method, globalns=available_services)
    service_types: list[ServiceType] = []
    for param_name, param_type in type_hints.items():
        if param_name == "return":
            continue
        type_name = param_type.__name__.upper().replace("SERVICE", "_SERVICE")
        try:
            service_types.append(ServiceType[type_name])
        except KeyError as e:
            msg = f"No matching ServiceType for parameter type: {param_type.__name__}"
            raise ValueError(msg) from e
    return service_types


@cached(cache=LRUCache(maxsize=1))
def import_all_services_into_a_dict():
    """Import concrete Service subclasses for factory type-hint resolution."""
    services: dict = {}
    for service_type in ServiceType:
        try:
            service_name = ServiceType(service_type).value.replace("_service", "")
            if service_name in _LFX_OWNED:
                module_name = f"lfx.services.{service_name}.service"
            else:
                module_name = f"services.{service_name}.service"
            module = importlib.import_module(module_name)
            services.update(
                {
                    name: obj
                    for name, obj in inspect.getmembers(module, inspect.isclass)
                    if isinstance(obj, type) and issubclass(obj, Service) and obj is not Service
                }
            )
        except Exception as exc:
            logger.exception(exc)
            msg = "Could not initialize services. Please check your settings."
            raise RuntimeError(msg) from exc

    from lfx.services.auth.base import BaseAuthService
    from lfx.services.authorization.base import BaseAuthorizationService
    from lfx.services.settings.service import SettingsService

    services["BaseAuthService"] = BaseAuthService
    services["BaseAuthorizationService"] = BaseAuthorizationService
    services["SettingsService"] = SettingsService
    return services
