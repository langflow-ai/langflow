# ruff: noqa: T201, RUF001, RUF002, RUF003, BLE001, PGH003

import argparse
import asyncio
import logging
from collections.abc import Sequence
from typing import Any

"""Demo MCP client for integration tests.

This script attempts to connect to an MCP server using the official Python SDK.
It follows the recommended protocol-negotiation order:

1. Try Streamable HTTP (2025-03-26)
2. Fallback to HTTP+SSE (2024-11-05) if the first attempt fails

Once connected it:
• Initializes the session
• Lists tools and prints their names
• Calls the optional `echo` tool
"""

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client  # type: ignore[import-not-found]
    from mcp.client.stdio import (
        StdioServerParameters,  # type: ignore[import-not-found]
        stdio_client,  # type: ignore[import-not-found]
    )
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    print('[demo_mcp_client] MCP SDK not found. Add "mcp>=1.6.0" to your dependencies.')
    raise

# ---------------------------------------------------------------------------
# Configure logging so that only critical errors appear on stdout.
# This hides the SDK's benign "Session termination failed: 404" message.
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.CRITICAL)
for noisy in ("mcp", "httpx", "anyio", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.CRITICAL)


async def _normalize_tool_list(raw: Any) -> list[str]:
    """Return a list of tool names from whatever the SDK returns."""
    if raw is None:
        return []

    # Newer SDKs return an object with .tools attribute
    if hasattr(raw, "tools"):
        raw = raw.tools  # type: ignore[attr-defined]

    # Ensure we have a sequence to iterate over
    if not isinstance(raw, Sequence):
        return []

    names: list[str] = []
    for item in raw:
        if item is None:
            continue
        # Dataclass / namespace with .name
        if hasattr(item, "name"):
            names.append(item.name)  # type: ignore[arg-type]
        # Dict style
        elif isinstance(item, dict) and "name" in item:
            names.append(str(item["name"]))
        # Tuple style (name, ...)
        elif isinstance(item, tuple) and len(item) > 0:
            names.append(str(item[0]))
    return names


async def run_demo(url: str) -> None:
    """Attempt Streamable HTTP first, fallback to SSE if necessary."""
    # Determine the transport order configured by main()
    order = globals().get("_transport_order")
    if not order:
        order = [
            ("streamable-http", streamablehttp_client),
            ("http+sse", sse_client),
        ]

    for transport_name, factory in order:
        try:
            async with factory(url) as streams:  # type: ignore[misc]
                # Unpack variable-length tuple (read, write, *rest)
                read_stream, write_stream, *_ = (*streams, None, None)[:2]  # type: ignore[misc]

                async with ClientSession(read_stream, write_stream) as session:
                    print(f"[demo_mcp_client] Connected using {transport_name} → {url}")

                    await session.initialize()
                    print("[demo_mcp_client] Session initialized ✔️")

                    tools_resp = await session.list_tools()
                    tool_names = await _normalize_tool_list(tools_resp)
                    print("[demo_mcp_client] Tools:", tool_names)

                    if "echo" in tool_names:
                        print("[demo_mcp_client] Calling echo tool …")
                        result = await session.call_tool("echo", {"message": "Hello from demo_mcp_client"})
                        print("[demo_mcp_client] echo() result:", result)

                    # Per spec a JSON-RPC "shutdown" notification is already sent by the SDK
                    # when the ClientSession context exits, so no explicit call here.
                    print("[demo_mcp_client] Session closed.")
                    return  # success, exit function

        except Exception as exc:
            print(f"[demo_mcp_client] {transport_name} attempt failed: {exc}")

    print("[demo_mcp_client] Unable to establish a connection using either transport.")


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Minimal MCP demo client")
    parser.add_argument(
        "--protocol",
        default="auto",
        choices=["auto", "streamable-http", "http+sse", "stdio"],
        help="Transport to use",
    )
    parser.add_argument("--url", help="Server URL for HTTP/SSE transports; omit for stdio")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command for stdio server (ex: node server.js)")

    args = parser.parse_args()

    protocol_mode: str = args.protocol
    target_url: str | None = args.url

    if protocol_mode != "stdio" and not target_url:
        parser.error("--url is required unless --protocol=stdio")

    # Configure transport order
    if protocol_mode == "streamable-http":
        ordered = [("streamable-http", streamablehttp_client)]
    elif protocol_mode == "http+sse":
        ordered = [("http+sse", sse_client)]
    elif protocol_mode == "stdio":
        if not args.command:
            parser.error("stdio protocol requires a server command to run")

        cmd, *cmd_args = args.command

        def _stdio_factory(_ignored_url: str):
            params = StdioServerParameters(command=cmd, args=cmd_args)
            return stdio_client(params)

        ordered = [("stdio", _stdio_factory)]
        target_url = "stdio"  # placeholder
    else:  # auto
        ordered = [
            ("streamable-http", streamablehttp_client),
            ("http+sse", sse_client),
        ]

    global _transport_order  # noqa: PLW0603
    _transport_order = ordered

    asyncio.run(run_demo(target_url or ""))


if __name__ == "__main__":  # pragma: no cover
    main()
