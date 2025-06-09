#!/usr/bin/env python3
"""
Script to add selected_output fields to Langflow JSON template files.
This analyzes edge connections to determine which outputs are being used.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Set


def load_json_file(file_path: str) -> dict:
    """Load and parse a JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(file_path: str, data: dict) -> None:
    """Save data to a JSON file with proper formatting."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def analyze_edges_for_outputs(edges: List[dict]) -> Dict[str, str]:
    """
    Analyze edges to determine which output is selected for each node.
    Returns: {node_id: output_name}
    """
    node_outputs = {}

    for edge in edges:
        if "data" in edge and "sourceHandle" in edge["data"]:
            source_handle = edge["data"]["sourceHandle"]
            if isinstance(source_handle, dict):
                node_id = source_handle.get("id")
                output_name = source_handle.get("name")
                if node_id and output_name:
                    node_outputs[node_id] = output_name

    return node_outputs


def add_selected_output_to_node(node: dict, selected_output: str) -> None:
    """Add selected_output field to a node."""
    if "data" in node:
        node["data"]["selected_output"] = selected_output


def process_json_file(file_path: str) -> bool:
    """
    Process a single JSON file to add selected_output fields.
    Returns True if changes were made.
    """
    try:
        data = load_json_file(file_path)

        if (
            "data" not in data
            or "edges" not in data["data"]
            or "nodes" not in data["data"]
        ):
            return False

        edges = data["data"]["edges"]
        nodes = data["data"]["nodes"]

        # Analyze which outputs are being used
        selected_outputs = analyze_edges_for_outputs(edges)

        if not selected_outputs:
            return False

        changes_made = False

        # Add selected_output to each node
        for node in nodes:
            if "data" in node and "id" in node["data"]:
                node_id = node["data"]["id"]
                if node_id in selected_outputs:
                    selected_output = selected_outputs[node_id]
                    # Only add if not already present or different
                    current_selected = node["data"].get("selected_output")
                    if current_selected != selected_output:
                        add_selected_output_to_node(node, selected_output)
                        changes_made = True
                        print(
                            f"  Added selected_output '{selected_output}' to node {node_id}"
                        )

        if changes_made:
            save_json_file(file_path, data)

        return changes_made

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to process all JSON files."""
    starter_projects_dir = "src/backend/base/langflow/initial_setup/starter_projects"

    if not os.path.exists(starter_projects_dir):
        print(f"Directory not found: {starter_projects_dir}")
        return

    json_files = list(Path(starter_projects_dir).glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {starter_projects_dir}")
        return

    print(f"Processing {len(json_files)} JSON files...")

    total_changed = 0
    for json_file in sorted(json_files):
        print(f"\nProcessing: {json_file.name}")
        if process_json_file(str(json_file)):
            total_changed += 1
            print(f"  ✓ Updated {json_file.name}")
        else:
            print(f"  - No changes needed for {json_file.name}")

    print(f"\n✅ Complete! Updated {total_changed} out of {len(json_files)} files.")


if __name__ == "__main__":
    main()
