"""API schemas for durable project replacement operations."""

from typing import Any
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
    """Complete target flow set, description, and opaque dependency snapshot."""

    model_config = ConfigDict(extra="forbid")

    description: str
    flows: list[ReplacementFlowCreate]
    project_name: str | None = None
    # The Control Plane owns dependency validation and provisioning. The serving
    # plane stores the manifest as opaque JSON alongside the committed receipt.
    dependencies: dict[str, Any] | None = None

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
    # Optional for receipts written before dependency snapshots were introduced.
    dependencies: dict[str, Any] | None = None
