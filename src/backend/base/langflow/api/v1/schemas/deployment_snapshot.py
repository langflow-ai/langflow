"""Read-only deployment snapshot response models."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentSnapshotProject(BaseModel):
    """The serving project identity and display metadata."""

    id: UUID
    name: str
    description: str | None = None


class DeploymentSnapshotFlow(BaseModel):
    """One flow graph captured without serving-plane ownership metadata."""

    id: UUID
    name: str
    description: str | None = None
    data: dict[str, Any]


class DeploymentSnapshot(BaseModel):
    """A complete, safe baseline suitable for an Editor import."""

    project: DeploymentSnapshotProject
    flows: list[DeploymentSnapshotFlow]
    dependencies: dict[str, Any] = Field(default_factory=dict)
    required_variables: list[str] = Field(default_factory=list)
