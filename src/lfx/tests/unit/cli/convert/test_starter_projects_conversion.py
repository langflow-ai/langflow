"""Tests for converting all starter project flows.

Verifies that the CLI converter can successfully convert all JSON flows
from the starter_projects directory to valid Python code with correct graph structure.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from lfx.cli.convert.command import convert_flow_to_python

STARTER_PROJECTS_PATH = Path(__file__).parents[6] / "backend/base/langflow/initial_setup/starter_projects"
SKIP_NODE_TYPES = {"note", "Note"}


def get_all_starter_flows() -> list[Path]:
    """Get all JSON flow files from starter_projects directory."""
    if not STARTER_PROJECTS_PATH.exists():
        return []
    return sorted(STARTER_PROJECTS_PATH.glob("*.json"))


class TestStarterProjectsConversion:
    """Test conversion of all starter project flows."""

    @pytest.fixture(params=get_all_starter_flows(), ids=lambda p: p.stem)
    def flow_path(self, request: pytest.FixtureRequest) -> Path:
        """Parametrized fixture yielding each starter flow path."""
        return request.param

    def test_should_convert_to_valid_python(self, flow_path: Path) -> None:
        """Verify flow converts to syntactically valid Python code."""
        result = convert_flow_to_python(flow_path)

        try:
            compile(result, "<string>", "exec")
        except SyntaxError as e:
            pytest.fail(f"Syntax error in generated code: {e}")

    def test_should_have_graph_import(self, flow_path: Path) -> None:
        """Verify generated code imports Graph class."""
        result = convert_flow_to_python(flow_path)
        assert "from lfx.graph import Graph" in result

    def test_should_have_graph_function(self, flow_path: Path) -> None:
        """Verify generated code has *_graph function."""
        result = convert_flow_to_python(flow_path)
        assert "_graph():" in result
        assert "return Graph(start=" in result


class TestConversionCompleteness:
    """Test that all starter projects can be converted."""

    def test_should_convert_all_flows_without_errors(self) -> None:
        """Convert all flows and report any failures."""
        flows = get_all_starter_flows()
        if not flows:
            pytest.skip("No starter project flows found")

        failures: list[tuple[str, str]] = []
        successes: list[str] = []

        for flow_path in flows:
            try:
                result = convert_flow_to_python(flow_path)
                compile(result, "<string>", "exec")
                successes.append(flow_path.stem)
            except Exception as e:
                failures.append((flow_path.stem, str(e)[:200]))

        if failures:
            failure_report = "\n".join(f"  - {name}: {err}" for name, err in failures)
            pytest.fail(f"Failed to convert {len(failures)}/{len(flows)} flows:\n{failure_report}")

        assert len(successes) == len(flows)

    def test_should_report_conversion_summary(self) -> None:
        """Print summary of all flow conversions."""
        flows = get_all_starter_flows()
        if not flows:
            pytest.skip("No starter project flows found")

        results: list[dict] = []

        for flow_path in flows:
            try:
                result = convert_flow_to_python(flow_path)
                compile(result, "<string>", "exec")
                results.append(
                    {
                        "name": flow_path.stem,
                        "status": "OK",
                        "lines": len(result.splitlines()),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "name": flow_path.stem,
                        "status": "FAIL",
                        "error": str(e)[:100],
                    }
                )

        success_count = sum(1 for r in results if r["status"] == "OK")
        print(f"\n{'=' * 60}")
        print(f"Conversion Summary: {success_count}/{len(flows)} successful")
        print(f"{'=' * 60}")

        for r in results:
            if r["status"] == "OK":
                print(f"  ✓ {r['name']} ({r['lines']} lines)")
            else:
                print(f"  ✗ {r['name']}: {r.get('error', 'Unknown error')}")

        assert success_count == len(flows)


def _count_json_nodes_and_edges(flow_path: Path) -> tuple[int, int]:
    """Count nodes and edges from JSON file."""
    with flow_path.open() as f:
        data = json.load(f)

    flow_data = data.get("data", data)
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])

    # Filter out UI-only nodes (notes, etc.)
    valid_nodes = [
        n
        for n in nodes
        if n.get("data", {}).get("type") not in SKIP_NODE_TYPES and n.get("data", {}).get("type") is not None
    ]

    return len(valid_nodes), len(edges)


def _extract_graph_function_name(code: str) -> str | None:
    """Extract the *_graph function name from generated code."""
    match = re.search(r"def (\w+_graph)\(\)", code)
    return match.group(1) if match else None


def _execute_and_get_graph(code: str, func_name: str) -> Any:
    """Execute generated code and return the graph object."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.write(f"\n\ngraph = {func_name}()\n")
        temp_path = f.name

    try:
        temp_module_name = f"_temp_test_{Path(temp_path).stem}"
        import importlib.util

        spec = importlib.util.spec_from_file_location(temp_module_name, temp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[temp_module_name] = module
        spec.loader.exec_module(module)
        return module.graph
    finally:
        Path(temp_path).unlink(missing_ok=True)
        sys.modules.pop(temp_module_name, None)


class TestGraphStructureValidation:
    """Test that generated graphs have correct structure matching JSON."""

    @pytest.fixture(params=get_all_starter_flows(), ids=lambda p: p.stem)
    def flow_path(self, request: pytest.FixtureRequest) -> Path:
        """Parametrized fixture yielding each starter flow path."""
        return request.param

    def test_should_have_matching_node_count(self, flow_path: Path) -> None:
        """Verify generated graph has same number of nodes as JSON."""
        expected_nodes, _ = _count_json_nodes_and_edges(flow_path)
        code = convert_flow_to_python(flow_path)
        func_name = _extract_graph_function_name(code)

        assert func_name is not None, "Could not find graph function"

        graph = _execute_and_get_graph(code, func_name)
        actual_nodes = len(graph.vertices)

        assert actual_nodes == expected_nodes, f"Node count mismatch: expected {expected_nodes}, got {actual_nodes}"

    def test_should_have_matching_edge_count(self, flow_path: Path) -> None:
        """Verify generated graph has same number of edges as JSON."""
        _, expected_edges = _count_json_nodes_and_edges(flow_path)
        code = convert_flow_to_python(flow_path)
        func_name = _extract_graph_function_name(code)

        assert func_name is not None, "Could not find graph function"

        graph = _execute_and_get_graph(code, func_name)
        actual_edges = len(graph.edges)

        assert actual_edges == expected_edges, f"Edge count mismatch: expected {expected_edges}, got {actual_edges}"

    def test_should_report_structure_summary(self) -> None:
        """Print summary of graph structure validation for all flows."""
        flows = get_all_starter_flows()
        if not flows:
            pytest.skip("No starter project flows found")

        results: list[dict] = []

        for flow_path in flows:
            try:
                expected_nodes, expected_edges = _count_json_nodes_and_edges(flow_path)
                code = convert_flow_to_python(flow_path)
                func_name = _extract_graph_function_name(code)

                if func_name is None:
                    results.append(
                        {
                            "name": flow_path.stem,
                            "status": "FAIL",
                            "error": "No graph function found",
                        }
                    )
                    continue

                graph = _execute_and_get_graph(code, func_name)
                actual_nodes = len(graph.vertices)
                actual_edges = len(graph.edges)

                if actual_nodes == expected_nodes and actual_edges == expected_edges:
                    results.append(
                        {
                            "name": flow_path.stem,
                            "status": "OK",
                            "nodes": actual_nodes,
                            "edges": actual_edges,
                        }
                    )
                else:
                    results.append(
                        {
                            "name": flow_path.stem,
                            "status": "MISMATCH",
                            "expected": f"{expected_nodes}N/{expected_edges}E",
                            "actual": f"{actual_nodes}N/{actual_edges}E",
                        }
                    )
            except Exception as e:
                results.append(
                    {
                        "name": flow_path.stem,
                        "status": "ERROR",
                        "error": str(e)[:80],
                    }
                )

        success_count = sum(1 for r in results if r["status"] == "OK")
        print(f"\n{'=' * 70}")
        print(f"Graph Structure Validation: {success_count}/{len(flows)} matching")
        print(f"{'=' * 70}")

        for r in results:
            if r["status"] == "OK":
                print(f"  ✓ {r['name']} ({r['nodes']} nodes, {r['edges']} edges)")
            elif r["status"] == "MISMATCH":
                print(f"  ✗ {r['name']}: expected {r['expected']}, got {r['actual']}")
            else:
                print(f"  ✗ {r['name']}: {r.get('error', 'Unknown error')}")

        assert success_count == len(flows), f"Structure validation failed for {len(flows) - success_count} flows"
