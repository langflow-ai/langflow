"""Generate graph builder sections (components, connections, graph return)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..constants import COMPONENT_IMPORTS
from ..formatting import format_value

if TYPE_CHECKING:
    from ..types import EdgeInfo, FlowInfo, NodeInfo

_SINGLE_ITEM = 1
_INLINE_MAX_PARTS = 2
_INLINE_PART_THRESHOLD = 40
_INLINE_SET_ARG_THRESHOLD = 60


def generate_builder_function(lines: list[str], flow_info: FlowInfo, flow_name: str) -> None:
    """Generate the build_*_graph() function."""
    lines.append("")
    lines.append("# " + "=" * 70)
    lines.append("# Flow Builder")
    lines.append("# " + "=" * 70)
    lines.append("")
    lines.append(f"def build_{flow_name}_graph(")
    lines.append("    provider: str | None = None,")
    lines.append("    model_name: str | None = None,")
    lines.append("    api_key: str | None = None,")
    lines.append(") -> Graph:")
    lines.append(f'    """Build the {flow_info.name} graph.')
    lines.append("")
    lines.append("    Args:")
    lines.append('        provider: Model provider (e.g., "Anthropic", "OpenAI")')
    lines.append("        model_name: Model name to use")
    lines.append("        api_key: API key for the provider")
    lines.append("")
    lines.append("    Returns:")
    lines.append("        Configured Graph ready for execution")
    lines.append('    """')

    id_to_var = {node.node_id: node.var_name for node in flow_info.nodes}
    edges_by_target = _build_edges_by_target(flow_info.edges)
    tool_node_ids = _find_tool_node_ids(flow_info.edges)

    generate_components(lines, flow_info.nodes, tool_node_ids)
    generate_connections(lines, flow_info.nodes, edges_by_target, id_to_var)
    generate_graph_return(lines, flow_info)


def _build_edges_by_target(edges: list[EdgeInfo]) -> dict[str, list[EdgeInfo]]:
    """Build mapping of target_id -> list of edges."""
    edges_by_target: dict[str, list[EdgeInfo]] = {}
    for edge in edges:
        if edge.target_id not in edges_by_target:
            edges_by_target[edge.target_id] = []
        edges_by_target[edge.target_id].append(edge)
    return edges_by_target


def _find_tool_node_ids(edges: list[EdgeInfo]) -> set[str]:
    """Find nodes that are used as tools."""
    return {edge.source_id for edge in edges if edge.target_input == "tools"}


def generate_components(lines: list[str], nodes: list[NodeInfo], tool_node_ids: set[str]) -> None:
    """Generate component instantiation code."""
    lines.append("")
    lines.append("    # === Components ===")

    for node in nodes:
        class_name = _get_class_name(node)
        config_parts = _build_config_parts(node, tool_node_ids)

        if len(config_parts) == _SINGLE_ITEM:
            lines.append(f'    {node.var_name} = {class_name}(_id="{node.node_id}")')
        elif len(config_parts) <= _INLINE_MAX_PARTS and all(len(p) < _INLINE_PART_THRESHOLD for p in config_parts):
            lines.append(f"    {node.var_name} = {class_name}({', '.join(config_parts)})")
        else:
            lines.append(f"    {node.var_name} = {class_name}(")
            lines.extend(f"        {part}," for part in config_parts)
            lines.append("    )")

    tool_components = [n for n in nodes if n.node_id in tool_node_ids]
    if tool_components:
        lines.append("")
        lines.append("    # Initialize tool outputs")
        lines.extend(f"    {node.var_name}._append_tool_to_outputs_map()" for node in tool_components)


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


def _build_config_parts(node: NodeInfo, tool_node_ids: set[str]) -> list[str]:
    """Build configuration parts for component instantiation."""
    config_parts = [f'_id="{node.node_id}"']
    if node.node_id in tool_node_ids:
        config_parts.append("add_tool_output=True")
    if node.has_custom_code and node.custom_code:
        escaped_code = node.custom_code.replace("\\", "\\\\").replace('"""', r"\"\"\"")
        config_parts.append(f'_code="""{escaped_code}"""')
    for key, value in node.config.items():
        if key != "tools":
            config_parts.append(f"{key}={format_value(value, 8)}")
    return config_parts


def generate_connections(
    lines: list[str],
    nodes: list[NodeInfo],
    edges_by_target: dict[str, list[EdgeInfo]],
    id_to_var: dict[str, str],
) -> None:
    """Generate .set() connection code."""
    lines.append("")
    lines.append("    # === Connections ===")

    for node in nodes:
        edges = edges_by_target.get(node.node_id, [])
        if not edges:
            continue

        tool_edges = [e for e in edges if e.target_input == "tools"]
        other_edges = [e for e in edges if e.target_input != "tools"]

        set_args = []
        for edge in other_edges:
            source_var = id_to_var.get(edge.source_id, edge.source_id)
            set_args.append(f"{edge.target_input}={source_var}.{edge.source_method}")

        if tool_edges:
            tool_refs = [f"{id_to_var.get(e.source_id, e.source_id)}.component_as_tool" for e in tool_edges]
            if len(tool_refs) == _SINGLE_ITEM:
                set_args.append(f"tools=[{tool_refs[0]}]")
            else:
                tools_str = ",\n            ".join(tool_refs)
                set_args.append(f"tools=[\n            {tools_str},\n        ]")

        if set_args:
            var_name = id_to_var.get(node.node_id, node.node_id)
            if len(set_args) == _SINGLE_ITEM and len(set_args[0]) < _INLINE_SET_ARG_THRESHOLD:
                lines.append(f"    {var_name}.set({set_args[0]})")
            else:
                lines.append(f"    {var_name}.set(")
                lines.extend(f"        {arg}," for arg in set_args)
                lines.append("    )")


def generate_graph_return(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate the Graph return statement."""
    source_ids = {e.source_id for e in flow_info.edges}
    target_ids = {e.target_id for e in flow_info.edges}
    all_ids = {n.node_id for n in flow_info.nodes}
    start_nodes = all_ids - target_ids
    end_nodes = all_ids - source_ids

    start_node = _find_start_node(flow_info.nodes, start_nodes)
    end_node = _find_end_node(flow_info.nodes, end_nodes)

    lines.append("")
    lines.append("    # === Build Graph ===")
    lines.append(f"    return Graph({start_node}, {end_node})")
    lines.append("")


def _find_start_node(nodes: list[NodeInfo], start_nodes: set[str]) -> str:
    """Find the start node variable name."""
    for node in nodes:
        if node.node_type == "ChatInput" and node.node_id in start_nodes:
            return node.var_name
    for node in nodes:
        if node.node_id in start_nodes:
            return node.var_name
    return "None"


def _find_end_node(nodes: list[NodeInfo], end_nodes: set[str]) -> str:
    """Find the end node variable name."""
    for node in nodes:
        if node.node_type == "ChatOutput" and node.node_id in end_nodes:
            return node.var_name
    for node in nodes:
        if node.node_id in end_nodes:
            return node.var_name
    return "None"


def generate_get_graph_function(lines: list[str], flow_name: str) -> None:
    """Generate the get_graph() function for lfx run compatibility."""
    lines.append("")
    lines.append("def get_graph() -> Graph:")
    lines.append('    """Entry point for lfx run command and backend execution.')
    lines.append("")
    lines.append("    This function is called by the lfx CLI and backend services")
    lines.append("    to load the graph for execution.")
    lines.append('    """')
    lines.append(f"    return build_{flow_name}_graph()")
    lines.append("")


def generate_main_block(lines: list[str], flow_name: str) -> None:
    """Generate the if __name__ == '__main__' block."""
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append(f"    graph = build_{flow_name}_graph()")
    lines.append('    print(f"Graph: {len(graph.vertices)} nodes, {len(graph.edges)} edges")')
    lines.append("    for v in graph.vertices:")
    lines.append('        print(f"  - {v.id}: {type(v.custom_component).__name__}")')
    lines.append("")
