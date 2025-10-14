from unittest.mock import patch

import pytest
from langflow.components.tools.python_code_structured_tool import PythonCodeStructuredTool

from tests.base import ComponentTestBaseWithoutClient


class TestPythonCodeStructuredTool(ComponentTestBaseWithoutClient):
    """Test cases for PythonCodeStructuredTool component."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return PythonCodeStructuredTool

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "tool_code": "def test_func(): return 42",
            "tool_name": "test_tool",
            "tool_description": "Test description",
            "return_direct": False,
            "tool_function": "test_func",
            "global_variables": [],
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_initialization(self, component_class, default_kwargs):
        """Test proper initialization of component."""
        component = await self.component_setup(component_class, default_kwargs)
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

    async def test_field_order(self, component_class, default_kwargs):
        """Test field order configuration."""
        component = await self.component_setup(component_class, default_kwargs)
        # field_order can be None if not explicitly set at instance level
        assert hasattr(component, "field_order")
        # The class-level field_order is what we expect
        expected_order = ["name", "description", "tool_code", "return_direct", "tool_function"]
        assert PythonCodeStructuredTool.field_order == expected_order

    async def test_inputs_configuration(self, component_class, default_kwargs):
        """Test that inputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        # The component should have inputs defined
        assert hasattr(component, "inputs")
        assert len(component.inputs) > 0

        # Check for expected input names
        input_names = [input_field.name for input_field in component.inputs]
        expected_inputs = ["tool_code", "tool_name", "tool_description", "return_direct", "tool_function"]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    async def test_outputs_configuration(self, component_class, default_kwargs):
        """Test that outputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        assert hasattr(component, "outputs")
        assert len(component.outputs) > 0

    @pytest.mark.asyncio
    async def test_build_tool_method_exists(self, component_class, default_kwargs):
        """Test that build_tool method exists and can be called."""
        component = await self.component_setup(component_class, default_kwargs)
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
