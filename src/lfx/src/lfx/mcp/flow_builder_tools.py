"""Tools for searching components and building flows on the user's canvas.

These components expose flow_builder capabilities as Agent tools.
Each mutating tool pushes a flow_update event to a per-request queue
so the assistant service can send real-time SSE updates to the frontend.
"""

from __future__ import annotations

from collections import deque
from contextvars import ContextVar
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
# Per-request state using contextvars. Each async request gets its own
# working flow, flow ID, and event queue -- safe under concurrency.
# ---------------------------------------------------------------------------

_flow_events_var: ContextVar[deque[dict[str, Any]]] = ContextVar("_flow_events_var")
_working_flow_var: ContextVar[dict | None] = ContextVar("_working_flow_var", default=None)
_current_flow_id_var: ContextVar[str | None] = ContextVar("_current_flow_id_var", default=None)


def _get_flow_events() -> deque[dict[str, Any]]:
    """Get the per-request event queue, creating one if needed."""
    try:
        return _flow_events_var.get()
    except LookupError:
        q: deque[dict[str, Any]] = deque()
        _flow_events_var.set(q)
        return q


def drain_flow_events() -> list[dict[str, Any]]:
    """Return and clear all pending flow update events."""
    q = _get_flow_events()
    events = list(q)
    q.clear()
    return events


def get_working_flow() -> dict | None:
    """Return the current working flow (for the assistant service)."""
    return _working_flow_var.get(None)


def init_working_flow(flow_data: dict, flow_id: str | None = None) -> None:
    """Initialize working flow from actual canvas data."""
    _working_flow_var.set(flow_data)
    _current_flow_id_var.set(flow_id)
    _get_flow_events().clear()


def reset_working_flow() -> None:
    """Reset the working flow state between requests."""
    _working_flow_var.set(None)
    _current_flow_id_var.set(None)
    _get_flow_events().clear()


def _emit(action: str, **data: Any) -> None:
    """Push a flow_update event."""
    _get_flow_events().append({"action": action, **data})


def _ensure_working_flow() -> dict:
    """Get or create the working flow."""
    flow = _working_flow_var.get(None)
    if flow is None:
        flow = empty_flow()
        _working_flow_var.set(flow)
    return flow


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
        # ModelInput targets (`type='model'`) render an inline dropdown by
        # default. The "Connect other models" UX in the dropdown switches
        # the field to connection mode by setting `_connectionMode=true` on
        # the node — only THEN does the left handle accept an external
        # model edge visibly. We mirror that flag at connect time so the
        # canvas renders the edge instead of the dropdown.
        target_node = _find_node(flow, self.target_id)
        target_is_model_input = False
        if target_node is not None:
            target_template = target_node.get("data", {}).get("node", {}).get("template", {})
            target_field = target_template.get(self.target_input) or {}
            target_is_model_input = isinstance(target_field, dict) and target_field.get("type") == "model"

        try:
            fb_add_connection(flow, self.source_id, self.source_output, self.target_id, self.target_input)
            layout_flow(flow)
            if target_is_model_input and target_node is not None:
                target_node["data"]["_connectionMode"] = True
                _emit("set_connection_mode", component_id=self.target_id, enabled=True)
            edge = flow["data"]["edges"][-1]
            _emit("connect", edge=edge)
            # When the source has multiple outputs, mirror the connected output
            # into the source node's `selected_output` so the canvas dropdown
            # reflects what the agent actually wired (e.g. switching OpenAIModel
            # from "Model Response" to "Language Model" when connected via
            # `model_output`). Without this the edge exists in state but the
            # node label stays on the default output, looking unconnected.
            source_node = _find_node(flow, self.source_id)
            if source_node is not None:
                outputs = source_node.get("data", {}).get("node", {}).get("outputs", [])
                if len(outputs) > 1:
                    # Frontend reads `data.selected_output` (top-level on the
                    # ReactFlow node) to decide which output handle is rendered
                    # for components with multiple outputs. Setting this at
                    # `data.node.selected_output` is invisible to the canvas.
                    source_node["data"]["selected_output"] = self.source_output
                    _emit("select_output", component_id=self.source_id, output_name=self.source_output)
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
    description = "Set one or more parameters on a component. Pass a JSON dict for multiple params at once."
    icon = "Settings"
    name = "ConfigureComponent"

    inputs = [
        MessageTextInput(name="component_id", display_name="Component ID", required=True, tool_mode=True),
        MessageTextInput(
            name="params",
            display_name="Parameters",
            info='JSON dict of params to set, e.g. \'{"model_name": "gpt-4o", "temperature": 0.7}\'',
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="configure_component"),
    ]

    def configure_component(self) -> Data:
        import json

        flow = _ensure_working_flow()

        # Accept params as dict (from tool framework) or JSON string
        raw = self.params
        if isinstance(raw, dict):
            params = raw
        else:
            raw = (raw or "").strip()
            try:
                params = json.loads(raw)
                if not isinstance(params, dict):
                    return Data(data={"error": f"params must be a JSON object, got {type(params).__name__}"})
            except json.JSONDecodeError:
                return Data(data={"error": f'Invalid JSON in params: {raw!r}. Use format: {{"key": "value"}}'})

        try:
            fb_configure(flow, self.component_id, params)
            # Special case: ModelInput (`type='model'`) has a frontend dropdown
            # that displays via `options.find(o.name === value[0].name)`. If
            # the new model isn't in `options`, the dropdown silently falls
            # back to the previous selection — making the swap invisible to
            # the user. Mirror the new value into `options` so the match
            # succeeds and the canvas reflects the change immediately.
            _mirror_model_value_into_options(flow, self.component_id, params)
            _emit("configure", component_id=self.component_id, params=params)
            summary = ", ".join(f"{k}={v!r}" for k, v in params.items())
            return Data(data={"text": f"Set {summary} on {self.component_id}", "configured": list(params.keys())})
        except (ValueError, KeyError) as e:
            logger.warning("configure_component failed: %s", e)
            return Data(data={"error": str(e)})


def _mirror_model_value_into_options(flow: dict, component_id: str, params: dict) -> None:
    """For each ModelInput field touched in `params`, ensure the new selection
    is present in the field's `options` array.

    No-op for non-model fields. Idempotent: existing entries with the same
    name+provider are not duplicated.
    """
    node = _find_node(flow, component_id)
    if node is None:
        return
    template = node.get("data", {}).get("node", {}).get("template", {})
    for field_name, value in params.items():
        field = template.get(field_name)
        if not isinstance(field, dict) or field.get("type") != "model":
            continue
        if not isinstance(value, list) or not value:
            continue
        first = value[0]
        if not isinstance(first, dict):
            continue
        new_name = first.get("name")
        new_provider = first.get("provider")
        if not new_name:
            continue
        options = field.get("options") or []
        if any(
            isinstance(o, dict) and o.get("name") == new_name and o.get("provider") == new_provider for o in options
        ):
            continue
        options.append({"name": new_name, "provider": new_provider})
        field["options"] = options


class ProposePlan(Component):
    """Propose a build plan to the user and pause until they approve or dismiss.

    Emitted as a `propose_plan` event with the markdown body; the assistant
    service forwards it to the frontend, which renders a Continue/Dismiss card
    in the chat. The agent MUST stop after this tool call — the user's reply
    arrives as a new user turn (Continue ⇒ "User approved the plan. Proceed.",
    Dismiss ⇒ free-form refinement feedback).
    """

    display_name = "Propose Plan"
    description = (
        "Propose a high-level build plan to the user as markdown. The user sees a "
        "Continue/Dismiss card and the agent must wait for the next user turn before "
        "calling any other tools."
    )
    icon = "ClipboardList"
    name = "ProposePlan"

    inputs = [
        MessageTextInput(
            name="plan",
            display_name="Plan (Markdown)",
            info=(
                "Markdown text describing what the agent will build. Should cover the "
                "components to add, the model/persona, and any non-obvious configuration. "
                "Keep it readable for the user — they will Continue or Dismiss it."
            ),
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="plan_result", display_name="Plan Result", method="propose_plan"),
    ]

    def propose_plan(self) -> Data:
        plan = (self.plan or "").strip()
        if not plan:
            error_msg = (
                "Plan is empty. Provide a non-empty markdown description of what you intend to build, "
                "then call propose_plan again."
            )
            return Data(data={"error": error_msg, "text": error_msg})

        _emit("propose_plan", markdown=self.plan)
        marker = (
            "Plan emitted to the user. STOP — do NOT call any other tools. "
            "The user's Continue/Dismiss reply arrives as the next user turn. "
            "On Continue, proceed with search_components / describe_component / build_flow. "
            "On Dismiss, the user will send refinement feedback — replan with propose_plan."
        )
        return Data(data={"text": marker, "status": "awaiting_user_approval"})


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
        existing = get_working_flow()
        if existing and existing.get("data", {}).get("nodes"):
            node_count = len(existing["data"]["nodes"])
            logger.warning("build_flow called on non-empty canvas (%d nodes) -- replacing", node_count)

        result = build_flow_from_spec(self.spec)
        if "error" in result:
            error_msg = f"Flow build failed: {result['error']}"
            if "details" in result:
                error_msg += f"\nDetails: {result['details']}"
            logger.warning("build_flow_from_spec failed: %s", result["error"])
            result["text"] = error_msg
        elif "flow" in result:
            orphan_ids = _find_orphan_nodes(result["flow"])
            if orphan_ids:
                # Reject orphan-bearing flows so the LLM retries instead of
                # rendering an unconnected component on the user's canvas.
                # The agent prompt explicitly forbids orphans; this is the
                # safety net for when it slips through anyway.
                error_msg = (
                    f"Flow build rejected: orphan components with no edges: {orphan_ids}. "
                    "Either wire each component into the flow or remove it from the spec, "
                    "then call build_flow again."
                )
                logger.warning("build_flow_from_spec produced orphans: %s", orphan_ids)
                return Data(data={"error": error_msg, "text": error_msg, "orphans": orphan_ids})
            result["text"] = (
                f"Flow '{result['name']}' built successfully "
                f"({result['node_count']} nodes, {result['edge_count']} edges)."
            )
            _working_flow_var.set(result["flow"])
            _emit("set_flow", flow=result["flow"])
        return Data(data=result)


def _find_orphan_nodes(flow: dict) -> list[str]:
    """Return the IDs of nodes that have no edges (incoming or outgoing).

    A 1-node flow is treated as all-orphans by definition: a flow with no edges
    has no execution path. Callers can distinguish 1-node specs by inspecting
    the result's node_count if needed.
    """
    data = flow.get("data") or {}
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []

    connected: set[str] = set()
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src:
            connected.add(src)
        if tgt:
            connected.add(tgt)

    orphans: list[str] = []
    for node in nodes:
        node_id = node.get("id") or node.get("data", {}).get("id")
        if node_id and node_id not in connected:
            orphans.append(node_id)
    return orphans
