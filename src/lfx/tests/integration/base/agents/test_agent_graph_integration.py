# ruff: noqa: PT018
"""Integration tests for agent graph execution.

These tests require:
- OPENAI_API_KEY environment variable
- langchain-openai package (install with: uv sync --group integration)
"""

import os

import pytest
from lfx.components.agent_blocks.agent_step import AgentStepComponent
from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.graph import Graph
from lfx.schema.message import Message

pytestmark = [pytest.mark.integration]


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
class TestAgentGraphEndToEnd:
    """End-to-end tests for agent graph execution with real LLM."""

    @pytest.mark.asyncio
    async def test_simple_chat_without_tools(self):
        """Test a simple chat without tools using gpt-5-nano."""
        api_key = os.environ.get("OPENAI_API_KEY")

        # Build the components manually to have direct access to agent_step
        while_loop = WhileLoopComponent(_id="e2e_test_while_loop")
        agent_step = AgentStepComponent(_id="e2e_test_agent_step")
        execute_tool = ExecuteToolComponent(_id="e2e_test_execute_tool")

        # Configure WhileLoop
        while_loop.set(
            max_iterations=10,
            loop=execute_tool.execute_tools,
            input_value="Say 'Hello' and nothing else.",
        )

        # Configure AgentStep
        agent_step.set(
            model="gpt-5-nano",
            api_key=api_key,
            system_message="You are a helpful assistant. Be brief.",
            temperature=0.1,
            messages=while_loop.loop_output,
        )

        # Configure ExecuteTool (no tools, so it won't be used)
        execute_tool.set(ai_message=agent_step.get_tool_calls)

        # Build and execute the graph
        graph = Graph(start=while_loop, end=agent_step)
        async for _ in graph.async_start(
            max_iterations=10,
            config={"output": {"cache": False}},
        ):
            pass

        # Verify we got a response from agent_step's output
        output = agent_step.get_output_by_method(agent_step.get_ai_message)
        assert output is not None
        assert hasattr(output, "value") and output.value is not None
        result = output.value
        assert isinstance(result, Message)
        assert "hello" in result.text.lower()

    @pytest.mark.asyncio
    async def test_graph_builds_with_tools(self):
        """Test that agent graph builds correctly with tools.

        Note: Full tool call execution is tested separately. This test verifies
        that the graph structure is correct when tools are provided.
        """
        from lfx.components.tools.calculator import CalculatorToolComponent

        # Get tools from a component using to_toolkit()
        calculator = CalculatorToolComponent()
        tools = await calculator.to_toolkit()

        api_key = os.environ.get("OPENAI_API_KEY")

        # Build the components directly
        while_loop = WhileLoopComponent(_id="e2e_tool_test_while_loop")
        agent_step = AgentStepComponent(_id="e2e_tool_test_agent_step")
        execute_tool = ExecuteToolComponent(_id="e2e_tool_test_execute_tool")

        # Configure WhileLoop
        while_loop.set(
            max_iterations=10,
            loop=execute_tool.execute_tools,
            input_value="Hello",
        )

        # Configure AgentStep
        agent_step.set(
            model="gpt-5-nano",
            api_key=api_key,
            system_message="You are a helpful assistant.",
            temperature=0.1,
            tools=tools,
            messages=while_loop.loop_output,
        )

        # Configure ExecuteTool
        execute_tool.set(ai_message=agent_step.get_tool_calls, tools=tools)

        # Build the graph
        graph = Graph(start=while_loop, end=agent_step)

        # Verify graph structure
        graph.prepare()
        assert graph.is_cyclic is True
        assert len(graph.vertices) == 3

        vertex_ids = {v.id for v in graph.vertices}
        assert "e2e_tool_test_while_loop" in vertex_ids
        assert "e2e_tool_test_agent_step" in vertex_ids
        assert "e2e_tool_test_execute_tool" in vertex_ids
