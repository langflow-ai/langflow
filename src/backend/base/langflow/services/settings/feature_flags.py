from lfx.services.settings.feature_flags import FEATURE_FLAGS

<<<<<<< HEAD

class FeatureFlags(BaseSettings):
    mvp_components: bool = False

    class Config:
        env_prefix = "LANGFLOW_FEATURE_"


FEATURE_FLAGS = FeatureFlags()
=======
__all__ = ["FEATURE_FLAGS"]
>>>>>>> main
