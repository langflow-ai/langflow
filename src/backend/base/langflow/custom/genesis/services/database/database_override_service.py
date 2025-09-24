"""Database override service for Langflow integration."""

import os
from typing import Optional

from langflow.services.base import Service
from loguru import logger

from .azure_postgres_service import AzurePostgreSQLService
from .settings import DatabaseSettings


class DatabaseOverrideService(Service):
    """Service for overriding Langflow's database configuration."""

    name = "database_override_service"

    def __init__(
        self,
        settings: Optional[DatabaseSettings] = None,
        postgres_service: Optional[AzurePostgreSQLService] = None,
    ):
        super().__init__()
        self.settings = settings or DatabaseSettings()
        self.postgres_service = postgres_service or AzurePostgreSQLService(
            self.settings
        )
        self._original_database_url: Optional[str] = None
        self._override_applied = False

    def is_override_needed(self) -> bool:
        """Check if database override is needed."""
        return self.postgres_service.is_enabled()

    def apply_override(self) -> bool:
        """Apply database override to Langflow configuration.

        Returns:
            bool: True if override was applied successfully, False otherwise.
        """
        if not self.is_override_needed():
            logger.debug(
                "Database override not needed - Azure PostgreSQL managed identity disabled"
            )
            return False

        if self._override_applied:
            logger.debug("Database override already applied")
            return True

        try:
            # Store original database URL if it exists
            self._original_database_url = os.environ.get("LANGFLOW_DATABASE_URL")

            # Get connection string with current token
            connection_string = self.postgres_service.get_connection_string_sync()

            # Override Langflow's database URL
            os.environ["LANGFLOW_DATABASE_URL"] = connection_string
            self._override_applied = True

            logger.info(
                f"Database override applied: {self.settings.get_server_fqdn()}/"
                f"{self.settings.AZURE_POSTGRES_DATABASE_NAME}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to apply database override: {e}")
            return False

    def remove_override(self) -> bool:
        """Remove database override and restore original configuration.

        Returns:
            bool: True if override was removed successfully, False otherwise.
        """
        if not self._override_applied:
            logger.debug("No database override to remove")
            return True

        try:
            if self._original_database_url is not None:
                # Restore original database URL
                os.environ["LANGFLOW_DATABASE_URL"] = self._original_database_url
                logger.debug("Restored original database URL")
            else:
                # Remove the environment variable if it didn't exist originally
                os.environ.pop("LANGFLOW_DATABASE_URL", None)
                logger.debug("Removed database URL environment variable")

            self._override_applied = False
            self._original_database_url = None

            logger.info("Database override removed")
            return True

        except Exception as e:
            logger.error(f"Failed to remove database override: {e}")
            return False

    async def refresh_connection(self) -> bool:
        """Refresh database connection with new token.

        Returns:
            bool: True if connection was refreshed successfully, False otherwise.
        """
        if not self._override_applied:
            logger.debug("No database override active - cannot refresh connection")
            return False

        try:
            # Clear cache to force token refresh
            self.postgres_service.clear_cache()

            # Get fresh connection string
            connection_string = (
                await self.postgres_service.get_connection_string_async()
            )

            # Update environment variable
            os.environ["LANGFLOW_DATABASE_URL"] = connection_string

            logger.debug("Database connection refreshed with new token")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh database connection: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test current database connection.

        Returns:
            bool: True if connection test successful, False otherwise.
        """
        return await self.postgres_service.test_connection_async()

    def get_current_database_url(self) -> Optional[str]:
        """Get current database URL from environment.

        Returns:
            Optional[str]: Current database URL or None if not set.
        """
        return os.environ.get("LANGFLOW_DATABASE_URL")

    def get_connection_info(self) -> dict:
        """Get current connection information for diagnostics.

        Returns:
            dict: Connection information including server, database, and status.
        """
        info = {
            "override_applied": self._override_applied,
            "azure_enabled": self.postgres_service.is_enabled(),
            "current_database_url": self.get_current_database_url(),
            "original_database_url": self._original_database_url,
        }

        if self.postgres_service.is_enabled():
            try:
                info.update(
                    {
                        "server_fqdn": self.settings.get_server_fqdn(),
                        "database_name": self.settings.AZURE_POSTGRES_DATABASE_NAME,
                        "username": self.settings.AZURE_POSTGRES_USERNAME,
                        "port": self.settings.AZURE_POSTGRES_PORT,
                    }
                )
            except Exception as e:
                info["configuration_error"] = str(e)

        return info

    async def cleanup(self) -> None:
        """Clean up resources and remove override if applied."""
        try:
            if self._override_applied:
                self.remove_override()

            await self.postgres_service.cleanup()
            logger.debug("Database override service cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
