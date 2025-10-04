from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class KnowledgeSettings(BaseSettings):
    """KnowledgeHub settings configuration"""

    ENDPOINT_URL: str = "http://localhost:3002"
    CLIENT_ID: str = "1"
    USER_AGENT: str = "genesis_studio"
    TIMEOUT: int = 120
    GENESIS_CLIENT_ID: str = os.getenv("GENESIS_CLIENT_ID", "")

    def is_configured(self) -> bool:
        """Check if required settings are configured."""
        return bool(self.ENDPOINT_URL and self.CLIENT_ID)

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGEHUB_", case_sensitive=True, validate_assignment=True
    )
