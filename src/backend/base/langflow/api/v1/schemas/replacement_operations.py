"""API schemas for durable project replacement operations."""

from uuid import UUID

from pydantic import ConfigDict, field_validator
from sqlmodel import SQLModel

from langflow.services.database.models.flow.model import FlowCreate, FlowRead
from langflow.services.database.models.folder.model import FolderRead


class ReplacementFlowCreate(FlowCreate):
    """Ordinary flow-create fields with the stable id required by replacement."""

    id: UUID

    model_config = ConfigDict(extra="forbid")


class ProjectReplacementRequest(SQLModel):
    """Complete target flow set and project description for one replacement."""

    model_config = ConfigDict(extra="forbid")

    description: str
    flows: list[ReplacementFlowCreate]
    project_name: str | None = None

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "project_name must not be blank"
            raise ValueError(msg)
        return value


class ProjectReplacementResult(SQLModel):
    """Immutable response snapshot saved with the replacement transaction."""

    project: FolderRead
    flows: list[FlowRead]
