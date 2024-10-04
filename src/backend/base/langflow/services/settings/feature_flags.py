from pydantic_settings import BaseSettings


class FeatureFlags(BaseSettings):
    add_toolkit_output: bool = False

    class Config:
        env_prefix = "LANGFLOW_FEATURE_"


FEATURE_FLAGS = FeatureFlags()
