"""Pydantic schemas for v2 API endpoints."""

from pydantic import BaseModel, ConfigDict


class MCPServerConfig(BaseModel):
    """Pydantic model for MCP server configuration."""

    model_config = ConfigDict(extra="allow")

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    url: str | None = None
