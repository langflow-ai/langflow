"""Pydantic schemas for v2 API endpoints."""

import logging
from pathlib import Path

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# SECURITY: Allowlist of approved MCP stdio commands
# Following Flowise best practice: https://github.com/FlowiseAI/Flowise/blob/main/packages/components/nodes/tools/MCP/CustomMCP/CustomMCP.ts#L166
# Only allow commands that are legitimate MCP server executables
ALLOWED_MCP_COMMANDS = {
    "node",  # Node.js MCP servers
    "python",  # Python MCP servers
    "python3",  # Python 3 MCP servers
    "npx",  # npm package executor for MCP servers
    "uvx",  # uv package executor for Python MCP servers
    "docker",  # Docker-based MCP servers
}

# SECURITY: Shell metacharacters that enable command injection
DANGEROUS_SHELL_CHARS = [";", "|", "&", "$", "`", "<", ">", "\n", "\r"]

# SECURITY: Keywords that enable code execution or package installation
DANGEROUS_KEYWORDS = {
    "-c",  # Python code execution
    "-e",  # Node eval
    "pip",  # Python package manager
    "install",  # Package installation
    "npm",  # Node package manager
    "yarn",  # Alternative Node package manager
    "pnpm",  # Alternative Node package manager
    "eval",  # Code evaluation
    "exec",  # Code execution
}


class MCPServerConfig(BaseModel):
    """Pydantic model for MCP server configuration."""

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    url: str | None = None

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str | None) -> str | None:
        """Validate MCP command against allowlist to prevent command injection.

        This prevents attackers from executing arbitrary commands via the MCP stdio interface.
        Only approved MCP server executables are allowed.

        Args:
            v: The command string to validate

        Returns:
            The validated command string

        Raises:
            ValueError: If the command is not in the allowlist
        """
        if v is None:
            return None

        # Extract base command (handle paths like /usr/bin/node or C:\Program Files\nodejs\node.exe)
        # Replace backslashes with forward slashes to handle Windows paths on any platform
        normalized_path = v.replace("\\", "/")
        base_command = Path(normalized_path).name

        # Remove .exe extension on Windows (case-insensitive)
        if base_command.lower().endswith(".exe"):
            base_command = base_command[:-4]

        # Validate against allowlist
        if base_command not in ALLOWED_MCP_COMMANDS:
            allowed_list = ", ".join(sorted(ALLOWED_MCP_COMMANDS))
            msg = f"Command '{base_command}' is not allowed for security reasons. Allowed commands: {allowed_list}"
            logger.warning(
                "MCP command rejected",
                extra={
                    "security_event": "mcp_command_rejected",
                    "rejected_command": base_command,
                    "full_path": v,
                    "allowed_commands": list(ALLOWED_MCP_COMMANDS),
                },
            )
            raise ValueError(msg)

        return v

    @field_validator("args")
    @classmethod
    def validate_args(cls, v: list[str] | None) -> list[str] | None:
        """Validate MCP command arguments to prevent shell injection and code execution.

        Blocks shell metacharacters and dangerous flags that could be used for
        command injection, code execution, or package installation attacks.

        Args:
            v: The list of arguments to validate

        Returns:
            The validated arguments list

        Raises:
            ValueError: If any argument contains dangerous patterns
        """
        if v is None:
            return None

        # Block shell metacharacters that could enable command injection
        for arg in v:
            for char in DANGEROUS_SHELL_CHARS:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    logger.warning(
                        "MCP argument rejected - shell metacharacter",
                        extra={
                            "security_event": "mcp_arg_shell_char_rejected",
                            "rejected_arg": arg,
                            "dangerous_char": char,
                            "all_args": v,
                        },
                    )
                    raise ValueError(msg)

        # Block dangerous flags that enable code execution or package installation
        # Note: We allow -m for legitimate Python MCP servers, but block pip/install
        for arg in v:
            # Check if argument matches any dangerous keyword (case-insensitive)
            if arg.lower() in DANGEROUS_KEYWORDS:
                msg = f"Argument '{arg}' is not allowed for security reasons"
                logger.warning(
                    "MCP argument rejected - dangerous keyword",
                    extra={
                        "security_event": "mcp_arg_keyword_rejected",
                        "rejected_arg": arg,
                        "all_args": v,
                    },
                )
                raise ValueError(msg)

        return v

    class Config:
        extra = "allow"  # Allow additional fields for flexibility
