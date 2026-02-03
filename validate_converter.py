#!/usr/bin/env python3
"""Validate that lfx convert generates graphs with correct structure.

This script converts all JSON flows in starter_projects and verifies
that the generated Python code creates graphs with matching node/edge counts.

Usage:
    uv run python validate_converter.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

STARTER_PROJECTS_PATH = Path(__file__).parent / "src/backend/base/langflow/initial_setup/starter_projects"
SKIP_NODE_TYPES = {"note", "Note"}


def count_json_nodes_and_edges(flow_path: Path) -> tuple[int, int]:
    """Count nodes and edges from JSON file."""
    with flow_path.open() as f:
        data = json.load(f)

    flow_data = data.get("data", data)
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])

    valid_nodes = [
        n for n in nodes
        if n.get("data", {}).get("type") not in SKIP_NODE_TYPES
        and n.get("data", {}).get("type") is not None
    ]

    return len(valid_nodes), len(edges)


def extract_graph_function_name(code: str) -> str | None:
    """Extract the *_graph function name from generated code."""
    match = re.search(r"def (\w+_graph)\(\)", code)
    return match.group(1) if match else None


def execute_and_get_graph(code: str, func_name: str):
    """Execute generated code and return the graph object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.write(f"\n\ngraph = {func_name}()\n")
        temp_path = f.name

    temp_module_name = f"_temp_validate_{Path(temp_path).stem}"
    try:
        spec = importlib.util.spec_from_file_location(temp_module_name, temp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[temp_module_name] = module
        spec.loader.exec_module(module)
        return module.graph
    finally:
        Path(temp_path).unlink(missing_ok=True)
        sys.modules.pop(temp_module_name, None)


def validate_all_flows():
    """Validate all starter project flows."""
    from lfx.cli.convert.command import convert_flow_to_python

    flows = sorted(STARTER_PROJECTS_PATH.glob("*.json"))
    if not flows:
        print(f"No JSON files found in {STARTER_PROJECTS_PATH}")
        return 1

    results = []
    for flow_path in flows:
        try:
            expected_nodes, expected_edges = count_json_nodes_and_edges(flow_path)
            code = convert_flow_to_python(flow_path)
            func_name = extract_graph_function_name(code)

            if func_name is None:
                results.append({
                    "name": flow_path.stem,
                    "status": "FAIL",
                    "error": "No graph function found",
                })
                continue

            graph = execute_and_get_graph(code, func_name)
            actual_nodes = len(graph.vertices)
            actual_edges = len(graph.edges)

            if actual_nodes == expected_nodes and actual_edges == expected_edges:
                results.append({
                    "name": flow_path.stem,
                    "status": "OK",
                    "nodes": actual_nodes,
                    "edges": actual_edges,
                })
            else:
                results.append({
                    "name": flow_path.stem,
                    "status": "MISMATCH",
                    "expected_nodes": expected_nodes,
                    "expected_edges": expected_edges,
                    "actual_nodes": actual_nodes,
                    "actual_edges": actual_edges,
                })
        except Exception as e:
            results.append({
                "name": flow_path.stem,
                "status": "ERROR",
                "error": str(e)[:100],
            })

    # Print results
    success_count = sum(1 for r in results if r["status"] == "OK")
    print(f"\n{'=' * 70}")
    print(f"Graph Structure Validation: {success_count}/{len(flows)} OK")
    print(f"{'=' * 70}")

    for r in results:
        if r["status"] == "OK":
            print(f"  ✓ {r['name']} ({r['nodes']} nodes, {r['edges']} edges)")
        elif r["status"] == "MISMATCH":
            print(f"  ✗ {r['name']}: expected {r['expected_nodes']}N/{r['expected_edges']}E, "
                  f"got {r['actual_nodes']}N/{r['actual_edges']}E")
        else:
            print(f"  ✗ {r['name']}: {r.get('error', 'Unknown error')}")

    print(f"\n{'=' * 70}")
    if success_count == len(flows):
        print("✅ All flows validated successfully!")
        return 0
    else:
        print(f"❌ {len(flows) - success_count} flows failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(validate_all_flows())
