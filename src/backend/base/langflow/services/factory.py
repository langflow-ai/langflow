import importlib
import inspect
from typing import get_type_hints

from cachetools import LRUCache, cached
from lfx.log.logger import logger

from langflow.services.base import Service
from langflow.services.schema import ServiceType


class ServiceFactory:
    def __init__(
        self,
        service_class: type[Service] | None = None,
    ) -> None:
        if service_class is None:
            msg = "service_class is required"
            raise ValueError(msg)
        self.service_class = service_class
        self.dependencies = infer_service_types(self, import_all_services_into_a_dict())

    def create(self, *args, **kwargs) -> "Service":
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
def infer_service_types(factory: ServiceFactory, available_services=None) -> list["ServiceType"]:
    create_method = factory.create

    type_hints = get_type_hints(create_method, globalns=available_services)

    service_types = []
    for param_name, param_type in type_hints.items():
        # Skip the return type if it's included in type hints
        if param_name == "return":
            continue

        # Convert the type to the expected enum format directly without appending "_SERVICE"
        type_name = param_type.__name__.upper().replace("SERVICE", "_SERVICE")

        try:
            # Attempt to find a matching enum value
            service_type = ServiceType[type_name]
            service_types.append(service_type)
        except KeyError as e:
            msg = f"No matching ServiceType for parameter type: {param_type.__name__}"
            raise ValueError(msg) from e
    return service_types


@cached(cache=LRUCache(maxsize=1))
def import_all_services_into_a_dict():
    # Services are all in langflow.services.{service_name}.service
    # and are subclass of Service
    # We want to import all of them and put them in a dict
    # to use as globals
    from langflow.services.base import Service

    services = {}
    for service_type in ServiceType:
        try:
            service_name = ServiceType(service_type).value.replace("_service", "")

            # Special handling for mcp_composer which is now in lfx module
            if service_name == "mcp_composer":
                module_name = f"lfx.services.{service_name}.service"
            else:
                module_name = f"langflow.services.{service_name}.service"

            module = importlib.import_module(module_name)
            services.update(
                {
                    name: obj
                    for name, obj in inspect.getmembers(module, inspect.isclass)
                    if issubclass(obj, Service) and obj is not Service
                }
            )
        except Exception as exc:
            logger.exception(exc)
            msg = "Could not initialize services. Please check your settings."
            raise RuntimeError(msg) from exc
    # Import settings service from lfx
    from lfx.services.settings.service import SettingsService

    services["SettingsService"] = SettingsService
    return services
