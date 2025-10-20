"""MCP Server implementation for Langflow Agentic features.

This module provides an MCP server that automatically exposes functions
from the agentic folder as tools.
"""

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .config import SERVER_DESCRIPTION, SERVER_NAME, SERVER_VERSION
from .discovery import discover_all_tools, get_tool_list


def create_server() -> Server:
    """Create and configure the MCP server.

    Returns:
        Configured MCP Server instance
    """
    server = Server(SERVER_NAME)

    # Discover all available tools
    discovered_tools = discover_all_tools()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools.

        Returns:
            List of available MCP tools
        """
        tools = []

        for tool_name, metadata in discovered_tools.items():
            tool = Tool(
                name=tool_name,
                description=metadata["description"],
                inputSchema=metadata["schema"],
            )
            tools.append(tool)

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a tool with the given arguments.

        Args:
            name: The name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            List containing the tool execution result

        Raises:
            ValueError: If the tool is not found
        """
        if name not in discovered_tools:
            msg = f"Tool '{name}' not found"
            raise ValueError(msg)

        tool_metadata = discovered_tools[name]
        func = tool_metadata["function"]

        try:
            # Execute the function
            result = func(**arguments)

            # Format the result
            return [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, default=str),
                }
            ]

        except Exception as e:
            # Return error information
            return [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": str(e),
                            "type": type(e).__name__,
                        },
                        indent=2,
                    ),
                }
            ]

    return server


async def run_server():
    """Run the MCP server using stdio transport.

    This is the main entry point for running the server.
    """
    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def get_server_info() -> dict[str, Any]:
    """Get information about the server and available tools.

    Returns:
        Dictionary containing server metadata and available tools
    """
    return {
        "name": SERVER_NAME,
        "version": SERVER_VERSION,
        "description": SERVER_DESCRIPTION,
        "tools": get_tool_list(),
    }


def main():
    """Main entry point for the MCP server."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
