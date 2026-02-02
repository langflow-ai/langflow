"""Parsing functions for JSON flow conversion."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from .constants import (
    COMPONENT_IMPORTS,
    LONG_TEXT_FIELDS,
    MIN_PROMPT_LENGTH,
    PYTHON_RESERVED_WORDS,
    SKIP_FIELDS,
    SKIP_NODE_TYPES,
    get_method_name,
)
from .types import EdgeInfo, FlowInfo, NodeInfo

if TYPE_CHECKING:
    from pathlib import Path


def parse_flow_json(flow_path: Path) -> FlowInfo:
    """Parse a flow JSON file into structured data."""
    with flow_path.open() as f:
        data = json.load(f)

    flow_data = data.get("data", data)
    nodes_data = flow_data.get("nodes", [])
    edges_data = flow_data.get("edges", [])

    flow_info = FlowInfo(
        name=data.get("name", "UnnamedFlow"),
        description=data.get("description", ""),
    )

    used_var_names: dict[str, int] = {}

    for node in nodes_data:
        node_info = _parse_node(node, used_var_names, flow_info)
        if node_info:
            flow_info.nodes.append(node_info)

    # Build mapping of node_id -> node_type for method name resolution
    id_to_type = {node.node_id: node.node_type for node in flow_info.nodes}

    for edge in edges_data:
        edge_info = _parse_edge(edge, id_to_type)
        flow_info.edges.append(edge_info)

    return flow_info


def _parse_node(
    node: dict,
    used_var_names: dict[str, int],
    flow_info: FlowInfo,
) -> NodeInfo | None:
    """Parse a single node from the flow JSON.

    Returns None for UI-only nodes (notes, comments, etc.) that should be skipped.
    """
    node_data = node.get("data", {})
    node_id = node_data.get("id", "")
    node_type = node_data.get("type", "")

    # Skip UI-only node types (notes, comments, readme, etc.)
    if node_type in SKIP_NODE_TYPES:
        return None
    node_config = node_data.get("node", {})
    display_name = node_config.get("display_name", node_type)
    template = node_config.get("template", {})

    base_var_name = _parse_var_name(display_name, node_type)
    var_name = _parse_unique_var_name(base_var_name, used_var_names)
    used_var_names[base_var_name] = used_var_names.get(base_var_name, 0) + 1

    config = _parse_node_config(template, var_name, flow_info)
    has_custom_code, custom_code = _parse_custom_code(template, node_type)

    return NodeInfo(
        node_id=node_id,
        node_type=node_type,
        display_name=display_name,
        var_name=var_name,
        config=config,
        has_custom_code=has_custom_code,
        custom_code=custom_code,
    )


def _parse_node_config(
    template: dict,
    var_name: str,
    flow_info: FlowInfo,
) -> dict:
    """Parse configuration values from node template."""
    config = {}

    for field_name, field_data in template.items():
        if field_name in SKIP_FIELDS or not isinstance(field_data, dict):
            continue

        value = field_data.get("value")
        if value is None or value in ("", []):
            continue
        if field_name == "model" and value == []:
            continue

        if _is_long_text_field(field_name, value):
            prompt_name = f"{var_name.upper()}_{field_name.upper()}"
            flow_info.prompts[prompt_name] = value
            config[field_name] = f"${prompt_name}"
        else:
            config[field_name] = value

    return config


def _is_long_text_field(field_name: str, value: object) -> bool:
    """Check if a field contains long text that should be extracted."""
    return field_name in LONG_TEXT_FIELDS and isinstance(value, str) and len(value) > MIN_PROMPT_LENGTH


def _parse_custom_code(template: dict, node_type: str) -> tuple[bool, str | None]:
    """Parse custom component code from a node template."""
    code_field = template.get("code", {})
    if isinstance(code_field, dict):
        code_value = code_field.get("value", "")
        if code_value and "class " in code_value and node_type not in COMPONENT_IMPORTS:
            return True, code_value
    return False, None


def _parse_edge(edge: dict, id_to_type: dict[str, str]) -> EdgeInfo:
    """Parse a single edge from the flow JSON.

    Args:
        edge: Edge data from JSON
        id_to_type: Mapping of node_id to node_type for method name resolution
    """
    source_id = edge.get("source", "")
    target_id = edge.get("target", "")
    edge_data = edge.get("data", {})
    source_handle = edge_data.get("sourceHandle", {})
    target_handle = edge_data.get("targetHandle", {})

    output_name = source_handle.get("name", "output")
    source_type = id_to_type.get(source_id, "")

    # Resolve output name to method name
    method_name = get_method_name(source_type, output_name)

    return EdgeInfo(
        source_id=source_id,
        source_output=output_name,
        source_method=method_name,
        target_id=target_id,
        target_input=target_handle.get("fieldName", "input"),
    )


def _parse_var_name(display_name: str, node_type: str) -> str:
    """Parse a clean Python variable name from display name or type."""
    name = _parse_to_snake_case(display_name or node_type)
    if not name or name[0].isdigit():
        name = f"node_{name}" if name else "node"
    if name in PYTHON_RESERVED_WORDS:
        name = f"{name}_component"
    return name


def _parse_unique_var_name(base_name: str, used_names: dict[str, int]) -> str:
    """Parse a unique variable name by appending a number if needed."""
    if base_name not in used_names:
        return base_name
    return f"{base_name}_{used_names[base_name] + 1}"


def _parse_to_snake_case(name: str) -> str:
    """Parse a name to snake_case format."""
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    name = re.sub(r"\s+", "_", name)
    name = name.lower()
    name = re.sub(r"_+", "_", name)
    return name.strip("_")
