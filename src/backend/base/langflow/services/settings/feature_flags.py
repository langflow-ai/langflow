from pydantic_settings import BaseSettings

from langflow.services.deps import get_settings_service


class FeatureFlags(BaseSettings):
    mvp_components: bool = False
    mcp_composer: bool = get_settings_service().settings.mcp_composer_enabled

    class Config:
        env_prefix = "LANGFLOW_FEATURE_"


FEATURE_FLAGS = FeatureFlags()
