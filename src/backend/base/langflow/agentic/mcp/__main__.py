"""Entry point for running the Langflow Agentic MCP server.

This allows running the server with:
    python -m langflow.agentic.mcp
"""

from langflow.agentic.mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
