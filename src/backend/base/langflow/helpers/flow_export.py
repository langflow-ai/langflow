import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Constants for code generation
IGNORE_LINT = "# ruff: noqa"
FILE_COMMENT = "# This file is auto-generated from a flow JSON file by generate_flow_vc."
FILE_PREFIX = f"{FILE_COMMENT}\n{IGNORE_LINT}\n"
MERMAID_FILENAME = "mermaid_graph.txt"
COMPONENTS_DIR = "components"
FLOW_FILENAME = "flow.py"


def _generate_mermaid_diagram(
    flow_dict: dict[str, Any],
    dest_folder: str,
) -> str:
    nodes = flow_dict["data"]["nodes"]
    edges = flow_dict["data"]["edges"]
    flow_name = flow_dict["name"]
    mermaid_lines = ["graph TD", f"    subgraph {flow_name}"]

    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        display_name = node["data"].get("display_name", node_id)
        safe_display_name = display_name.replace('"', '\\"').replace("\n", " ").replace("\r", "").strip()
        mermaid_lines.append(f'        {node_id}["{safe_display_name}"]')

    for edge in edges:
        src = _fix_node_id(edge["source"])
        tgt = _fix_node_id(edge["target"])
        mermaid_lines.append(f"        {src} --> {tgt}")

    mermaid_lines.append("    end")
    mermaid_text = "\n".join(mermaid_lines)
    mermaid_file_path = Path(dest_folder) / MERMAID_FILENAME
    _write_file(mermaid_file_path, mermaid_text)
    return mermaid_file_path


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


def _topological_sort_nodes(flow_dict: dict):
    """Return nodes sorted in topological order based on edges."""
    nodes = flow_dict["data"]["nodes"]
    edges = flow_dict["data"]["edges"]
    node_map = {}
    input_map: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)

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
        src_handle = edge["data"].get("sourceHandle", {}).get("name", "output")
        tgt_handle = edge["data"].get("targetHandle", {}).get("fieldName", "input")
        input_map[_fix_node_id(edge["target"])][tgt_handle] = (_fix_node_id(src), src_handle)

    node_id_map = {node["data"]["id"]: node for node in nodes}
    sorted_nodes = []
    processed_ids = set()

    while len(sorted_nodes) < len(nodes):
        available_nodes = _find_available_nodes(node_map, processed_ids)

        if not available_nodes:
            error_msg = "Graph has cycles or disconnected components"
            raise ValueError(error_msg)

        for node_id, _ in available_nodes:
            sorted_nodes.append(node_id_map[node_id])
            processed_ids.add(node_id)

    flow_dict["data"]["nodes"] = sorted_nodes
    return flow_dict, input_map


def _build_component_inputs(
    node_id: str,
    input_map: dict[str, dict[str, tuple[str, str]]],
    node: dict[str, Any],
) -> dict[str, str]:
    """Build input dictionary for a component."""
    template = node["data"]["node"].get("template", {})
    input_dict = {}
    for key, value in template.items():
        if key in input_dict or not isinstance(value, dict):
            continue
        if value.get("load_from_db"):
            env_key = value.get("value", "")
            input_dict[key] = f'env_values.get("{env_key}", "")' if env_key else '""'
        else:
            val = value.get("value") if "value" in value else value
            if val is not None and val != "":
                input_dict[key] = repr(val)

    # remove all None or empty string values
    input_dict = {k: v for k, v in input_dict.items() if v not in {None, "", "None", '""'}}
    for input_name, (_src_node_id, _src_output) in input_map.get(node_id, {}).items():
        if input_name in input_dict:
            input_dict.pop(input_name)
    input_dict.pop("code")
    return input_dict


def _write_file(path: str | Path, content: str) -> None:
    """Write content to a file, creating directories if necessary."""
    path = Path(path)
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        f.write(content.replace("\r\n", "\n"))


def _ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


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
    components_dir = Path(dest_folder) / COMPONENTS_DIR
    _ensure_dir(components_dir)
    node_id_to_class_name = {}

    for node in nodes:
        node_id = _fix_node_id(node["data"]["id"])
        code = node["data"]["node"]["template"].get("code", {}).get("value", "")
        if not code:
            continue

        file_path = components_dir / f"{node_id}.py"
        _write_file(file_path, FILE_PREFIX + code)

        class_name = _extract_class_name_from_code(code)
        node_id_to_class_name[node_id] = class_name or node_id

    return node_id_to_class_name


def _clean_destination_folder(dest_folder: str) -> None:
    """Remove all files and folders from the destination folder."""
    dest_path = Path(dest_folder)
    _ensure_dir(dest_folder)
    if not dest_path.exists():
        return

    for root, dirs, files in os.walk(dest_folder, topdown=False):
        for name in files:
            (Path(root) / name).unlink()
        for name in dirs:
            (Path(root) / name).rmdir()
    _ensure_dir(dest_folder)


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
    flow_dict, input_map = _topological_sort_nodes(flow_dict)
    nodes = flow_dict["data"]["nodes"]
    edges = flow_dict["data"]["edges"]
    node_id_to_class_name = _write_component_files(nodes, dest_folder)
    components_imports = [
        f"from components.{node_id} import {class_name} as _{node_id}"
        for node_id, class_name in node_id_to_class_name.items()
        if class_name
    ]
    components_instances = []
    for node in nodes:
        if not node["data"]["node"]["template"].get("code", {}).get("value"):
            continue
        node_id = _fix_node_id(node["data"]["id"])
        class_name = "_" + _fix_node_id(node["data"]["id"])
        inputs = _build_component_inputs(
            node_id,
            input_map,
            node,
        )
        input_items = [f"'{key}': {value}," for key, value in inputs.items()]
        inputs_str = "\n        ".join(input_items)
        components_instances.append(
            f"""\n    components['{node_id}'] = {class_name}(**{{**global_state, **{{"_id": '{node["data"]["id"]}'}}}})""",
        )
        components_instances.append(
            f"""\n    components['{node_id}'].set(**{{
        {inputs_str}
    }})""",
        )
        edges_values = [
            json.dumps({"source": edge["source"], "target": edge["target"], "data": edge["data"]}, indent=4)
            for edge in edges
        ]
        edges_setups = []
        for edge in edges_values:
            edges_setups.append(
                f"""    graph.add_edge({edge.replace("\n", "\n    ")})""",
            )

    main_code = f"""{FILE_PREFIX}
import anyio
import os
import sys
from uuid import uuid4
import json
from langflow.custom.custom_component.component import Component
from langflow.graph.graph.base import Graph
import argparse
{chr(10).join(components_imports)}

def get_graph(
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

    # Initialize all components
{"".join(components_instances)}
    graph = Graph()
    for component in components.values():
        graph.add_component(component)
{"\n".join(edges_setups)}
    graph.flow_id = global_state["_flow_id"]
    graph.flow_name = global_state["_flow_name"]
    graph.session_id = global_state["_session_id"]
    graph.user_id = global_state["_user_id"]
    graph.set_run_id(global_state["_session_id"])
    graph.initialize()
    return graph


def print_results_as_json(results):
    def convert_data_to_dict(data):
        if isinstance(data, dict):
            return {{k: convert_data_to_dict(v) for k, v in data.items()}}
        elif isinstance(data, list):
            return [convert_data_to_dict(item) for item in data]
        elif hasattr(data, 'model_dump'):
            return data.model_dump()
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
    parser = argparse.ArgumentParser(description='Run the language_test flow')
    parser.add_argument('--flow-input', type=str, default='', help='Input for the flow')
    parser.add_argument('--session-id', type=str, default=str(uuid4()), help='Session ID for the flow')
    parser.add_argument('--user-id', type=str, default=None, help='User ID for the flow')
    parser.add_argument('--flow-name', type=str, default=None, help='Flow name')
    parser.add_argument('--flow-id', type=str, default=None, help='Flow ID')
    args = parser.parse_args()
    graph = get_graph(
        session_id=args.session_id,
        user_id=args.user_id,
        flow_name=args.flow_name,
        flow_id=args.flow_id
    )
    inputs = {{ "input_value": args.flow_input }} if args.flow_input else {{}}
    result = anyio.run(graph.arun, inputs)
    print_results_as_json(result)
"""
    _write_file(Path(dest_folder) / FLOW_FILENAME, main_code)
    _generate_mermaid_diagram(flow_dict, dest_folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export a Langflow JSON file as executable Python code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python flow_export.py --input flow.json --output ./exported_flow
  python flow_export.py -i my_flow.json -o ./output --verbose
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Path to the input Langflow JSON file",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Output directory for generated Python code",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{args.input}' does not exist")
        sys.exit(1)

    if not input_path.suffix.lower() == ".json":
        print(f"Warning: Input file '{args.input}' does not have a .json extension")

    # Load the flow JSON
    try:
        with open(input_path, encoding="utf-8") as f:
            flow_dict = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file '{args.input}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read file '{args.input}': {e}")
        sys.exit(1)

    # Validate flow structure
    if not isinstance(flow_dict, dict):
        print("Error: Flow JSON must be a dictionary")
        sys.exit(1)

    if "name" not in flow_dict:
        print("Error: Flow JSON must contain a 'name' field")
        sys.exit(1)

    if "data" not in flow_dict or "nodes" not in flow_dict["data"] or "edges" not in flow_dict["data"]:
        print("Error: Flow JSON must contain 'data.nodes' and 'data.edges' fields")
        sys.exit(1)

    # Create output directory
    output_path = Path(args.output)

    if args.verbose:
        print(f"Input file: {input_path.absolute()}")
        print(f"Output directory: {output_path.absolute()}")
        print(f"Flow name: {flow_dict['name']}")
        print(f"Number of nodes: {len(flow_dict['data']['nodes'])}")
        print(f"Number of edges: {len(flow_dict['data']['edges'])}")

    try:
        # Export the flow as code
        export_flow_as_code(flow_dict, str(output_path))

        if args.verbose:
            print(f"\nSuccessfully exported flow to: {output_path.absolute()}")
            print("Generated files:")
            for file_path in output_path.rglob("*"):
                if file_path.is_file():
                    print(f"  - {file_path.relative_to(output_path)}")
        else:
            print(f"Successfully exported flow to: {output_path.absolute()}")

    except Exception as e:
        print(f"Error: Failed to export flow: {e}")
        sys.exit(1)
