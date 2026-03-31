"""Tools for searching components and building flows on the user's canvas.

These components expose flow_builder capabilities as Agent tools.
Each mutating tool pushes a flow_update event to a module-level queue
so the assistant service can send real-time SSE updates to the frontend.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from lfx.custom import Component
from lfx.graph.flow_builder.builder import build_flow_from_spec, load_local_registry
from lfx.graph.flow_builder.component import add_component as fb_add_component
from lfx.graph.flow_builder.component import configure_component as fb_configure
from lfx.graph.flow_builder.component import remove_component as fb_remove_component
from lfx.graph.flow_builder.connect import add_connection as fb_add_connection
from lfx.graph.flow_builder.flow import empty_flow
from lfx.graph.flow_builder.layout import layout_flow
from lfx.io import MessageTextInput, Output
from lfx.log.logger import logger
from lfx.mcp.redact import is_sensitive_field
from lfx.mcp.registry import describe_component, search_registry
from lfx.schema import Data

# ---------------------------------------------------------------------------
# Module-level state for communicating between tool execution and the
# assistant service streaming loop. Tools push events here; the service
# drains them and sends SSE events to the frontend.
# ---------------------------------------------------------------------------

_flow_events: deque[dict[str, Any]] = deque()
_working_flow: dict | None = None
_current_flow_id: str | None = None


def drain_flow_events() -> list[dict[str, Any]]:
    """Return and clear all pending flow update events."""
    events = list(_flow_events)
    _flow_events.clear()
    return events


def get_working_flow() -> dict | None:
    """Return the current working flow (for the assistant service)."""
    return _working_flow


def init_working_flow(flow_data: dict, flow_id: str | None = None) -> None:
    """Initialize working flow from actual canvas data."""
    global _working_flow, _current_flow_id  # noqa: PLW0603
    _working_flow = flow_data
    _current_flow_id = flow_id
    _flow_events.clear()


def reset_working_flow() -> None:
    """Reset the working flow state between requests."""
    global _working_flow, _current_flow_id  # noqa: PLW0603
    _working_flow = None
    _current_flow_id = None
    _flow_events.clear()


def _emit(action: str, **data: Any) -> None:
    """Push a flow_update event."""
    _flow_events.append({"action": action, **data})


def _save_working_flow() -> None:
    """Persist the working flow to the database if we have a flow_id."""
    if _working_flow is None or _current_flow_id is None:
        return
    try:
        import asyncio
        from uuid import UUID

        from lfx.services.deps import session_scope

        async def _save():
            from langflow.services.database.models.flow import Flow

            async with session_scope() as session:
                flow = await session.get(Flow, UUID(_current_flow_id))
                if flow:
                    flow.data = _working_flow.get("data", {})
                    session.add(flow)

        # Run in the existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context -- schedule as a task
            # This is safe because session_scope uses the same DB engine
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _save()).result()
        else:
            loop.run_until_complete(_save())
    except Exception:  # noqa: BLE001
        logger.warning("Failed to save working flow to DB", exc_info=True)


def _ensure_working_flow() -> dict:
    """Get or create the working flow."""
    global _working_flow  # noqa: PLW0603
    if _working_flow is None:
        _working_flow = empty_flow()
    return _working_flow


def _find_node(flow: dict, component_id: str) -> dict | None:
    """Find a node in the flow by component ID."""
    for node in flow.get("data", {}).get("nodes", []):
        nid = node.get("data", {}).get("id", node.get("id", ""))
        if nid == component_id:
            return node
    return None


# ---------------------------------------------------------------------------
# Search / Describe (read-only, no events)
# ---------------------------------------------------------------------------


class SearchComponentTypes(Component):
    display_name = "Search Components"
    description = "Search available Langflow component types by name, category, or output type."
    icon = "Search"
    name = "SearchComponentTypes"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Search term to filter by name or category (case-insensitive).",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="results", display_name="Results", method="search_components"),
    ]

    def search_components(self) -> Data:
        registry = load_local_registry()
        results = search_registry(registry, query=self.query or None)
        return Data(data={"results": results, "count": len(results)})


class DescribeComponentType(Component):
    display_name = "Describe Component"
    description = "Get a component type's inputs, outputs, and fields. Use to learn what a component accepts."
    icon = "Info"
    name = "DescribeComponentType"

    inputs = [
        MessageTextInput(
            name="component_type",
            display_name="Component Type",
            info="The component type name (e.g. 'ChatInput', 'OpenAIModel').",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="description", display_name="Description", method="describe_component"),
    ]

    def describe_component(self) -> Data:
        registry = load_local_registry()
        try:
            result = describe_component(registry, self.component_type)
        except ValueError as e:
            logger.warning("describe_component failed: %s", e)
            return Data(data={"error": str(e)})
        return Data(data=result)


class GetFieldValue(Component):
    display_name = "Get Field Value"
    description = "Read field values from a component on the canvas. Use the component ID from the flow summary."
    icon = "Eye"
    name = "GetFieldValue"

    inputs = [
        MessageTextInput(
            name="component_id",
            display_name="Component ID",
            info="Full component ID from the flow summary (e.g. 'ChatInput-a1B2c').",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="field_name",
            display_name="Field Name",
            info="Field to read (e.g. 'input_value', 'model_name'). Leave empty to list all fields.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="get_field_value"),
    ]

    def get_field_value(self) -> Data:
        flow = _ensure_working_flow()
        node = _find_node(flow, self.component_id)
        if node is None:
            available = [n.get("data", {}).get("id", "") for n in flow.get("data", {}).get("nodes", [])]
            return Data(data={"error": f"Component '{self.component_id}' not found. Available: {available}"})

        template = node.get("data", {}).get("node", {}).get("template", {})

        if not self.field_name:
            # List all fields with their values
            fields = {}
            for fname, fdata in template.items():
                if not isinstance(fdata, dict) or fname in ("code", "_type"):
                    continue
                value = fdata.get("value")
                if is_sensitive_field(fname) and value:
                    fields[fname] = "***REDACTED***"
                else:
                    fields[fname] = value
            return Data(data={"component_id": self.component_id, "fields": fields})

        # Get specific field
        if self.field_name not in template:
            available = [k for k, v in template.items() if isinstance(v, dict) and k not in ("code", "_type")]
            return Data(data={"error": f"Field '{self.field_name}' not found. Available: {available}"})

        fdata = template[self.field_name]
        value = fdata.get("value") if isinstance(fdata, dict) else fdata
        if is_sensitive_field(self.field_name) and value:
            value = "***REDACTED***"
        return Data(data={"component_id": self.component_id, "field": self.field_name, "value": value})


# ---------------------------------------------------------------------------
# Propose edits (validated, user-reviewable)
# ---------------------------------------------------------------------------


class ProposeFieldEdit(Component):
    display_name = "Propose Field Edit"
    description = "Propose a field value change on a component. Validates and generates a reviewable patch."
    icon = "Pencil"
    name = "ProposeFieldEdit"

    inputs = [
        MessageTextInput(
            name="component_id",
            display_name="Component ID",
            info="Full component ID (e.g. 'OpenAIModel-x3Y4z').",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="field_name",
            display_name="Field Name",
            info="The field to change (e.g. 'model_name', 'temperature').",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="new_value",
            display_name="New Value",
            info="The new value to set.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="propose_field_edit"),
    ]

    def propose_field_edit(self) -> Data:
        import copy
        import uuid

        import jsonpatch

        flow = get_working_flow()
        if flow is None:
            return Data(data={"error": "No flow loaded. Cannot propose edits on an empty canvas."})

        # 1. Find the node
        node = _find_node(flow, self.component_id)
        if node is None:
            available = [n.get("data", {}).get("id", "") for n in flow.get("data", {}).get("nodes", [])]
            return Data(
                data={
                    "error": f"Component '{self.component_id}' not found. Available: {available}",
                }
            )

        # 2. Validate field exists
        template = node.get("data", {}).get("node", {}).get("template", {})
        if self.field_name not in template or not isinstance(template.get(self.field_name), dict):
            available = [k for k, v in template.items() if isinstance(v, dict) and k not in ("code", "_type")]
            return Data(
                data={
                    "error": f"Field '{self.field_name}' not found on '{self.component_id}'. Available: {available}",
                }
            )

        # 3. Read old value
        old_value = template[self.field_name].get("value")

        # 4. Resolve node index
        node_idx = None
        for i, n in enumerate(flow.get("data", {}).get("nodes", [])):
            nid = n.get("data", {}).get("id", n.get("id", ""))
            if nid == self.component_id:
                node_idx = i
                break

        if node_idx is None:
            return Data(data={"error": f"Could not resolve index for '{self.component_id}'"})

        # 5. Build JSON Patch
        path = f"/data/nodes/{node_idx}/data/node/template/{self.field_name}/value"
        patch_ops = [{"op": "replace", "path": path, "value": self.new_value}]

        # 6. Dry run -- apply to a copy
        try:
            patch = jsonpatch.JsonPatch(patch_ops)
            patched = patch.apply(copy.deepcopy(flow))
            # Verify the value actually changed
            patched_node = patched["data"]["nodes"][node_idx]
            patched_val = patched_node["data"]["node"]["template"][self.field_name]["value"]
            if patched_val != self.new_value:
                return Data(data={"error": "Patch dry run: value did not change as expected"})
        except (jsonpatch.JsonPatchException, KeyError, IndexError) as e:
            return Data(data={"error": f"Patch validation failed: {e}"})

        # 7. Emit flow_action event
        component_type = node.get("data", {}).get("type", "?")
        action_id = str(uuid.uuid4())[:8]
        _emit(
            "edit_field",
            id=action_id,
            component_id=self.component_id,
            component_type=component_type,
            field=self.field_name,
            old_value=old_value,
            new_value=self.new_value,
            description=f"Set {self.field_name} to {self.new_value!r} on {component_type}",
            patch=patch_ops,
        )

        text = f"Proposed: set {self.field_name} = {self.new_value!r} on {component_type} (pending user approval)"
        return Data(data={"text": text})


# ---------------------------------------------------------------------------
# Mutating tools (push events for real-time UI updates)
# ---------------------------------------------------------------------------


class AddComponent(Component):
    display_name = "Add Component"
    description = "Add a component to the user's flow canvas. Returns the component's id."
    icon = "Plus"
    name = "AddComponent"

    inputs = [
        MessageTextInput(
            name="component_type",
            display_name="Component Type",
            info="Component type name (e.g. 'ChatInput', 'OpenAIModel'). Use search_components to find types.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="add_component"),
    ]

    def add_component(self) -> Data:
        registry = load_local_registry()
        flow = _ensure_working_flow()
        try:
            result = fb_add_component(flow, self.component_type, registry)
            layout_flow(flow)
            _emit("add_component", node=flow["data"]["nodes"][-1])
            text = f"Added {self.component_type} ({result['id']})"
            return Data(data={"id": result["id"], "type": self.component_type, "text": text})
        except (ValueError, KeyError) as e:
            logger.warning("add_component failed: %s", e)
            return Data(data={"error": str(e)})


class RemoveComponent(Component):
    display_name = "Remove Component"
    description = "Remove a component and its connections from the flow."
    icon = "Trash2"
    name = "RemoveComponent"

    inputs = [
        MessageTextInput(
            name="component_id",
            display_name="Component ID",
            info="The component ID to remove (e.g. 'ChatInput-a1B2c').",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="remove_component"),
    ]

    def remove_component(self) -> Data:
        flow = _ensure_working_flow()
        try:
            fb_remove_component(flow, self.component_id)
            layout_flow(flow)
            _emit("remove_component", component_id=self.component_id)
            return Data(data={"removed": self.component_id, "text": f"Removed {self.component_id}"})
        except (ValueError, KeyError) as e:
            logger.warning("remove_component failed: %s", e)
            return Data(data={"error": str(e)})


class ConnectComponents(Component):
    display_name = "Connect Components"
    description = "Connect an output of one component to an input of another."
    icon = "Link"
    name = "ConnectComponents"

    inputs = [
        MessageTextInput(name="source_id", display_name="Source ID", required=True, tool_mode=True),
        MessageTextInput(name="source_output", display_name="Source Output", required=True, tool_mode=True),
        MessageTextInput(name="target_id", display_name="Target ID", required=True, tool_mode=True),
        MessageTextInput(name="target_input", display_name="Target Input", required=True, tool_mode=True),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="connect_components"),
    ]

    def connect_components(self) -> Data:
        flow = _ensure_working_flow()
        try:
            fb_add_connection(flow, self.source_id, self.source_output, self.target_id, self.target_input)
            layout_flow(flow)
            edge = flow["data"]["edges"][-1]
            _emit("connect", edge=edge)
            return Data(
                data={
                    "text": f"Connected {self.source_id}.{self.source_output} -> {self.target_id}.{self.target_input}",
                }
            )
        except (ValueError, KeyError) as e:
            logger.warning("connect_components failed: %s", e)
            return Data(data={"error": str(e)})


class ConfigureComponent(Component):
    display_name = "Configure Component"
    description = "Set parameter values on a component (e.g. model_name, temperature)."
    icon = "Settings"
    name = "ConfigureComponent"

    inputs = [
        MessageTextInput(name="component_id", display_name="Component ID", required=True, tool_mode=True),
        MessageTextInput(
            name="param_name",
            display_name="Parameter Name",
            info="The parameter to set (e.g. 'model_name', 'temperature').",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="param_value",
            display_name="Value",
            info="The value to set.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="configure_component"),
    ]

    def configure_component(self) -> Data:
        flow = _ensure_working_flow()
        try:
            fb_configure(flow, self.component_id, {self.param_name: self.param_value})
            _emit("configure", component_id=self.component_id, param_name=self.param_name, param_value=self.param_value)
            return Data(data={"text": f"Set {self.param_name}={self.param_value} on {self.component_id}"})
        except (ValueError, KeyError) as e:
            logger.warning("configure_component failed: %s", e)
            return Data(data={"error": str(e)})


class BuildFlowFromSpec(Component):
    display_name = "Build Flow"
    description = (
        "Build a complete flow from a text spec. Use for building entire flows at once. "
        "For incremental changes, use add_component/connect_components instead."
    )
    icon = "Workflow"
    name = "BuildFlowFromSpec"

    inputs = [
        MessageTextInput(
            name="spec",
            display_name="Flow Spec",
            info=(
                "Text spec defining the flow. Format:\n"
                "  name: My Flow\n"
                "  nodes:\n"
                "    A: ChatInput\n"
                "    B: ChatOutput\n"
                "  edges:\n"
                "    A.message -> B.input_value\n"
                "  config:\n"
                "    A.input_value: hello"
            ),
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="flow_result", display_name="Flow Result", method="build_flow"),
    ]

    def build_flow(self) -> Data:
        global _working_flow  # noqa: PLW0603
        result = build_flow_from_spec(self.spec)
        if "error" in result:
            error_msg = f"Flow build failed: {result['error']}"
            if "details" in result:
                error_msg += f"\nDetails: {result['details']}"
            logger.warning("build_flow_from_spec failed: %s", result["error"])
            result["text"] = error_msg
        elif "flow" in result:
            result["text"] = (
                f"Flow '{result['name']}' built successfully "
                f"({result['node_count']} nodes, {result['edge_count']} edges)."
            )
            _working_flow = result["flow"]
            _emit("set_flow", flow=result["flow"])
        return Data(data=result)
