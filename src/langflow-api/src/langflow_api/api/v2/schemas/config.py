from enum import Enum
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class FeatureFlags(BaseSettings):
    mvp_components: bool = False

    class Config:
        env_prefix = "LANGFLOW_FEATURE_"

FEATURE_FLAGS = FeatureFlags()

class BuildStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    STARTED = "started"
    IN_PROGRESS = "in_progress"

class ConfigResponse(BaseModel):
    feature_flags: FeatureFlags
    serialization_max_items_lenght: int
    serialization_max_text_length: int
    frontend_timeout: int
    auto_saving: bool
    auto_saving_interval: int
    health_check_max_retries: int
    max_file_size_upload: int
    webhook_polling_interval: int
    public_flow_cleanup_interval: int
    public_flow_expiration: int
    event_delivery: str
