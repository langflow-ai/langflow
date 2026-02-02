"""Python code generation from parsed flow data."""

from __future__ import annotations

import re

from .constants import COMPONENT_IMPORTS
from .formatting import format_value
from .parsing import _parse_to_snake_case
from .types import EdgeInfo, FlowInfo, NodeInfo


def generate_python_code(flow_info: FlowInfo) -> str:
    """Generate Python code from parsed flow info."""
    lines: list[str] = []
    flow_name = _parse_to_snake_case(flow_info.name) or "unnamed_flow"

    _generate_header(lines, flow_info)
    _generate_imports(lines, flow_info)
    _generate_custom_components(lines, flow_info)
    _generate_prompts(lines, flow_info)
    _generate_builder_function(lines, flow_info, flow_name)
    _generate_get_graph_function(lines, flow_name)
    _generate_main_block(lines, flow_name)

    return "\n".join(lines)


def _generate_header(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate the module docstring header."""
    lines.append(f'"""Flow: {flow_info.name}')
    if flow_info.description:
        lines.append(f"\n{flow_info.description}")
    lines.append("\nAuto-generated from JSON using `lfx convert`.")
    lines.append("Review and adjust as needed before committing.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")


def _generate_imports(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate import statements for components."""
    imports_by_module: dict[str, set[str]] = {}

    for node in flow_info.nodes:
        if node.has_custom_code:
            continue
        import_path = COMPONENT_IMPORTS.get(node.node_type)
        if import_path:
            module, class_name = import_path.rsplit(".", 1)
            if module not in imports_by_module:
                imports_by_module[module] = set()
            imports_by_module[module].add(class_name)

    lines.append("from lfx.graph import Graph")
    for module in sorted(imports_by_module.keys()):
        classes = sorted(imports_by_module[module])
        if len(classes) == 1:
            lines.append(f"from {module} import {classes[0]}")
        else:
            lines.append(f"from {module} import (")
            for cls in classes:
                lines.append(f"    {cls},")
            lines.append(")")
    lines.append("")


def _generate_custom_components(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate custom component class definitions."""
    custom_components = [n for n in flow_info.nodes if n.has_custom_code]
    if not custom_components:
        return

    lines.append("")
    lines.append("# " + "=" * 70)
    lines.append("# Custom Components")
    lines.append("# " + "=" * 70)
    lines.append("# NOTE: Review and move to a separate file if needed.")
    lines.append("")
    for node in custom_components:
        lines.append(f"# Custom component: {node.display_name}")
        if node.custom_code:
            lines.append(node.custom_code.rstrip())
        lines.append("")


def _generate_prompts(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate prompt constant definitions."""
    if not flow_info.prompts:
        return

    lines.append("")
    lines.append("# " + "=" * 70)
    lines.append("# Prompts and System Instructions")
    lines.append("# " + "=" * 70)
    lines.append("# NOTE: Consider moving to a separate prompts.py file.")
    lines.append("")
    for name, value in flow_info.prompts.items():
        escaped = value.replace('"""', r"\"\"\"")
        lines.append(f'{name} = """')
        lines.append(escaped.rstrip())
        lines.append('"""')
        lines.append("")


def _generate_builder_function(
    lines: list[str],
    flow_info: FlowInfo,
    flow_name: str,
) -> None:
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

    # Build edges by target mapping inline
    edges_by_target: dict[str, list[EdgeInfo]] = {}
    for edge in flow_info.edges:
        if edge.target_id not in edges_by_target:
            edges_by_target[edge.target_id] = []
        edges_by_target[edge.target_id].append(edge)

    _generate_components(lines, flow_info.nodes)
    _generate_connections(lines, flow_info.nodes, edges_by_target, id_to_var)
    _generate_graph_return(lines, flow_info)


def _generate_components(lines: list[str], nodes: list[NodeInfo]) -> None:
    """Generate component instantiation code."""
    lines.append("")
    lines.append("    # === Components ===")

    for node in nodes:
        # Get class name inline
        if node.has_custom_code:
            class_match = re.search(r"class\s+(\w+)", node.custom_code or "")
            class_name = class_match.group(1) if class_match else node.node_type
        else:
            import_path = COMPONENT_IMPORTS.get(node.node_type, "")
            class_name = import_path.rsplit(".", 1)[-1] if import_path else node.node_type

        # Build config parts inline
        config_parts = [f'_id="{node.node_id}"']
        for key, value in node.config.items():
            if key != "tools":
                config_parts.append(f"{key}={format_value(value, 8)}")

        if len(config_parts) == 1:
            lines.append(f'    {node.var_name} = {class_name}(_id="{node.node_id}")')
        elif len(config_parts) <= 2 and all(len(p) < 40 for p in config_parts):
            lines.append(f"    {node.var_name} = {class_name}({', '.join(config_parts)})")
        else:
            lines.append(f"    {node.var_name} = {class_name}(")
            for part in config_parts:
                lines.append(f"        {part},")
            lines.append("    )")


def _generate_connections(
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

        # Build set args inline
        set_args = []
        for edge in other_edges:
            source_var = id_to_var.get(edge.source_id, edge.source_id)
            set_args.append(f"{edge.target_input}={source_var}.{edge.source_output}")

        if tool_edges:
            tool_refs = [f"{id_to_var.get(e.source_id, e.source_id)}.component_as_tool" for e in tool_edges]
            if len(tool_refs) == 1:
                set_args.append(f"tools=[{tool_refs[0]}]")
            else:
                tools_str = ",\n            ".join(tool_refs)
                set_args.append(f"tools=[\n            {tools_str},\n        ]")

        if set_args:
            var_name = id_to_var.get(node.node_id, node.node_id)
            if len(set_args) == 1 and len(set_args[0]) < 60:
                lines.append(f"    {var_name}.set({set_args[0]})")
            else:
                lines.append(f"    {var_name}.set(")
                for arg in set_args:
                    lines.append(f"        {arg},")
                lines.append("    )")


def _generate_graph_return(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate the Graph return statement."""
    source_ids = {e.source_id for e in flow_info.edges}
    target_ids = {e.target_id for e in flow_info.edges}
    all_ids = {n.node_id for n in flow_info.nodes}
    start_nodes = all_ids - target_ids
    end_nodes = all_ids - source_ids

    # Find start node inline
    start_node = "None"
    for node in flow_info.nodes:
        if node.node_type == "ChatInput" and node.node_id in start_nodes:
            start_node = node.var_name
            break
    if start_node == "None":
        for node in flow_info.nodes:
            if node.node_id in start_nodes:
                start_node = node.var_name
                break

    # Find end node inline
    end_node = "None"
    for node in flow_info.nodes:
        if node.node_type == "ChatOutput" and node.node_id in end_nodes:
            end_node = node.var_name
            break
    if end_node == "None":
        for node in flow_info.nodes:
            if node.node_id in end_nodes:
                end_node = node.var_name
                break

    lines.append("")
    lines.append("    # === Build Graph ===")
    lines.append(f"    return Graph({start_node}, {end_node})")
    lines.append("")


def _generate_get_graph_function(lines: list[str], flow_name: str) -> None:
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


def _generate_main_block(lines: list[str], flow_name: str) -> None:
    """Generate the if __name__ == '__main__' block."""
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append(f"    graph = build_{flow_name}_graph()")
    lines.append('    print(f"Graph: {len(graph.vertices)} nodes, {len(graph.edges)} edges")')
    lines.append("    for v in graph.vertices:")
    lines.append('        print(f"  - {v.id}: {type(v.custom_component).__name__}")')
    lines.append("")
