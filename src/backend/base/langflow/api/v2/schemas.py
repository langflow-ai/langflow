"""Pydantic schemas for v2 API endpoints."""

from pathlib import Path

from pydantic import BaseModel, field_validator

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
            return v

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
            raise ValueError(msg)

        return v

    @field_validator("args")
    @classmethod
    def validate_args(cls, v: list[str] | None) -> list[str] | None:
        """Validate MCP command arguments to prevent shell injection.

        Blocks shell metacharacters that could be used for command injection.

        Args:
            v: The list of arguments to validate

        Returns:
            The validated arguments list

        Raises:
            ValueError: If any argument contains dangerous shell metacharacters
        """
        if v is None:
            return v

        # Block shell metacharacters that could enable command injection
        dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\n", "\r"]

        for arg in v:
            for char in dangerous_chars:
                if char in arg:
                    msg = f"Argument contains dangerous shell metacharacter '{char}': {arg}"
                    raise ValueError(msg)

        return v

    class Config:
        extra = "allow"  # Allow additional fields for flexibility
