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
    # Narrower than FlowCreate.data (``dict | None``): a replacement's graph is
    # never optional, and a None here would be accepted by this endpoint only
    # to be refused later by the deployment snapshot's strict capture ("flow
    # has no graph data"), letting content the snapshot cannot round-trip get
    # committed as a replacement in the first place.
    data: dict

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            msg = "name must not be blank"
            raise ValueError(msg)
        return value


class ProjectReplacementRequest(SQLModel):
    """Complete target flow set, description, and opaque dependency snapshot."""

    model_config = ConfigDict(extra="forbid")

    # Nullable so a snapshot carrying a null project description (Folder.description
    # is nullable) is restorable unchanged.
    description: str | None
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
