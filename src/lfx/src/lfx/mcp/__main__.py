"""Entry point for the Langflow MCP server.

Usage:
    python -m lfx.mcp
    # or via console script:
    lfx-mcp

Environment variables:
    LANGFLOW_SERVER_URL: Langflow server URL (default: http://localhost:7860)
    LANGFLOW_API_KEY: API key for authentication (skips login)
"""

from lfx.mcp.server import mcp


def main():
    mcp.run()


if __name__ == "__main__":
    main()
