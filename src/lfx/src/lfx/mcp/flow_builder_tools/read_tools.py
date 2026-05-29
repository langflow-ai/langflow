"""Read-only inspection tools for the flow-builder assistant.

These tools never mutate the working flow or emit events: they answer the
agent's "what components exist / what does this look like / what is the
flow shaped like" questions, so the agent can plan before editing.
"""

from __future__ import annotations

from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.log.logger import logger
from lfx.mcp.redact import is_sensitive_field
from lfx.mcp.registry import describe_component, search_registry
from lfx.schema import Data

from ._state import _ensure_working_flow, _find_node, _load_registry_user_aware


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
