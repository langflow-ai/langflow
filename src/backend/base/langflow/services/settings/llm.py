from typing import Literal

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_LLM_")
    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "gpt-4o"
    base_url: str | None = None
    api_key: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str, info: ValidationInfo) -> str:
        # If the provider is openai and base_url was not provided, the base_url should be https://api.openai.com/v1
        # else it is whatever is provided
        if info.data.get("provider") == "openai" and not v:
            return "https://api.openai.com/v1"
        return v
