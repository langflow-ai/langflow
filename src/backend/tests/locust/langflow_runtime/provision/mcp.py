"""MCP project settings helpers."""

from __future__ import annotations

from typing import Any

from tests.locust.langflow_runtime.clients.mcp_streamable import McpStreamableClient
from tests.locust.langflow_runtime.provision.api import ProvisionHttp


def configure_project_mcp(
    http: ProvisionHttp,
    *,
    project_id: str,
    flow_id: str,
    action_name: str | None,
    enable: bool = True,
    auth_type: str = "apikey",
) -> dict[str, Any]:
    """PATCH project MCP settings so tools/list works with API-key auth."""
    settings = [
        {
            "id": flow_id,
            "mcp_enabled": enable,
            "action_name": action_name,
            "action_description": action_name or "perf suite tool",
        }
    ]
    return http.patch_mcp_project(
        project_id,
        settings=settings,
        auth_settings={"auth_type": auth_type},
    )


def configure_mcp_for_state(http: ProvisionHttp, state: dict[str, Any]) -> None:
    """Enable MCP on every provisioned flow that declares an mcp_action_name."""
    flows = state.get("flows") or {}
    configured = 0
    for record in flows.values():
        action = record.get("mcp_action_name")
        if not action:
            continue
        configure_project_mcp(
            http,
            project_id=str(record["project_id"]),
            flow_id=str(record["flow_id"]),
            action_name=str(action),
        )
        configured += 1
    state["mcp"] = {"configured": configured > 0, "flow_count": configured}
    state.setdefault("flags", {})["mcp_configured"] = configured > 0


def validate_mcp_tools_listable(http: ProvisionHttp, state: dict[str, Any]) -> bool:
    """Initialize MCP and list tools for the first MCP-enabled flow."""
    api_key = state.get("api_key")
    if not api_key:
        return False
    for record in (state.get("flows") or {}).values():
        action = record.get("mcp_action_name")
        if not action:
            continue
        client = McpStreamableClient(
            api=http.api_client(api_key=str(api_key)),
            project_id=str(record["project_id"]),
        )
        client.initialize()
        client.notify_initialized()
        tools = client.list_tools()
        names = {tool.get("name") for tool in tools}
        ok = str(action) in names or any(str(action) in str(n) for n in names)
        state.setdefault("flags", {})["mcp_tools_ok"] = ok
        state["mcp"]["tools_ok"] = ok
        state["mcp"]["discovered"] = sorted(str(n) for n in names if n)
        return ok
    state.setdefault("flags", {})["mcp_tools_ok"] = False
    return False
