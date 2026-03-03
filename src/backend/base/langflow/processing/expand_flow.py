"""Expand compact flow format to full flow format.

This module provides functionality to expand a minimal/compact flow format
(used by AI agents) into the full flow format expected by Langflow.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CompactNode(BaseModel):
    """A compact node representation for AI-generated flows."""

    id: str
    type: str
    values: dict[str, Any] = Field(default_factory=dict)
    # If edited is True, the node field must contain the full node data
    edited: bool = False
    node: dict[str, Any] | None = None


class CompactEdge(BaseModel):
    """A compact edge representation for AI-generated flows."""

    source: str
    source_output: str
    target: str
    target_input: str


class CompactFlowData(BaseModel):
    """The compact flow data structure."""

    nodes: list[CompactNode]
    edges: list[CompactEdge]


def _get_flat_components(all_types_dict: dict[str, Any]) -> dict[str, Any]:
    """Flatten the component types dict for easy lookup by component name."""
    return {
        comp_name: comp_data
        for components in all_types_dict.values()
        if isinstance(components, dict)
        for comp_name, comp_data in components.items()
    }


def _expand_node(
    compact_node: CompactNode,
    flat_components: dict[str, Any],
) -> dict[str, Any]:
    """Expand a compact node to full node format.

    Args:
        compact_node: The compact node to expand
        flat_components: Flattened component templates dict

    Returns:
        Full node data structure

    Raises:
        ValueError: If component type is not found and node is not edited
    """
    # If the node is edited, it should have full node data
    if compact_node.edited:
        if not compact_node.node:
            msg = f"Node {compact_node.id} is marked as edited but has no node data"
            raise ValueError(msg)
        return {
            "id": compact_node.id,
            "type": "genericNode",
            "data": {
                "type": compact_node.type,
                "node": compact_node.node,
                "id": compact_node.id,
            },
        }

    # Look up component template
    if compact_node.type not in flat_components:
        msg = f"Component type '{compact_node.type}' not found in component index"
        raise ValueError(msg)

    # Fast deepcopy for known structure.
    # Instead of deepcopy, use shallow copy and per-field dict copy for template subdict.
    src_data = flat_components[compact_node.type]
    # Assume template is a dict (if present)
    if "template" in src_data:
        # Shallow copy for outer structure
        template_data = src_data.copy()
        # Deep copy only 'template' portion (which is mutated and thus not shared)
        template_data["template"] = template = src_data["template"].copy()
    else:
        template_data = src_data.copy()
        template = template_data.get("template", {})

    # Merge user values into template
    # Use items() directly, reduce field lookups
    for field_name, field_value in compact_node.values.items():
        t_value = template.get(field_name)
        if t_value is not None:
            if isinstance(t_value, dict):
                t_value["value"] = field_value
            else:
                template[field_name] = field_value
        else:
            # Add as new field if not in template
            template[field_name] = {"value": field_value}

    return {
        "id": compact_node.id,
        "type": "genericNode",
        "data": {
            "type": compact_node.type,
            "node": template_data,
            "id": compact_node.id,
        },
    }


def _encode_handle(data: dict[str, Any]) -> str:
    """Encode a handle dict to the special string format used by ReactFlow.

    Uses œ instead of " for JSON encoding.
    """
    from lfx.utils.util import escape_json_dump

    return escape_json_dump(data)


def _build_source_handle_data(
    node_id: str,
    component_type: str,
    output_name: str,
    output_types: list[str],
) -> dict[str, Any]:
    """Build the sourceHandle data dict for an edge."""
    return {
        "dataType": component_type,
        "id": node_id,
        "name": output_name,
        "output_types": output_types,
    }


def _build_target_handle_data(
    node_id: str,
    field_name: str,
    input_types: list[str],
    field_type: str,
) -> dict[str, Any]:
    """Build the targetHandle data dict for an edge."""
    return {
        "fieldName": field_name,
        "id": node_id,
        "inputTypes": input_types,
        "type": field_type,
    }


def _expand_edge(
    compact_edge: CompactEdge,
    expanded_nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Expand a compact edge to full edge format.

    Args:
        compact_edge: The compact edge to expand
        expanded_nodes: Dict of node_id -> expanded node data

    Returns:
        Full edge data structure
    """
    source_node = expanded_nodes.get(compact_edge.source)
    target_node = expanded_nodes.get(compact_edge.target)

    if not source_node:
        msg = f"Source node '{compact_edge.source}' not found"
        raise ValueError(msg)
    if not target_node:
        msg = f"Target node '{compact_edge.target}' not found"
        raise ValueError(msg)

    source_node_data = source_node["data"]["node"]
    target_node_data = target_node["data"]["node"]

    # Find output types from source node
    source_outputs = source_node_data.get("outputs", [])
    source_output = next(
        (o for o in source_outputs if o.get("name") == compact_edge.source_output),
        None,
    )
    output_types = source_output.get("types", []) if source_output else []

    # If no outputs defined, use base_classes
    if not output_types:
        output_types = source_node_data.get("base_classes", [])

    # Find input types and field type from target node template
    target_template = target_node_data.get("template", {})
    target_field = target_template.get(compact_edge.target_input, {})
    input_types = target_field.get("input_types", [])
    field_type = target_field.get("type", "str") if isinstance(target_field, dict) else "str"
    if not input_types and isinstance(target_field, dict):
        input_types = [field_type]

    source_type = source_node["data"]["type"]

    # Build handle data objects
    source_handle_data = _build_source_handle_data(
        compact_edge.source,
        source_type,
        compact_edge.source_output,
        output_types,
    )
    target_handle_data = _build_target_handle_data(
        compact_edge.target,
        compact_edge.target_input,
        input_types,
        field_type,
    )

    # Encode handles to string format
    source_handle_str = _encode_handle(source_handle_data)
    target_handle_str = _encode_handle(target_handle_data)

    edge_id = f"reactflow__edge-{compact_edge.source}{source_handle_str}-{compact_edge.target}{target_handle_str}"

    return {
        "source": compact_edge.source,
        "sourceHandle": source_handle_str,
        "target": compact_edge.target,
        "targetHandle": target_handle_str,
        "id": edge_id,
        "data": {
            "sourceHandle": source_handle_data,
            "targetHandle": target_handle_data,
        },
        "className": "",
        "selected": False,
        "animated": False,
    }


def expand_compact_flow(
    compact_data: dict[str, Any],
    all_types_dict: dict[str, Any],
) -> dict[str, Any]:
    """Expand a compact flow format to full flow format.

    Args:
        compact_data: The compact flow data with nodes and edges
        all_types_dict: The component types dictionary from component_cache

    Returns:
        Full flow data structure ready for Langflow UI

    Example compact input:
        {
            "nodes": [
                {"id": "1", "type": "ChatInput"},
                {"id": "2", "type": "OpenAIModel", "values": {"model_name": "gpt-4"}}
            ],
            "edges": [
                {"source": "1", "source_output": "message", "target": "2", "target_input": "input_value"}
            ]
        }
    """
    # Parse and validate compact data
    flow_data = CompactFlowData(**compact_data)

    # Flatten components for lookup
    flat_components = _get_flat_components(all_types_dict)

    # Expand nodes
    expanded_nodes: dict[str, dict[str, Any]] = {}
    for compact_node in flow_data.nodes:
        expanded = _expand_node(compact_node, flat_components)
        expanded_nodes[compact_node.id] = expanded

    # Expand edges
    expanded_edges = []
    for compact_edge in flow_data.edges:
        expanded = _expand_edge(compact_edge, expanded_nodes)
        expanded_edges.append(expanded)

    return {
        "nodes": list(expanded_nodes.values()),
        "edges": expanded_edges,
    }
