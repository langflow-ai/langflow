"""Configuration for connector service and retry behavior."""

from pydantic import BaseModel, Field


class ConnectorRetryConfig(BaseModel):
    """Configuration for connector retry behavior."""

    # Retry configuration
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed operations",
        ge=0,
        le=10,
    )
    initial_delay: float = Field(
        default=1.0,
        description="Initial delay in seconds between retries",
        gt=0,
        le=60,
    )
    max_delay: float = Field(
        default=60.0,
        description="Maximum delay in seconds between retries",
        gt=0,
        le=300,
    )
    exponential_base: float = Field(
        default=2.0,
        description="Base for exponential backoff calculation",
        ge=1.1,
        le=10,
    )
    jitter_enabled: bool = Field(
        default=True,
        description="Whether to add random jitter to retry delays",
    )

    # Circuit breaker configuration
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Whether to use circuit breaker pattern",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        description="Number of failures before circuit opens",
        ge=1,
        le=20,
    )
    circuit_breaker_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds to wait before attempting recovery",
        gt=0,
        le=600,
    )
    circuit_breaker_success_threshold: int = Field(
        default=1,
        description="Number of successes needed to close circuit",
        ge=1,
        le=10,
    )

    # Rate limiting configuration
    max_concurrent_operations_per_user: int = Field(
        default=10,
        description="Maximum concurrent operations per user",
        ge=1,
        le=100,
    )
    rate_limit_window_seconds: float = Field(
        default=60.0,
        description="Time window for rate limiting",
        gt=0,
        le=3600,
    )

    # Dead letter queue configuration
    dlq_enabled: bool = Field(
        default=True,
        description="Whether to use dead letter queue for failed operations",
    )
    dlq_max_retries: int = Field(
        default=3,
        description="Maximum retries for DLQ entries",
        ge=0,
        le=10,
    )
    dlq_batch_size: int = Field(
        default=10,
        description="Number of DLQ entries to process in batch",
        ge=1,
        le=100,
    )
    dlq_processing_interval: float = Field(
        default=300.0,
        description="Seconds between DLQ processing runs",
        gt=0,
        le=3600,
    )

    # Provider-specific timeouts
    provider_timeout_seconds: float = Field(
        default=30.0,
        description="Default timeout for provider API calls",
        gt=0,
        le=300,
    )
    provider_connect_timeout: float = Field(
        default=10.0,
        description="Connection timeout for provider APIs",
        gt=0,
        le=60,
    )
    provider_read_timeout: float = Field(
        default=30.0,
        description="Read timeout for provider APIs",
        gt=0,
        le=300,
    )

    # Webhook configuration
    webhook_renewal_interval_hours: float = Field(
        default=48.0,
        description="Hours between webhook subscription renewals",
        gt=0,
        le=168,  # 1 week
    )
    webhook_retry_on_failure: bool = Field(
        default=True,
        description="Whether to retry webhook operations on failure",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "LANGFLOW_CONNECTOR_"
        env_file = ".env"
        extra = "ignore"


class ConnectorProviderConfig(BaseModel):
    """Configuration for specific connector providers."""

    # Google Drive configuration
    google_drive_enabled: bool = Field(
        default=True,
        description="Whether Google Drive connector is enabled",
    )
    google_drive_scopes: list[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ],
        description="OAuth scopes for Google Drive",
    )
    google_drive_batch_size: int = Field(
        default=100,
        description="Number of files to fetch per batch",
        ge=1,
        le=1000,
    )
    google_drive_max_file_size_mb: float = Field(
        default=100.0,
        description="Maximum file size to sync in MB",
        gt=0,
        le=1000,
    )

    # OneDrive configuration
    onedrive_enabled: bool = Field(
        default=True,
        description="Whether OneDrive connector is enabled",
    )
    onedrive_scopes: list[str] = Field(
        default_factory=lambda: [
            "Files.Read",
            "Files.Read.All",
            "Sites.Read.All",
        ],
        description="OAuth scopes for OneDrive",
    )
    onedrive_batch_size: int = Field(
        default=200,
        description="Number of files to fetch per batch",
        ge=1,
        le=1000,
    )
    onedrive_max_file_size_mb: float = Field(
        default=100.0,
        description="Maximum file size to sync in MB",
        gt=0,
        le=1000,
    )

    # Dropbox configuration
    dropbox_enabled: bool = Field(
        default=False,
        description="Whether Dropbox connector is enabled",
    )
    dropbox_batch_size: int = Field(
        default=100,
        description="Number of files to fetch per batch",
        ge=1,
        le=1000,
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "LANGFLOW_CONNECTOR_"
        env_file = ".env"
        extra = "ignore"


class ConnectorServiceConfig(BaseModel):
    """Complete configuration for connector service."""

    retry: ConnectorRetryConfig = Field(
        default_factory=ConnectorRetryConfig,
        description="Retry and resilience configuration",
    )
    providers: ConnectorProviderConfig = Field(
        default_factory=ConnectorProviderConfig,
        description="Provider-specific configuration",
    )

    # General configuration
    enabled: bool = Field(
        default=True,
        description="Whether connector service is enabled",
    )
    encryption_key: str | None = Field(
        default=None,
        description="Master key for token encryption (auto-generated if not provided)",
        exclude=True,  # Don't expose in API responses
    )
    debug_mode: bool = Field(
        default=False,
        description="Enable debug logging for connectors",
    )
    telemetry_enabled: bool = Field(
        default=True,
        description="Whether to collect telemetry for connector operations",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "LANGFLOW_CONNECTOR_"
        env_file = ".env"
        extra = "ignore"


def get_connector_config() -> ConnectorServiceConfig:
    """Get connector configuration from environment or defaults.

    Returns:
        ConnectorServiceConfig instance
    """
    import os

    # Load from environment variables
    config_dict = {}

    # Check for nested configuration
    retry_config = {}
    provider_config = {}

    for key, value in os.environ.items():
        if key.startswith("LANGFLOW_CONNECTOR_"):
            clean_key = key.replace("LANGFLOW_CONNECTOR_", "").lower()

            if clean_key.startswith("retry_"):
                retry_key = clean_key.replace("retry_", "")
                retry_config[retry_key] = value
            elif clean_key.startswith("provider_") or "_enabled" in clean_key:
                provider_config[clean_key] = value
            else:
                config_dict[clean_key] = value

    # Build nested config
    if retry_config:
        config_dict["retry"] = ConnectorRetryConfig(**retry_config)
    if provider_config:
        config_dict["providers"] = ConnectorProviderConfig(**provider_config)

    return ConnectorServiceConfig(**config_dict)


# Global config instance
_connector_config: ConnectorServiceConfig | None = None


def get_cached_config() -> ConnectorServiceConfig:
    """Get cached connector configuration.

    Returns:
        Cached ConnectorServiceConfig instance
    """
    global _connector_config
    if _connector_config is None:
        _connector_config = get_connector_config()
    return _connector_config


def reset_config():
    """Reset cached configuration (useful for testing)."""
    global _connector_config
    _connector_config = None
