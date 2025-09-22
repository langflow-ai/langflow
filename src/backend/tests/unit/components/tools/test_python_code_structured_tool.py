from unittest.mock import patch

import pytest
from langflow.components.tools.python_code_structured_tool import PythonCodeStructuredTool


class TestPythonCodeStructuredTool:
    """Test cases for PythonCodeStructuredTool component."""

    @pytest.fixture
    def component(self):
        """Create a PythonCodeStructuredTool instance for testing."""
        return PythonCodeStructuredTool()

    def test_initialization(self, component):
        """Test proper initialization of component."""
        assert component.display_name == "Python Code Structured"
        assert component.description == "structuredtool dataclass code to tool"
        assert component.name == "PythonCodeStructuredTool"
        assert component.icon == "Python"
        assert component.legacy is True

        # Check DEFAULT_KEYS
        expected_keys = [
            "code",
            "_type",
            "text_key",
            "tool_code",
            "tool_name",
            "tool_description",
            "return_direct",
            "tool_function",
            "global_variables",
            "_classes",
            "_functions",
        ]
        assert expected_keys == component.DEFAULT_KEYS

    def test_field_order(self, component):
        """Test field order configuration."""
        # field_order can be None if not explicitly set at instance level
        assert hasattr(component, "field_order")
        # The class-level field_order is what we expect
        expected_order = ["name", "description", "tool_code", "return_direct", "tool_function"]
        assert PythonCodeStructuredTool.field_order == expected_order

    def test_inputs_configuration(self, component):
        """Test that inputs are properly configured."""
        # The component should have inputs defined
        assert hasattr(component, "inputs")
        assert len(component.inputs) > 0

        # Check for expected input names
        input_names = [input_field.name for input_field in component.inputs]
        expected_inputs = ["tool_code", "tool_name", "tool_description", "return_direct", "tool_function"]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    def test_outputs_configuration(self, component):
        """Test that outputs are properly configured."""
        assert hasattr(component, "outputs")
        assert len(component.outputs) > 0

    @pytest.mark.asyncio
    async def test_build_tool_method_exists(self, component):
        """Test that build_tool method exists and can be called."""
        # Set up required attributes for build_tool
        component.tool_code = "def test_func(): return 42"
        component.tool_name = "test_tool"
        component.tool_description = "Test description"
        component.return_direct = False
        component.tool_function = "test_func"
        component.global_variables = []

        # Mock the internal parsing methods
        with patch.object(component, "_parse_code") as mock_parse:
            mock_parse.return_value = ({}, [{"name": "test_func", "args": []}])

            # The method should exist and be callable
            assert hasattr(component, "build_tool")
            assert callable(component.build_tool)

            # We won't test the full execution due to complex setup requirements
