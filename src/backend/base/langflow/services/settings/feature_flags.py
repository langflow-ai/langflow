from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlags(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFLOW_FEATURE_")
    add_toolkit_output: bool = False


FEATURE_FLAGS = FeatureFlags()
