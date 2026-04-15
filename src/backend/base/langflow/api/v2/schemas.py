"""Pydantic schemas for v2 API endpoints."""

from pydantic import BaseModel


class MCPServerConfig(BaseModel):
    """Pydantic model for MCP server configuration."""

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    url: str | None = None

    class Config:
        extra = "allow"  # Allow additional fields for flexibility
