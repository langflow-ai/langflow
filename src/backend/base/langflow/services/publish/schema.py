from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReleaseStage(str, Enum):
    PUBLISH = "publish"
    DEPLOY = "deploy"


class PublishedFlowMetadata(BaseModel):
    """Composite key to identify a specific published flow version."""

    model_config = ConfigDict(extra="ignore")
    version_id: str = Field(..., description="The version ID (publish_id).")
    last_modified: datetime | None = Field(None, description="The last modified timestamp from the storage service.")


class PublishedProjectMetadata(BaseModel):
    """Composite key to identify a specific published project version."""

    model_config = ConfigDict(extra="ignore")
    version_id: str = Field(..., description="The version ID (publish_id).")
    last_modified: datetime | None = Field(None, description="The last modified timestamp from the storage service.")
