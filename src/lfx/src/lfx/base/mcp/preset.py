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

A preset may additionally run in **pinned mode**: :meth:`_pinned_spec` returns a
:class:`~lfx.base.mcp.pinned.PinnedServerSpec` (usually built from the bundle's
capability manifest) and the component then refuses to use anything the server
returns that the bundle did not pin.  Unpinned presets keep today's behavior
exactly.

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

from lfx.base.mcp.pinned import PinnedServerSpec, enforce_pinned_tools, validate_pinned_arguments
from lfx.base.mcp.util import MCPStreamableHttpClient, update_tools
from lfx.custom.custom_component.component_with_cache import ComponentWithCache
from lfx.integrations.errors import IncompatibleToolError
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

    def _pinned_spec(self) -> PinnedServerSpec | None | Awaitable[PinnedServerSpec | None]:
        """Return the pinned server/tool contract, or ``None`` for discovery mode.

        A bundle that pins an action builds the spec from its capability manifest
        (``lfx.base.mcp.pinned.pinned_spec_from_capabilities``).  Returning ``None``
        -- the default -- keeps the historical behavior: the component uses whatever
        the server advertises.  May be declared ``async``.
        """
        return None

    # --------------------------------------------------------------- helpers
    def _pinned_provider(self) -> str | None:
        """Provider id used to tag pinned-mode errors (``IntegrationError.provider``)."""
        return getattr(self, "integration_provider_id", None)

    async def _resolved_pin(self) -> PinnedServerSpec | None:
        spec = self._pinned_spec()
        if inspect.isawaitable(spec):
            spec = await spec
        return spec

    def _resolved_timeout(self) -> float | None:
        raw = getattr(self, "tool_execution_timeout", 0) or 0
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _pinned_server_config(self, spec: PinnedServerSpec, server_config: dict[str, Any]) -> dict[str, Any]:
        """Force the pinned endpoint and transport onto the subclass's config.

        A subclass may leave the URL out entirely (the pin owns it).  If it does
        supply one, disagreeing with the pin is drift in the bundle itself and
        fails closed rather than silently connecting to the pinned endpoint.
        """
        declared = (server_config.get("url") or "").strip()
        if declared and declared != spec.server_url:
            msg = (
                f"This component is pinned to the MCP endpoint {spec.server_url} but its configuration "
                f"resolved to {declared}."
            )
            raise IncompatibleToolError(
                msg,
                provider=self._pinned_provider(),
                hint="Reinstall the bundle release that owns this pinned action.",
                details={"pinned_url": spec.server_url, "resolved_url": declared},
            )
        return {
            **server_config,
            "url": spec.server_url,
            "mode": "Streamable_HTTP",
            # The transport is part of the pin: an endpoint that only answers on the
            # legacy transport is drift, and the SSE fallback would hide it behind a
            # connection error.
            "allow_sse_fallback": False,
        }

    def _guarded_tool(self, tool: StructuredTool, spec: PinnedServerSpec) -> StructuredTool:
        """Wrap a pinned tool so call-time arguments are checked against its pin.

        Discovery-time comparison is not enough on its own: the engine's
        ``MCPStructuredTool`` forwards keys that are absent from the derived args
        schema, so an Agent could still hand a drifted argument to the provider.
        """
        pinned = spec.tool(getattr(tool, "name", "") or "")
        if pinned is None:
            return tool
        provider = self._pinned_provider()
        original = getattr(tool, "coroutine", None)
        if original is None:
            return tool
        property_order = list((pinned.input_schema or {}).get("properties") or {})

        async def guarded(*args: Any, **kwargs: Any) -> Any:
            arguments = dict(kwargs)
            for index, value in enumerate(args):
                if index >= len(property_order):
                    msg = f"The pinned tool {pinned.name!r} does not declare {len(args)} positional arguments."
                    raise IncompatibleToolError(msg, provider=provider, details={"tool": pinned.name})
                arguments[property_order[index]] = value
            validate_pinned_arguments(pinned, arguments, provider=provider)
            return await original(*args, **kwargs)

        try:
            tool.coroutine = guarded
        except (AttributeError, TypeError, ValueError):
            copier = getattr(tool, "model_copy", None)
            if copier is None:
                raise
            return copier(update={"coroutine": guarded})
        return tool

    async def _load_tools(self) -> tuple[list[StructuredTool], dict[str, StructuredTool]]:
        spec = await self._resolved_pin()
        config = self._mcp_server_config()
        if inspect.isawaitable(config):
            config = await config
        server_name, server_config = config
        if spec is not None:
            server_config = self._pinned_server_config(spec, server_config)
        _, tools, tool_cache = await update_tools(
            server_name,
            server_config,
            mcp_streamable_http_client=self._streamable_http_client,
            tool_execution_timeout=self._resolved_timeout(),
        )
        if spec is None:
            if not tools:
                msg = f"No tools were returned by {server_name}. Check the endpoint, IDs, and credentials."
                raise ValueError(msg)
            return tools, tool_cache

        # Fail closed: any added, removed, renamed, or re-shaped tool, and any
        # server-version or tools/list digest mismatch, is an incompatibility.
        enforce_pinned_tools(
            spec,
            tools,
            provider=self._pinned_provider(),
            server_label=server_name,
            server_info=self._streamable_http_client.server_info,
        )
        guarded = [self._guarded_tool(tool, spec) for tool in tools]
        return guarded, {tool.name: tool for tool in guarded}

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
        """Refresh the *Tool* dropdown from the live server (best effort).

        In pinned mode the options are the pinned tool identifiers and the live
        server is never consulted: letting discovery rewrite the dropdown would let
        the UI accept a drifted tool that ``run_tool`` then rejects.
        """
        if field_name == "tool":
            spec = await self._resolved_pin()
            if spec is not None:
                options = list(spec.names)
                build_config["tool"]["options"] = options
                if build_config["tool"].get("value") not in options:
                    build_config["tool"]["value"] = ""
                return build_config
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
