from pydantic import BaseModel, ConfigDict, Field


class PublishedFlowMetadata(BaseModel):
    """Composite key to identify a specific published flow version."""
    model_config = ConfigDict(extra="ignore")
    version_id: str = Field(..., description="The version ID (publish_id).")
    timestamp: str = Field(..., description="The creation timestamp.")
    flow_name: str = Field(..., description="The name of the flow at the time of publishing.")
