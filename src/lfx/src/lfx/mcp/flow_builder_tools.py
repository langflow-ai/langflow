"""Tools for searching components and building flows on the user's canvas.

These components expose flow_builder capabilities as Agent tools.
Each mutating tool pushes a flow_update event to a per-request queue
so the assistant service can send real-time SSE updates to the frontend.
"""

from __future__ import annotations

import asyncio
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


def _load_registry_user_aware() -> dict[str, dict]:
    """Return the base registry merged with the calling user's overlay.

    Tries the langflow-side overlay (which reads the current_user_id
    ContextVar and walks ``<sandbox>/.components/*.py`` for that user).
    Falls back to the bare base registry when:
        - the langflow package isn't installed alongside lfx (e.g., the
          MCP server is running standalone),
        - no user is bound to the context.

    Keeps the lfx package free of a hard dependency on the langflow
    code path while letting the agent's tools see user-registered
    Components when both packages are co-installed.
    """
    try:
        from langflow.agentic.services.user_components_overlay import (
            load_registry_for_current_user,
        )
    except ImportError:
        return load_local_registry()
    return load_registry_for_current_user()


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


def isolate_flow_run_context() -> None:
    """Rebind the per-run flow ContextVars to FRESH values.

    For a NESTED pipeline run (``GenerateComponent`` re-entering
    ``execute_flow_with_validation`` mid agent-loop), the parent loop's
    canvas/events must be invisible and untouchable. Unlike
    ``reset_working_flow()`` — which ``.clear()``s the event deque that a
    child context inherited *by reference* from the parent — this installs
    a brand-new deque, so the nested run can neither drain the parent's
    queued events nor wipe the parent's working flow.
    """
    _flow_events_var.set(deque())
    _working_flow_var.set(None)
    _current_flow_id_var.set(None)


def _emit(action: str, **data: Any) -> None:
    """Push a flow_update event."""
    _get_flow_events().append({"action": action, **data})


def _readable_preview(value: Any, limit: int = 120) -> str:
    r"""One-line, human-readable rendering of a field value for a summary.

    The full value is carried separately (``new_value``/the patch) for the
    diff body — this is only the short headline. Uses ``repr()``-free
    formatting (no surrounding quotes, no escaped ``\n``) and collapses all
    whitespace so a multi-line system prompt doesn't blow up the card.
    """
    text = value if isinstance(value, str) else str(value)
    # Collapse BOTH real control chars and their two-char escape sequences
    # ("\\n"/"\\r"/"\\t") — LLMs emit either, and the card must never show
    # a literal backslash-n.
    for esc in ("\\n", "\\r", "\\t"):
        text = text.replace(esc, " ")
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


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
        # Pure read against the local registry — memoize per request so
        # repeated planning turns don't re-walk the registry.
        from lfx.mcp.tool_cache import cached_tool_call

        def producer() -> Data:
            registry = _load_registry_user_aware()
            results = search_registry(registry, query=self.query or None)
            return Data(data={"results": results, "count": len(results)})

        return cached_tool_call(
            "search_components",
            {"query": self.query or None},
            producer,
        )


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
        # Pure read — describing a registry type is deterministic per
        # request. Cached so repeated configure/connect flows reuse it.
        from lfx.mcp.tool_cache import cached_tool_call

        component_type = self.component_type

        def producer() -> Data:
            registry = _load_registry_user_aware()
            try:
                result = describe_component(registry, component_type)
            except ValueError as e:
                logger.warning("describe_component failed: %s", e)
                return Data(data={"error": str(e)})
            return Data(data=result)

        return cached_tool_call(
            "describe_component",
            {"component_type": component_type},
            producer,
        )


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


class DescribeFlowIO(Component):
    """Deterministically resolve the flow's input/output/tool components.

    Computed from the graph wiring — O(1) for the agent and exact at ANY
    flow size, so the agent never has to scan `connections` by eye (which
    mis-targets on large flows: e.g. editing a tool component instead of
    the ChatInput). Call this to find which component "the input" means
    BEFORE editing it.

    Classification (by role in the edges, never by name):
      - tool: a source whose every outgoing edge feeds a `tools` handle
        (the `component_as_tool` wiring) — NOT the flow input.
      - input: a node with NO incoming edges that is not a tool — its
        `value_field` is the field to set ("input_value"/"input_text"/...).
      - output: a sink (no outgoing edges), typically ChatOutput.
    """

    display_name = "Describe Flow IO"
    description = (
        "Return the flow's input components (and which field carries the run input), output "
        "components, and tool components, computed from the canvas wiring. Use this to find "
        "which component 'the input' / 'o input' refers to before editing it — never guess "
        "from names. If there is more than one input, ask the user which one."
    )
    icon = "ArrowRightLeft"
    name = "DescribeFlowIO"

    inputs = [
        MessageTextInput(
            name="reason",
            display_name="Reason",
            info="Optional short note on why you are inspecting the flow IO (does not change anything).",
            required=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Flow IO", method="describe_flow_io"),
    ]

    _VALUE_FIELDS = ("input_value", "input_text", "text")

    def describe_flow_io(self) -> Data:
        flow = _ensure_working_flow()
        data = flow.get("data") or {}
        nodes = data.get("nodes") or []
        edges = data.get("edges") or []

        def _nid(node: dict) -> str:
            nd = node.get("data", {}) or {}
            return nd.get("id", node.get("id", ""))

        def _ntype(node: dict) -> str:
            return (node.get("data", {}) or {}).get("type", "?")

        def _template(node: dict) -> dict:
            return (node.get("data", {}) or {}).get("node", {}).get("template", {}) or {}

        incoming: dict[str, int] = {}
        out_target_fields: dict[str, list] = {}
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            tgt_handle = (edge.get("data", {}) or {}).get("targetHandle", {})
            field = tgt_handle.get("fieldName") if isinstance(tgt_handle, dict) else None
            if tgt:
                incoming[tgt] = incoming.get(tgt, 0) + 1
            if src:
                out_target_fields.setdefault(src, []).append(field)

        inputs: list[dict] = []
        outputs: list[dict] = []
        tools: list[dict] = []
        for node in nodes:
            nid = _nid(node)
            ntype = _ntype(node)
            outs = out_target_fields.get(nid, [])
            # A tool provider's every outgoing edge targets a `tools` input.
            if outs and all(f == "tools" for f in outs):
                tools.append({"id": nid, "type": ntype})
                continue
            if not outs:
                outputs.append({"id": nid, "type": ntype})
            if incoming.get(nid, 0) == 0:
                tmpl = _template(node)
                value_field = next((f for f in self._VALUE_FIELDS if isinstance(tmpl.get(f), dict)), None)
                inputs.append({"id": nid, "type": ntype, "value_field": value_field})

        def _fmt(items: list, *, with_field: bool = False) -> str:
            if not items:
                return "(none)"
            parts = []
            for it in items:
                if with_field and it.get("value_field"):
                    parts.append(f"{it['id']} ({it['type']}, set {it['value_field']})")
                else:
                    parts.append(f"{it['id']} ({it['type']})")
            return ", ".join(parts)

        text = f"inputs: {_fmt(inputs, with_field=True)}\noutputs: {_fmt(outputs)}\ntools: {_fmt(tools)}"
        return Data(data={"inputs": inputs, "outputs": outputs, "tools": tools, "text": text})


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
            description=f'Set {self.field_name} to "{_readable_preview(self.new_value)}" on {component_type}',
            patch=patch_ops,
        )

        preview = _readable_preview(self.new_value)
        text = f'Proposed: set {self.field_name} = "{preview}" on {component_type} (pending user approval)'
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
        registry = _load_registry_user_aware()
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
                output_names = {o.get("name") for o in outputs if isinstance(o, dict)}
                if len(outputs) > 1:
                    # Frontend reads `data.selected_output` (top-level on the
                    # ReactFlow node) to decide which output handle is rendered
                    # for components with multiple outputs. Setting this at
                    # `data.node.selected_output` is invisible to the canvas.
                    source_node["data"]["selected_output"] = self.source_output
                    _emit("select_output", component_id=self.source_id, output_name=self.source_output)
                else:
                    # Single/zero output now (e.g. tool-mode collapsed the
                    # outputs). A leftover `selected_output` from a prior
                    # wiring would point at a removed output and the node
                    # label would render "unconnected" — reconcile it.
                    stale = source_node["data"].get("selected_output")
                    if stale is not None and stale not in output_names:
                        source_node["data"].pop("selected_output", None)
                        if outputs:
                            _emit(
                                "select_output",
                                component_id=self.source_id,
                                output_name=outputs[0].get("name", ""),
                            )
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
    """Mirror the new ModelInput selection into the field's `options` array.

    For each ModelInput field touched in `params`, ensure the new selection
    is present in the field's `options` array. No-op for non-model fields.
    Idempotent: existing entries with the same name+provider are not
    duplicated.
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

        # Pass the user-aware registry so user-registered Components
        # (created via Layer-2 validated generation) are addressable in
        # the spec by their class name.
        result = build_flow_from_spec(self.spec, registry=_load_registry_user_aware())
        if "error" in result:
            error_msg = f"Flow build failed: {result['error']}"
            if "details" in result:
                error_msg += f"\nDetails: {result['details']}"
            logger.warning("build_flow_from_spec failed: %s", result["error"])
            result["text"] = error_msg
        elif "flow" in result:
            orphan_ids = _find_orphan_nodes(result["flow"])
            # A single-component flow has no edges by definition — it is a
            # valid standalone flow (e.g. the agent built one component to
            # run/inspect), NOT an orphan mistake. Only reject when 2+
            # nodes exist but wiring is missing.
            if orphan_ids and result.get("node_count", len(orphan_ids)) > 1:
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
            # Mutate the EXISTING working-flow dict in place instead of
            # rebinding the ContextVar. A `.set()` rebind is invisible
            # across tool-execution contexts, so a later `run_flow` tool
            # call (different context) would still see the old empty flow
            # ("There is no flow on the canvas to run"). In-place mutation
            # of the shared object is visible everywhere — same proven
            # pattern as `configure_component` (`fb_configure(flow, ...)`).
            working = _ensure_working_flow()
            working.clear()
            working.update(result["flow"])
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


def _format_run_metrics(metrics: dict) -> str:
    """Render run metrics as one human line the agent can repeat verbatim.

    Always reports wall time; appends token usage only when an LLM was
    actually involved (total > 0), so non-LLM flows don't read "0 tokens".
    """
    if not metrics:
        return ""
    duration = metrics.get("duration_seconds") or 0
    parts = [f"Ran in {duration:g}s"]
    total = metrics.get("total_tokens") or 0
    if total:
        in_tok = metrics.get("input_tokens") or 0
        out_tok = metrics.get("output_tokens") or 0
        parts.append(f"used {total} tokens ({in_tok} in / {out_tok} out)")
    return f"({' · '.join(parts)})"


class RunFlow(Component):
    """Run the user's current canvas flow and return its result.

    Executes the working flow exactly as it is on the canvas (honoring any
    unsaved assistant edits) with the components' currently-configured
    values — no input is invented. Vertex-build events are forwarded so the
    canvas animates like a normal Run, and the result text is returned to
    the agent so it can answer follow-up questions about it.

    Decoupled from ``langflow`` via a late import (same pattern as
    ``_load_registry_user_aware``): ``lfx`` may run without the backend.
    """

    display_name = "Run Flow"
    description = (
        "Execute the user's current flow on the canvas (with its configured values) and "
        "return the result. Use when the user asks to run/test/execute the flow or asks "
        "about what it produces. The canvas animates while it runs; the result comes back "
        "so you can discuss it. Do not invent inputs; run it as configured."
    )
    icon = "Play"
    name = "RunFlow"

    inputs = [
        MessageTextInput(
            name="reason",
            display_name="Reason",
            info="Optional short note on why you are running the flow (does not change the run).",
            required=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="run_result", display_name="Run Result", method="run_flow"),
    ]

    async def run_flow(self) -> Data:
        flow = _ensure_working_flow()
        nodes = (flow.get("data") or {}).get("nodes") or []
        if not nodes:
            msg = "There is no flow on the canvas to run. Build or add components first."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.flow_run import run_working_flow
        except ImportError:
            msg = "Flow execution is not available in this environment."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.user_components_context import current_user_id

            user_id = current_user_id()
        except ImportError:
            user_id = None

        # The run engine (ChatOutput/session) requires a valid UUID flow id;
        # a non-UUID placeholder makes the run fail with "badly formed
        # hexadecimal UUID string". Fall back to a fresh uuid4 when the
        # canvas has no persisted id yet.
        from uuid import uuid4

        flow_id = _current_flow_id_var.get() or str(uuid4())

        # The assistant runs with a verified provider/model/api_key. The
        # LLM-chosen (or empty) model on a built Agent often has no
        # configured key -> "Authentication failed". Propagate the
        # assistant's working credential into the Agent node(s) so this
        # assistant-triggered run actually authenticates and returns a
        # result. Deterministic and LLM-agnostic; the canvas still shows
        # the Agent, so the user can change the model afterwards.
        try:
            from langflow.agentic.services.agent_run_context import current_agent_run_model
            from langflow.agentic.services.flow_preparation import inject_model_into_flow

            run_model = current_agent_run_model() or {}
            run_provider = run_model.get("provider")
            run_model_name = run_model.get("model_name")
            if run_provider and run_model_name:
                inject_model_into_flow(flow, run_provider, run_model_name, run_model.get("api_key_var"))
        except (ImportError, ValueError) as exc:
            logger.warning("run_flow.verified_model_inject_skipped: %s", exc)

        result = await run_working_flow(flow_data=flow, flow_id=flow_id, user_id=user_id)
        if "error" in result:
            return Data(data={"error": result["error"], "text": result["error"]})
        # Deterministic, LLM/language-agnostic signal that the flow ACTUALLY
        # ran this turn. The streaming generator uses it to apply a built
        # flow to the canvas (running a flow the user can't see is
        # contradictory) instead of guessing intent from the prompt wording.
        # Emitted only on success — a failed run must never claim it ran.
        _emit("flow_ran", flow_id=flow_id)
        text = result.get("result", "")
        metrics = result.get("metrics") or {}
        summary = _format_run_metrics(metrics)
        # The LLM only reads `text`, so the performance summary must be inline
        # for the agent to be able to report time/tokens; `metrics` is kept
        # structured for any programmatic use.
        text_with_metrics = f"{text}\n\n{summary}" if summary else text
        return Data(data={"text": text_with_metrics, "result": text, "metrics": metrics})


class GenerateComponent(Component):
    """Generate, validate and register a NEW custom Langflow component.

    This is what lets ONE agent loop handle "create a component that does X
    and use it in a flow" without an intent router or phase orchestration:
    the agent calls this tool, then ``search_components`` finds the new
    component by class name and ``build_flow``/``add_component`` use it.

    Wraps the full backend pipeline (LLM generation → security scan → code
    + runtime validation with retries → user-scoped registration). Lazily
    imports ``langflow`` (same decoupling as ``RunFlow``): ``lfx`` may run
    without the backend.
    """

    display_name = "Generate Component"
    description = (
        "Create a brand-new custom Langflow component from a natural-language description. "
        "Use this when the user asks for a component/tool that does not exist yet. On success "
        "the component is validated and registered — then call search_components to find it by "
        "its class name and add it to the flow. Returns the generated component's class name."
    )
    icon = "Wand2"
    name = "GenerateComponent"

    inputs = [
        MessageTextInput(
            name="spec",
            display_name="Spec",
            info="Natural-language spec of the component to create (what it takes and what it returns).",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="generate_component"),
    ]

    async def generate_component(self) -> Data:
        spec = (self.spec or "").strip()
        if not spec:
            msg = "Describe the component to generate (what it takes as input and what it returns)."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.assistant_service import execute_flow_with_validation
            from langflow.agentic.services.file_events import reset_file_events
            from langflow.agentic.services.flow_types import LANGFLOW_ASSISTANT_FLOW
        except ImportError:
            msg = "Component generation is not available in this environment."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.agent_run_context import current_agent_run_model
            from langflow.agentic.services.user_components_context import current_user_id

            user_id = current_user_id()
            model = current_agent_run_model() or {}
        except ImportError:
            user_id = None
            model = {}

        # Give the internal generation sub-flow a valid (ephemeral) flow id
        # so its tracing doesn't log "Invalid flow_id ... None" and persist
        # under a sentinel on every component generation.
        from uuid import uuid4

        from lfx.mcp.tool_cache import reset_tool_cache

        flow_id = str(uuid4())

        async def _isolated_generation() -> dict:
            # This nested pipeline drains flow events and resets the
            # working flow internally. Run it with fresh per-run state so
            # it can neither steal the parent agent loop's queued events
            # nor wipe the canvas the agent already built this turn.
            isolate_flow_run_context()
            reset_tool_cache()
            reset_file_events()
            return await execute_flow_with_validation(
                flow_filename=LANGFLOW_ASSISTANT_FLOW,
                input_value=spec,
                global_variables={"FLOW_ID": flow_id},
                user_id=user_id,
                provider=model.get("provider"),
                model_name=model.get("model_name"),
                api_key_var=model.get("api_key_var"),
            )

        # asyncio.create_task runs the coroutine in a COPY of the current
        # context; ContextVar writes inside it (incl. the isolate/reset
        # calls above) do not propagate back to the parent agent loop.
        result = await asyncio.create_task(_isolated_generation())

        if result.get("validated"):
            class_name = result.get("class_name", "")
            text = (
                f"Component '{class_name}' created, validated and registered. "
                f"Now call search_components to find '{class_name}' and add it to the flow."
            )
            return Data(data={"text": text, "class_name": class_name, "component_code": result.get("component_code")})

        err = result.get("validation_error") or result.get("result") or "Component generation failed."
        return Data(data={"error": err, "text": err})
