"""CLI for the Langflow Agentic MCP Server."""

import argparse
import json
import sys

from lfx.log.logger import  logger

from .server import get_server_info
from .server import main as run_mcp_server


def print_tools():
    """Print all available tools and their descriptions."""
    info = get_server_info()

    logger.info(f"\n{info['name']} v{info['version']}")
    logger.info("=" * 80)
    logger.info(f"{info['description']}\n")

    logger.info(f"Available Tools ({len(info['tools'])}):")
    logger.info("-" * 80)

    for tool in info["tools"]:
        logger.info(f"\n  {tool['name']}")
        logger.info(f"    {tool['description']}")

        # Show parameters
        schema = tool.get("input_schema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if properties:
            logger.info("    Parameters:")
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "any")
                is_required = param_name in required
                req_marker = " (required)" if is_required else " (optional)"
                logger.info(f"      - {param_name}: {param_type}{req_marker}")

                if "description" in param_info:
                    logger.info(f"        {param_info['description']}")

    logger.info("\n" + "=" * 80 + "\n")


def print_tools_json():
    """Print tools information as JSON."""
    info = get_server_info()
    logger.info(json.dumps(info, indent=2))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Langflow Agentic MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run MCP server (stdio)
  python -m langflow.agentic.mcp.cli

  # Run HTTP server
  python -m langflow.agentic.mcp.cli --http

  # Run WebSocket server
  python -m langflow.agentic.mcp.cli --websocket

  # List available tools
  python -m langflow.agentic.mcp.cli --list-tools
        """,
    )

    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List all available tools",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format (use with --list-tools)",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Print server version",
    )

    parser.add_argument(
        "--http",
        action="store_true",
        help="Run HTTP/SSE server instead of MCP stdio",
    )

    parser.add_argument(
        "--websocket",
        action="store_true",
        help="Run WebSocket server instead of MCP stdio",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (for HTTP/WebSocket) (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: 8000 for HTTP, 8001 for WebSocket)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development (HTTP/WebSocket only)",
    )

    args = parser.parse_args()

    if args.version:
        info = get_server_info()
        logger.info(f"{info['name']} version {info['version']}")
        sys.exit(0)

    if args.list_tools:
        if args.json:
            print_tools_json()
        else:
            print_tools()
        sys.exit(0)

    # Determine which server to run
    if args.http:
        from .http_server import run_http_server

        port = args.port or 8000
        logger.info(f"Starting HTTP/SSE server on {args.host}:{port}")
        run_http_server(host=args.host, port=port, reload=args.reload)

    elif args.websocket:
        from .websocket_server import run_websocket_server

        port = args.port or 8001
        logger.info(f"Starting WebSocket server on {args.host}:{port}")
        run_websocket_server(host=args.host, port=port, reload=args.reload)

    else:
        # Default: run MCP stdio server
        logger.info("Starting MCP server (stdio)...")
        run_mcp_server()


if __name__ == "__main__":
    main()
