"""Factory for creating and managing database services."""

from typing import Optional

from loguru import logger

from .azure_credential_service import AzureCredentialService
from .azure_postgres_service import AzurePostgreSQLService
from .database_override_service import DatabaseOverrideService
from .settings import DatabaseSettings


class DatabaseServiceFactory:
    """Factory for creating database services with proper dependency injection."""

    _instance: Optional["DatabaseServiceFactory"] = None

    def __init__(self, settings: Optional[DatabaseSettings] = None):
        self.settings = settings or DatabaseSettings()
        self._credential_service: Optional[AzureCredentialService] = None
        self._postgres_service: Optional[AzurePostgreSQLService] = None
        self._override_service: Optional[DatabaseOverrideService] = None

    @classmethod
    def get_instance(
        cls, settings: Optional[DatabaseSettings] = None
    ) -> "DatabaseServiceFactory":
        """Get singleton instance of the factory."""
        if cls._instance is None:
            cls._instance = cls(settings)
            logger.debug("Created database service factory instance")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    @property
    def credential_service(self) -> AzureCredentialService:
        """Get or create Azure credential service."""
        if self._credential_service is None:
            self._credential_service = AzureCredentialService(self.settings)
            logger.debug("Created Azure credential service")
        return self._credential_service

    @property
    def postgres_service(self) -> AzurePostgreSQLService:
        """Get or create Azure PostgreSQL service."""
        if self._postgres_service is None:
            self._postgres_service = AzurePostgreSQLService(
                self.settings, self.credential_service
            )
            logger.debug("Created Azure PostgreSQL service")
        return self._postgres_service

    @property
    def override_service(self) -> DatabaseOverrideService:
        """Get or create database override service."""
        if self._override_service is None:
            self._override_service = DatabaseOverrideService(
                self.settings, self.postgres_service
            )
            logger.debug("Created database override service")
        return self._override_service

    async def cleanup(self) -> None:
        """Clean up all services."""
        services = [
            ("override_service", self._override_service),
            ("postgres_service", self._postgres_service),
            ("credential_service", self._credential_service),
        ]

        for name, service in services:
            if service:
                try:
                    await service.cleanup()
                    logger.debug(f"Cleaned up {name}")
                except Exception as e:
                    logger.error(f"Error cleaning up {name}: {e}")

        # Reset all services
        self._override_service = None
        self._postgres_service = None
        self._credential_service = None


def get_database_factory(
    settings: Optional[DatabaseSettings] = None,
) -> DatabaseServiceFactory:
    """Get the database service factory instance."""
    return DatabaseServiceFactory.get_instance(settings)


def create_database_service(
    service_type: str, settings: Optional[DatabaseSettings] = None
) -> object:
    """Create a specific database service.

    Args:
        service_type: Type of service to create ('credential', 'postgres', 'override')
        settings: Optional settings override

    Returns:
        The requested service instance

    Raises:
        ValueError: If service_type is not recognized
    """
    factory = get_database_factory(settings)

    service_map = {
        "credential": factory.credential_service,
        "postgres": factory.postgres_service,
        "override": factory.override_service,
    }

    if service_type not in service_map:
        available_types = list(service_map.keys())
        raise ValueError(
            f"Unknown service type: {service_type}. "
            f"Available types: {available_types}"
        )

    return service_map[service_type]


# Convenience functions for direct service access
def get_credential_service(
    settings: Optional[DatabaseSettings] = None,
) -> AzureCredentialService:
    """Get Azure credential service."""
    return create_database_service("credential", settings)


def get_postgres_service(
    settings: Optional[DatabaseSettings] = None,
) -> AzurePostgreSQLService:
    """Get Azure PostgreSQL service."""
    return create_database_service("postgres", settings)


def get_override_service(
    settings: Optional[DatabaseSettings] = None,
) -> DatabaseOverrideService:
    """Get database override service."""
    return create_database_service("override", settings)


async def cleanup_all_services() -> None:
    """Clean up all database services."""
    factory = DatabaseServiceFactory.get_instance()
    await factory.cleanup()
    DatabaseServiceFactory.reset_instance()
    logger.debug("All database services cleaned up")
