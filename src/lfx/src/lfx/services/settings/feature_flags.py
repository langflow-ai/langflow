from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlags(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGFLOW_FEATURE_")

    mvp_components: bool = False


FEATURE_FLAGS = FeatureFlags()
