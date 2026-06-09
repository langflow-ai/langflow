import os

import pytest
from langchain_core.tools import ToolException
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

    async def test_build_tool_returns_non_executable_stub(self, component_class, default_kwargs):
        """build_tool returns a tool that refuses to run instead of exec()'ing tool_code.

        Security regression for report H1-3754930: this legacy component used to
        ``exec()`` the ``tool_code`` field at build time, which was reachable as
        an unauthenticated RCE through public flows.
        """
        component = await self.component_setup(component_class, default_kwargs)
        tool = await component.build_tool()

        # The tool exists but is inert: invoking it raises a clear deprecation error.
        with pytest.raises(ToolException) as exc_info:
            tool.func()

        message = str(exc_info.value)
        assert "disabled" in message.lower()
        assert "PythonREPLComponent" in message

    async def test_build_tool_does_not_execute_tool_code(self, component_class, default_kwargs):
        """Neither building nor invoking the tool may execute attacker-supplied tool_code."""
        sentinel = "PCT_SHOULD_NEVER_RUN"
        assert sentinel not in os.environ

        component = await self.component_setup(component_class, default_kwargs)
        # Code that would set an env var if it were ever exec()'d.
        component.tool_code = f"import os\nos.environ['{sentinel}'] = 'pwned'\ndef test_func():\n    return 42"

        tool = await component.build_tool()
        # Building must not have executed the payload.
        assert sentinel not in os.environ

        # Invoking must refuse rather than execute the payload.
        with pytest.raises(ToolException):
            tool.func()
        assert sentinel not in os.environ
