"""Entry point for the shell MCP server.

Usage:
    python -m lfx.mcp.shell
    # or via console script:
    lfx-shell-mcp

Environment variables:
    LANGFLOW_SHELL_WORKING_DIR        Working directory for commands
    LANGFLOW_SHELL_MODE               read_write (default) or read_only
    LANGFLOW_SHELL_MAX_TIMEOUT        Per-call timeout cap in seconds
    LANGFLOW_SHELL_MAX_OUTPUT_BYTES   Output truncation threshold
    LANGFLOW_SHELL_MAX_COMMAND_LENGTH Input length cap
"""

from lfx.mcp.shell.shell_server import get_config, mcp


def main() -> None:
    # Touch the config eagerly so misconfiguration fails before stdio
    # transport handshake — easier to debug than a half-booted server.
    get_config()
    mcp.run()


if __name__ == "__main__":
    main()
