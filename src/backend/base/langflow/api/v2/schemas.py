"""Pydantic schemas for v2 API endpoints."""

# SECURITY: the MCP stdio command/args/env security policy lives in lfx
# (lfx.base.mcp.security). Both this REST-layer model and the flow-execution-time enforcement
# in lfx.base.mcp.util call the SAME validate_mcp_stdio_config, so the allowlist/metacharacter/
# env/docker checks are byte-for-byte identical and can never drift. The allowlist/blocklist
# constants and the base-command helper are re-exported here for backwards compatibility with
# code that imported them from this module before they were moved to lfx.
from lfx.base.mcp.security import (  # noqa: F401 - re-exported for backwards compatibility
    ALLOWED_MCP_COMMANDS,
    DANGEROUS_ENV_VARS,
    DANGEROUS_KEYWORDS,
    DANGEROUS_SHELL_CHARS,
    DOCKER_DANGEROUS_ARG_PREFIXES,
    DOCKER_DANGEROUS_ARGS,
    SHELL_EXEC_FLAGS,
    SHELL_WRAPPERS,
    validate_mcp_stdio_config,
)
from lfx.base.mcp.security import (
    extract_base_command as _extract_base_command,  # noqa: F401 - re-exported for compatibility
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
        """Enforce the MCP stdio command/args/env security policy.

        Prevents command injection / arbitrary code execution via the MCP stdio interface:
        command allowlist (cmd/sh/bash may only WRAP another allowed command), shell-metacharacter
        and dangerous-keyword rejection in args, an environment-variable blocklist
        (LD_PRELOAD/NODE_OPTIONS/PATH/...), and docker isolation-breaking args. A command that
        embeds its own arguments (e.g. ``bash -c '<payload>'``) is tokenized before the checks so
        the embedded tokens cannot bypass them.

        Delegates to ``lfx.base.mcp.security.validate_mcp_stdio_config`` (the single source of
        truth). It raises ``MCPStdioSecurityError`` (a ``ValueError``), which pydantic surfaces
        as a ``ValidationError``.
        """
        validate_mcp_stdio_config(self.command, self.args, self.env)
        return self
