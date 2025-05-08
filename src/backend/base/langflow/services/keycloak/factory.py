"""Keycloak Service Factory.

This module provides a factory for creating KeycloakService instances.
The factory defines the dependencies required by the KeycloakService
and is responsible for its creation and initialization.

This follows the Factory pattern used throughout Langflow's service architecture,
allowing for dependency injection and service management.
"""

from langflow.services.factory import ServiceFactory
from langflow.services.keycloak.service import KeycloakService
from langflow.services.schema import ServiceType
from langflow.services.settings.service import SettingsService


class KeycloakServiceFactory(ServiceFactory):
    """Factory for creating and configuring KeycloakService instances.

    This factory is responsible for:
    1. Defining the dependencies of KeycloakService
    2. Creating KeycloakService instances with required dependencies
    3. Registering the service with the service manager

    The KeycloakService depends on SettingsService to get configuration
    parameters for connecting to the Keycloak server.
    """

    def __init__(self):
        """Initialize the KeycloakServiceFactory.

        Sets up the service class and defines its dependencies.
        """
        super().__init__(KeycloakService)
        # Define dependencies - KeycloakService depends on SettingsService
        self.dependencies = [ServiceType.SETTINGS_SERVICE]

    def create(self, settings_service: SettingsService) -> KeycloakService:
        """Create a new KeycloakService instance with its dependencies.

        This method is called by the service manager when a KeycloakService
        is requested, after ensuring all dependencies are available.

        Args:
            settings_service: The SettingsService instance containing Keycloak configuration

        Returns:
            KeycloakService: A new KeycloakService instance
        """
        return KeycloakService(settings_service)
