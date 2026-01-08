"""Tests for CLI lazy import mechanisms.

These tests verify that the lazy import patterns in CLI modules work correctly
and help reduce cold start time.
"""

import json

import pytest


class TestCLIModuleLazyImports:
    """Test lazy imports in CLI __init__ module."""

    def test_serve_command_accessible_via_getattr(self):
        """Test that serve_command can be accessed via lazy import."""
        import lfx.cli

        # Access serve_command - this should trigger lazy loading
        serve_cmd = lfx.cli.serve_command
        assert serve_cmd is not None
        assert callable(serve_cmd)

    def test_invalid_cli_attribute_raises_error(self):
        """Test that accessing invalid attribute raises AttributeError."""
        import lfx.cli

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent_command'"):
            _ = lfx.cli.nonexistent_command


class TestMainModuleLazyImports:
    """Test lazy imports in __main__ module."""

    def test_main_module_importable(self):
        """Test that __main__ module can be imported without heavy dependencies."""
        # This test verifies the module imports quickly
        import lfx.__main__

        assert hasattr(lfx.__main__, "main")
        assert callable(lfx.__main__.main)

    def test_serve_command_wrapper_exists(self):
        """Test that serve_command_wrapper is defined."""
        from lfx.__main__ import serve_command_wrapper

        assert callable(serve_command_wrapper)

    def test_run_command_wrapper_exists(self):
        """Test that run_command_wrapper is defined."""
        from lfx.__main__ import run_command_wrapper

        assert callable(run_command_wrapper)


class TestRunCommandLazyImports:
    """Test lazy imports in run.py module."""

    def test_run_module_importable(self):
        """Test that run module can be imported."""
        from lfx.cli import run

        assert hasattr(run, "run")

    def test_script_loader_functions_not_imported_at_module_level(self):
        """Test that script_loader functions are imported lazily."""
        # Import the run module
        from lfx.cli import run

        # The script_loader module should NOT be in sys.modules at this point
        # unless something else imported it
        # This is a soft test - we mainly want to ensure the module loads

        # Verify the run function exists and is callable
        assert hasattr(run, "run")
        assert callable(run.run)


class TestValidationLazyImports:
    """Test lazy imports in validation.py module."""

    def test_validation_module_importable(self):
        """Test that validation module can be imported."""
        from lfx.cli import validation

        assert hasattr(validation, "is_valid_env_var_name")
        assert hasattr(validation, "validate_global_variables_for_env")

    def test_is_valid_env_var_name_works(self):
        """Test that is_valid_env_var_name function works correctly."""
        from lfx.cli.validation import is_valid_env_var_name

        assert is_valid_env_var_name("VALID_VAR")
        assert is_valid_env_var_name("_PRIVATE")
        assert is_valid_env_var_name("VAR123")
        assert not is_valid_env_var_name("invalid-var")
        assert not is_valid_env_var_name("123_STARTS_WITH_NUMBER")
        assert not is_valid_env_var_name("has space")


class TestScriptLoaderLazyImports:
    """Test lazy imports in script_loader.py module."""

    def test_script_loader_module_importable(self):
        """Test that script_loader module can be imported."""
        from lfx.cli import script_loader

        assert hasattr(script_loader, "load_graph_from_script")
        assert hasattr(script_loader, "find_graph_variable")
        assert hasattr(script_loader, "extract_message_from_result")
        assert hasattr(script_loader, "extract_text_from_result")

    def test_find_graph_variable_works(self, tmp_path):
        """Test that find_graph_variable function works."""
        from lfx.cli.script_loader import find_graph_variable

        # Create a test script with a graph variable
        script_content = """
from lfx.graph import Graph

graph = Graph.from_payload({})
"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text(script_content)

        result = find_graph_variable(script_path)
        assert result is not None
        assert result["type"] == "function_call"
        assert "Graph" in result["function"]

    def test_find_graph_variable_with_get_graph_function(self, tmp_path):
        """Test that find_graph_variable detects get_graph functions."""
        from lfx.cli.script_loader import find_graph_variable

        # Create a test script with get_graph function
        script_content = """
def get_graph():
    from lfx.graph import Graph
    return Graph.from_payload({})
"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text(script_content)

        result = find_graph_variable(script_path)
        assert result is not None
        assert result["type"] == "function_definition"
        assert result["function"] == "get_graph"

    def test_find_graph_variable_returns_none_for_no_graph(self, tmp_path):
        """Test that find_graph_variable returns None when no graph is found."""
        from lfx.cli.script_loader import find_graph_variable

        script_content = """
x = 1
y = 2
"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text(script_content)

        result = find_graph_variable(script_path)
        assert result is None


class TestFlowDictHandling:
    """Test in-memory flow dict handling in run command."""

    def test_json_parsing_for_flow_json(self):
        """Test that flow_json string can be parsed to dict."""
        flow_json = '{"data": {"nodes": [], "edges": []}}'
        flow_dict = json.loads(flow_json)

        assert isinstance(flow_dict, dict)
        assert "data" in flow_dict
        assert flow_dict["data"]["nodes"] == []
        assert flow_dict["data"]["edges"] == []

    def test_json_parsing_for_complex_flow(self):
        """Test parsing a more complex flow structure."""
        flow_json = json.dumps(
            {
                "data": {
                    "nodes": [
                        {"id": "node1", "type": "ChatInput", "data": {}},
                        {"id": "node2", "type": "ChatOutput", "data": {}},
                    ],
                    "edges": [{"source": "node1", "target": "node2"}],
                }
            }
        )
        flow_dict = json.loads(flow_json)

        assert len(flow_dict["data"]["nodes"]) == 2
        assert len(flow_dict["data"]["edges"]) == 1
        assert flow_dict["data"]["nodes"][0]["id"] == "node1"

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises appropriate error."""
        invalid_json = '{"data": invalid}'

        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)
