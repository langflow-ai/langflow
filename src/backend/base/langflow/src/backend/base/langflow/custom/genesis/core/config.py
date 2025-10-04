"""Genesis Studio Configuration Settings.

This module provides configuration settings for Genesis Studio extensions.
"""

import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings
    from pydantic_settings import SettingsConfigDict
from pydantic import Field


class GenesisSettings(BaseSettings):
    """Genesis Studio settings loaded from environment variables."""

    # Tracing settings
    AUTONOMIZE_TRACING_ENABLED: bool = Field(default=False, env="AUTONOMIZE_TRACING_ENABLED")
    AUTONOMIZE_KAFKA_BROKERS: Optional[str] = Field(default=None, env="AUTONOMIZE_KAFKA_BROKERS")
    AUTONOMIZE_KAFKA_USERNAME: Optional[str] = Field(default=None, env="AUTONOMIZE_KAFKA_USERNAME")
    AUTONOMIZE_KAFKA_PASSWORD: Optional[str] = Field(default=None, env="AUTONOMIZE_KAFKA_PASSWORD")
    AUTONOMIZE_KAFKA_STREAMING_TOPIC: str = Field(default="genesis-traces-streaming", env="AUTONOMIZE_KAFKA_STREAMING_TOPIC")

    # Auth settings (disabled by default - authentication handled by genesis-bff)
    GENESIS_AUTH_ENABLED: bool = Field(default=False, env="GENESIS_AUTH_ENABLED")
    GENESIS_CLIENT_ID: Optional[str] = Field(default=None, env="GENESIS_CLIENT_ID")
    GENESIS_SERVICE_AUTH_URL: Optional[str] = Field(default=None, env="GENESIS_SERVICE_AUTH_URL")

    # Experiment/project name
    AUTONOMIZE_EXPERIMENT_NAME: str = Field(default="GenesisStudio", env="AUTONOMIZE_EXPERIMENT_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Allow extra environment variables without validation errors
    )

    @property
    def kafka_brokers_clean(self) -> Optional[str]:
        """Clean Kafka brokers string."""
        if not self.AUTONOMIZE_KAFKA_BROKERS:
            return None
        return self.AUTONOMIZE_KAFKA_BROKERS.strip('"\'')

    @property
    def kafka_username_clean(self) -> Optional[str]:
        """Clean Kafka username."""
        if not self.AUTONOMIZE_KAFKA_USERNAME:
            return None
        return self.AUTONOMIZE_KAFKA_USERNAME.strip('"\'')

    @property
    def kafka_security_protocol_clean(self) -> str:
        """Get Kafka security protocol."""
        return os.getenv("AUTONOMIZE_KAFKA_SECURITY_PROTOCOL", "SASL_SSL")

    @property
    def kafka_mechanism_clean(self) -> str:
        """Get Kafka SASL mechanism."""
        return os.getenv("AUTONOMIZE_KAFKA_SASL_MECHANISM", "PLAIN")

    def _strip_quotes(self, value: str) -> str:
        """Strip quotes from a string value."""
        return value.strip('"\'')


# Create global settings instance
settings = GenesisSettings()
