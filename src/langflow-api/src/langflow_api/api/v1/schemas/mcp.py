from uuid import UUID

from pydantic import BaseModel


class MCPSettings(BaseModel):
    id: UUID
    mcp_enabled: bool | None = None
    action_name: str | None = None
    action_description: str | None = None
    name: str | None = None
    description: str | None = None
