"""Tests that externally exposed MCP tool names match the batch dispatch keys.

Both paths must agree so a caller scripting a `batch` can copy tool names
straight from the `list_tools` output without translation.
"""

from __future__ import annotations


async def test_layout_flow_tool_is_exposed_as_layout_flow() -> None:
    """Expose the layout tool as layout_flow.

    The Python function stays named layout_flow_tool to avoid a clash with
    the imported helper, but the MCP-exposed tool name should match what
    batch expects in its dispatch map.
    """
    from lfx.mcp.server import mcp

    tools = await mcp.list_tools()
    names = {t.name for t in tools}

    assert "layout_flow" in names
    assert "layout_flow_tool" not in names


async def test_batch_tool_map_keys_match_exposed_tool_names() -> None:
    """Keep batch dispatch keys in sync with exposed MCP tool names.

    A caller reading the MCP tool list should be able to drive batch
    without translating names.
    """
    from lfx.mcp.server import _get_tool_map, mcp

    tools = await mcp.list_tools()
    exposed = {t.name for t in tools}
    # batch itself is a tool but is not dispatched through the map -- skip it.
    batch_keys = {k for k in _get_tool_map() if k != "batch"}

    missing = batch_keys - exposed
    assert not missing, f"batch tool_map keys not exposed via MCP: {sorted(missing)}"
