"""Base class for "preset" MCP tool components.

A preset component wraps a *known* remote MCP server -- one whose endpoint
shape and auth scheme are fixed by the vendor -- so the flow author fills in
a handful of IDs and a credential instead of hand-assembling an MCP server
entry.  It reuses Langflow's MCP client engine (``lfx.base.mcp.util``) rather
than the ``MCP Tools`` picker UI:

* ``update_tools`` connects over Streamable HTTP (with the engine's SSE
  fallback), SSRF-validates the endpoint, and returns ready ``StructuredTool``
  objects that carry the correct argument schema.
* ``add_tool_output = True`` + ``_get_tools()`` gives the component a
  ``Toolset`` output that plugs straight into an Agent's *Tools* handle
  (the same pattern as the in-tree File System tool).
* A direct ``Response`` output runs one selected tool for non-agent flows.

Subclasses declare their own inputs and implement
:meth:`_mcp_server_config`.  They must include the shared inputs returned by
:func:`preset_control_inputs` so the base class can find the selected tool,
its JSON arguments, the timeout, and the SSL toggle.

The class lives in ``lfx.base`` (like ``LCModelComponent`` /
``LCVectorStoreComponent``) rather than inside a bundle because the
extension loader registers every ``*Component`` class it finds in a bundle
module -- a base class shipped inside a bundle would surface in the palette
as a broken node.  Consumers: ``lfx-confluent`` (Real-Time Context Engine)
and ``lfx-ibm`` (watsonx.data remote MCP server).
"""

from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Any

from lfx.base.mcp.util import MCPStreamableHttpClient, update_tools
from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.io import BoolInput, DropdownInput, FloatInput, MultilineInput, Output, StrInput
from lfx.log.logger import logger
from lfx.schema.dataframe import DataFrame

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from langchain_core.tools import StructuredTool, Tool

# Name of the hidden input that makes the "Tool Mode" toggle appear on the
# node header without hiding any real, user-editable input in tool mode.
TOOL_MODE_TRIGGER = "tool_mode_trigger"


def preset_control_inputs(tool_options: list[str], *, tool_info: str) -> list:
    """Return the shared control inputs every MCP preset component declares.

    ``tool_options`` seeds the *Tool* dropdown with the vendor-documented tool
    names so the component is usable before the first live connection; the
    dropdown's refresh button re-reads the list from the server.
    """
    return [
        DropdownInput(
            name="tool",
            display_name="Tool",
            options=list(tool_options),
            value="",
            info=tool_info,
            real_time_refresh=True,
            refresh_button=True,
        ),
        MultilineInput(
            name="tool_arguments",
            display_name="Tool Arguments (JSON)",
            info=(
                "JSON object passed as the arguments of the selected tool when the Response "
                'output is used directly (for example {"topic": "orders"}). Ignored in Tool '
                "Mode, where the Agent supplies the arguments."
            ),
            value="{}",
        ),
        FloatInput(
            name="tool_execution_timeout",
            display_name="Tool Execution Timeout (seconds)",
            info="Maximum time to wait for a tool call. Set to 0 to use the system-configured MCP timeout.",
            value=0.0,
            range_spec={"min": 0.0, "max": 3600.0, "step": 0.5},
            advanced=True,
        ),
        BoolInput(
            name="verify_ssl",
            display_name="Verify SSL Certificate",
            info="Disable only for development against a self-signed endpoint.",
            value=True,
            advanced=True,
        ),
        # Synthetic hidden input: exists ONLY so the "Tool Mode" toggle appears on
        # the node header (toggle visibility = any(input.tool_mode)). ``show=False``
        # keeps it out of the config UI; putting ``tool_mode=True`` on a real input
        # would hide that input in tool mode instead.
        StrInput(
            name=TOOL_MODE_TRIGGER,
            display_name="",
            show=False,
            tool_mode=True,
            required=False,
        ),
    ]


class MCPPresetComponent(ComponentWithCache):
    """Component base wrapping a fixed remote MCP server as an Agent toolset."""

    # Enables the "Tool Mode" toggle; when ON the framework calls ``_get_tools()``
    # and emits a Toolset output that connects to an Agent's "Tools" handle.
    add_tool_output = True

    outputs = [
        Output(display_name="Response", name="response", method="run_tool", types=["DataFrame"]),
    ]

    def __init__(self, **data) -> None:
        super().__init__(**data)
        # One HTTP client per component so concurrent tool loads share a session.
        self._streamable_http_client: MCPStreamableHttpClient = MCPStreamableHttpClient(
            component_cache=self._shared_component_cache
        )

    # ------------------------------------------------------------------ hooks
    def _mcp_server_config(self) -> tuple[str, dict[str, Any]] | Awaitable[tuple[str, dict[str, Any]]]:
        """Return ``(server_name, server_config)`` for ``update_tools``.

        ``server_config`` must contain ``url`` (already SSRF-validated by the
        engine, but subclasses should build it from validated tokens) and may
        contain ``headers`` and ``verify_ssl``.  May be declared ``async`` when
        building the config needs I/O (for example a token exchange).
        """
        raise NotImplementedError

    # --------------------------------------------------------------- helpers
    def _resolved_timeout(self) -> float | None:
        raw = getattr(self, "tool_execution_timeout", 0) or 0
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    async def _load_tools(self) -> tuple[list[StructuredTool], dict[str, StructuredTool]]:
        config = self._mcp_server_config()
        if inspect.isawaitable(config):
            config = await config
        server_name, server_config = config
        _, tools, tool_cache = await update_tools(
            server_name,
            server_config,
            mcp_streamable_http_client=self._streamable_http_client,
            tool_execution_timeout=self._resolved_timeout(),
        )
        if not tools:
            msg = f"No tools were returned by {server_name}. Check the endpoint, IDs, and credentials."
            raise ValueError(msg)
        return tools, tool_cache

    def _parse_tool_arguments(self) -> dict[str, Any]:
        raw = getattr(self, "tool_arguments", None)
        if raw is None or raw == "":
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError as exc:
            msg = f"Tool Arguments must be a JSON object: {exc}"
            raise ValueError(msg) from exc
        if not isinstance(parsed, dict):
            msg = 'Tool Arguments must be a JSON object (for example {"topic": "orders"}).'
            raise TypeError(msg)
        return parsed

    @staticmethod
    def _result_rows(result: Any) -> list[dict[str, Any]]:
        """Flatten an MCP ``CallToolResult`` into DataFrame rows.

        Text blocks that parse as a JSON object become one row; a JSON array of
        objects becomes one row per element; anything else is kept as a
        ``{"type": ..., "text": ...}`` row so no content is dropped.
        """
        content = getattr(result, "content", None) or []
        rows: list[dict[str, Any]] = []
        for item in content:
            if hasattr(item, "model_dump"):
                item_dict = item.model_dump()
            elif isinstance(item, dict):
                item_dict = dict(item)
            elif hasattr(item, "type"):
                item_dict = {"type": getattr(item, "type", "text"), "text": getattr(item, "text", None)}
            else:
                item_dict = {"type": "text", "text": str(item)}
            if item_dict.get("type") != "text":
                rows.append(item_dict)
                continue
            text = item_dict.get("text")
            try:
                parsed = json.loads(text) if isinstance(text, str) else None
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                rows.append(parsed)
            elif isinstance(parsed, list) and parsed and all(isinstance(x, dict) for x in parsed):
                rows.extend(parsed)
            elif parsed is not None:
                rows.append({"type": "text", "text": text, "parsed_value": parsed})
            else:
                rows.append(item_dict)
        return rows

    # -------------------------------------------------------- tool-mode hook
    async def _get_tools(self) -> list[Tool]:
        """Tool Mode entrypoint. Called by ``Component.to_toolkit()``."""
        tools, _ = await self._load_tools()
        return list(tools)

    # ------------------------------------------------------- direct output
    async def run_tool(self) -> DataFrame:
        """Run the selected tool once and return its content as a table."""
        tool_name = (getattr(self, "tool", "") or "").strip()
        if not tool_name:
            msg = "Select a tool to run, or turn on Tool Mode and connect the Toolset output to an Agent."
            raise ValueError(msg)
        _, tool_cache = await self._load_tools()
        tool = tool_cache.get(tool_name)
        if tool is None:
            available = ", ".join(sorted(tool_cache)) or "none"
            msg = f"Tool {tool_name!r} is not available on this server. Available tools: {available}."
            raise ValueError(msg)
        arguments = self._parse_tool_arguments()
        result = await tool.coroutine(**arguments)
        rows = self._result_rows(result)
        frame = DataFrame(rows)
        self.status = frame
        return frame

    # ------------------------------------------------ dropdown live refresh
    async def update_build_config(
        self,
        build_config: dict,
        field_value: Any,  # noqa: ARG002 - framework signature; the refresh does not depend on the value
        field_name: str | None = None,
    ) -> dict:
        """Refresh the *Tool* dropdown from the live server (best effort)."""
        if field_name == "tool":
            try:
                tools, _ = await self._load_tools()
            except Exception as exc:  # noqa: BLE001 -- keep the documented defaults on any failure
                await logger.adebug(f"MCP preset tool refresh failed; keeping default options: {exc}")
            else:
                names = [t.name for t in tools if getattr(t, "name", None)]
                if names:
                    build_config["tool"]["options"] = names
                    current = build_config["tool"].get("value")
                    if current not in names:
                        build_config["tool"]["value"] = ""
        return build_config
