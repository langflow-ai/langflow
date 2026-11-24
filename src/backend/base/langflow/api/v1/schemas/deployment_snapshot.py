"""Read-only deployment snapshot response models."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from langflow.services.database.models.flow.model import AccessTypeEnum, FlowType


class DeploymentSnapshotProject(BaseModel):
    """The serving project identity and display metadata."""

    id: UUID
    name: str
    description: str | None = None


class DeploymentSnapshotFlow(BaseModel):
    """One flow graph captured without serving-plane ownership metadata.

    Exposure/presentation fields (same types and defaults as FlowBase) are
    carried alongside the graph so a rollback or a restore-after-delete can
    put them back exactly, rather than resetting them to FlowCreate's
    defaults. workspace_id/user_id/folder_id are deliberately excluded
    pending a decision on how a deploy target should treat them.
    """

    id: UUID
    name: str
    endpoint_name: str | None = None
    description: str | None = None
    data: dict[str, Any]
    is_component: bool | None = False
    locked: bool | None = False
    mcp_enabled: bool | None = False
    action_name: str | None = None
    action_description: str | None = None
    access_type: AccessTypeEnum = AccessTypeEnum.PRIVATE
    flow_type: FlowType = FlowType.WORKFLOW
    a2a_enabled: bool | None = False
    a2a_card_overrides: dict[str, Any] | None = None
    tags: list[str] | None = None
    icon: str | None = None
    icon_bg_color: str | None = None
    gradient: str | None = None


class DeploymentSnapshotRequiredConnection(BaseModel):
    """One non-secret connection handle and its static scope requirements."""

    provider: str
    name: str
    scopes: list[str] = Field(default_factory=list)


class DeploymentSnapshotRequiredModel(BaseModel):
    """One model a captured flow selects, in the shape the policy blocks by."""

    provider: str
    name: str
    model_type: str | None = None


class DeploymentSnapshotRequiredMcpProject(BaseModel):
    """One sibling project a flow calls, and the name its config calls it by."""

    server_name: str
    project_id: str


class DeploymentSnapshot(BaseModel):
    """A complete, safe baseline suitable for an Editor import."""

    project: DeploymentSnapshotProject
    flows: list[DeploymentSnapshotFlow]
    dependencies: dict[str, Any] = Field(default_factory=dict)
    required_variables: list[str] = Field(default_factory=list)
    required_connections: list[DeploymentSnapshotRequiredConnection] = Field(default_factory=list)
    # Model provider identities the captured flows select, and the number of
    # model fields that selected none. Both default empty, so a caller written
    # against the earlier response shape reads an unchanged payload.
    required_providers: list[str] = Field(default_factory=list)
    required_models: list[DeploymentSnapshotRequiredModel] = Field(default_factory=list)
    unresolved_model_fields: int = 0
    # What the captured flows' MCP servers need from the deploy target: variable
    # names it must already hold, and sibling projects that must already be
    # deployed there. Both default empty, for the same reason as above.
    required_mcp_variables: list[str] = Field(default_factory=list)
    required_mcp_projects: list[DeploymentSnapshotRequiredMcpProject] = Field(default_factory=list)
