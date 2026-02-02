"""Tests for converting all starter project flows.

Verifies that the CLI converter can successfully convert all JSON flows
from the starter_projects directory to valid Python code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lfx.cli.convert.command import convert_flow_to_python

STARTER_PROJECTS_PATH = Path(__file__).parents[6] / "backend/base/langflow/initial_setup/starter_projects"


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

    def test_should_have_builder_function(self, flow_path: Path) -> None:
        """Verify generated code has build_*_graph function."""
        result = convert_flow_to_python(flow_path)
        assert "def build_" in result
        assert "_graph(" in result
        assert ") -> Graph:" in result

    def test_should_have_get_graph_entrypoint(self, flow_path: Path) -> None:
        """Verify generated code has get_graph() entry point."""
        result = convert_flow_to_python(flow_path)
        assert "def get_graph() -> Graph:" in result

    def test_should_have_main_block(self, flow_path: Path) -> None:
        """Verify generated code has __main__ block."""
        result = convert_flow_to_python(flow_path)
        assert 'if __name__ == "__main__":' in result


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
            pytest.fail(
                f"Failed to convert {len(failures)}/{len(flows)} flows:\n{failure_report}"
            )

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
                results.append({
                    "name": flow_path.stem,
                    "status": "OK",
                    "lines": len(result.splitlines()),
                })
            except Exception as e:
                results.append({
                    "name": flow_path.stem,
                    "status": "FAIL",
                    "error": str(e)[:100],
                })

        success_count = sum(1 for r in results if r["status"] == "OK")
        print(f"\n{'='*60}")
        print(f"Conversion Summary: {success_count}/{len(flows)} successful")
        print(f"{'='*60}")

        for r in results:
            if r["status"] == "OK":
                print(f"  ✓ {r['name']} ({r['lines']} lines)")
            else:
                print(f"  ✗ {r['name']}: {r.get('error', 'Unknown error')}")

        assert success_count == len(flows)
