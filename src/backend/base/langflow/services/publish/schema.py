import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALNUM_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")  # Allowed: a-z, A-Z, 0-9, _, ., -

INVALID_FLOW_MSG = (
    "Invalid flow. Flow data must contain ALL of these keys:\n"
    "- name (must be non-empty and contain at least one alphanumeric character)\n"
    "- description (can be None or empty)\n"
    "- nodes (can be None or empty)\n"
    "- edges (can be None or empty)"
)
INVALID_PROJECT_MSG = (
    "Invalid project. Project data must contain ALL of these keys:\n"
    "- name (must be non-empty and contain at least one alphanumeric character)\n"
    "- description (can be None or empty)\n"
    "- flows (must be a nonempty list)"
)


def _to_alnum_string(value: str | None) -> str | None:
    """Returns a new string with invalid characters removed."""
    return ALNUM_PATTERN.sub("", value) if value else None


IDType = str | UUID | None
IDTypeStrict = str | UUID

class ReleaseStage(str, Enum):
    PUBLISH = "publish"
    DEPLOY = "deploy"


class PublishedFlowMetadata(BaseModel):
    """Metadata for a specific published flow version."""
    model_config = ConfigDict(extra="ignore")
    version_id: str = Field(..., description="The version ID (publish_id).")
    last_modified: datetime | None = Field(
        None, description="The last modified timestamp from the storage service."
    )


class PublishedProjectMetadata(BaseModel):
    """Metadata for a specific published project version."""
    model_config = ConfigDict(extra="ignore")
    version_id: str = Field(..., description="The version ID (publish_id).")
    last_modified: datetime | None = Field(
        None, description="The last modified timestamp from the storage service."
    )


class FlowBlob(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    description: str | None
    nodes: list | None
    edges: list | None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return _to_alnum_string(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if not value:
            raise ValueError(INVALID_FLOW_MSG)
        return value


class PublishedFlowReference(BaseModel):
    model_config = ConfigDict(extra="allow")
    version_id: str


class ProjectFlowEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str # flow id
    database_flow: FlowBlob | None = None
    published_version: PublishedFlowReference | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if bool(self.published_version) == bool(self.database_flow):
            msg = "Each flow entry must have exactly one of published_version or database_flow."
            raise ValueError(msg)
        return self


class ProjectBlob(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    description: str | None
    flows: list[ProjectFlowEntry] = Field(..., min_length=1)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return _to_alnum_string(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if not value:
            raise ValueError(INVALID_PROJECT_MSG)
        return value
