"""Real-component execution tests for tool-mode wrappers.

These assert that a tool wrapping a real component actually runs that component
when the agent invokes it, rather than returning a synthetic placeholder.
"""

import json

import pytest
from langchain_core.tools import StructuredTool

from langflow_stepflow.worker.handlers.tool_wrapper import ToolWrapperInputHandler
from tests.helpers.tool_components import (
    InMemoryContext,
    make_real_tool_wrapper,
    simple_component_node_info,
)


class TestToolExecutesRealComponent:
    @pytest.mark.asyncio
    async def test_tool_invocation_runs_wrapped_component(self):
        context = InMemoryContext()
        blob_id = await context.put_blob(simple_component_node_info())
        wrapper = make_real_tool_wrapper(blob_id)

        handler = ToolWrapperInputHandler()
        prepared = await handler.prepare({"tools": (wrapper, {})}, context)
        tool = prepared["tools"]

        assert isinstance(tool, StructuredTool)
        assert tool.name == "simple_test"
        assert tool.description == "Runs the simple test component"

        output = await tool.ainvoke({"text_input": "Hello World"})

        dumped = json.dumps(output, default=str)
        assert "Processed: Hello World" in dumped
        # The old synthetic placeholder must be gone.
        assert "executed with inputs" not in dumped

    @pytest.mark.asyncio
    async def test_static_inputs_flow_into_component(self):
        """Static inputs (wired component values) reach the component at execution."""
        context = InMemoryContext()
        blob_id = await context.put_blob(simple_component_node_info())
        # No tool params: the agent passes nothing, so the static input drives it.
        wrapper = make_real_tool_wrapper(
            blob_id,
            static_inputs={"text_input": "Static Value"},
            properties={},
        )

        handler = ToolWrapperInputHandler()
        prepared = await handler.prepare({"tools": (wrapper, {})}, context)

        output = await prepared["tools"].ainvoke({})

        assert "Processed: Static Value" in json.dumps(output, default=str)

    @pytest.mark.asyncio
    async def test_prepare_list_of_real_tools(self):
        context = InMemoryContext()
        blob_id = await context.put_blob(simple_component_node_info())
        wrapper_a = make_real_tool_wrapper(blob_id, name="tool_a")
        wrapper_b = make_real_tool_wrapper(blob_id, name="tool_b")

        handler = ToolWrapperInputHandler()
        result = await handler.prepare({"tools": ([wrapper_a, wrapper_b], {})}, context)

        tools = result["tools"]
        assert [t.name for t in tools] == ["tool_a", "tool_b"]
        assert all(isinstance(t, StructuredTool) for t in tools)

    @pytest.mark.asyncio
    async def test_prepare_mixed_list_keeps_non_wrappers(self):
        context = InMemoryContext()
        blob_id = await context.put_blob(simple_component_node_info())
        wrapper = make_real_tool_wrapper(blob_id, name="real_tool")

        handler = ToolWrapperInputHandler()
        result = await handler.prepare({"tools": ([wrapper, "not_a_wrapper", 42], {})}, context)

        tools = result["tools"]
        assert isinstance(tools[0], StructuredTool)
        assert tools[1] == "not_a_wrapper"
        assert tools[2] == 42

    @pytest.mark.asyncio
    async def test_prepare_multiple_fields(self):
        context = InMemoryContext()
        blob_id = await context.put_blob(simple_component_node_info())
        wrapper_a = make_real_tool_wrapper(blob_id, name="tool_a")
        wrapper_b = make_real_tool_wrapper(blob_id, name="tool_b")

        handler = ToolWrapperInputHandler()
        result = await handler.prepare(
            {"primary_tool": (wrapper_a, {}), "secondary_tool": (wrapper_b, {})},
            context,
        )

        assert result["primary_tool"].name == "tool_a"
        assert result["secondary_tool"].name == "tool_b"
