from langflow.services.schema import ServiceType
from typing import TYPE_CHECKING, Dict, List, Optional
from loguru import logger

if TYPE_CHECKING:
    from langflow.services.factory import ServiceFactory
    from langflow.services.base import Service


class ServiceManager:
    """
    Manages the creation of different services.
    """

    def __init__(self):
        self.services: Dict[str, "Service"] = {}
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
        self.services[service_name].set_ready()

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
            if service is None:
                continue
            logger.debug(f"Teardown service {service.name}")
            try:
                service.teardown()
            except Exception as exc:
                logger.exception(exc)
        self.services = {}
        self.factories = {}
        self.dependencies = {}


service_manager = ServiceManager()


def reinitialize_services():
    """
    Reinitialize all the services needed.
    """

    service_manager.update(ServiceType.SETTINGS_SERVICE)
    service_manager.update(ServiceType.DATABASE_SERVICE)
    service_manager.update(ServiceType.CACHE_SERVICE)
    service_manager.update(ServiceType.CHAT_SERVICE)
    service_manager.update(ServiceType.SESSION_SERVICE)
    service_manager.update(ServiceType.AUTH_SERVICE)
    service_manager.update(ServiceType.TASK_SERVICE)

    # Test cache connection
    service_manager.get(ServiceType.CACHE_SERVICE)
    # Test database connection
    service_manager.get(ServiceType.DATABASE_SERVICE)

    # Test cache connection
    service_manager.get(ServiceType.CACHE_SERVICE)
    # Test database connection
    service_manager.get(ServiceType.DATABASE_SERVICE)


def initialize_settings_service():
    """
    Initialize the settings manager.
    """
    from langflow.services.settings import factory as settings_factory

    service_manager.register_factory(settings_factory.SettingsServiceFactory())


def initialize_session_service():
    """
    Initialize the session manager.
    """
    from langflow.services.session import factory as session_service_factory  # type: ignore
    from langflow.services.cache import factory as cache_factory

    initialize_settings_service()

    service_manager.register_factory(
        cache_factory.CacheServiceFactory(), dependencies=[ServiceType.SETTINGS_SERVICE]
    )

    service_manager.register_factory(
        session_service_factory.SessionServiceFactory(),
        dependencies=[ServiceType.CACHE_SERVICE],
    )
