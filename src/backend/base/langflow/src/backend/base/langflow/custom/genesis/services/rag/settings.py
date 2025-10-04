"""Settings for RAG service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGSettings(BaseSettings):
    """RAG QnA service settings configuration"""

    BASE_URL: str | None = None
    V2_BASE_URL: str | None = None
    USER_AGENT: str = "genesis_studio"
    TIMEOUT: int = 120

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.BASE_URL and self.V2_BASE_URL)

    model_config = SettingsConfigDict(
        env_prefix="RAG_", case_sensitive=True, validate_assignment=True
    )
