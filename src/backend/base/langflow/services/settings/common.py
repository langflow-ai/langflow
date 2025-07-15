from pydantic_settings import BaseSettings, SettingsConfigDict


class LangflowBaseSettings(BaseSettings):
    """Base settings class ensuring all Langflow settings share the same env prefix."""

    model_config = SettingsConfigDict(
        validate_assignment=True,
        extra="ignore",
        env_prefix="LANGFLOW_",
    )
