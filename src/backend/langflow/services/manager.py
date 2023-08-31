from langflow.services.schema import ServiceType
from typing import TYPE_CHECKING, List, Optional
from langflow.utils.logger import logger

if TYPE_CHECKING:
    from langflow.services.factory import ServiceFactory


class ServiceManager:
    """
    Manages the creation of different services.
    """

    def __init__(self):
        self.services = {}
        self.factories = {}
        self.dependencies = {}

    def register_factory(
        self,
        service_factory: "ServiceFactory",
        dependencies: Optional[List[ServiceType]] = None,
    ):
        """
        Registers a new factory with dependencies.
        """
        if dependencies is None:
            dependencies = []
        service_name = service_factory.service_class.name
        self.factories[service_name] = service_factory
        self.dependencies[service_name] = dependencies

    def get(self, service_name: ServiceType):
        """
        Get (or create) a service by its name.
        """
        if service_name not in self.services:
            self._create_service(service_name)

        return self.services[service_name]

    def _create_service(self, service_name: ServiceType):
        """
        Create a new service given its name, handling dependencies.
        """
        logger.debug(f"Create service {service_name}")
        self._validate_service_creation(service_name)

        # Create dependencies first
        for dependency in self.dependencies.get(service_name, []):
            if dependency not in self.services:
                self._create_service(dependency)

        # Collect the dependent services
        dependent_services = {
            dep.value: self.services[dep]
            for dep in self.dependencies.get(service_name, [])
        }

        # Create the actual service
        self.services[service_name] = self.factories[service_name].create(
            **dependent_services
        )

    def _validate_service_creation(self, service_name: ServiceType):
        """
        Validate whether the service can be created.
        """
        if service_name not in self.factories:
            raise ValueError(
                f"No factory registered for the service class '{service_name.name}'"
            )

    def update(self, service_name: ServiceType):
        """
        Update a service by its name.
        """
        if service_name in self.services:
            logger.debug(f"Update service {service_name}")
            self.services.pop(service_name, None)
            self.get(service_name)

    def teardown(self):
        """
        Teardown all the services.
        """
        for service in self.services.values():
            logger.debug(f"Teardown service {service.name}")
            service.teardown()
        self.services = {}
        self.factories = {}
        self.dependencies = {}


service_manager = ServiceManager()


def initialize_services():
    """
    Initialize all the services needed.
    """
    from langflow.services.database import factory as database_factory
    from langflow.services.cache import factory as cache_factory
    from langflow.services.chat import factory as chat_factory
    from langflow.services.settings import factory as settings_factory
    from langflow.services.auth import factory as auth_factory

    service_manager.register_factory(settings_factory.SettingsManagerFactory())
    service_manager.register_factory(
        auth_factory.AuthManagerFactory(), dependencies=[ServiceType.SETTINGS_MANAGER]
    )
    service_manager.register_factory(
        database_factory.DatabaseManagerFactory(),
        dependencies=[ServiceType.SETTINGS_MANAGER],
    )
    service_manager.register_factory(cache_factory.CacheManagerFactory())
    service_manager.register_factory(chat_factory.ChatManagerFactory())

    # Test cache connection
    service_manager.get(ServiceType.CACHE_MANAGER)
    # Test database connection
    service_manager.get(ServiceType.DATABASE_MANAGER)


def initialize_settings_manager():
    """
    Initialize the settings manager.
    """
    from langflow.services.settings import factory as settings_factory

    service_manager.register_factory(settings_factory.SettingsManagerFactory())


def initialize_session_manager():
    """
    Initialize the session manager.
    """
    from langflow.services.session import factory as session_manager_factory  # type: ignore
    from langflow.services.cache import factory as cache_factory

    initialize_settings_manager()

    service_manager.register_factory(
        cache_factory.CacheManagerFactory(), dependencies=[ServiceType.SETTINGS_MANAGER]
    )

    service_manager.register_factory(
        session_manager_factory.SessionManagerFactory(),
        dependencies=[ServiceType.CACHE_MANAGER],
    )


def teardown_services():
    """
    Teardown all the services.
    """
    service_manager.teardown()
