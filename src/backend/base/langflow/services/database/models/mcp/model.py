from uuid import UUID

from pydantic import BaseModel


class MCPSettings(BaseModel):
    """Model representing MCP settings for a flow."""
    mcp_enabled: bool | None = None
    action_name: str | None = None
    action_description: str | None = None


class BatchMCPSettingsUpdate(BaseModel):
    """Model for updating MCP settings of multiple flows at once."""
    flow_ids: list[UUID]
    mcp_settings: MCPSettings


class ProjectMCPSettingsUpdate(BaseModel):
    """Model for updating MCP settings of all flows in a project."""
    mcp_enabled: bool | None = None
    set_action_names: bool = False  # If True, will set action_name to flow name if not set
