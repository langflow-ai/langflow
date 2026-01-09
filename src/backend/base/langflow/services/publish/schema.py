from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublishedFlowMetadata(BaseModel):
    """Composite key to identify a specific published flow version."""
    model_config = ConfigDict(extra="ignore")
    version_id: str = Field(..., description="The version ID (publish_id).")
    last_modified: datetime | None = Field(
        None, description="The authoritative creation timestamp from the storage service."
    )
    flow_name: str = Field(..., description="The name of the flow at the time of publishing.")
