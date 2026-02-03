"""Generate graph builder sections (components, connections, graph return)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..constants import COMPONENT_IMPORTS
from ..formatting import format_value
from .graph_analysis import (
    build_edges_by_target,
    find_all_endpoints,
    find_all_start_nodes,
    find_connected_components,
    find_loop_feedback_edges,
    find_loop_node_ids,
    find_tool_node_ids,
    topological_sort,
)

if TYPE_CHECKING:
    from ..types import EdgeInfo, FlowInfo, NodeInfo

_SINGLE_ITEM = 1
_INLINE_MAX_PARTS = 2
_INLINE_SET_ARG_THRESHOLD = 60


def generate_builder_function(lines: list[str], flow_info: FlowInfo, flow_name: str) -> None:
    """Generate the *_graph() function - minimal style matching hand-written files."""
    lines.append(f"def {flow_name}_graph():")

    id_to_var = {node.node_id: node.var_name for node in flow_info.nodes}
    edges_by_target = build_edges_by_target(flow_info.edges)
    tool_node_ids = find_tool_node_ids(flow_info.edges)
    loop_node_ids = find_loop_node_ids(flow_info.nodes)

    generate_components(lines, flow_info.nodes, tool_node_ids, loop_node_ids, edges_by_target, id_to_var)
    generate_graph_return(lines, flow_info)


def generate_components(
    lines: list[str],
    nodes: list[NodeInfo],
    tool_node_ids: set[str],
    loop_node_ids: set[str],
    edges_by_target: dict[str, list[EdgeInfo]],
    id_to_var: dict[str, str],
) -> None:
    """Generate component instantiation with two-step pattern: constructor then .set()."""
    # Build flat edge list for feedback detection
    all_edges = [e for edges in edges_by_target.values() for e in edges]
    feedback_edges = find_loop_feedback_edges(all_edges, loop_node_ids)

    sorted_nodes = topological_sort(nodes, edges_by_target, loop_node_ids)
    deferred_feedback_args: list[tuple[str, str]] = []  # (var_name, arg_string)

    for node in sorted_nodes:
        class_name = _get_class_name(node)
        constructor_args = _build_constructor_args(node, tool_node_ids)
        set_args, feedback_args = _build_set_args_with_feedback(node, edges_by_target, id_to_var, feedback_edges)

        # Constructor - minimal args (no _id)
        if constructor_args:
            lines.append(f"    {node.var_name} = {class_name}({', '.join(constructor_args)})")
        else:
            lines.append(f"    {node.var_name} = {class_name}()")

        # Tool components need _append_tool_to_outputs_map() before .set() can reference them
        if node.node_id in tool_node_ids:
            lines.append(f"    {node.var_name}._append_tool_to_outputs_map()")

        # .set() call if there are connections or config values (excluding feedback)
        if set_args:
            if len(set_args) == _SINGLE_ITEM and len(set_args[0]) < _INLINE_SET_ARG_THRESHOLD:
                lines.append(f"    {node.var_name}.set({set_args[0]})")
            else:
                lines.append(f"    {node.var_name}.set(")
                lines.extend(f"        {arg}," for arg in set_args)
                lines.append("    )")

        # Defer feedback args to be set after all components are defined
        if feedback_args:
            deferred_feedback_args.extend((node.var_name, arg) for arg in feedback_args)

        lines.append("")

    # Now add deferred feedback connections (loop edges)
    for var_name, arg in deferred_feedback_args:
        lines.append(f"    {var_name}.set({arg})")
        lines.append("")


def _get_class_name(node: NodeInfo) -> str:
    """Get the class name for a node."""
    if node.has_custom_code:
        component_class_match = re.search(
            r"class\s+(\w+)\s*\(\s*(?:\w+\.)*(?:Component|CustomComponent)",
            node.custom_code or "",
        )
        if component_class_match:
            return component_class_match.group(1)
        class_match = re.search(r"class\s+(\w+)", node.custom_code or "")
        return class_match.group(1) if class_match else node.node_type
    import_path = COMPONENT_IMPORTS.get(node.node_type, "")
    return import_path.rsplit(".", 1)[-1] if import_path else node.node_type


def _build_constructor_args(node: NodeInfo, tool_node_ids: set[str]) -> list[str]:
    """Build constructor arguments - minimal, only special cases."""
    args: list[str] = []
    if node.node_id in tool_node_ids:
        args.append("add_tool_output=True")
    if node.has_custom_code and node.custom_code:
        escaped_code = node.custom_code.replace("\\", "\\\\").replace('"""', r"\"\"\"")
        args.append(f'_code="""{escaped_code}"""')
    # model_name can go in constructor for model components
    if "model_name" in node.config and node.node_type in ("OpenAIModelComponent", "LanguageModelComponent"):
        args.append(f"model_name={format_value(node.config['model_name'], 8)}")
    # _display_name can go in constructor
    if "_display_name" in node.config:
        args.append(f"_display_name={format_value(node.config['_display_name'], 8)}")
    return args


def _build_set_args_with_feedback(
    node: NodeInfo,
    edges_by_target: dict[str, list[EdgeInfo]],
    id_to_var: dict[str, str],
    feedback_edges: set[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """Build .set() arguments, separating feedback args from regular args.

    Returns: (regular_args, feedback_args)
    """
    set_args: list[str] = []
    feedback_args: list[str] = []

    # Get edge target fields to avoid duplicating them from config
    edges = edges_by_target.get(node.node_id, [])
    edge_target_fields = {e.target_input for e in edges}

    # Config values (excluding constructor-only args and edge-connected fields)
    constructor_only = {"model_name", "_display_name", "tools"}
    for key, value in node.config.items():
        if key not in constructor_only and key not in edge_target_fields:
            set_args.append(f"{key}={format_value(value, 8)}")

    # Edge connections - separate feedback edges
    tool_edges = [e for e in edges if e.target_input == "tools"]
    other_edges = [e for e in edges if e.target_input != "tools"]

    for edge in other_edges:
        source_var = id_to_var.get(edge.source_id, edge.source_id)
        arg = f"{edge.target_input}={source_var}.{edge.source_method}"

        # Check if this is a feedback edge
        if (edge.source_id, node.node_id) in feedback_edges:
            feedback_args.append(arg)
        else:
            set_args.append(arg)

    if tool_edges:
        tool_refs = [f"{id_to_var.get(e.source_id, e.source_id)}.component_as_tool" for e in tool_edges]
        if len(tool_refs) == _SINGLE_ITEM:
            set_args.append(f"tools=[{tool_refs[0]}]")
        else:
            tools_str = ",\n            ".join(tool_refs)
            set_args.append(f"tools=[\n            {tools_str},\n        ]")

    return set_args, feedback_args


def generate_graph_return(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate the Graph return statement with start= and end= kwargs.

    Handles multiple connected components, multiple start nodes, and multiple endpoints.
    """
    components = find_connected_components(flow_info.nodes, flow_info.edges)
    graph_parts: list[str] = []

    for component in components:
        # Find all start nodes and endpoints in this component
        start_nodes = find_all_start_nodes(component, flow_info.edges)
        endpoints = find_all_endpoints(component, flow_info.edges)

        # Create Graph for each start-end combination to ensure all nodes are included
        graph_parts.extend(
            f"Graph(start={start_node}, end={end_node})" for start_node in start_nodes for end_node in endpoints
        )

    # Deduplicate identical graph parts
    graph_parts = list(dict.fromkeys(graph_parts))

    if len(graph_parts) == _SINGLE_ITEM:
        lines.append(f"    return {graph_parts[0]}")
    elif len(graph_parts) <= _INLINE_MAX_PARTS:
        lines.append(f"    return {' + '.join(graph_parts)}")
    else:
        lines.append("    return (")
        for i, part in enumerate(graph_parts):
            suffix = " +" if i < len(graph_parts) - 1 else ""
            lines.append(f"        {part}{suffix}")
        lines.append("    )")
    lines.append("")
