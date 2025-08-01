"""Export format schemas for LFX CLI."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FlowExport(BaseModel):
    """Flow data for export - lightweight version without SQLModel dependencies."""

    # Required fields from FlowRead
    id: str | UUID = Field(..., description="Unique identifier for the flow")
    name: str = Field(..., description="Name of the flow")

    # Optional fields from FlowBase
    description: str | None = Field(None, description="Description of the flow")
    icon: str | None = Field(None, description="Icon identifier")
    icon_bg_color: str | None = Field(None, description="Icon background color")
    gradient: str | None = Field(None, description="Gradient configuration")
    data: dict | None = Field(None, description="Flow graph data containing nodes and edges")
    is_component: bool | None = Field(default=False, description="Whether this flow is a component")
    updated_at: datetime | str | None = Field(None, description="Last update timestamp")
    webhook: bool | None = Field(default=False, description="Whether webhooks are enabled")
    endpoint_name: str | None = Field(None, description="Endpoint name for API access")
    tags: list[str] | None = Field(None, description="Tags associated with the flow")
    locked: bool | None = Field(default=False, description="Whether the flow is locked")
    mcp_enabled: bool | None = Field(default=False, description="Whether MCP is enabled")
    action_name: str | None = Field(None, description="MCP action name")
    action_description: str | None = Field(None, description="MCP action description")
    access_type: str = Field(default="PRIVATE", description="Access type (PRIVATE/PUBLIC)")

    # Fields from FlowRead
    user_id: str | UUID | None = Field(None, description="User ID who owns the flow")
    folder_id: str | UUID | None = Field(None, description="Folder/Project ID containing the flow")


class ProjectExportMetadata(BaseModel):
    """Metadata for the project export."""

    id: str = Field(..., description="Unique identifier for the project")
    name: str = Field(..., description="Name of the project")
    description: str | None = Field(None, description="Description of the project")
    auth_settings: dict | None = Field(default_factory=dict, description="Authentication settings for the project")


class ProjectExport(BaseModel):
    """Complete project export format."""

    version: str = Field(default="1.0", description="Export format version")
    langflow_version: str = Field(..., description="Version of Langflow that created this export")
    export_type: Literal["project"] = Field(default="project", description="Type of export")
    exported_at: str = Field(..., description="Export timestamp in ISO format")
    project: ProjectExportMetadata = Field(..., description="Project metadata")
    flows: list[FlowExport | dict] = Field(default_factory=list, description="List of flows in the project")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0",
                "langflow_version": "1.5.0",
                "export_type": "project",
                "exported_at": "2024-01-31T10:00:00Z",
                "project": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "My AI Project",
                    "description": "A collection of AI workflows",
                    "auth_settings": {},
                },
                "flows": [],
            }
        }
    )
