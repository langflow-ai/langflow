from uuid import UUID

from pydantic import BaseModel


class MCPSettings(BaseModel):
    """Model representing MCP settings for a flow."""

    id: UUID
    mcp_enabled: bool | None = None
    action_name: str | None = None
    action_description: str | None = None
    name: str | None = None
    description: str | None = None


class BatchMCPSettingsUpdate(BaseModel):
    """Model for updating MCP settings of multiple flows at once."""

    flow_ids: list[UUID]
    mcp_settings: MCPSettings
