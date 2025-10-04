"""Azure PostgreSQL service for Genesis Studio Backend."""

import asyncio
import time
from typing import Optional

from langflow.services.base import Service
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from .azure_credential_service import AzureCredentialService
from .settings import DatabaseSettings

# Constants to replace magic numbers
TOKEN_CACHE_DURATION = 3600  # 1 hour
POOL_SIZE = 5
MAX_OVERFLOW = 10


class AzurePostgreSQLService(Service):
    """Service for Azure PostgreSQL operations with managed identity."""

    name = "azure_postgres_service"

    def __init__(
        self,
        settings: Optional[DatabaseSettings] = None,
        credential_service: Optional[AzureCredentialService] = None,
    ):
        super().__init__()
        self.settings = settings or DatabaseSettings()
        self.credential_service = credential_service or AzureCredentialService(
            self.settings
        )
        self._connection_string_cache: Optional[str] = None
        self._cache_expires_at: float = 0

    def is_enabled(self) -> bool:
        """Check if Azure PostgreSQL managed identity is enabled and configured."""
        return self.settings.is_azure_managed_identity_configured()

    def _is_connection_string_valid(self) -> bool:
        """Check if cached connection string is still valid."""
        return self._connection_string_cache is not None and time.time() < (
            self._cache_expires_at - self.settings.TOKEN_REFRESH_BUFFER
        )

    def _build_connection_string(self, access_token: str) -> str:
        """Build PostgreSQL connection string with access token.

        Args:
            access_token: Azure access token to use as password

        Returns:
            str: Complete PostgreSQL connection string
        """
        server_fqdn = self.settings.get_server_fqdn()
        return (
            f"postgresql://{self.settings.AZURE_POSTGRES_USERNAME}:{access_token}@"
            f"{server_fqdn}:{self.settings.AZURE_POSTGRES_PORT}/"
            f"{self.settings.AZURE_POSTGRES_DATABASE_NAME}"
            f"?sslmode=require&connect_timeout={self.settings.CONNECTION_TIMEOUT}"
        )

    def _cache_connection_string(self, connection_string: str) -> None:
        """Cache connection string with expiration.

        Args:
            connection_string: Connection string to cache
        """
        self._connection_string_cache = connection_string
        self._cache_expires_at = time.time() + TOKEN_CACHE_DURATION

    def get_connection_string_sync(self) -> str:
        """Get PostgreSQL connection string with current access token (synchronous)."""
        if not self.is_enabled():
            raise ValueError(
                "Azure PostgreSQL managed identity is not properly configured"
            )

        # Return cached connection string if still valid
        if self._is_connection_string_valid():
            logger.debug("Using cached PostgreSQL connection string")
            return self._connection_string_cache

        try:
            # Get fresh access token
            access_token = self.credential_service.get_token_sync()

            # Build and cache connection string
            connection_string = self._build_connection_string(access_token)
            self._cache_connection_string(connection_string)

            server_fqdn = self.settings.get_server_fqdn()
            logger.debug(f"Generated PostgreSQL connection string for {server_fqdn}")
            return connection_string

        except Exception as e:
            logger.error(f"Failed to generate PostgreSQL connection string: {e}")
            raise

    async def get_connection_string_async(self) -> str:
        """Get PostgreSQL connection string with current access token (asynchronous)."""
        if not self.is_enabled():
            raise ValueError(
                "Azure PostgreSQL managed identity is not properly configured"
            )

        # Return cached connection string if still valid
        if self._is_connection_string_valid():
            logger.debug("Using cached PostgreSQL connection string")
            return self._connection_string_cache

        try:
            # Get fresh access token
            access_token = await self.credential_service.get_token_async()

            # Build and cache connection string
            connection_string = self._build_connection_string(access_token)
            self._cache_connection_string(connection_string)

            server_fqdn = self.settings.get_server_fqdn()
            logger.debug(f"Generated PostgreSQL connection string for {server_fqdn}")
            return connection_string

        except Exception as e:
            logger.error(f"Failed to generate PostgreSQL connection string: {e}")
            raise

    def test_connection_sync(self) -> bool:
        """Test database connection synchronously."""
        if not self.is_enabled():
            return False

        try:
            connection_string = self.get_connection_string_sync()
            engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                pool_recycle=TOKEN_CACHE_DURATION,
                connect_args={"connect_timeout": self.settings.CONNECTION_TIMEOUT},
            )

            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar()
                if result == 1:
                    logger.debug("PostgreSQL connection test successful")
                    return True

        except SQLAlchemyError as e:
            logger.warning(f"PostgreSQL connection test failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during connection test: {e}")

        return False

    async def test_connection_async(self) -> bool:
        """Test database connection asynchronously."""
        if not self.is_enabled():
            return False

        try:
            # Run connection test in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.test_connection_sync)

        except Exception as e:
            logger.warning(f"Async connection test failed: {e}")
            return False

    def create_engine(self) -> Engine:
        """Create SQLAlchemy engine with proper configuration."""
        if not self.is_enabled():
            raise ValueError("Azure PostgreSQL managed identity is not enabled")

        connection_string = self.get_connection_string_sync()

        return create_engine(
            connection_string,
            # Connection pool settings
            pool_size=POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=TOKEN_CACHE_DURATION,  # Recycle connections before token expires
            # Connection arguments
            connect_args={
                "connect_timeout": self.settings.CONNECTION_TIMEOUT,
                "application_name": "genesis-studio-backend",
                "sslmode": "require",
            },
            # Echo SQL queries for debugging (disable in production)
            echo=False,
        )

    def clear_cache(self) -> None:
        """Clear connection string cache."""
        self._connection_string_cache = None
        self._cache_expires_at = 0
        self.credential_service.clear_cache()
        logger.debug("PostgreSQL connection cache cleared")

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.clear_cache()
        await self.credential_service.cleanup()
        logger.debug("Azure PostgreSQL service cleaned up")
