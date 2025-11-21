"""Settings for the Prompt service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class PromptSettings(BaseSettings):
    """Prompt service settings configuration"""

    PROMPTS_ENDPOINT_URL: str = (
        "http://localhost:8174/genesis-platform/prompt-management-be"  # Default to local prompt management service
    )
    TIMEOUT: int = 30
    USER_AGENT: str = "Langflow/1.0"

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.PROMPTS_ENDPOINT_URL)

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=True, validate_assignment=True)
