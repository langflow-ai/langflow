from pydantic_settings import BaseSettings, SettingsConfigDict


class FlexStoreSettings(BaseSettings):
    """FlexStore service settings configuration"""

    ENDPOINT_URL: str | None = None
    USER_AGENT: str = "genesis_studio"
    DEFAULT_STORAGE_ACCOUNT: str | None = None
    DEFAULT_TEMPORARY_STORAGE_ACCOUNT: str | None = None
    DEFAULT_TEMPORARY_STORAGE_CONTAINER: str | None = None
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
