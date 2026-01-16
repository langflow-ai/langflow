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
CHECKPOINT_KEYS = ["name", "description", "data"]


class FlowCheckpointMetadata(BaseModel):
    """Metadata for a specific published flow version."""
    model_config = ConfigDict(extra="ignore")
    id: UUID = Field(..., description="The checkpoint ID.")
    flow_id: UUID = Field(..., description="The flow ID.")
    created_at: datetime | None = Field(
        None, description="The last modified timestamp from the storage service."
    )

# class FlowBlob(BaseModel):
#     model_config = ConfigDict(extra="allow")
#     name: str
#     description: str | None
#     nodes: list | None
#     edges: list | None

#     INVALID_FLOW_MSG: ClassVar[str] = (
#         "Invalid flow. Flow data must contain ALL of these keys:\n"
#         "- name (must be non-empty and contain at least one alphanumeric character)\n"
#         "- description (can be None or empty)\n"
#         "- nodes (can be None or empty)\n"
#         "- edges (can be None or empty)"
#         )

#     @field_validator("name", mode="before")
#     @classmethod
#     def normalize_name(cls, value):
#         return _to_alnum_string(value)

#     @field_validator("name")
#     @classmethod
#     def validate_name(cls, value):
#         if not value:
#             raise ValueError(cls.INVALID_FLOW_MSG)
#         return value


# class PublishedFlowReference(BaseModel):
#     model_config = ConfigDict(extra="allow")
#     version_id: str


# class ProjectFlowEntry(BaseModel):
#     model_config = ConfigDict(extra="allow")
#     id: str # flow id
#     database_flow: FlowBlob | None = None
#     published_version: PublishedFlowReference | None = None

#     @model_validator(mode="after")
#     def validate_source(self):
#         if bool(self.published_version) == bool(self.database_flow):
#             msg = "Each flow entry must have exactly one of published_version or database_flow."
#             raise ValueError(msg)
#         return self


# class ProjectBlob(BaseModel):
#     model_config = ConfigDict(extra="allow")
#     name: str
#     description: str | None
#     flows: list[ProjectFlowEntry] = Field(..., min_length=1)
#     INVALID_PROJECT_MSG: ClassVar[str] = (
#         "Invalid project. Project data must contain ALL of these keys:\n"
#         "- name (must be non-empty and contain at least one alphanumeric character)\n"
#         "- description (can be None or empty)\n"
#         "- flows (must be a nonempty list)"
#         )
#     @field_validator("name", mode="before")
#     @classmethod
#     def normalize_name(cls, value):
#         return _to_alnum_string(value)

#     @field_validator("name")
#     @classmethod
#     def validate_name(cls, value):
#         if not value:
#             raise ValueError(cls.INVALID_PROJECT_MSG)
#         return value
