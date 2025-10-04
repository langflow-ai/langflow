"""AI Gateway Settings Configuration."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIGatewaySettings(BaseSettings):
    """AI Gateway settings configuration."""

    ADMIN_KEY: str = Field(
        default=os.getenv("GENESIS_AI_GATEWAY_ADMIN_KEY", ""),
        description="Genesis AI Gateway admin key for model discovery",
    )

    GATEWAY_URL: str = Field(
        default="https://genesis.dev-v2.platform.autonomize.dev", description="AI Gateway base URL"
    )

    TIMEOUT: int = Field(default=120, description="Request timeout in seconds")

    def is_configured(self) -> bool:
        """Check if admin key is configured."""
        return bool(self.ADMIN_KEY)

    model_config = SettingsConfigDict(env_prefix="GENESIS_AI_GATEWAY_", case_sensitive=True, validate_assignment=True)


ai_gateway_settings = AIGatewaySettings()
