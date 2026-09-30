from pydantic_settings import BaseSettings


class FeatureFlags(BaseSettings):
    wxo_deployments: bool = False
    """
    Enable Watsonx Orchestrate deployments.
    """
    mvp_components: bool = False
    instance_migration: bool = False
    """
    Enable Settings > Migration, which guides a superuser through moving this instance to a new one.
    """

    class Config:
        env_prefix = "LANGFLOW_FEATURE_"


FEATURE_FLAGS = FeatureFlags()
