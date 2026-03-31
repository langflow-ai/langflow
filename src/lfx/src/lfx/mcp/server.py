"""FastMCP server exposing Langflow operations as MCP tools.

Connects to a running Langflow server via REST API. Flow data is never
cached — every mutating tool does GET -> modify -> PATCH. The component
registry is cached on first access.

Tools are organized into 5 groups: auth, flow, component, connection, execution.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any

from mcp.server.fastmcp import FastMCP

from lfx.graph.flow_builder import (
    add_component as fb_add_component,
)
from lfx.graph.flow_builder import (
    add_connection as fb_add_connection,
)
from lfx.graph.flow_builder import (
    configure_component as fb_configure,
)
from lfx.graph.flow_builder import (
    empty_flow,
    layout_flow,
    needs_server_update,
)
from lfx.graph.flow_builder import (
    flow_info as fb_flow_info,
)
from lfx.graph.flow_builder import (
    get_component as fb_get_component,
)
from lfx.graph.flow_builder import (
    list_components as fb_list_components,
)
from lfx.graph.flow_builder import (
    remove_component as fb_remove_component,
)
from lfx.graph.flow_builder import (
    remove_connection as fb_remove_connection,
)
from lfx.mcp.client import LangflowClient
from lfx.mcp.registry import (
    describe_component as reg_describe,
)
from lfx.mcp.registry import (
    load_registry,
    search_registry,
)

# Session state.
#
# Each session (SSE or stdio) gets its own client and registry via contextvars.
# For stdio there's only one context so it just works. For SSE, each request
# gets its own context copy so sessions never leak into each other.
_client_var: contextvars.ContextVar[LangflowClient | None] = contextvars.ContextVar("_client", default=None)
_registry_var: contextvars.ContextVar[dict[str, dict] | None] = contextvars.ContextVar("_registry", default=None)

mcp = FastMCP("langflow-mcp-client")


def _get_client() -> LangflowClient:
    client = _client_var.get()
    if client is None:
        client = LangflowClient()
        _client_var.set(client)
    return client


def _set_client(client: LangflowClient) -> None:
    _client_var.set(client)


async def _get_registry() -> dict[str, dict]:
    registry = _registry_var.get()
    if registry is not None:
        return registry
    registry = await load_registry(_get_client())
    _registry_var.set(registry)
    return registry


async def _get_flow(flow_id: str) -> dict:
    """Fetch a flow from the server."""
    return await _get_client().get(f"/flows/{flow_id}")


async def _patch_flow(flow_id: str, flow: dict) -> dict:
    """Patch a flow on the server."""
    return await _get_client().patch(f"/flows/{flow_id}", json_data={"data": flow["data"]})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@mcp.tool()
async def login(username: str, password: str, server_url: str | None = None) -> dict[str, str]:
    """Authenticate with a Langflow server.

    The credentials are stored internally and used automatically for all
    subsequent tool calls. The API key is not returned for security.

    Args:
        username: Langflow username.
        password: Langflow password.
        server_url: Server URL (defaults to LANGFLOW_SERVER_URL env var or http://localhost:7860).

    Returns:
        Dict with 'status' and 'server_url'.
    """
    old_client = _client_var.get()
    if old_client is not None:
        with contextlib.suppress(Exception):
            await old_client.close()
    client = LangflowClient(server_url=server_url)
    _set_client(client)
    _registry_var.set(None)
    await client.login(username, password)
    return {"status": "authenticated", "server_url": client.server_url}


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_flow(name: str = "Untitled Flow", description: str = "") -> dict[str, Any]:
    """Create a new empty flow on the Langflow server.

    Args:
        name: Flow name.
        description: Flow description.

    Returns:
        Dict with 'id', 'name', and 'description' of the created flow.
    """
    flow = empty_flow(name=name, description=description)
    result = await _get_client().post("/flows/", json_data=flow)
    return {"id": result["id"], "name": result["name"], "description": result.get("description", "")}


@mcp.tool()
async def list_flows() -> list[dict[str, Any]]:
    """List all flows on the Langflow server.

    Returns:
        List of dicts with 'id', 'name', 'description', and component counts.
    """
    flows = await _get_client().get("/flows/")
    results = []
    for f in flows:
        data = f.get("data", {})
        results.append(
            {
                "id": f["id"],
                "name": f.get("name", ""),
                "description": f.get("description", ""),
                "node_count": len(data.get("nodes", [])),
                "edge_count": len(data.get("edges", [])),
            }
        )
    return results


@mcp.tool()
async def get_flow_info(flow_id: str) -> dict[str, Any]:
    """Get summary information about a flow.

    Args:
        flow_id: The flow UUID.

    Returns:
        Dict with name, description, component list, input/output nodes, and counts.
    """
    flow = await _get_flow(flow_id)
    info = fb_flow_info(flow)
    info["id"] = flow_id
    return info


@mcp.tool()
async def delete_flow(flow_id: str) -> dict[str, str]:
    """Delete a flow from the server.

    Args:
        flow_id: The flow UUID to delete.

    Returns:
        Confirmation dict.
    """
    await _get_client().delete(f"/flows/{flow_id}")
    return {"deleted": flow_id}


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


@mcp.tool()
async def add_component(flow_id: str, component_type: str) -> dict[str, Any]:
    """Add a component to a flow.

    Fetches the flow, adds the component with proper template from the registry,
    applies layout, and saves back.

    Args:
        flow_id: The flow UUID.
        component_type: Component type name (e.g. "ChatInput", "OpenAIModel").

    Returns:
        Dict with 'id' and 'display_name' of the added component.
    """
    flow = await _get_flow(flow_id)
    registry = await _get_registry()
    result = fb_add_component(flow, component_type, registry)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    return result


@mcp.tool()
async def remove_component(flow_id: str, component_id: str) -> dict[str, str]:
    """Remove a component and its connections from a flow.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID to remove (e.g. "ChatInput-a1B2c").

    Returns:
        Confirmation dict.
    """
    flow = await _get_flow(flow_id)
    fb_remove_component(flow, component_id)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    return {"removed": component_id}


@mcp.tool()
async def configure_component(
    flow_id: str,
    component_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Configure a component's parameters.

    Automatically handles dynamic fields (real_time_refresh, tool_mode) by
    calling the server's /custom_component/update endpoint when needed.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID.
        params: Dict of parameter names to values (e.g. {"model_name": "gpt-4o", "temperature": 0.5}).

    Returns:
        Dict with component_id and configured params.
    """
    client = _get_client()
    flow = await _get_flow(flow_id)

    # Find the node to check for dynamic fields
    node = None
    for n in flow.get("data", {}).get("nodes", []):
        nid = n.get("data", {}).get("id", n.get("id", ""))
        if nid == component_id:
            node = n
            break

    if node is None:
        msg = f"Component not found: {component_id}"
        raise ValueError(msg)

    template = node["data"].get("node", {}).get("template", {})

    # Separate dynamic fields from static ones
    static_params = {}
    for key, value in params.items():
        if needs_server_update(template, key):
            # Handle tool_mode specially
            if key == "tool_mode":
                enabled = value in (True, "true", "True", "1", 1)
                code = template.get("code", {}).get("value", "")
                updated = await client.post(
                    "/custom_component/update",
                    json_data={
                        "code": code,
                        "template": template,
                        "field": "tool_mode",
                        "field_value": enabled,
                        "tool_mode": enabled,
                    },
                )
                if not isinstance(updated, dict) or "template" not in updated:
                    msg = f"Server returned invalid response for tool_mode update on '{component_id}'"
                    raise RuntimeError(msg)
                node["data"]["node"] = updated
                template = updated["template"]
            else:
                # Set value in template before sending
                if key in template and isinstance(template[key], dict):
                    template[key]["value"] = value
                else:
                    template[key] = {"value": value}
                code = template.get("code", {}).get("value", "")
                tool_mode = node["data"]["node"].get("tool_mode", False)
                updated = await client.post(
                    "/custom_component/update",
                    json_data={
                        "code": code,
                        "template": template,
                        "field": key,
                        "field_value": value,
                        "tool_mode": tool_mode,
                    },
                )
                if not isinstance(updated, dict) or "template" not in updated:
                    msg = f"Server returned invalid response for '{key}' update on '{component_id}'"
                    raise RuntimeError(msg)
                node["data"]["node"] = updated
                template = updated["template"]
        else:
            static_params[key] = value

    # Apply static params
    if static_params:
        fb_configure(flow, component_id, static_params)

    await _patch_flow(flow_id, flow)
    return {"component_id": component_id, "configured": list(params.keys())}


@mcp.tool()
async def list_components(flow_id: str) -> list[dict[str, Any]]:
    """List all components in a flow.

    Args:
        flow_id: The flow UUID.

    Returns:
        List of dicts with 'id', 'display_name', and 'type' for each component.
    """
    flow = await _get_flow(flow_id)
    return fb_list_components(flow)


@mcp.tool()
async def get_component_info(
    flow_id: str,
    component_id: str,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Get details about a specific component in a flow.

    Sensitive fields (API keys, passwords) are redacted in the response.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID.
        field_name: Optional field name to return only that field's value and metadata.

    Returns:
        When field_name is None: dict with id, display_name, type, params, and outputs.
        When field_name is given: dict with component_id, field_name, value, and field metadata.
    """
    flow = await _get_flow(flow_id)
    info = fb_get_component(flow, component_id)

    # Redact sensitive params (checks field name against SENSITIVE_KEYWORDS)
    from lfx.mcp.redact import is_sensitive_field

    for key in list(info.get("params", {}).keys()):
        if is_sensitive_field(key) and info["params"][key]:
            info["params"][key] = "***REDACTED***"

    if field_name is None:
        return info

    # Return just the requested field
    if field_name not in info.get("params", {}):
        available = list(info.get("params", {}).keys())
        msg = f"Field '{field_name}' not found on component '{component_id}'. Available: {available}"
        raise ValueError(msg)

    # Get the raw field metadata from the node template
    node = None
    for n in flow.get("data", {}).get("nodes", []):
        nid = n.get("data", {}).get("id", n.get("id", ""))
        if nid == component_id:
            node = n
            break

    field_meta = {}
    if node is not None:
        template = node["data"].get("node", {}).get("template", {})
        raw_field = template.get(field_name, {})
        if isinstance(raw_field, dict):
            field_meta = {
                "type": raw_field.get("type", ""),
                "display_name": raw_field.get("display_name", field_name),
                "required": raw_field.get("required", False),
                "real_time_refresh": raw_field.get("real_time_refresh", False),
            }

    return {
        "component_id": component_id,
        "field_name": field_name,
        "value": info["params"][field_name],
        **field_meta,
    }


@mcp.tool()
async def search_component_types(query: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Search available component types.

    Args:
        query: Search term to filter by name or category (case-insensitive).
        category: Filter by category name (case-insensitive).

    Returns:
        List of matching component types with type, category, display_name, description.
    """
    registry = await _get_registry()
    return search_registry(registry, query=query, category=category)


@mcp.tool()
async def describe_component_type(component_type: str) -> dict[str, Any]:
    """Describe a component type's inputs, outputs, and configuration.

    Args:
        component_type: The component type name (e.g. "ChatInput", "OpenAIModel").

    Returns:
        Dict with type, category, display_name, description, inputs, and outputs.
    """
    registry = await _get_registry()
    return reg_describe(registry, component_type)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@mcp.tool()
async def connect_components(
    flow_id: str,
    source_id: str,
    source_output: str,
    target_id: str,
    target_input: str,
) -> dict[str, Any]:
    """Connect two components in a flow.

    Creates an edge from source_output to target_input with proper
    ReactFlow handle format.

    Args:
        flow_id: The flow UUID.
        source_id: Source component ID.
        source_output: Source output name (e.g. "message", "text_output").
        target_id: Target component ID.
        target_input: Target input name (e.g. "input_value").

    Returns:
        Dict with connection details.
    """
    flow = await _get_flow(flow_id)

    # Auto-enable tool_mode when connecting via component_as_tool
    if source_output == "component_as_tool":
        await configure_component(flow_id, source_id, {"tool_mode": True})
        # Re-fetch flow after tool_mode update changed the template
        flow = await _get_flow(flow_id)

    fb_add_connection(flow, source_id, source_output, target_id, target_input)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    return {
        "source_id": source_id,
        "source_output": source_output,
        "target_id": target_id,
        "target_input": target_input,
    }


@mcp.tool()
async def disconnect_components(
    flow_id: str,
    source_id: str,
    target_id: str,
    source_output: str | None = None,
    target_input: str | None = None,
) -> dict[str, Any]:
    """Remove connections between two components.

    Args:
        flow_id: The flow UUID.
        source_id: Source component ID.
        target_id: Target component ID.
        source_output: Optional filter by source output name.
        target_input: Optional filter by target input name.

    Returns:
        Dict with count of removed connections.
    """
    flow = await _get_flow(flow_id)
    removed = fb_remove_connection(flow, source_id, target_id, source_output, target_input)
    if removed == 0:
        msg = f"No connections found between '{source_id}' and '{target_id}'"
        raise ValueError(msg)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    return {"removed_count": removed}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_flow(
    flow_id: str,
    input_value: str = "",
    input_type: str = "chat",
    output_type: str = "chat",
    tweaks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a flow and return results.

    Args:
        flow_id: The flow UUID.
        input_value: Input text to send to the flow.
        input_type: Input type (default: "chat").
        output_type: Output type (default: "chat").
        tweaks: Optional dict of component tweaks {component_id: {param: value}}.

    Returns:
        Flow execution results.
    """
    request = {
        "input_value": input_value,
        "input_type": input_type,
        "output_type": output_type,
        "tweaks": tweaks or {},
    }
    return await _get_client().post(f"/run/{flow_id}", json_data=request, timeout=300.0)
