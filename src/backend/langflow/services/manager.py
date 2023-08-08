from langflow.services.schema import ServiceType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.factory import ServiceFactory


class ServiceManager:
    """
    Manages the creation of different services.
    """

    def __init__(self):
        self.services = {}
        self.factories = {}

    def register_factory(self, service_factory: "ServiceFactory"):
        """
        Registers a new factory.
        """
        self.factories[service_factory.service_class.name] = service_factory

    def get(self, service_name: ServiceType):
        """
        Get (or create) a service by its name.
        """
        if service_name not in self.services:
            self._create_service(service_name)

        return self.services[service_name]

    def _create_service(self, service_name: ServiceType):
        """
        Create a new service given its name.
        """
        self._validate_service_creation(service_name)

        if service_name == ServiceType.SETTINGS_MANAGER:
            self.services[service_name] = self.factories[service_name].create()
        else:
            settings_service = self.get(ServiceType.SETTINGS_MANAGER)
            self.services[service_name] = self.factories[service_name].create(
                settings_service
            )

    def _validate_service_creation(self, service_name: ServiceType):
        """
        Validate whether the service can be created.
        """
        if service_name not in self.factories:
            raise ValueError(
                f"No factory registered for the service class '{service_name.name}'"
            )

        if (
            ServiceType.SETTINGS_MANAGER not in self.factories
            and service_name != ServiceType.SETTINGS_MANAGER
        ):
            raise ValueError(
                f"Cannot create service '{service_name.name}' before the settings service"
            )

    def update(self, service_name: ServiceType):
        """
        Update a service by its name.
        """
        if service_name in self.services:
            self.services.pop(service_name, None)
            self.get(service_name)


service_manager = ServiceManager()


def initialize_services():
    """
    Initialize all the services needed.
    """
    from langflow.services.database import factory as database_factory
    from langflow.services.cache import factory as cache_factory
    from langflow.services.chat import factory as chat_factory
    from langflow.services.settings import factory as settings_factory

    service_manager.register_factory(settings_factory.SettingsManagerFactory())
    service_manager.register_factory(database_factory.DatabaseManagerFactory())
    service_manager.register_factory(cache_factory.CacheManagerFactory())
    service_manager.register_factory(chat_factory.ChatManagerFactory())
