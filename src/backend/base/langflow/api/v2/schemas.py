"""Pydantic schemas for v2 API endpoints."""

# Keep these names available from the historical module while sharing the actual policy with
# standalone LFX and every execution-time gate.
from lfx.base.mcp.security import (  # noqa: F401 - compatibility re-exports
    ALLOWED_MCP_COMMANDS,
    DANGEROUS_ENV_VARS,
    DANGEROUS_KEYWORDS,
    DANGEROUS_SHELL_CHARS,
    SHELL_EXEC_FLAGS,
    SHELL_WRAPPERS,
    validate_mcp_stdio_config,
)
from pydantic import BaseModel, ConfigDict, model_validator


class MCPServerConfig(BaseModel):
    """Pydantic model for MCP server configuration."""

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    url: str | None = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validate_stdio_security(self) -> "MCPServerConfig":
        """Apply the shared MCP stdio policy to database/API configurations."""
        validate_mcp_stdio_config(self.command, self.args, self.env)
        return self
