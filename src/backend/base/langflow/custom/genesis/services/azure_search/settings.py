"""Azure AI Search configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureSearchSettings(BaseSettings):
    """Azure AI Search configuration settings."""

    # === Azure AI Search ===
    AZURE_SEARCH_ENDPOINT: str = Field(
        description="Azure AI Search service endpoint URL",
    )

    AZURE_SEARCH_API_KEY: str = Field(
        description="Azure AI Search API key",
    )

    AZURE_SEARCH_API_VERSION: str = Field(
        description="Azure AI Search API version",
    )

    model_config = SettingsConfigDict(
        env_prefix="", case_sensitive=True, validate_assignment=True, extra="ignore"
    )

    def is_configured(self) -> bool:
        """Check if Azure AI Search is properly configured."""
        return bool(
            self.AZURE_SEARCH_ENDPOINT and
            self.AZURE_SEARCH_API_KEY and
            self.AZURE_SEARCH_API_VERSION
        )
