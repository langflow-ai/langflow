import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# url-friendly pattern (is "." ok?)
ALNUM_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")  # Allowed: a-z, A-Z, 0-9, _, ., -
def _to_alnum_string(value: str | None) -> str | None:
    """Returns a new string with invalid characters removed."""
    return ALNUM_PATTERN.sub("", value) if value else None


IDType = str | UUID | None
IDTypeStrict = str | UUID


# keys to use for checkpointing
TOP_LEVEL_CHECKPOINT_KEYS = ["name", "description"]
DATA_LEVEL_CHECKPOINT_KEYS = ["nodes", "edges", "viewport"]


class FlowCheckpointMetadata(BaseModel):
    """Metadata for a specific published flow version."""
    model_config = ConfigDict(extra="ignore")
    id: UUID = Field(..., description="The checkpoint ID.")
    flow_id: UUID = Field(..., description="The flow ID.")
    created_at: datetime | None = Field(
        None, description="The last modified timestamp from the storage service."
    )
