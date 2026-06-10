import re

from pydantic import BaseModel, field_validator

from lfx.log.logger import logger


class McpSettings(BaseModel):
    """MCP server, session manager, and composer settings."""

    mcp_base_url: str = ""
    """External base URL used to build MCP server URLs in the UI configuration JSON
    (e.g. 'https://langflow.example.com'). When empty, the frontend falls back to
    the browser's window.location.origin."""

    mcp_server_timeout: int = 20
    """The number of seconds to wait before giving up on establishing a connection to the MCP server."""

    mcp_tool_execution_timeout: float = 180.0
    """Maximum seconds to wait for MCP tool execution before timing out.
    Default is 180 seconds (3 minutes) to support long-running operations.
    Supports decimal values for sub-second timeouts (e.g., 0.5 for 500ms).
    Individual components can override this with their own timeout setting.
    Must be a positive number greater than 0."""

    @field_validator("mcp_tool_execution_timeout")
    @classmethod
    def validate_mcp_tool_execution_timeout(cls, v: float) -> float:
        """Validate that mcp_tool_execution_timeout is positive."""
        if v <= 0:
            msg = "mcp_tool_execution_timeout must be greater than 0"
            raise ValueError(msg)
        return v

    # ---------------------------------------------------------------------
    # MCP Session-manager tuning
    # ---------------------------------------------------------------------
    mcp_max_sessions_per_server: int = 10
    """Maximum number of MCP sessions to keep per unique server (command/url).
    Mirrors the default constant MAX_SESSIONS_PER_SERVER in util.py. Adjust to
    control resource usage or concurrency per server."""

    mcp_session_idle_timeout: int = 400  # seconds (~6.7 minutes)
    """How long (in seconds) an MCP session can stay idle before the background
    cleanup task disposes of it."""

    mcp_session_cleanup_interval: int = 120  # seconds
    """Frequency (in seconds) at which the background cleanup task wakes up to
    reap idle sessions."""

    # MCP Server
    mcp_server_enabled: bool = True
    """If set to False, Langflow will not enable the MCP server."""
    mcp_server_enable_progress_notifications: bool = False
    """If set to False, Langflow will not send progress notifications in the MCP server."""

    # Add projects to MCP servers automatically on creation
    add_projects_to_mcp_servers: bool = True
    """If set to True, newly created projects will be added to the user's MCP servers config automatically."""

    # MCP Composer
    mcp_composer_enabled: bool = True
    """If set to False, Langflow will not start the MCP Composer service."""
    mcp_composer_version: str = "==0.1.0.8.10"
    """Version constraint for mcp-composer when using uvx. Uses PEP 440 syntax."""

    # MCP Server management
    mcp_servers_locked: bool = False
    """If set to True, users cannot add or modify MCP servers via the UI/API.

    This control is independent from ``embedded_mode`` and must be enabled
    explicitly when you want to lock MCP server management.
    """

    @field_validator("mcp_composer_version", mode="before")
    @classmethod
    def validate_mcp_composer_version(cls, value):
        """Ensure the version string has a version specifier prefix.

        If a bare version like '0.1.0.7' is provided, prepend '~=' to allow patch updates.
        Supports PEP 440 specifiers: ==, !=, <=, >=, <, >, ~=, ===
        """
        if not value:
            return "==0.1.0.8.10"  # Default

        specifiers = ["===", "==", "!=", "<=", ">=", "~=", "<", ">"]
        if any(value.startswith(spec) for spec in specifiers):
            return value

        if re.match(r"^\d+(\.\d+)*", value):
            logger.debug(f"Adding ~= prefix to bare version '{value}' -> '~={value}'")
            return f"~={value}"

        return value
