"""MCP Streamable HTTP (stateless) lifecycle client."""

from __future__ import annotations

import json
from typing import Any

from tests.locust.langflow_runtime.clients.base import ApiClient, ApplicationError, TransportError, wrap_response
from tests.locust.langflow_runtime.clients.sse import SseDeadlines, parse_sse_events

try:
    from mcp.types import LATEST_PROTOCOL_VERSION
except ImportError:  # pragma: no cover
    LATEST_PROTOCOL_VERSION = "2025-11-25"

MCP_SESSION_HEADER = "mcp-session-id"
MCP_PROTOCOL_HEADER = "mcp-protocol-version"
JSON_CONTENT = "application/json"
SSE_CONTENT = "text/event-stream"


class McpStreamableClient:
    """Drive initialize → initialized → tools/list → tools/call over streamable HTTP."""

    def __init__(
        self,
        http: Any,
        *,
        base_url: str,
        project_id: str,
        api_key: str,
        workload: str = "mcp",
        flow_class: str = "passthrough",
        api: ApiClient | None = None,
    ) -> None:
        self.api = api or ApiClient(http, base_url=base_url, api_key=api_key)
        self.project_id = str(project_id)
        self.workload = workload
        self.flow_class = flow_class
        self._next_id = 1
        self._session_id: str | None = None
        self._protocol_version: str | None = None
        self._endpoint = f"/api/v1/mcp/project/{self.project_id}/streamable"

    def _tx(self, operation: str) -> str:
        return ApiClient.tx_name("mcp", operation, self.workload, self.flow_class)

    def _rpc_id(self) -> int:
        current = self._next_id
        self._next_id += 1
        return current

    def _mcp_headers(self) -> dict[str, str]:
        headers = {
            "Accept": f"{JSON_CONTENT}, {SSE_CONTENT}",
            "Content-Type": JSON_CONTENT,
        }
        if self._session_id:
            headers[MCP_SESSION_HEADER] = self._session_id
        if self._protocol_version:
            headers[MCP_PROTOCOL_HEADER] = self._protocol_version
        return headers

    def _build_request(
        self, method: str, *, params: dict[str, Any] | None = None, is_notification: bool = False
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            payload["id"] = self._rpc_id()
        if params is not None:
            payload["params"] = params
        return payload

    def _capture_session(self, response: Any) -> None:
        headers = getattr(response, "headers", {}) or {}
        session_id = headers.get(MCP_SESSION_HEADER) or headers.get(MCP_SESSION_HEADER.lower())
        if session_id:
            self._session_id = str(session_id)

    def _parse_jsonrpc_response(self, body: Any, *, request_id: int | None) -> dict[str, Any]:
        data = json.loads(body) if isinstance(body, str) else body
        if not isinstance(data, dict):
            msg = "MCP response is not a JSON object"
            raise ApplicationError(msg, body=data)
        if "error" in data and data["error"] is not None:
            raise ApplicationError("MCP JSON-RPC error", body=data["error"])
        if request_id is not None and data.get("id") not in (None, request_id):
            raise ApplicationError("MCP response id mismatch", body=data)
        result = data.get("result")
        if result is None and "result" not in data:
            raise ApplicationError("MCP response missing result", body=data)
        return result if isinstance(result, dict) else {"value": result}

    def _read_response_body(
        self, response: Any, *, request_id: int | None, is_initialize: bool = False
    ) -> dict[str, Any]:
        status = int(getattr(response, "status_code", getattr(response, "status", 0)))
        if status == 202:
            return {}
        if status >= 400:
            parsed = wrap_response(response)
            raise ApplicationError(f"MCP HTTP {status}", status_code=status, body=parsed.text)

        if is_initialize:
            self._capture_session(response)

        headers = getattr(response, "headers", {}) or {}
        content_type = str(headers.get("content-type", headers.get("Content-Type", ""))).lower()

        if content_type.startswith(JSON_CONTENT):
            parsed = wrap_response(response, expect_json=True)
            result = self._parse_jsonrpc_response(parsed.json_data, request_id=request_id)
            if is_initialize and isinstance(result, dict) and "protocolVersion" in result:
                self._protocol_version = str(result["protocolVersion"])
            return result

        if content_type.startswith(SSE_CONTENT):
            iter_lines = getattr(response, "iter_lines", None)
            if iter_lines is None:
                msg = "streaming MCP response lacks iter_lines()"
                raise TransportError(msg)
            for event in parse_sse_events(
                iter_lines(),
                deadlines=SseDeadlines(read_s=60.0, idle_s=30.0),
                terminal_events={"message"},
            ):
                if event.event != "message" or not event.data:
                    continue
                payload = json.loads(event.data)
                result = self._parse_jsonrpc_response(payload, request_id=request_id)
                if is_initialize and isinstance(result, dict) and "protocolVersion" in result:
                    self._protocol_version = str(result["protocolVersion"])
                return result
            msg = "MCP SSE response ended without JSON-RPC payload"
            raise ApplicationError(msg)

        parsed = wrap_response(response)
        if parsed.text:
            return self._parse_jsonrpc_response(parsed.text, request_id=request_id)
        msg = f"unsupported MCP content-type: {content_type!r}"
        raise ApplicationError(msg)

    def _post(self, payload: dict[str, Any], *, name: str, is_initialize: bool = False) -> dict[str, Any]:
        request_id = payload.get("id")
        response = self.api.request(
            "POST",
            self._endpoint,
            name=name,
            json=payload,
            headers=self._mcp_headers(),
        )
        return self._read_response_body(response, request_id=request_id, is_initialize=is_initialize)

    def initialize(self) -> dict[str, Any]:
        payload = self._build_request(
            "initialize",
            params={
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "langflow-perf-suite", "version": "1.0"},
            },
        )
        return self._post(payload, name=self._tx("streamable_initialize"), is_initialize=True)

    def notify_initialized(self) -> None:
        payload = self._build_request("notifications/initialized", is_notification=True)
        self._post(payload, name=self._tx("initialized_notification"))

    def list_tools(self) -> list[dict[str, Any]]:
        payload = self._build_request("tools/list", params={})
        result = self._post(payload, name=self._tx("tools_list"))
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            msg = "tools/list result.tools is not a list"
            raise ApplicationError(msg, body=result)
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = self._build_request("tools/call", params={"name": name, "arguments": arguments})
        result = self._post(payload, name=self._tx("tools_call"))
        if result.get("isError"):
            raise ApplicationError("tools/call returned isError", body=result)
        return result

    def full_lifecycle_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.initialize()
        self.notify_initialized()
        tools = self.list_tools()
        names = {tool.get("name") for tool in tools}
        if tool_name not in names:
            msg = f"expected tool {tool_name!r} in discovered tools {sorted(names)}"
            raise ApplicationError(msg, body=tools)
        return self.call_tool(tool_name, arguments)

    def close_session(self) -> None:
        if not self._session_id:
            return
        self.api.request(
            "DELETE",
            self._endpoint,
            name=self._tx("session_delete"),
            headers=self._mcp_headers(),
        )
        self._session_id = None
