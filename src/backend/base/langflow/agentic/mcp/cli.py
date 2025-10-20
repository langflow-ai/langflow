#!/usr/bin/env python3
"""Command-line interface for the Langflow Agentic MCP server."""

import argparse
import sys


def main() -> int:
    """Run the Langflow Agentic MCP server."""
    parser = argparse.ArgumentParser(
        description="Langflow Agentic MCP Server - Expose template search tools via Model Context Protocol"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List all available MCP tools and exit",
    )

    args = parser.parse_args()

    if args.list_tools:
        # Import here to avoid circular imports
        from langflow.agentic.mcp.server import mcp

        print("Available MCP Tools:")
        print("=" * 60)
        # Access the tools from the FastMCP instance
        if hasattr(mcp, "_tools"):
            for tool_name in mcp._tools:
                print(f"  - {tool_name}")
        else:
            print("  - search_templates")
            print("  - get_template")
            print("  - list_all_tags")
            print("  - count_templates")
        print("=" * 60)
        return 0

    # Run the FastMCP server
    from langflow.agentic.mcp.server import mcp

    print("Starting Langflow Agentic MCP Server...")
    print("Server: langflow-agentic")
    print("Tools: search_templates, get_template, list_all_tags, count_templates")
    print("-" * 60)

    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
