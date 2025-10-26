"""FlexStore service settings configuration."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class FlexStoreSettings(BaseSettings):
    """FlexStore service settings configuration."""

    ENDPOINT_URL: Optional[str] = None
    USER_AGENT: str = "genesis_studio"
    DEFAULT_STORAGE_ACCOUNT: Optional[str] = None
    DEFAULT_TEMPORARY_STORAGE_ACCOUNT: Optional[str] = None
    DEFAULT_TEMPORARY_STORAGE_CONTAINER: Optional[str] = None
    TIMEOUT: int = 120  # Increased from 60 to 120 seconds
    UPLOAD_TIMEOUT: int = 300  # Longer timeout for uploads
    CONNECT_TIMEOUT: int = 10  # Connection timeout
    READ_TIMEOUT: int = 120  # Increased from 60 to 120 seconds

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.ENDPOINT_URL)

    model_config = SettingsConfigDict(
        env_prefix="FLEXSTORE_", case_sensitive=True, validate_assignment=True
    )