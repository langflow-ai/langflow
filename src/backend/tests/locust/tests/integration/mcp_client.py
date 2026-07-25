"""Live MCP streamable-HTTP client helper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID


async def mcp_initialize_list_call(
    *,
    base_url: str,
    api_key: str,
    project_id: UUID,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Live MCP streamable-HTTP: initialize → initialized → tools/list → tools/call."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url = f"{base_url}/api/v1/mcp/project/{project_id}/streamable"
    headers = {"x-api-key": api_key}
    async with (
        streamablehttp_client(url, headers=headers, timeout=60.0, sse_read_timeout=60.0) as (
            read_stream,
            write_stream,
            _get_session_id,
        ),
        ClientSession(read_stream, write_stream) as session,
    ):
        init = await session.initialize()
        assert init is not None
        listed = await session.list_tools()
        names = [tool.name for tool in listed.tools]
        assert tool_name in names, f"expected tool {tool_name!r} in {names}"
        return await session.call_tool(tool_name, arguments)
