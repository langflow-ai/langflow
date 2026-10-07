from pydantic_settings import BaseSettings


class FeatureFlags(BaseSettings):
    wxo_deployments: bool = False
    """
    Enable Watsonx Orchestrate deployments.
    """
    mvp_components: bool = False
    data_subject_requests: bool = False
    """
    Enable GDPR data subject requests: the request queue, find, export and erase APIs.
    """

    class Config:
        env_prefix = "LANGFLOW_FEATURE_"


FEATURE_FLAGS = FeatureFlags()
