"""FastMCP server exposing Langflow operations as MCP tools.

Connects to a running Langflow server via REST API. Flow data is never
cached — every mutating tool does GET -> modify -> PATCH. The component
registry is cached on first access.

Tools are organized into groups: auth, flow, component, connection, execution, batch.
"""

from __future__ import annotations

import contextlib
import contextvars
import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from mcp.server.fastmcp import Context, FastMCP

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
    parse_flow_spec,
)
from lfx.graph.flow_builder import (
    flow_graph_repr as fb_graph_repr,
)
from lfx.graph.flow_builder import (
    flow_info as fb_flow_info,
)
from lfx.graph.flow_builder import (
    flow_to_spec_summary as fb_spec_summary,
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
from lfx.graph.flow_builder.spec import validate_spec_references
from lfx.log.logger import logger
from lfx.mcp.client import LangflowClient
from lfx.mcp.registry import (
    describe_component as reg_describe,
)
from lfx.mcp.registry import (
    load_registry,
    search_registry,
)
from lfx.services.telemetry import MCPToolPayload, TelemetryService

# Session state. Module-level singletons for stdio (single agent), with
# contextvars overlay for SSE (multiple concurrent agents).
_client_var: contextvars.ContextVar[LangflowClient | None] = contextvars.ContextVar("_client", default=None)
_registry_var: contextvars.ContextVar[dict[str, dict] | None] = contextvars.ContextVar("_registry", default=None)
_shared_client: LangflowClient | None = None
_shared_registry: dict[str, dict] | None = None
_telemetry: TelemetryService | None = None


@asynccontextmanager
async def _telemetry_lifespan(_server: FastMCP) -> AsyncIterator[dict]:
    """Start/stop the telemetry service with the MCP server lifecycle."""
    global _telemetry  # noqa: PLW0603
    svc = TelemetryService()
    svc.start()
    _telemetry = svc
    try:
        yield {}
    finally:
        await svc.stop()
        _telemetry = None


mcp = FastMCP(
    "langflow-mcp",
    instructions=(
        "Langflow MCP server -- build and run AI flows on a Langflow instance.\n"
        "\n"
        "Typical workflow:\n"
        "  1. login (or set LANGFLOW_API_KEY env var)\n"
        "  2. search_component_types / describe_component_type to discover components\n"
        "  3. create_flow_from_spec to define nodes, edges, and config in one text spec\n"
        "     (or step-by-step: create_flow, add_component, configure_component, connect_components)\n"
        "  4. run_flow to execute\n"
        "\n"
        "Key concepts:\n"
        "- describe_component_type shows a type's inputs, outputs, fields, and advanced_fields\n"
        "- Connections are type-safe: an output's types must overlap with the input's input_types\n"
        "- Outputs named 'component_as_tool' turn any component into a Tool for an Agent\n"
        "- search_component_types with no args returns all available types\n"
        "- Use batch to send multiple actions in one call with $N.field references"
    ),
    lifespan=_telemetry_lifespan,
)


def _get_client() -> LangflowClient:
    # Try contextvar first (SSE sessions), fall back to shared (stdio)
    client = _client_var.get()
    if client is not None:
        return client
    global _shared_client  # noqa: PLW0603
    if _shared_client is None:
        _shared_client = LangflowClient()
    return _shared_client


def _set_client(client: LangflowClient) -> None:
    global _shared_client  # noqa: PLW0603
    _client_var.set(client)
    _shared_client = client


async def _get_registry() -> dict[str, dict]:
    registry = _registry_var.get()
    if registry is not None:
        return registry
    global _shared_registry  # noqa: PLW0603
    if _shared_registry is not None:
        return _shared_registry
    _shared_registry = await load_registry(_get_client())
    _registry_var.set(_shared_registry)
    return _shared_registry


def _get_telemetry() -> TelemetryService | None:
    return _telemetry


def _tracked(fn):
    """Decorator that sends an MCPToolPayload after each tool call."""
    import functools
    import time

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        t0 = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            with contextlib.suppress(BaseException):
                svc = _get_telemetry()
                if svc is not None:
                    await svc.log_mcp_tool(
                        MCPToolPayload(
                            tool=fn.__name__,
                            success=False,
                            ms=int((time.monotonic() - t0) * 1000),
                            error=type(exc).__name__,
                        )
                    )
            raise
        with contextlib.suppress(BaseException):
            svc = _get_telemetry()
            if svc is not None:
                await svc.log_mcp_tool(
                    MCPToolPayload(tool=fn.__name__, success=True, ms=int((time.monotonic() - t0) * 1000))
                )
        return result

    return wrapper


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
@_tracked
async def login(username: str, password: str, server_url: str | None = None) -> dict[str, str]:
    """Authenticate with a Langflow server. Call this first.

    Credentials are stored and reused for all subsequent calls.

    Args:
        username: Langflow username.
        password: Langflow password.
        server_url: Server URL (defaults to LANGFLOW_SERVER_URL env var or http://localhost:7860).
    """
    old_client = _client_var.get() or _shared_client
    if old_client is not None:
        await old_client.close()
    client = LangflowClient(server_url=server_url)
    _set_client(client)
    _registry_var.set(None)
    global _shared_registry  # noqa: PLW0603
    _shared_registry = None
    await client.login(username, password)
    return {"status": "authenticated", "server_url": client.server_url}


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


@mcp.tool()
@_tracked
async def create_flow(name: str = "Untitled Flow", description: str = "") -> dict[str, Any]:
    """Create a new empty flow. Returns the flow's id, name, and description.

    Args:
        name: Flow name.
        description: Flow description.
    """
    flow = empty_flow(name=name, description=description)
    result = await _get_client().post("/flows/", json_data=flow)
    return {"id": result["id"], "name": result["name"], "description": result.get("description", "")}


_TEMPLATE_VAR_RE = re.compile(r"\{(\w+)\}")

PROMPT_TYPES = {"Prompt Template", "Prompt"}


async def _create_prompt_template_vars(flow_id: str, parsed: dict, id_map: dict[str, str]) -> None:
    """Create dynamic input fields for Prompt template variables.

    When a Prompt Template's template contains {variable_name} placeholders,
    the UI creates input fields for them. This function does the same so that
    edges can connect to those fields.
    """
    # Find Prompt nodes that have template config
    node_types = {n["id"]: n["type"] for n in parsed["nodes"]}
    prompt_nodes = {sid for sid, ntype in node_types.items() if ntype in PROMPT_TYPES}
    if not prompt_nodes:
        return

    flow = await _get_flow(flow_id)
    changed = False

    for spec_id in prompt_nodes:
        real_id = id_map.get(spec_id)
        if real_id is None:
            continue

        # Find the node in the flow
        node = None
        for n in flow.get("data", {}).get("nodes", []):
            if n.get("data", {}).get("id") == real_id:
                node = n
                break
        if node is None:
            continue

        template = node["data"].get("node", {}).get("template", {})
        template_value = ""
        if isinstance(template.get("template"), dict):
            template_value = template["template"].get("value", "")

        if not template_value:
            continue

        # Parse {variable_name} placeholders
        variables = _TEMPLATE_VAR_RE.findall(template_value)
        for var_name in variables:
            if var_name in template:
                continue  # already exists
            template[var_name] = {
                "_input_type": "MessageInput",
                "advanced": False,
                "display_name": var_name,
                "dynamic": False,
                "info": "",
                "input_types": ["Message"],
                "list": False,
                "load_from_db": False,
                "name": var_name,
                "placeholder": "",
                "required": False,
                "show": True,
                "title_case": False,
                "tool_mode": False,
                "trace_as_metadata": True,
                "type": "str",
                "value": "",
            }
            changed = True

        # Update custom_fields to track template variables
        custom_fields = node["data"]["node"].setdefault("custom_fields", {})
        custom_fields["template"] = variables

    if changed:
        await _patch_flow(flow_id, flow)


@mcp.tool()
@_tracked
async def create_flow_from_spec(spec: str, *, validate: bool = True) -> dict[str, Any]:
    """Create a complete flow from a compact text spec. Best for building full flows.

    Format:
        name: My Chatbot
        description: A simple chatbot

        nodes:
          A: ChatInput
          B: OpenAIModel
          C: ChatOutput

        edges:
          A.message -> B.input_value
          B.text_output -> C.input_value

        config:
          B.model_name: gpt-4o
          B.temperature: 0.5

    Use describe_component_type to find output/input names for edges.
    Connecting via component_as_tool auto-enables tool mode.
    Multi-line config values use YAML-style "|" continuation.

    Args:
        spec: The flow spec as a text string.
        validate: Build the flow's graph to validate components and connections (default: True).
    """
    parsed = parse_flow_spec(spec)

    # Validate references before creating anything
    validate_spec_references(parsed)

    # Create flow
    created = await create_flow(
        name=parsed.get("name", "Untitled Flow"),
        description=parsed.get("description", ""),
    )
    flow_id = created["id"]

    try:
        # Add all components
        id_map: dict[str, str] = {}
        for node in parsed["nodes"]:
            result = await add_component(flow_id, node["type"])
            id_map[node["id"]] = result["id"]

        # Apply config via configure_component (handles dynamic fields automatically)
        for spec_id, params in parsed.get("config", {}).items():
            await configure_component(flow_id, id_map[spec_id], params)

        # Create dynamic template variable fields on Prompt components.
        # When a Prompt template contains {var_name}, the UI creates an input
        # field for it. We do the same here so edges can connect to them.
        await _create_prompt_template_vars(flow_id, parsed, id_map)

        # Connect edges via connect_components (handles tool_mode automatically)
        for edge in parsed["edges"]:
            await connect_components(
                flow_id,
                id_map[edge["source_id"]],
                edge["source_output"],
                id_map[edge["target_id"]],
                edge["target_input"],
            )
        # Validate by building the graph server-side
        if validate:
            await build_flow(flow_id)
    except Exception:
        # Signal settle so the UI banner doesn't hang
        with contextlib.suppress(Exception):
            await _get_client().post_event(flow_id, "flow_settled", "Failed, rolling back")
        # Clean up the partially-built flow (best-effort)
        with contextlib.suppress(Exception):
            await delete_flow(flow_id)
        raise

    # Signal that the batch creation is complete
    await _get_client().post_event(flow_id, "flow_settled", "Created flow from spec")

    # Return flow info
    info = await get_flow_info(flow_id)
    info["node_id_map"] = id_map
    return info


@mcp.tool()
@_tracked
async def list_flows(query: str | None = None) -> list[dict[str, Any]]:
    """List flows on the server. Each result includes an ASCII graph diagram.

    Args:
        query: Optional filter by name (case-insensitive).
    """
    flows = await _get_client().get("/flows/")
    results = []
    for f in flows:
        name = f.get("name", "")
        if query and query.lower() not in name.lower():
            continue
        data = f.get("data", {})
        results.append(
            {
                "id": f["id"],
                "name": name,
                "description": f.get("description", ""),
                "graph": fb_graph_repr(f),
                "spec_summary": fb_spec_summary(f),
                "node_count": len(data.get("nodes", [])),
                "edge_count": len(data.get("edges", [])),
            }
        )
    return results


@mcp.tool()
@_tracked
async def get_flow_info(flow_id: str) -> dict[str, Any]:
    """Get detailed info about a flow: components, connections, ASCII graph diagram.

    Args:
        flow_id: The flow UUID.
    """
    flow = await _get_flow(flow_id)
    info = fb_flow_info(flow)
    info["id"] = flow_id
    info["graph"] = fb_graph_repr(flow)
    info["spec_summary"] = fb_spec_summary(flow)
    return info


@mcp.tool()
@_tracked
async def delete_flow(flow_id: str) -> dict[str, str]:
    """Delete a flow from the server.

    Args:
        flow_id: The flow UUID to delete.
    """
    await _get_client().delete(f"/flows/{flow_id}")
    return {"deleted": flow_id}


@mcp.tool()
@_tracked
async def duplicate_flow(flow_id: str, new_name: str | None = None) -> dict[str, Any]:
    """Create a copy of an existing flow.

    Args:
        flow_id: The UUID of the flow to duplicate.
        new_name: Name for the copy (defaults to original name + " (copy)").
    """
    flow = await _get_flow(flow_id)
    name = new_name or f"{flow.get('name', 'Untitled')} (copy)"
    copy_data = {
        "name": name,
        "description": flow.get("description", ""),
        "data": flow.get("data", {}),
    }
    result = await _get_client().post("/flows/", json_data=copy_data)
    return {"id": result["id"], "name": result["name"], "description": result.get("description", "")}


@mcp.tool()
@_tracked
async def list_starter_projects() -> list[dict[str, Any]]:
    """List pre-built example flows. Use use_starter_project to create one."""
    flows = await _get_client().get("/flows/basic_examples/")
    return [
        {
            "name": f.get("name", ""),
            "description": f.get("description", ""),
            "graph": fb_graph_repr(f),
        }
        for f in flows
    ]


@mcp.tool()
@_tracked
async def use_starter_project(starter_name: str, new_name: str | None = None) -> dict[str, Any]:
    """Create a new flow from a starter project template.

    Args:
        starter_name: Exact name from list_starter_projects (case-insensitive).
        new_name: Name for the new flow (defaults to starter name).
    """
    flows = await _get_client().get("/flows/basic_examples/")
    starter = None
    for f in flows:
        if f.get("name", "").lower() == starter_name.lower():
            starter = f
            break
    if starter is None:
        available = [f.get("name", "") for f in flows]
        msg = f"Starter project '{starter_name}' not found. Available: {available}"
        raise ValueError(msg)

    name = new_name or starter.get("name", "Untitled")
    copy_data = {
        "name": name,
        "description": starter.get("description", ""),
        "data": starter.get("data", {}),
    }
    result = await _get_client().post("/flows/", json_data=copy_data)
    return {"id": result["id"], "name": result["name"], "description": result.get("description", "")}


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


@mcp.tool()
@_tracked
async def add_component(flow_id: str, component_type: str) -> dict[str, Any]:
    """Add a component to a flow. Returns the component's id and display_name.

    Use search_component_types or describe_component_type to discover types.

    Args:
        flow_id: The flow UUID.
        component_type: Component type name (e.g. "ChatInput", "OpenAIModel").
    """
    flow = await _get_flow(flow_id)
    registry = await _get_registry()
    result = fb_add_component(flow, component_type, registry)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    await _get_client().post_event(flow_id, "component_added", f"Added {component_type}")
    return result


@mcp.tool()
@_tracked
async def remove_component(flow_id: str, component_id: str) -> dict[str, str]:
    """Remove a component and all its connections from a flow.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID (e.g. "ChatInput-a1B2c").
    """
    flow = await _get_flow(flow_id)
    fb_remove_component(flow, component_id)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    await _get_client().post_event(flow_id, "component_removed", f"Removed {component_id}")
    return {"removed": component_id}


@mcp.tool()
@_tracked
async def configure_component(
    flow_id: str,
    component_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Set parameter values on a component.

    Use get_component_info to check current values, or describe_component_type
    to see available fields. Some fields trigger server-side template updates
    (e.g. changing model_name may update available options) -- the response
    reflects the final state, no need to re-fetch.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID.
        params: Dict of parameter names to values (e.g. {"model_name": "gpt-4o", "temperature": 0.5}).
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
    warnings = []
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
                try:
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
                except RuntimeError:
                    # Server refresh failed (e.g. missing API key for model list).
                    # The value is already set in the template above, so save it
                    # locally and warn the agent.
                    warnings.append(
                        f"Field '{key}' was set to '{value}' but the server-side "
                        f"refresh failed. This usually means a required credential "
                        f"(like an API key) is not configured on the component yet. "
                        f"Set the credential first, then reconfigure '{key}'."
                    )
                    continue
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
    await _get_client().post_event(flow_id, "component_configured", f"Configured {component_id}")
    result: dict[str, Any] = {"component_id": component_id, "configured": list(params.keys())}
    if warnings:
        result["warnings"] = warnings
    return result


@mcp.tool()
@_tracked
async def list_components(flow_id: str) -> list[dict[str, Any]]:
    """List all components in a flow with their IDs, names, and types.

    Args:
        flow_id: The flow UUID.
    """
    flow = await _get_flow(flow_id)
    return fb_list_components(flow)


@mcp.tool()
@_tracked
async def get_component_info(
    flow_id: str,
    component_id: str,
    field_name: str | None = None,
) -> dict[str, Any]:
    """Get a specific component instance's current parameter values and outputs.

    Unlike describe_component_type (which shows the type definition),
    this returns the actual values set on a component in a flow.
    Sensitive fields (API keys, passwords) are redacted.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID.
        field_name: Optional -- narrow the response to a single field.
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
@_tracked
async def search_component_types(
    query: str | None = None,
    category: str | None = None,
    output_type: str | None = None,
) -> list[dict[str, Any]]:
    """Find component types by name, category, or output type. Call with no args to list all.

    Args:
        query: Search term to filter by name or category (case-insensitive).
        category: Filter by category name, case-insensitive (e.g. "models", "inputs", "outputs").
        output_type: Filter by what the component produces (e.g. "LanguageModel", "Message", "Tool").
    """
    registry = await _get_registry()
    return search_registry(registry, query=query, category=category, output_type=output_type)


@mcp.tool()
@_tracked
async def describe_component_type(component_type: str) -> dict[str, Any]:
    """Get a component type's definition: inputs (connectable), outputs, fields, and advanced_fields.

    Use this to learn what a component accepts before adding it to a flow.
    Inputs show input_types -- connect outputs whose types overlap.
    Outputs named 'component_as_tool' turn any component into a Tool for Agents.

    Args:
        component_type: The component type name (e.g. "ChatInput", "OpenAIModel").
    """
    registry = await _get_registry()
    return reg_describe(registry, component_type)


@mcp.tool()
@_tracked
async def components(
    query: str | None = None,
    component_type: str | None = None,
    category: str | None = None,
    output_type: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Search or describe component types in one call.

    With component_type: returns full description (inputs, outputs, fields).
    Without component_type: searches/lists component types.
    No args: lists all available types.

    Args:
        query: Search term to filter by name or category.
        component_type: If given, describe this specific type instead of searching.
        category: Filter by category (e.g. "models", "inputs").
        output_type: Filter by output type (e.g. "LanguageModel", "Message").
    """
    registry = await _get_registry()
    if component_type:
        return reg_describe(registry, component_type)
    return search_registry(registry, query=query, category=category, output_type=output_type)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@mcp.tool()
@_tracked
async def connect_components(
    flow_id: str,
    source_id: str,
    source_output: str,
    target_id: str,
    target_input: str,
) -> dict[str, Any]:
    """Connect an output of one component to an input of another.

    Use describe_component_type to see available outputs and inputs.
    Connecting via 'component_as_tool' automatically enables tool mode.

    Args:
        flow_id: The flow UUID.
        source_id: Source component ID.
        source_output: Output name on the source (e.g. "message", "text_output", "component_as_tool").
        target_id: Target component ID.
        target_input: Input name on the target (e.g. "input_value", "tools").
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
    await _get_client().post_event(flow_id, "connection_added", f"Connected {source_id} to {target_id}")
    return {
        "source_id": source_id,
        "source_output": source_output,
        "target_id": target_id,
        "target_input": target_input,
    }


@mcp.tool()
@_tracked
async def disconnect_components(
    flow_id: str,
    source_id: str,
    target_id: str,
    source_output: str | None = None,
    target_input: str | None = None,
) -> dict[str, Any]:
    """Remove connections between two components.

    Omit source_output and target_input to remove all connections between them.

    Args:
        flow_id: The flow UUID.
        source_id: Source component ID.
        target_id: Target component ID.
        source_output: Only remove connections from this specific output.
        target_input: Only remove connections to this specific input.
    """
    flow = await _get_flow(flow_id)
    removed = fb_remove_connection(flow, source_id, target_id, source_output, target_input)
    if removed == 0:
        msg = f"No connections found between '{source_id}' and '{target_id}'"
        raise ValueError(msg)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    await _get_client().post_event(flow_id, "connection_removed", f"Disconnected {source_id} from {target_id}")
    return {"removed_count": removed}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@mcp.tool()
@_tracked
async def run_flow(
    flow_id: str,
    input_value: str = "",
    input_type: str = "chat",
    output_type: str = "chat",
    tweaks: dict[str, Any] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run a flow and return the output.

    Streams progress events (tokens, messages) when the client supports it.

    Args:
        flow_id: The flow UUID.
        input_value: Text to send to the flow's input component.
        input_type: Input type (default: "chat").
        output_type: Output type (default: "chat").
        tweaks: Override component params at runtime: {component_id: {param: value}}.
        ctx: MCP context for progress reporting (injected automatically).
    """
    request = {
        "input_value": input_value,
        "input_type": input_type,
        "output_type": output_type,
        "tweaks": tweaks or {},
    }
    client = _get_client()

    result: dict[str, Any] = {}
    token_count = 0
    async for event in client.stream_post(f"/run/{flow_id}?stream=true", json_data=request):
        event_type = event.get("event", "")
        data = event.get("data", {})

        if event_type == "token" and ctx is not None:
            token_count += 1
            chunk = data.get("chunk", "")
            await ctx.report_progress(token_count, message=chunk)

        elif event_type == "end":
            result = data.get("result", data)
            break

        elif event_type == "error":
            msg = data.get("error", "Flow execution failed")
            raise RuntimeError(msg)

    if not result:
        logger.warning("Streaming produced no result for flow %s, falling back to synchronous execution", flow_id)
        return await client.post(f"/run/{flow_id}", json_data=request, timeout=300.0)
    return result


@mcp.tool()
@_tracked
async def build_flow(flow_id: str) -> dict[str, Any]:
    """Trigger a server-side build that validates components and connections.

    Returns a job_id for the build. Use after creating or modifying a flow
    to catch errors early.

    Args:
        flow_id: The flow UUID.
    """
    result = await _get_client().post(f"/build/{flow_id}/flow")
    return {"flow_id": flow_id, "job_id": result.get("job_id", "")}


@mcp.tool()
@_tracked
async def get_build_results(flow_id: str) -> dict[str, Any]:
    """Get per-component build results from the last run of a flow.

    Returns each component's output data, validity status, and any errors.
    Use this to debug which component failed or inspect intermediate outputs.

    Args:
        flow_id: The flow UUID.
    """
    data = await _get_client().get(f"/monitor/builds?flow_id={flow_id}")
    builds = data.get("vertex_builds", {})

    # Flatten to a more agent-friendly format
    summary: dict[str, Any] = {}
    for comp_id, build_list in builds.items():
        if not build_list:
            continue
        latest = build_list[-1]  # most recent build
        entry: dict[str, Any] = {
            "valid": latest.get("valid", False),
            "timestamp": latest.get("timestamp", ""),
        }
        # Include output data if present
        build_data = latest.get("data", {})
        if build_data:
            # Extract the result outputs
            results = build_data.get("results", {})
            for output_name, output_val in results.items():
                if isinstance(output_val, dict) and "text" in output_val:
                    entry[f"output_{output_name}"] = output_val["text"]
                elif isinstance(output_val, str):
                    entry[f"output_{output_name}"] = output_val
        # Include error info from artifacts if build failed
        artifacts = latest.get("artifacts", {})
        if not latest.get("valid") and artifacts:
            entry["error"] = str(artifacts)
        summary[comp_id] = entry

    return {"flow_id": flow_id, "builds": summary}


@mcp.tool()
@_tracked
async def get_component_output(
    flow_id: str,
    component_id: str,
) -> dict[str, Any]:
    """Get a specific component's output from the last run.

    Use this to inspect what a component produced -- useful for debugging
    when the final output is wrong and you need to find which step broke.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID to inspect.
    """
    data = await _get_client().get(f"/monitor/builds?flow_id={flow_id}")
    builds = data.get("vertex_builds", {})

    if component_id not in builds or not builds[component_id]:
        available = list(builds.keys())
        return {
            "error": f"No build data for '{component_id}'",
            "available_components": available,
        }

    latest = builds[component_id][-1]
    result: dict[str, Any] = {
        "component_id": component_id,
        "valid": latest.get("valid", False),
        "timestamp": latest.get("timestamp", ""),
    }

    build_data = latest.get("data", {})
    if build_data:
        result["outputs"] = build_data.get("results", {})

    artifacts = latest.get("artifacts", {})
    if artifacts:
        result["artifacts"] = artifacts

    if not latest.get("valid"):
        result["error"] = "Component build failed"

    return result


# ---------------------------------------------------------------------------
# Flow management
# ---------------------------------------------------------------------------


@mcp.tool()
@_tracked
async def validate_flow(flow_id: str) -> dict[str, Any]:
    """Validate a flow and return structured per-component results.

    Unlike build_flow (which returns a job_id), this waits for the build
    to complete and returns a clear pass/fail with specific errors.
    Use this before run_flow to catch issues early.

    Args:
        flow_id: The flow UUID.
    """
    import asyncio

    # Get expected component count
    flow = await _get_flow(flow_id)
    expected = len(flow.get("data", {}).get("nodes", []))
    if expected == 0:
        return {"valid": True, "component_count": 0, "errors": [], "warnings": []}

    # Trigger a build
    build_result = await _get_client().post(f"/build/{flow_id}/flow")
    job_id = build_result.get("job_id", "")
    if not job_id:
        return {"valid": False, "error": "Build did not return a job_id"}

    # Poll until build completes or timeout
    builds: dict[str, Any] = {}
    for _ in range(30):
        await asyncio.sleep(1.0)
        data = await _get_client().get(f"/monitor/builds?flow_id={flow_id}")
        builds = data.get("vertex_builds", {})
        if len(builds) >= expected:
            break
    else:
        return {
            "valid": False,
            "error": f"Build timed out: {len(builds)}/{expected} components completed",
        }

    errors = []
    for comp_id, build_list in builds.items():
        if not build_list:
            continue
        latest = build_list[-1]
        if not latest.get("valid", False):
            artifacts = latest.get("artifacts", {})
            error_msg = artifacts.get("error", str(artifacts)) if isinstance(artifacts, dict) else str(artifacts)
            errors.append({"component_id": comp_id, "error": error_msg or "Unknown error"})

    return {
        "valid": len(errors) == 0,
        "component_count": len(builds),
        "errors": errors,
    }


@mcp.tool()
@_tracked
async def rename_flow(
    flow_id: str,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update a flow's name and/or description.

    Args:
        flow_id: The flow UUID.
        name: New name (omit to keep current).
        description: New description (omit to keep current).
    """
    update: dict[str, Any] = {}
    if name is not None:
        update["name"] = name
    if description is not None:
        update["description"] = description
    if not update:
        msg = "Provide at least name or description"
        raise ValueError(msg)

    result = await _get_client().patch(f"/flows/{flow_id}", json_data=update)
    return {"id": flow_id, "name": result.get("name", ""), "description": result.get("description", "")}


@mcp.tool()
@_tracked
async def export_flow(flow_id: str) -> dict[str, Any]:
    """Export a flow as a complete JSON object for backup or sharing.

    Returns the full flow data with sensitive fields (API keys, passwords) redacted.

    Args:
        flow_id: The flow UUID.
    """
    from lfx.mcp.redact import redact_node

    flow = await _get_flow(flow_id)
    data = flow.get("data", {})
    # Redact sensitive fields before exposing to LLM context
    if "nodes" in data:
        data = {
            **data,
            "nodes": [{**n, "data": redact_node(n.get("data", {}))} for n in data["nodes"]],
        }
    return {
        "id": flow_id,
        "name": flow.get("name", ""),
        "description": flow.get("description", ""),
        "data": data,
    }


@mcp.tool()
@_tracked
async def update_flow_from_spec(flow_id: str, spec: str) -> dict[str, Any]:
    """Update an existing flow to match a spec, preserving the flow ID.

    Replaces all nodes, edges, and config with what the spec defines.
    Useful for iterating on a flow without creating a new one each time.

    Args:
        flow_id: The flow UUID to update.
        spec: Text spec in the same format as create_flow_from_spec.
    """
    parsed = parse_flow_spec(spec)
    registry = await _get_registry()

    validate_spec_references(parsed)

    # Build new flow data from spec
    flow = empty_flow(
        name=parsed.get("name", "Untitled Flow"),
        description=parsed.get("description", ""),
    )

    id_map: dict[str, str] = {}
    for node in parsed["nodes"]:
        result = fb_add_component(flow, node["type"], registry)
        id_map[node["id"]] = result["id"]

    for spec_id, params in parsed.get("config", {}).items():
        fb_configure(flow, id_map[spec_id], params)

    for edge in parsed["edges"]:
        fb_add_connection(
            flow,
            id_map[edge["source_id"]],
            edge["source_output"],
            id_map[edge["target_id"]],
            edge["target_input"],
        )

    layout_flow(flow)

    # Patch the existing flow with new data
    patch_data: dict[str, Any] = {
        "data": flow["data"],
        "description": parsed.get("description", ""),
    }
    if parsed.get("name"):
        patch_data["name"] = parsed["name"]

    await _get_client().patch(f"/flows/{flow_id}", json_data=patch_data)
    await _get_client().post_event(flow_id, "flow_updated", "Updated flow from spec")

    return {
        "id": flow_id,
        "name": parsed.get("name", ""),
        "node_count": len(flow["data"]["nodes"]),
        "edge_count": len(flow["data"]["edges"]),
        "node_id_map": id_map,
        "spec_summary": fb_spec_summary(flow),
    }


async def _set_frozen(flow_id: str, component_id: str, *, frozen: bool) -> dict[str, str]:
    """Set the frozen state of a component."""
    flow = await _get_flow(flow_id)
    for node in flow.get("data", {}).get("nodes", []):
        nid = node.get("data", {}).get("id", node.get("id", ""))
        if nid == component_id:
            node_config = node.get("data", {}).get("node")
            if node_config is None:
                msg = f"Component '{component_id}' has malformed data (missing 'node' key)"
                raise ValueError(msg)
            node_config["frozen"] = frozen
            await _patch_flow(flow_id, flow)
            key = "frozen" if frozen else "unfrozen"
            return {key: component_id}

    msg = f"Component not found: {component_id}"
    raise ValueError(msg)


@mcp.tool()
@_tracked
async def freeze_component(flow_id: str, component_id: str) -> dict[str, str]:
    """Freeze a component so it uses cached output and skips re-execution.

    Useful when iterating on downstream components without paying the
    cost of re-running expensive upstream LLM calls.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID to freeze.
    """
    result = await _set_frozen(flow_id, component_id, frozen=True)
    await _get_client().post_event(flow_id, "component_configured", f"Froze {component_id}")
    return result


@mcp.tool()
@_tracked
async def unfreeze_component(flow_id: str, component_id: str) -> dict[str, str]:
    """Unfreeze a component so it re-executes on the next run.

    Args:
        flow_id: The flow UUID.
        component_id: The component ID to unfreeze.
    """
    result = await _set_frozen(flow_id, component_id, frozen=False)
    await _get_client().post_event(flow_id, "component_configured", f"Unfroze {component_id}")
    return result


@mcp.tool()
@_tracked
async def layout_flow_tool(flow_id: str) -> dict[str, str]:
    """Re-layout a flow's components using the Sugiyama algorithm.

    Useful after adding or removing components to clean up positioning.

    Args:
        flow_id: The flow UUID.
    """
    flow = await _get_flow(flow_id)
    layout_flow(flow)
    await _patch_flow(flow_id, flow)
    await _get_client().post_event(flow_id, "flow_updated", "Re-laid out flow")
    return {"laid_out": flow_id}


@mcp.tool()
@_tracked
async def notify_done(flow_id: str, summary: str | None = None) -> dict[str, str]:
    """Signal that you are done modifying a flow.

    Call this after completing a series of modifications so the UI updates immediately.
    If you don't call this, the UI will still update after a short timeout.

    Args:
        flow_id: The flow UUID you were modifying.
        summary: Optional human-readable summary of what you did (e.g. "Built a RAG pipeline with OpenAI and Pinecone").
    """
    try:
        await _get_client().post(
            f"/flows/{flow_id}/events",
            json_data={"type": "flow_settled", "summary": summary or ""},
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to post flow_settled event", exc_info=True)
        return {
            "status": "warning",
            "flow_id": flow_id,
            "detail": "Event could not be delivered; UI will update after timeout",
        }
    return {"status": "ok", "flow_id": flow_id}


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

# Tool name -> callable mapping (built lazily)
_TOOL_MAP: dict[str, Any] | None = None


def _get_tool_map() -> dict[str, Any]:
    global _TOOL_MAP  # noqa: PLW0603
    if _TOOL_MAP is None:
        _TOOL_MAP = {
            "login": login,
            "create_flow": create_flow,
            "create_flow_from_spec": create_flow_from_spec,
            "list_flows": list_flows,
            "get_flow_info": get_flow_info,
            "delete_flow": delete_flow,
            "duplicate_flow": duplicate_flow,
            "list_starter_projects": list_starter_projects,
            "use_starter_project": use_starter_project,
            "add_component": add_component,
            "remove_component": remove_component,
            "configure_component": configure_component,
            "list_components": list_components,
            "get_component_info": get_component_info,
            "search_component_types": search_component_types,
            "describe_component_type": describe_component_type,
            "connect_components": connect_components,
            "disconnect_components": disconnect_components,
            "run_flow": run_flow,
            "build_flow": build_flow,
            "validate_flow": validate_flow,
            "rename_flow": rename_flow,
            "export_flow": export_flow,
            "update_flow_from_spec": update_flow_from_spec,
            "get_build_results": get_build_results,
            "get_component_output": get_component_output,
            "components": components,
            "freeze_component": freeze_component,
            "unfreeze_component": unfreeze_component,
            "layout_flow": layout_flow_tool,
            "notify_done": notify_done,
        }
    return _TOOL_MAP


_REF_PATTERN = re.compile(r"^\$(\d+)\.(\w+)$")


def _resolve_refs(value: Any, results: list[Any]) -> Any:
    """Replace $N.field references with actual values from previous results."""
    if isinstance(value, str):
        match = _REF_PATTERN.match(value)
        if match:
            idx, field = int(match.group(1)), match.group(2)
            if idx >= len(results):
                msg = f"Reference ${idx} is out of range (only {len(results)} results so far)"
                raise ValueError(msg)
            result = results[idx]
            if isinstance(result, dict) and field in result:
                return result[field]
            msg = f"${idx}.{field}: field '{field}' not found in result {idx}"
            raise ValueError(msg)
        return value
    if isinstance(value, dict):
        return {k: _resolve_refs(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, results) for v in value]
    return value


@mcp.tool()
@_tracked
async def batch(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Execute multiple actions in sequence, returning all results.

    Use $N.field to reference results from previous actions (zero-indexed).

    Example -- build a complete chatbot in one call:
        [
            {"tool": "create_flow", "args": {"name": "My Chatbot"}},
            {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "ChatInput"}},
            {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "OpenAIModel"}},
            {"tool": "add_component", "args": {"flow_id": "$0.id", "component_type": "ChatOutput"}},
            {"tool": "connect_components", "args": {
                "flow_id": "$0.id", "source_id": "$1.id", "source_output": "message",
                "target_id": "$2.id", "target_input": "input_value"
            }},
            {"tool": "connect_components", "args": {
                "flow_id": "$0.id", "source_id": "$2.id", "source_output": "text_output",
                "target_id": "$3.id", "target_input": "input_value"
            }}
        ]

    Args:
        actions: List of {"tool": "tool_name", "args": {...}} dicts.
    """
    tool_map = _get_tool_map()
    results: list[dict[str, Any]] = []

    for i, action in enumerate(actions):
        tool_name = action.get("tool", "")
        if tool_name not in tool_map:
            available = sorted(tool_map.keys())
            msg = f"Action {i}: unknown tool '{tool_name}'. Available: {available}"
            raise ValueError(msg)

        raw_args = action.get("args", {})
        resolved_args = _resolve_refs(raw_args, results)

        try:
            result = await tool_map[tool_name](**resolved_args)
        except Exception as exc:
            msg = f"Action {i} ('{tool_name}') failed: {exc}"
            raise type(exc)(msg) from exc
        results.append(result if isinstance(result, dict) else {"result": result})

    return results
