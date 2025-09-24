"""Database configuration settings for Genesis Studio Backend."""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Centralized database configuration settings."""

    # === Azure PostgreSQL Managed Identity ===
    AZURE_POSTGRES_MANAGED_IDENTITY_ENABLED: bool = Field(
        default=False,
        description="Enable Azure PostgreSQL with managed identity authentication",
    )

    AZURE_POSTGRES_SERVER_NAME: str = Field(
        default="",
        description="Azure PostgreSQL server name (without .postgres.database.azure.com suffix)",
    )

    AZURE_POSTGRES_DATABASE_NAME: str = Field(
        default="genesis_studio", description="PostgreSQL database name"
    )

    AZURE_POSTGRES_USERNAME: str = Field(
        default="",
        description="Managed identity username for PostgreSQL authentication",
    )

    AZURE_POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port number")

    # === Azure Managed Identity ===
    AZURE_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="User-assigned managed identity client ID (optional for system-assigned)",
    )

    # === Connection Settings ===
    CONNECTION_TIMEOUT: int = Field(
        default=30, description="Database connection timeout in seconds"
    )

    TOKEN_REFRESH_BUFFER: int = Field(
        default=300, description="Token refresh buffer time in seconds (5 minutes)"
    )

    # === Retry Configuration ===
    MAX_RETRIES: int = Field(
        default=3, description="Maximum number of connection retries"
    )

    RETRY_DELAY: float = Field(
        default=1.0, description="Initial retry delay in seconds"
    )

    @field_validator("AZURE_POSTGRES_SERVER_NAME")
    @classmethod
    def validate_server_name(cls, v: str) -> str:
        """Ensure server name doesn't include the Azure suffix."""
        if v and v.endswith(".postgres.database.azure.com"):
            # Remove the suffix if accidentally included
            return v.replace(".postgres.database.azure.com", "")
        return v

    @field_validator("AZURE_POSTGRES_PORT")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate PostgreSQL port number."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    def is_azure_managed_identity_configured(self) -> bool:
        """Check if Azure managed identity is properly configured."""
        return (
            self.AZURE_POSTGRES_MANAGED_IDENTITY_ENABLED
            and bool(self.AZURE_POSTGRES_SERVER_NAME)
            and bool(self.AZURE_POSTGRES_DATABASE_NAME)
            and bool(self.AZURE_POSTGRES_USERNAME)
        )

    def get_server_fqdn(self) -> str:
        """Get the fully qualified domain name for the Azure PostgreSQL server."""
        if not self.AZURE_POSTGRES_SERVER_NAME:
            raise ValueError("Azure PostgreSQL server name is not configured")
        return f"{self.AZURE_POSTGRES_SERVER_NAME}.postgres.database.azure.com"

    model_config = SettingsConfigDict(
        env_prefix="", case_sensitive=True, validate_assignment=True, extra="ignore"
    )
