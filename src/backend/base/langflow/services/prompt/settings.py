"""Settings for the Prompt service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class PromptSettings(BaseSettings):
    """Prompt service settings configuration"""

    ENDPOINT_URL: str = "http://localhost:7860"  # Default to local Langflow server
    TIMEOUT: int = 30

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.ENDPOINT_URL)

    model_config = SettingsConfigDict(
        env_prefix="PROMPT_", case_sensitive=True, validate_assignment=True
    )