import os
from collections import defaultdict
from typing import Any

# Constants for code generation
IGNORE_LINT = "# ruff: noqa"
FILE_COMMENT = "# This file is auto-generated from a flow JSON file by generate_flow_vc."
FILE_PREFIX = f"{FILE_COMMENT}\n{IGNORE_LINT}\n"

HELPERS_CODE = """\
async def set_component_inputs_and_run(component: Component, inputs: dict | None = None):
    if inputs:
        component.build(**inputs)
    await component.run()
"""

# Constants for node classification
CHAT_INPUT_TYPES = {"chatinput", "textinput", "message"}
MERMAID_FILENAME = "mermaid_graph.txt"
COMPONENTS_DIR = "components"
FLOW_FILENAME = "flow.py"


def _escape_mermaid_display_name(display_name: str) -> str:
    """Escape special characters in display names for Mermaid syntax."""
    return display_name.replace('"', '\\"').replace("\n", " ").replace("\r", "").strip()


def _generate_mermaid_diagram(
    flow_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    dest_folder: str,
) -> str:
    mermaid_lines = ["graph TD", f"    subgraph {flow_name}"]

    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        display_name = node["data"].get("display_name", node_id)
        safe_display_name = _escape_mermaid_display_name(display_name)
        mermaid_lines.append(f'        {node_id}["{safe_display_name}"]')

    for edge in edges:
        src = _fix_node_id(edge["source"])
        tgt = _fix_node_id(edge["target"])
        mermaid_lines.append(f"        {src} --> {tgt}")

    mermaid_lines.append("    end")
    mermaid_text = "\n".join(mermaid_lines)
    mermaid_file_path = os.path.join(dest_folder, MERMAID_FILENAME)
    _write_file(mermaid_file_path, mermaid_text)
    return mermaid_file_path


def _build_node_dependency_map(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a mapping of node dependencies and targets from edges."""
    node_map = {}
    for node in nodes:
        node_id = node["data"]["id"]
        node_map[node_id] = {
            "id": node_id,
            "dependencies": [],
            "targets": [],
        }

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        node_map[tgt]["dependencies"].append(src)
        node_map[src]["targets"].append(tgt)

    return node_map


def _find_available_nodes(node_map: dict[str, dict[str, Any]], processed_ids: set[str]) -> list[tuple[str, int]]:
    """Find nodes without remaining dependencies, sorted by targets count (desc) then by ID (asc)."""
    available_nodes = []
    for node_id, node_info in node_map.items():
        if node_id in processed_ids:
            continue
        remaining_deps = [dep for dep in node_info["dependencies"] if dep not in processed_ids]
        if not remaining_deps:
            available_nodes.append((node_id, len(node_info["targets"])))

    available_nodes.sort(key=lambda x: (-x[1], x[0]))
    return available_nodes


def _topological_sort_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return nodes sorted in topological order based on edges."""
    node_id_map = {node["data"]["id"]: node for node in nodes}
    node_map = _build_node_dependency_map(nodes, edges)
    sorted_nodes = []
    processed_ids = set()

    while len(sorted_nodes) < len(nodes):
        available_nodes = _find_available_nodes(node_map, processed_ids)

        if not available_nodes:
            raise ValueError("Graph has cycles or disconnected components")

        for node_id, _ in available_nodes:
            sorted_nodes.append(node_id_map[node_id])
            processed_ids.add(node_id)

    return sorted_nodes


def _extract_edge_handles(edge: dict[str, Any]) -> tuple[str, str]:
    """Extract source and target handles from an edge."""
    src_handle = edge["data"].get("sourceHandle", {}).get("name", "output")
    tgt_handle = edge["data"].get("targetHandle", {}).get("fieldName", "input")
    return src_handle, tgt_handle


def _build_input_and_output_maps(
    edges: list[dict[str, Any]],
    node_id_to_class_name: dict[str, str],
) -> tuple[dict[str, dict[str, tuple[str, str]]], list[str]]:
    input_map: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    reverse_dependency_graph: dict[str, set[str]] = defaultdict(set)

    for edge in edges:
        src = _fix_node_id(edge["source"])
        tgt = _fix_node_id(edge["target"])
        src_handle, tgt_handle = _extract_edge_handles(edge)
        reverse_dependency_graph[src].add(tgt)
        input_map[tgt][tgt_handle] = (src, src_handle)

    all_node_ids = set(node_id_to_class_name.keys())
    output_nodes = [nid for nid in all_node_ids if not reverse_dependency_graph[nid]]
    return input_map, output_nodes


def _build_component_inputs(
    node_id: str,
    input_map: dict[str, dict[str, tuple[str, str]]],
    node: dict[str, Any],
    chat_input_nodes: list[str],
) -> dict[str, str]:
    """Build input dictionary for a component."""
    input_dict = {}
    has_input_value = False

    for input_name, (src_node_id, src_output) in input_map.get(node_id, {}).items():
        input_dict[input_name] = f"components['{src_node_id}'].{src_output}.value"
        has_input_value = True

    input_dict = _process_template_inputs(node, input_dict)

    if node_id in chat_input_nodes and not has_input_value:
        default_value = input_dict.get("input_value", '""')
        input_dict["input_value"] = f"flow_input or {default_value}"

    return input_dict


def _generate_component_call_lines(node_id: str, input_dict: dict[str, str]) -> list[str]:
    """Generate lines for calling a component with inputs."""
    if not input_dict:
        return []

    input_items = [f"'{key}': {value}" for key, value in input_dict.items()]
    lines = [
        "    await set_component_inputs_and_run(",
        f"        components['{node_id}'],",
        "        {",
    ]
    for input_item in input_items:
        lines.append(f"            {input_item},")
    lines.extend(["        }", "    )"])
    return lines


def _generate_function_signature_and_setup(flow_dict: dict[str, Any]) -> list[str]:
    """Generate the function signature and initial setup code."""
    return [
        f"""async def run(
    flow_input: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None, flow_name: str | None = None,
    flow_id: str | None = None,
    env_values: dict | None = None
):
    env_values = env_values or os.environ.copy()
    global_state = {{
        "_session_id": session_id or str(uuid4()),
        "_user_id": user_id,
        "_flow_name": flow_name or "{flow_dict["name"]}",
        "_flow_id": flow_id or "{flow_dict["id"]}",
    }}
    components: dict[str, Component] = {{}}
    results = {{
        "outputs": {{}},
        "components": {{}},
        "global_state": global_state,
    }}
    """,
    ]


def _generate_component_initialization_lines(nodes: list[dict[str, Any]]) -> list[str]:
    """Generate lines for initializing all components."""
    lines = ["    # Initialize all components"]
    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        has_code = node["data"]["node"]["template"].get("code", {}).get("value")
        if has_code:
            lines.append(f"    components['{node_id}'] = _{node_id}(**global_state)")
    return lines


def _generate_execution_lines(
    flow_dict: dict[str, Any],
    nodes: list[dict[str, Any]],
    input_map: dict[str, dict[str, tuple[str, str]]],
    chat_input_nodes: list[str],
) -> list[str]:
    execution_lines = []
    execution_lines.extend(_generate_function_signature_and_setup(flow_dict))
    execution_lines.extend(_generate_component_initialization_lines(nodes))
    execution_lines.append("\n\n    # Set inputs and run components in topological order")

    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        input_dict = _build_component_inputs(node_id, input_map, node, chat_input_nodes)
        execution_lines.extend(_generate_component_call_lines(node_id, input_dict))

    return execution_lines


def _generate_imports(node_id_to_class_name: dict[str, str]) -> list[str]:
    imports = []
    for node_id, class_name in node_id_to_class_name.items():
        if not class_name:
            continue
        imports.append(f"from components.{node_id} import {class_name} as _{node_id}")
    return imports


def _generate_result_lines(output_nodes: list[str], node_id_to_outputs: dict[str, list[str]]) -> list[str]:
    result_lines = ["\n\n    # Collect results from output nodes"]
    output_nodes.sort()

    for node_id in output_nodes:
        for output_name in node_id_to_outputs.get(node_id, []):
            result_lines.append(
                f"    results['outputs']['{node_id}.{output_name}'] = components['{node_id}'].{output_name}",
            )

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
        for node_id, component in components.items()
    }""")
    result_lines.append("    return results")
    return result_lines


def _compose_main_code(
    flow_dict: dict[str, Any],
    components_imports: list[str],
    execution_lines: list[str],
    result_lines: list[str],
) -> str:
    code = f"""{FILE_PREFIX}
import asyncio
import os
import sys
from uuid import uuid4
import json
from langflow.custom.custom_component.component import Component
import argparse
{chr(10).join(components_imports)}

{HELPERS_CODE}

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
    parser = argparse.ArgumentParser(description='Run the {flow_dict["name"]} flow')
    parser.add_argument('--flow-input', type=str, default='', help='Input for the flow')
    parser.add_argument('--session-id', type=str, default=str(uuid4()), help='Session ID for the flow')
    parser.add_argument('--user-id', type=str, default=None, help='User ID for the flow')
    parser.add_argument('--flow-name', type=str, default=None, help='Flow name')
    parser.add_argument('--flow-id', type=str, default=None, help='Flow ID')
    args = parser.parse_args()
    result = asyncio.run(run(**vars(args)))
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


def _extract_class_name_from_code(code: str) -> str | None:
    """Extract the class name from Python code."""
    for line in code.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("class "):
            class_name = stripped_line.split()[1].split("(")[0]
            return class_name.strip(":")
    return None


def _write_component_files(nodes: list[dict[str, Any]], dest_folder: str) -> dict[str, str]:
    """Write individual component files for each node.

    Args:
        nodes: List of node data from the flow
        dest_folder: Destination folder for component files

    Returns:
        Mapping of node IDs to their class names
    """
    components_dir = os.path.join(dest_folder, COMPONENTS_DIR)
    _ensure_dir(components_dir)
    node_id_to_class_name = {}

    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        code = node["data"]["node"]["template"].get("code", {}).get("value", "")
        if not code:
            continue

        file_path = os.path.join(components_dir, f"{node_id}.py")
        _write_file(file_path, FILE_PREFIX + code)

        class_name = _extract_class_name_from_code(code)
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


def _is_chat_input_node(base_classes: list[str]) -> bool:
    """Check if a node is a chat input type based on its base classes."""
    return any(cls.lower() in CHAT_INPUT_TYPES for cls in base_classes)


def _identify_chat_input_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    """Identify nodes that are chat input, text input, or message types."""
    chat_input_nodes = []
    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        base_classes = node["data"]["node"].get("base_classes", [])
        if _is_chat_input_node(base_classes):
            chat_input_nodes.append(node_id)
    return chat_input_nodes


def _should_process_template_value(key: str, value: Any, input_dict: dict[str, str]) -> bool:
    """Check if a template value should be processed."""
    if key in input_dict:
        return False
    return isinstance(value, dict) and "_input_type" in value


def _process_environment_value(value: dict[str, Any]) -> str:
    """Process environment variable values."""
    env_key = value.get("value", "")
    return f'env_values.get("{env_key}", "")' if env_key else '""'


def _process_template_inputs(
    node: dict[str, Any],
    input_dict: dict[str, str],
) -> dict[str, str]:
    """Process template inputs for a node, handling environment variables and default values.

    Args:
        node: The node data containing template information
        input_dict: Existing input dictionary from edge connections

    Returns:
        Updated input dictionary with template inputs processed
    """
    template = node["data"]["node"].get("template", {})

    for key, value in template.items():
        if not _should_process_template_value(key, value, input_dict):
            continue

        if value.get("load_from_db"):
            input_dict[key] = _process_environment_value(value)
        else:
            input_dict[key] = repr(value.get("value") if "value" in value else value)

    return input_dict


def _write_main_file(
    flow_dict: dict[str, Any],
    node_id_to_class_name: dict[str, str],
    dest_folder: str,
    nodes: list[dict[str, Any]],
) -> None:
    """Generate the main flow execution file.

    Args:
        flow_dict: The complete flow dictionary
        node_id_to_class_name: Mapping of node IDs to their class names
        dest_folder: Destination folder for the generated file
        nodes: List of node data for processing
    """
    edges = flow_dict["data"]["edges"]
    imports = _generate_imports(node_id_to_class_name)
    input_map, output_nodes = _build_input_and_output_maps(edges, node_id_to_class_name)
    node_id_to_outputs = _extract_node_outputs(nodes)
    chat_input_nodes = _identify_chat_input_nodes(nodes)
    execution_lines = _generate_execution_lines(flow_dict, nodes, input_map, chat_input_nodes)
    result_lines = _generate_result_lines(output_nodes, node_id_to_outputs)
    main_code = _compose_main_code(flow_dict, imports, execution_lines, result_lines)
    _write_file(os.path.join(dest_folder, FLOW_FILENAME), main_code)


def _clean_destination_folder(dest_folder: str) -> None:
    """Remove all files and folders from the destination folder."""
    if not os.path.exists(dest_folder):
        return

    for root, dirs, files in os.walk(dest_folder, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


def export_flow_as_code(flow_dict: dict[str, Any], dest_folder: str) -> None:
    """Main function to generate flow components, runner, and Mermaid diagram from JSON flow file.

    Args:
        flow_dict: flow JSON
        dest_folder: Destination folder for generated files

    Generated files:
        - Component Python files in components/ subdirectory
        - flow.py: Main flow runner script
        - mermaid_graph.txt: Mermaid diagram source text
    """
    _clean_destination_folder(dest_folder)
    _ensure_dir(dest_folder)

    flow_name = flow_dict["name"]
    nodes = flow_dict["data"]["nodes"]
    edges = flow_dict["data"]["edges"]

    nodes = _topological_sort_nodes(nodes, edges)
    flow_dict["data"]["nodes"] = nodes

    node_id_to_class_name = _write_component_files(nodes, dest_folder)
    _write_main_file(flow_dict, node_id_to_class_name, dest_folder, nodes)
    _generate_mermaid_diagram(flow_name, nodes, edges, dest_folder)
