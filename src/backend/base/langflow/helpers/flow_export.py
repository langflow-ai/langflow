import os
from collections import defaultdict
from typing import Any

ignore_lint = "# ruff: noqa"
file_comment = "# This file is auto-generated from a flow JSON file by generate_flow_vc."
file_prefix = f"{file_comment}\n{ignore_lint}\n"
helpers_code: str = """\
async def set_component_inputs_and_run(component: Component, inputs: dict | None = None):
    if inputs:
        component.build(**inputs)
    await component.run()
"""


def _generate_mermaid_diagram(
    flow_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    dest_folder: str,
) -> str:
    mermaid_lines = ["graph TD", f"    subgraph {flow_name}"]

    # Add nodes with their display names
    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        display_name = node["data"].get("display_name", node_id)
        # Escape special characters in display names for Mermaid
        safe_display_name = display_name.replace('"', '\\"').replace("\n", " ").replace("\r", "").strip()
        mermaid_lines.append(f'        {node_id}["{safe_display_name}"]')

    # Add edges with their connections
    for edge in edges:
        src = _fix_node_id(edge["source"])
        tgt = _fix_node_id(edge["target"])
        mermaid_lines.append(f"        {src} --> {tgt}")
    mermaid_lines.append("    end")
    mermaid_text = "\n".join(mermaid_lines)
    mermaid_file_path = os.path.join(dest_folder, "mermaid_graph.txt")
    _write_file(mermaid_file_path, mermaid_text)
    return mermaid_file_path


def _topological_sort_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Return nodes sorted in topological order based on edges.
    """
    node_id_map = {node["data"]["id"]: node for node in nodes}

    # Build node dependency map
    node_map = {}
    for node in nodes:
        node_id = node["data"]["id"]
        node_map[node_id] = {
            "id": node_id,
            "dependencies": [],
            "targets": [],
        }

    # Fill dependencies and targets from edges
    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        node_map[tgt]["dependencies"].append(src)
        node_map[src]["targets"].append(tgt)

    sorted_nodes = []
    processed_ids = set()

    while len(sorted_nodes) < len(nodes):
        # Find nodes without remaining dependencies
        available_nodes = []
        for node_id, node_info in node_map.items():
            if node_id in processed_ids:
                continue
            remaining_deps = [dep for dep in node_info["dependencies"] if dep not in processed_ids]
            if not remaining_deps:
                available_nodes.append((node_id, len(node_info["targets"])))

        if not available_nodes:
            raise ValueError("Graph has cycles or disconnected components")

        # Sort by targets length desc, then by id asc
        available_nodes.sort(key=lambda x: (-x[1], x[0]))

        # Add available nodes to sorted list
        for node_id, _ in available_nodes:
            sorted_nodes.append(node_id_map[node_id])
            processed_ids.add(node_id)

    return sorted_nodes


def _build_input_and_output_maps(
    edges: list[dict[str, Any]],
    node_id_to_class_name: dict[str, str],
) -> tuple[dict[str, dict[str, tuple[str, str]]], list[str]]:
    input_map: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    reverse_dependency_graph: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        src: str = _fix_node_id(edge["source"])
        tgt: str = _fix_node_id(edge["target"])
        src_handle: str = edge["data"].get("sourceHandle", {}).get("name", "output")
        tgt_handle: str = edge["data"].get("targetHandle", {}).get("fieldName", "input")
        reverse_dependency_graph[src].add(tgt)
        input_map[tgt][tgt_handle] = (src, src_handle)
    all_node_ids: set[str] = set(node_id_to_class_name.keys())
    output_nodes: list[str] = [nid for nid in all_node_ids if not reverse_dependency_graph[nid]]
    return input_map, output_nodes


def _generate_execution_lines(
    flow_dict: dict[str, Any],
    nodes: list[dict[str, Any]],
    input_map: dict[str, dict[str, tuple[str, str]]],
    chat_input_nodes: list[str],
) -> list[str]:
    execution_lines: list[str] = []
    execution_lines.append(f"""async def run(
    flow_input: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None, flow_name: str | None = None,
    flow_id: str | None = None
):
    global_state = {{
        "_session_id": session_id or str(uuid4()),
        "_user_id": user_id,
        "_flow_name": flow_name or "{flow_dict["name"]}",
        "_flow_id": flow_id or "{flow_dict["id"]}",
    }}
    results = {{
        "outputs": {{}},
        "components": {{}},
        "global_state": global_state,
    }}
    """)
    execution_lines.append("    # Initialize all components")
    for node in nodes:
        node_id: str = _fix_node_id(node["data"]["id"])
        class_name = node["data"]["node"]["template"].get("code", {}).get("value", None)
        if class_name:
            execution_lines.append(f"    {node_id} = _{node_id}(**global_state)")
            execution_lines.append(f"    results['components']['{node_id}'] = {node_id}")
    execution_lines.append("\n\n    # Set inputs and run components in topological order")
    for node in nodes:
        node_id: str = _fix_node_id(node["data"]["id"])
        input_dict: dict[str, str] = {}
        have_input_value = False
        for input_name, (src_id, src_output) in input_map.get(node_id, {}).items():
            input_dict[input_name] = f"{src_id}.{src_output}.value"
            have_input_value = True
        input_dict = _process_template_inputs(node, input_dict)
        if node_id in chat_input_nodes and not have_input_value:
            input_dict["input_value"] = f"flow_input or {input_dict.get('input_value', '""')}"
        if input_dict:
            input_items: list[str] = []
            for key, value in input_dict.items():
                input_items.append(f"'{key}': {value}")
            execution_lines.append("    await set_component_inputs_and_run(")
            execution_lines.append(f"        {node_id},")
            execution_lines.append("        {")
            for input_name in input_items:
                execution_lines.append(f"            {input_name},")
            execution_lines.append("        }")
            execution_lines.append("    )")
    return execution_lines


def _generate_imports(node_id_to_class_name: dict[str, str]) -> list[str]:
    imports = []
    for node_id, class_name in node_id_to_class_name.items():
        if not class_name:
            continue
        imports.append(f"from components.{node_id} import {class_name} as _{node_id}")
    return imports


def _generate_result_lines(output_nodes: list[str], node_id_to_outputs: dict[str, list[str]]) -> list[str]:
    result_lines: list[str] = []
    result_lines.append("\n\n    # Collect results from output nodes")
    output_nodes.sort()  # Ensure consistent order
    for node_id in output_nodes:
        for output_name in node_id_to_outputs.get(node_id, []):
            result_lines.append(f"    results['outputs']['{node_id}.{output_name}'] = {node_id}.{output_name}")
    result_lines.append("""    results["components"] = {
        node_id: {
            "id": component._id,
            "description": component.description,
            "display_name": component.display_name,
            "name": component.name,
            "trace_name": component.trace_name,
            "trace_type": component.trace_type,
            "outputs": component.outputs,
            "inputs": component.inputs,
        }
        for node_id, component in results["components"].items()
    }""")
    result_lines.append("    return results")
    return result_lines


def _compose_main_code(
    imports: list[str],
    execution_lines: list[str],
    result_lines: list[str],
) -> str:
    code = f"""{file_prefix}
import asyncio
import os
import sys
from uuid import uuid4
import json
from langflow.custom.custom_component.component import Component
{chr(10).join(imports)}

{helpers_code}

{chr(10).join(execution_lines)}
{chr(10).join(result_lines)}

def print_results_as_json(results):
    def convert_data_to_dict(data):
        if isinstance(data, dict):
            return {{k: convert_data_to_dict(v) for k, v in data.items()}}
        elif isinstance(data, list):
            return [convert_data_to_dict(item) for item in data]
        elif hasattr(data, 'dict'):
            return data.dict()
        elif hasattr(data, 'to_dict'):
            return data.to_dict()
        elif hasattr(data, 'to_json'):
            return json.loads(data.to_json())
        else:
            return data
    results = convert_data_to_dict(results)
    print(json.dumps(results, default=str, indent=2))

if __name__ == '__main__':
    flow_input = sys.argv[1] if len(sys.argv) > 1 else ''
    session_id = os.environ.get("SESSION_ID", str(uuid4()))
    result = asyncio.run(run(flow_input=flow_input, session_id=session_id))
    print_results_as_json(result)
"""
    return code


def _write_file(path: str, content: str) -> None:
    """Write content to a file, creating directories if necessary."""
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.replace("\r\n", "\n"))


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _fix_node_id(node_id: str) -> str:
    """Replace dashes and spaces with underscores for valid Python identifiers."""
    return node_id.replace("-", "_").replace(" ", "_")


def _write_component_files(nodes: list[dict[str, Any]], dest_folder: str) -> dict[str, str]:
    """
    Write individual component files for each node.

    Args:
        nodes: List of node data from the flow
        dest_folder: Destination folder for component files

    Returns:
        Mapping of node IDs to their class names
    """
    components_dir: str = os.path.join(dest_folder, "components")
    _ensure_dir(components_dir)
    node_id_to_class_name: dict[str, str] = {}
    for node in nodes:
        node_id: str = _fix_node_id(node["data"]["id"])
        code: str = node["data"]["node"]["template"].get("code", {}).get("value", "")
        if not code:
            continue
        file_path: str = os.path.join(components_dir, f"{node_id}.py")
        _write_file(file_path, file_prefix + code)
        # Try to extract class name
        lines: list[str] = code.splitlines()
        class_name: str | None = None
        for line in lines:
            if line.strip().startswith("class "):
                class_name = line.strip().split()[1].split("(")[0]
                class_name = class_name.strip(":")
                break
        node_id_to_class_name[node_id] = class_name or node_id
    return node_id_to_class_name


def _extract_node_outputs(nodes: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Extract output names for each node by node_id."""
    node_id_to_outputs: dict[str, list[str]] = {}
    for node in nodes:
        node_id: str = _fix_node_id(node["data"]["id"])
        outputs: list[dict[str, Any]] = node["data"]["node"].get("outputs", [])
        node_id_to_outputs[node_id] = [output.get("name") for output in outputs if output.get("name")]
    return node_id_to_outputs


def _identify_chat_input_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    """Identify nodes that are chat input, text input, or message types."""
    chat_input_nodes: list[str] = []
    for node in nodes:
        node_id: str = _fix_node_id(node["data"]["id"])
        node_type: list[str] = node["data"]["node"].get("base_classes", [])
        if any(cls.lower() in {"chatinput", "textinput", "message"} for cls in node_type):
            chat_input_nodes.append(node_id)
    return chat_input_nodes


def _process_template_inputs(
    node: dict[str, Any],
    input_dict: dict[str, str],
) -> dict[str, str]:
    """
    Process template inputs for a node, handling environment variables and default values.

    Args:
        node: The node data containing template information
        input_dict: Existing input dictionary from edge connections
        chat_input_nodes: List of node IDs that are chat input nodes

    Returns:
        Updated input dictionary with template inputs processed
    """
    template: dict[str, Any] = node["data"]["node"].get("template", {})

    for key, value in template.items():
        if key in input_dict:
            continue  # Already set by edge
        # Only set if _input_type property exists
        if not (isinstance(value, dict) and "_input_type" in value):
            continue
        # If the value is a dict with 'load_from_db', handle env var
        if value.get("load_from_db"):
            env_key: str = value.get("value", "")
            input_dict[key] = f'os.environ.get("{env_key}", "")'
        else:
            # Use the value directly, repr for correct Python literal
            input_dict[key] = repr(value.get("value") if "value" in value else value)
    return input_dict


def _write_main_file(
    flow_dict: dict[str, Any],
    node_id_to_class_name: dict[str, str],
    dest_folder: str,
    nodes: list[dict[str, Any]],
) -> None:
    """
    Generate the main flow execution file.

    Args:
        edges: List of edge connections between nodes
        node_id_to_class_name: Mapping of node IDs to their class names
        dest_folder: Destination folder for the generated file
        nodes: List of node data for processing
    """
    nodes: list[dict[str, Any]] = flow_dict["data"]["nodes"]
    edges: list[dict[str, Any]] = flow_dict["data"]["edges"]
    imports = _generate_imports(node_id_to_class_name)
    input_map, output_nodes = _build_input_and_output_maps(edges, node_id_to_class_name)
    node_id_to_outputs = _extract_node_outputs(nodes)
    chat_input_nodes = _identify_chat_input_nodes(nodes)
    execution_lines = _generate_execution_lines(flow_dict, nodes, input_map, chat_input_nodes)
    result_lines = _generate_result_lines(output_nodes, node_id_to_outputs)
    main_code = _compose_main_code(imports, execution_lines, result_lines)
    _write_file(os.path.join(dest_folder, "flow.py"), main_code)


def export_flow_as_code(flow_dict: dict[str, Any], dest_folder: str) -> None:
    """
    Main function to generate flow components, runner, and Mermaid diagram from JSON flow file.

    Args:
        flow_dict: flow JSON
        dest_folder: Destination folder for generated files

    Generated files:
        - Component Python files in components/ subdirectory
        - flow.py: Main flow runner script
        - mermaid_graph.txt: Mermaid diagram source text
    """
    # Remove all files and folders from dest_folder
    if os.path.exists(dest_folder):
        for root, dirs, files in os.walk(dest_folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
    _ensure_dir(dest_folder)
    flow_name = flow_dict["name"]
    nodes: list[dict[str, Any]] = flow_dict["data"]["nodes"]
    edges: list[dict[str, Any]] = flow_dict["data"]["edges"]
    nodes = _topological_sort_nodes(nodes, edges)
    flow_dict["data"]["nodes"] = nodes
    node_id_to_class_name: dict[str, str] = _write_component_files(nodes, dest_folder)
    _write_main_file(flow_dict, node_id_to_class_name, dest_folder, nodes)
    _generate_mermaid_diagram(flow_name, nodes, edges, dest_folder)
