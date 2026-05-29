"""Connection management: wire component outputs to inputs.

Connections are represented as edges in the flow JSON matching
ReactFlow's edge format. Each edge needs:
- source/target: Component IDs
- sourceHandle/targetHandle: JSON-like strings with œ (U+0153) replacing quotes
- data.sourceHandle/data.targetHandle: Dicts with type info
- id: reactflow__edge-{source}{sourceHandle}-{target}{targetHandle}

All functions are pure — they operate on flow dicts, no I/O.
"""

from __future__ import annotations

from typing import Any

from lfx.graph.edge.base import types_compatible

# Langflow uses oe (U+0153) as a quote replacement in ReactFlow handle strings
_Q = "\u0153"

# Synthetic output name created at runtime when a component is set to tool
# mode. Must match lfx.base.tools.constants.TOOL_OUTPUT_NAME \u2014 duplicated as
# a literal here to avoid a cross-package import in the flow_builder layer.
_TOOL_OUTPUT_NAME = "component_as_tool"
_TOOL_OUTPUT_DISPLAY_NAME = "Toolset"


def _node_template_supports_tool_mode(node: dict) -> bool:
    """Return True when any INPUT field has tool_mode=True.

    Matches the runtime heuristic in Component._handle_tool_mode \u2014 the
    canonical source of truth for whether the Tool Mode toggle would
    render on the canvas. Output-side tool_mode is also accepted for
    backward compat with components that placed the flag there instead.
    """
    template = node.get("data", {}).get("node", {}).get("template", {})
    if any(isinstance(fdata, dict) and fdata.get("tool_mode") for fdata in template.values()):
        return True
    outputs = node.get("data", {}).get("node", {}).get("outputs", [])
    return any(o.get("tool_mode") for o in outputs)


def _enable_tool_mode(flow: dict, source_id: str) -> None:
    """Flip a component to tool mode in place.

    Mirrors Component._handle_tool_mode: when tool_mode is enabled the
    outputs list is replaced with a single synthesized tool output. The
    source node must already exist in the flow; raises ValueError otherwise.

    Raises ValueError when the component does not declare any tool-mode
    capable input (i.e. it genuinely cannot be wrapped as a Tool).
    """
    for node in flow.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        nid = node_data.get("id", node.get("id", ""))
        if nid != source_id:
            continue
        if not _node_template_supports_tool_mode(node):
            msg = (
                f"Cannot connect '{source_id}.component_as_tool': this component "
                "has no tool_mode-capable input. Either pick a different output or "
                "wire a component whose inputs declare tool_mode=True."
            )
            raise ValueError(msg)
        inner = node_data.setdefault("node", {})
        # Idempotent: already in tool mode with the synthesized output present.
        if inner.get("tool_mode") and any(o.get("name") == _TOOL_OUTPUT_NAME for o in inner.get("outputs", [])):
            return
        inner["tool_mode"] = True
        # Mirror the full Output schema (see lfx.template.field.base.Output).
        # The /custom_component/update endpoint and the canvas serializers
        # both expect every field — omitting any of them breaks the popup
        # with "string indices must be integers, not 'str'" because dataclass
        # validators downstream cannot reconcile a partial output dict.
        inner["outputs"] = [
            {
                "allows_loop": False,
                "cache": True,
                "display_name": _TOOL_OUTPUT_DISPLAY_NAME,
                "group_outputs": False,
                "hidden": False,
                "method": "to_toolkit",
                "name": _TOOL_OUTPUT_NAME,
                "options": None,
                "required_inputs": None,
                "selected": "Tool",
                "tool_mode": True,
                "types": ["Tool"],
                "value": "__UNDEFINED__",
            }
        ]
        return
    msg = f"Component not found in flow: {source_id}"
    raise ValueError(msg)


def _scaped_json_stringify(obj: Any) -> str:
    """Replicate Langflow frontend's scapedJSONStringfy: sorted keys, compact, oe for quotes."""
    return _custom_stringify(obj).replace('"', _Q)


def _custom_stringify(obj: Any) -> str:
    """Replicate Langflow frontend's customStringify for edge handle data.

    Covers the subset of types used in handle dicts. Uses json.dumps for
    strings to handle escaping correctly.
    """
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        import json

        return json.dumps(obj)
    if isinstance(obj, list):
        items = ",".join(_custom_stringify(item) for item in obj)
        return f"[{items}]"
    if isinstance(obj, dict):
        keys = sorted(obj.keys())
        pairs = ",".join(f'"{k}":{_custom_stringify(obj[k])}' for k in keys)
        return f"{{{pairs}}}"
    return str(obj)


def _resolve_output_types(flow: dict, component_id: str, output_name: str) -> list[str]:
    """Look up output types from the component's node data in the flow.

    Raises ValueError if the component or output is not found.
    """
    for node in flow.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        nid = node_data.get("id", node.get("id", ""))
        if nid != component_id:
            continue
        outputs = node_data.get("node", {}).get("outputs", [])
        for output in outputs:
            if output.get("name") == output_name:
                return output.get("types", ["Message"])
        available = [o.get("name") for o in outputs]
        msg = f"Output '{output_name}' not found on component '{component_id}'. Available: {available}"
        raise ValueError(msg)
    msg = f"Component not found in flow: {component_id}"
    raise ValueError(msg)


def _resolve_input_types(flow: dict, component_id: str, input_name: str) -> tuple[list[str], str]:
    """Look up input types and field type from the component's template.

    Raises ValueError if the component or input is not found.
    """
    for node in flow.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        nid = node_data.get("id", node.get("id", ""))
        if nid != component_id:
            continue
        template = node_data.get("node", {}).get("template", {})
        field = template.get(input_name, {})
        if isinstance(field, dict) and field:
            return field.get("input_types", ["Message"]), field.get("type", "str")
        available = [k for k, v in template.items() if isinstance(v, dict) and v.get("input_types")]
        msg = f"Input '{input_name}' not found on component '{component_id}'. Available: {available}"
        raise ValueError(msg)
    msg = f"Component not found in flow: {component_id}"
    raise ValueError(msg)


def add_connection(
    flow: dict,
    source_id: str,
    source_output: str,
    target_id: str,
    target_input: str,
    source_types: list[str] | None = None,
    target_types: list[str] | None = None,
) -> dict:
    """Add a connection (edge) between two components.

    When source_types/target_types are None they are resolved from the flow
    and type-compatibility is enforced.  When the caller passes explicit types
    the check is skipped (the caller is taking responsibility).

    When source_output is the synthesized "component_as_tool" handle, the
    source node is automatically flipped into tool mode before resolving
    types — this mirrors what the canvas does when a user drags from the
    Tool Mode toggle, and is required because the static component template
    does not list ``component_as_tool`` until tool mode is enabled.
    """
    source_type = source_id.rsplit("-", 1)[0] if "-" in source_id else source_id

    # Auto-enable tool mode on the source when wiring via component_as_tool.
    # Raises ValueError when the source has no tool-mode-capable input — so
    # the LLM gets a clear domain error instead of "output not found".
    if source_output == _TOOL_OUTPUT_NAME:
        _enable_tool_mode(flow, source_id)

    # Resolve types from the flow's node data if not explicitly provided
    types_resolved = source_types is None and target_types is None
    if source_types is None:
        source_types = _resolve_output_types(flow, source_id, source_output)
    if target_types is None:
        target_types, target_field_type = _resolve_input_types(flow, target_id, target_input)
    else:
        target_field_type = "str"

    if types_resolved and not types_compatible(source_types, target_types):
        msg = (
            f"Type mismatch: output '{source_output}' on '{source_id}' produces {source_types}, "
            f"but input '{target_input}' on '{target_id}' accepts {target_types}"
        )
        raise ValueError(msg)

    source_handle_dict = {
        "dataType": source_type,
        "id": source_id,
        "name": source_output,
        "output_types": source_types,
    }
    target_handle_dict = {
        "fieldName": target_input,
        "id": target_id,
        "inputTypes": target_types,
        "type": target_field_type,
    }

    source_handle_s = _scaped_json_stringify(source_handle_dict)
    target_handle_s = _scaped_json_stringify(target_handle_dict)

    edge_id = f"reactflow__edge-{source_id}{source_handle_s}-{target_id}{target_handle_s}"

    # Idempotent: if a connection between the same source output and target
    # input already exists, return it rather than appending a duplicate. We
    # compare structurally (source/target ids + handle name/fieldName) instead
    # of by edge id, since UI-saved edges from older Langflow versions use a
    # different id prefix (`xy-edge__` vs `reactflow__edge-`) even though the
    # underlying connection is the same. A repeat call (batch retry, UI-then-MCP)
    # would otherwise double-wire the flow at runtime.
    for existing in flow["data"]["edges"]:
        if (
            existing.get("source") == source_id
            and existing.get("target") == target_id
            and (existing.get("data") or {}).get("sourceHandle", {}).get("name") == source_output
            and (existing.get("data") or {}).get("targetHandle", {}).get("fieldName") == target_input
        ):
            return existing

    edge = {
        "animated": False,
        "className": "",
        "data": {
            "sourceHandle": source_handle_dict,
            "targetHandle": target_handle_dict,
        },
        "id": edge_id,
        "selected": False,
        "source": source_id,
        "sourceHandle": source_handle_s,
        "target": target_id,
        "targetHandle": target_handle_s,
    }
    flow["data"]["edges"].append(edge)
    return edge


def remove_connection(
    flow: dict,
    source_id: str,
    target_id: str,
    source_output: str | None = None,
    target_input: str | None = None,
) -> int:
    """Remove connections between two components. Returns count removed."""
    edges = flow["data"]["edges"]
    original_count = len(edges)

    def keep(e: dict) -> bool:
        if e.get("source") != source_id or e.get("target") != target_id:
            return True
        if source_output and e.get("data", {}).get("sourceHandle", {}).get("name") != source_output:
            return True
        return bool(target_input and e.get("data", {}).get("targetHandle", {}).get("fieldName") != target_input)

    flow["data"]["edges"] = [e for e in edges if keep(e)]
    return original_count - len(flow["data"]["edges"])


def list_connections(flow: dict) -> list[dict]:
    """List all connections in a flow."""
    results = []
    for edge in flow.get("data", {}).get("edges", []):
        source_handle = edge.get("data", {}).get("sourceHandle", {})
        target_handle = edge.get("data", {}).get("targetHandle", {})
        results.append(
            {
                "source_id": edge.get("source", ""),
                "target_id": edge.get("target", ""),
                "source_output": source_handle.get("name", ""),
                "target_input": target_handle.get("fieldName", ""),
                "source_types": source_handle.get("output_types", []),
                "target_types": target_handle.get("inputTypes", []),
            }
        )
    return results
