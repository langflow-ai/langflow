"""Tests for per-tool return_direct feature in tool mode components."""

import pandas as pd
import pytest
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom.custom_component.component import Component
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output


class TestPerToolReturnDirect:
    """Tests for per-tool return_direct functionality via metadata.

    return_direct is handled natively by LangChain — when True, the agent executor
    returns the tool's output directly without passing it back through the LLM.
    """

    def test_tool_has_return_direct_false_by_default(self):
        """Test that tools have return_direct=False by default."""

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="test")

        component = TestComponent()
        component.outputs[0].tool_mode = True
        toolkit = ComponentToolkit(component)
        tools = toolkit.get_tools()

        assert len(tools) == 1
        assert tools[0].return_direct is False

    def test_per_tool_return_direct_via_metadata(self):
        """Test that return_direct is set per-tool from metadata."""

        class TestComponent(Component):
            outputs = [
                Output(name="output_a", display_name="Output A", method="get_output_a", types=["Message"]),
                Output(name="output_b", display_name="Output B", method="get_output_b", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output_a(self) -> Message:
                return Message(text="output a")

            def get_output_b(self) -> Message:
                return Message(text="output b")

        component = TestComponent()
        component.outputs[0].tool_mode = True
        component.outputs[1].tool_mode = True

        # Create metadata where tool A has return_direct=True, tool B has return_direct=False
        metadata = pd.DataFrame([
            {
                "name": "get_output_a",
                "description": "Output A",
                "tags": ["get_output_a"],
                "status": True,
                "return_direct": True,
            },
            {
                "name": "get_output_b",
                "description": "Output B",
                "tags": ["get_output_b"],
                "status": True,
                "return_direct": False,
            },
        ])

        toolkit = ComponentToolkit(component, metadata=metadata)
        tools = toolkit.get_tools()
        tools = toolkit.update_tools_metadata(tools)

        assert len(tools) == 2
        tool_a = next(t for t in tools if t.name == "get_output_a")
        tool_b = next(t for t in tools if t.name == "get_output_b")

        assert tool_a.return_direct is True
        assert tool_b.return_direct is False

    def test_return_direct_tool_returns_result_normally(self):
        """Test that return_direct tools return their result normally (LangChain handles the rest)."""

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="direct response test")

        component = TestComponent()
        component.outputs[0].tool_mode = True

        toolkit = ComponentToolkit(component)
        tools = toolkit.get_tools()

        # Execute the tool — result is returned normally
        result = tools[0].invoke({})
        assert result == "direct response test"

    def test_normal_tool_returns_result(self):
        """Test that normal tools return their result as expected."""

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="normal response")

        component = TestComponent()
        component.outputs[0].tool_mode = True

        toolkit = ComponentToolkit(component)
        tools = toolkit.get_tools()

        result = tools[0].invoke({})
        assert result == "normal response"

    def test_data_result_returned_normally(self):
        """Test that Data results are returned as dict."""

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Data"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Data:
                return Data(data={"key": "value"})

        component = TestComponent()
        component.outputs[0].tool_mode = True

        toolkit = ComponentToolkit(component)
        tools = toolkit.get_tools()

        result = tools[0].invoke({})
        assert result == {"key": "value"}


class TestAsyncPerToolReturnDirect:
    """Tests for per-tool return_direct with async tool methods."""

    @pytest.mark.asyncio
    async def test_async_tool_returns_result_normally(self):
        """Test that async tools return their result normally."""

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            async def get_output(self) -> Message:
                return Message(text="async response")

        component = TestComponent()
        component.outputs[0].tool_mode = True

        toolkit = ComponentToolkit(component)
        tools = toolkit.get_tools()

        result = await tools[0].ainvoke({})
        assert result == "async response"


class TestDirectResponseOutput:
    """Tests for return_direct metadata in tool data."""

    def test_build_tool_data_includes_return_direct(self):
        """Test that _build_tool_data includes return_direct: False by default."""
        from pydantic import BaseModel

        from langchain_core.tools.structured import StructuredTool

        class EmptySchema(BaseModel):
            pass

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="test")

        component = TestComponent()

        # Create a mock tool
        tool = StructuredTool(
            name="test_tool",
            description="A test tool",
            func=lambda: None,
            args_schema=EmptySchema,
            tags=["test_tool"],
            metadata={"display_name": "test_tool", "display_description": "A test tool"},
        )

        tool_data = component._build_tool_data(tool)
        assert "return_direct" in tool_data
        assert tool_data["return_direct"] is False


class TestDisabledParams:
    """Tests for per-tool disabled_params functionality."""

    def test_build_tool_data_includes_disabled_params(self):
        """Test that _build_tool_data includes disabled_params: [] by default."""
        from pydantic import BaseModel

        from langchain_core.tools.structured import StructuredTool

        class EmptySchema(BaseModel):
            pass

        class TestComponent(Component):
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="test")

        component = TestComponent()
        tool = StructuredTool(
            name="test_tool",
            description="A test tool",
            func=lambda: None,
            args_schema=EmptySchema,
            tags=["test_tool"],
            metadata={"display_name": "test_tool", "display_description": "A test tool"},
        )

        tool_data = component._build_tool_data(tool)
        assert "disabled_params" in tool_data
        assert tool_data["disabled_params"] == []

    def test_disabled_params_filters_args_schema(self):
        """Test that disabled_params removes fields from tool's args_schema at runtime."""
        from lfx.inputs.inputs import MessageTextInput, StrInput

        class TestComponent(Component):
            inputs = [
                MessageTextInput(name="message", display_name="Message", tool_mode=True),
                StrInput(name="extra", display_name="Extra", tool_mode=True),
            ]
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="test")

        component = TestComponent()
        component.outputs[0].tool_mode = True

        # Create metadata that disables the "extra" param
        metadata = pd.DataFrame([
            {
                "name": "get_output",
                "description": "Test Output",
                "tags": ["get_output"],
                "status": True,
                "return_direct": False,
                "disabled_params": ["extra"],
            },
        ])

        toolkit = ComponentToolkit(component, metadata=metadata)
        tools = toolkit.get_tools()
        tools = toolkit.update_tools_metadata(tools)

        assert len(tools) == 1
        # The args_schema should only have "message", not "extra"
        schema_fields = list(tools[0].args_schema.model_fields.keys())
        assert "message" in schema_fields
        assert "extra" not in schema_fields

    def test_empty_disabled_params_keeps_all_fields(self):
        """Test that empty disabled_params keeps all fields in args_schema."""
        from lfx.inputs.inputs import MessageTextInput, StrInput

        class TestComponent(Component):
            inputs = [
                MessageTextInput(name="message", display_name="Message", tool_mode=True),
                StrInput(name="extra", display_name="Extra", tool_mode=True),
            ]
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="test")

        component = TestComponent()
        component.outputs[0].tool_mode = True

        metadata = pd.DataFrame([
            {
                "name": "get_output",
                "description": "Test Output",
                "tags": ["get_output"],
                "status": True,
                "return_direct": False,
                "disabled_params": [],
            },
        ])

        toolkit = ComponentToolkit(component, metadata=metadata)
        tools = toolkit.get_tools()
        tools = toolkit.update_tools_metadata(tools)

        assert len(tools) == 1
        schema_fields = list(tools[0].args_schema.model_fields.keys())
        assert "message" in schema_fields
        assert "extra" in schema_fields

    def test_disabled_params_all_fields_disabled_produces_empty_schema(self):
        """Test that disabling ALL params results in an empty args_schema."""
        from lfx.inputs.inputs import StrInput

        class TestComponent(Component):
            inputs = [
                StrInput(name="urls", display_name="Urls", tool_mode=True),
            ]
            outputs = [
                Output(name="test_output", display_name="Test Output", method="get_output", types=["Message"]),
            ]

            def build(self) -> None:
                pass

            def get_output(self) -> Message:
                return Message(text="test")

        component = TestComponent()
        component.outputs[0].tool_mode = True

        metadata = pd.DataFrame([
            {
                "name": "get_output",
                "description": "Test Output",
                "tags": ["get_output"],
                "status": True,
                "return_direct": False,
                "disabled_params": ["urls"],
            },
        ])

        toolkit = ComponentToolkit(component, metadata=metadata)
        tools = toolkit.get_tools()
        tools = toolkit.update_tools_metadata(tools)

        assert len(tools) == 1
        schema_fields = list(tools[0].args_schema.model_fields.keys())
        assert "urls" not in schema_fields
        assert len(schema_fields) == 0
