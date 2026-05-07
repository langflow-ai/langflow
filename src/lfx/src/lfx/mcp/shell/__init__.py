"""Shell command MCP server.

Standalone FastMCP server that exposes a single tool, ``execute_command``,
for running shell commands inside a controlled working directory with a
multi-stage validation pipeline (classification, destructive-pattern
detection, mode enforcement, path validation).

V1 is a configurable subprocess executor with timeouts and working
directory control. It is NOT a sandbox: there is no Docker/namespace
isolation. Treat it accordingly when configuring permissions.

Usage:
    python -m lfx.mcp.shell
"""
