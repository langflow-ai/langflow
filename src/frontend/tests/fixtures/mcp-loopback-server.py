# ruff: noqa: INP001
"""Small deterministic MCP server used by Playwright on stdio and HTTP."""

from __future__ import annotations

import argparse
import datetime as dt

from mcp.server.fastmcp import FastMCP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--tool-set", choices=("all", "fetch", "time"), default="all")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = FastMCP(
        "langflow-playwright-loopback",
        host=args.host,
        port=args.port,
        stateless_http=True,
    )

    def echo(text: str) -> str:
        """Echo text through the local MCP transport."""
        return f"echoed: {text}"

    def fetch(url: str, max_length: int = 1000) -> str:
        """Return deterministic content without accessing the network."""
        return f"loopback content for {url}"[:max_length]

    def get_current_time(timezone: str = "UTC") -> str:
        """Return a stable-shaped timestamp for tool-discovery tests."""
        return f"{dt.datetime.now(tz=dt.timezone.utc).isoformat()} ({timezone})"

    if args.tool_set == "all":
        server.tool()(echo)
    if args.tool_set in {"all", "fetch"}:
        server.tool()(fetch)
    if args.tool_set in {"all", "time"}:
        server.tool()(get_current_time)

    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
