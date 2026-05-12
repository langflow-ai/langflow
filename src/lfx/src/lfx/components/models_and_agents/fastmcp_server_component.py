"""FastMCP Server component — publish a FastMCP server from inside a flow.

Lets flow authors assemble their own FastMCP server with a curated list of
tools (sync or long-running) and resources (skills), choose a transport, and
get back an endpoint URL external MCP clients can connect to.

See ``docs/docs/Agents/mcp-fastmcp-component.mdx`` for the full spec.
"""

from __future__ import annotations

import os
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, TableInput
from lfx.log.logger import logger
from lfx.schema.data import Data

_DEFAULT_PORT_MIN = 7100
_DEFAULT_PORT_MAX = 7199
_VALID_TRANSPORTS = ("stdio", "streamable_http", "sse")


def _port_range() -> tuple[int, int]:
    pmin = int(os.environ.get("LANGFLOW_FASTMCP_PORT_MIN", _DEFAULT_PORT_MIN))
    pmax = int(os.environ.get("LANGFLOW_FASTMCP_PORT_MAX", _DEFAULT_PORT_MAX))
    return pmin, pmax


def _allow_external_bind() -> bool:
    return os.environ.get("LANGFLOW_FASTMCP_ALLOW_EXTERNAL_BIND", "false").lower() == "true"


class FastMCPServerComponent(Component):
    display_name: str = "FastMCP Server"
    description: str = (
        "Publish a FastMCP server exposing the selected tools and skills over the chosen "
        "transport. Long-running tools return job handles via the MCP job queue."
    )
    documentation: str = "https://docs.langflow.org/mcp-fastmcp-component"
    icon = "Wifi"
    name = "FastMCPServer"

    inputs = [
        MessageTextInput(
            name="server_name",
            display_name="Server Name",
            info="Unique FastMCP server name. Defaults to langflow-<flow_id> at runtime.",
            required=False,
        ),
        DropdownInput(
            name="transport",
            display_name="Transport",
            options=list(_VALID_TRANSPORTS),
            value="streamable_http",
            info="Transport over which the server is reachable.",
        ),
        MessageTextInput(
            name="host",
            display_name="Host",
            value="127.0.0.1",
            advanced=True,
            info="Bind address. 0.0.0.0 requires LANGFLOW_FASTMCP_ALLOW_EXTERNAL_BIND=true.",
        ),
        IntInput(
            name="port",
            display_name="Port",
            value=0,
            advanced=True,
            info="0 = auto-allocate from LANGFLOW_FASTMCP_PORT_MIN..MAX (default 7100-7199).",
        ),
        TableInput(
            name="tools",
            display_name="Tools",
            info=(
                "List of components or flows to expose as @mcp.tool(). Columns: name, "
                "description, source (component id or flow id), long_running (bool)."
            ),
            table_schema=[
                {"name": "name", "display_name": "Name", "type": "str"},
                {"name": "description", "display_name": "Description", "type": "str"},
                {"name": "source", "display_name": "Source (component/flow id)", "type": "str"},
                {"name": "long_running", "display_name": "Long Running", "type": "bool"},
            ],
            required=False,
        ),
        TableInput(
            name="resources",
            display_name="Resources / Skills",
            info=(
                "List of resources to expose. Columns: uri, name, mime_type, content_provider. "
                "Skills use mime_type=application/vnd.langflow.skill+json."
            ),
            table_schema=[
                {"name": "uri", "display_name": "URI", "type": "str"},
                {"name": "name", "display_name": "Name", "type": "str"},
                {"name": "mime_type", "display_name": "MIME Type", "type": "str"},
                {"name": "content_provider", "display_name": "Content Provider", "type": "str"},
            ],
            required=False,
        ),
        BoolInput(
            name="enable_telemetry",
            display_name="Enable Telemetry",
            value=True,
            advanced=True,
            info="Attach the standard FastMCP lifespan telemetry hooks.",
        ),
    ]

    outputs = [
        Output(display_name="Endpoint URL", name="endpoint_url", method="resolve_endpoint_url"),
        Output(display_name="Server Handle", name="server_handle", method="resolve_server_handle"),
        Output(display_name="Tool Descriptors", name="tool_descriptors", method="resolve_tool_descriptors"),
    ]

    def _validate_transport(self) -> str:
        transport = (self.transport or "streamable_http").strip()
        if transport not in _VALID_TRANSPORTS:
            msg = f"transport must be one of {_VALID_TRANSPORTS}, got {transport!r}"
            raise ValueError(msg)
        return transport

    def _validate_bind(self, host: str) -> None:
        if host not in {"127.0.0.1", "localhost"} and not _allow_external_bind():
            msg = (
                f"host={host!r} requires LANGFLOW_FASTMCP_ALLOW_EXTERNAL_BIND=true; "
                "external bind is disabled by default"
            )
            raise ValueError(msg)

    def _resolve_server_name(self) -> str:
        if self.server_name:
            return str(self.server_name)
        graph = getattr(self, "graph", None)
        flow_id = getattr(graph, "flow_id", None) if graph else None
        return f"langflow-{flow_id or 'fastmcp'}"

    def _allocate_port(self, requested: int) -> int:
        if requested and requested > 0:
            return requested
        pmin, _ = _port_range()
        # TODO(fastmcp-port-allocator): replace with a real persistent allocator
        # service. For now return the start of the configured range; callers
        # will get a clear bind error if the port is in use.
        return pmin

    def _row_value(self, row: Any, key: str, default: Any = None) -> Any:
        if isinstance(row, dict):
            return row.get(key, default)
        return default

    def _normalize_tools(self) -> list[dict[str, Any]]:
        rows = getattr(self, "tools", None) or []
        normalized: list[dict[str, Any]] = []
        for row in rows:
            name = self._row_value(row, "name")
            source = self._row_value(row, "source")
            if not name or not source:
                continue
            normalized.append(
                {
                    "name": str(name),
                    "description": str(self._row_value(row, "description", "") or ""),
                    "source": str(source),
                    "long_running": bool(self._row_value(row, "long_running", default=False)),
                }
            )
        return normalized

    def _normalize_resources(self) -> list[dict[str, Any]]:
        rows = getattr(self, "resources", None) or []
        normalized: list[dict[str, Any]] = []
        for row in rows:
            uri = self._row_value(row, "uri")
            if not uri:
                continue
            normalized.append(
                {
                    "uri": str(uri),
                    "name": str(self._row_value(row, "name", "") or ""),
                    "mime_type": str(
                        self._row_value(row, "mime_type", "application/octet-stream") or "application/octet-stream"
                    ),
                    "content_provider": str(self._row_value(row, "content_provider", "") or ""),
                }
            )
        return normalized

    async def resolve_endpoint_url(self) -> Data:
        transport = self._validate_transport()
        host = str(self.host or "127.0.0.1")
        self._validate_bind(host)
        if transport == "stdio":
            payload: dict[str, Any] = {
                "transport": "stdio",
                "command": f"python -m langflow.runtime.fastmcp_server {self._resolve_server_name()}",
            }
        else:
            port = self._allocate_port(int(self.port or 0))
            payload = {
                "transport": transport,
                "host": host,
                "port": port,
                "url": f"http://{host}:{port}",
            }
        # TODO(fastmcp-runtime): start the FastMCP instance via a long-lived
        # service registered on the component manager (see service spec). The
        # current build returns the resolved endpoint metadata so wiring can
        # be validated without spinning up a real listener.
        logger.debug("FastMCPServerComponent endpoint resolved: %s", payload)
        return Data(data=payload)

    async def resolve_server_handle(self) -> Data:
        name = self._resolve_server_name()
        return Data(
            data={
                "server_name": name,
                "tools": self._normalize_tools(),
                "resources": self._normalize_resources(),
            }
        )

    async def resolve_tool_descriptors(self) -> Data:
        # Returns the same shape resolve_server_handle exposes under "tools",
        # but as a standalone output so catalog and routing nodes can consume
        # just the tool list without unpacking the handle dict.
        return Data(data={"tools": self._normalize_tools()})
