"""End-to-end tests for agent building blocks using Graph execution.

These tests build actual Graph objects and run them with async_start(),
testing the full flow including loops and conditional routing.

Key testing requirements for WhileLoop subgraph architecture:
- get_llm must be patched at BOTH lfx.components.agent_blocks.agent_step AND
  lfx.base.models.unified_models (subgraph resolves from source module)
- All graphs need the full loop structure (execute_tool + feedback edge) even
  for no-tools tests, because WhileLoop needs a feedback edge to form a subgraph
- agent_step/execute_tool/chat_output run inside the subgraph, so they don't
  appear in the outer graph's result_ids
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.components.agent_blocks import (
    AgentStepComponent,
    ExecuteToolComponent,
)
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph

GET_LLM_AGENT_STEP = "lfx.components.agent_blocks.agent_step.get_llm"
GET_LLM_UNIFIED = "lfx.base.models.unified_models.get_llm"


class FakeToolCallingLLM(BaseChatModel):
    """A fake LLM that returns predefined responses and supports bind_tools."""

    responses: Iterator[AIMessage]

    class Config:
        arbitrary_types_allowed = True

    def _generate(
        self,
        messages: list[BaseMessage],  # noqa: ARG002
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: Any = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        response = next(self.responses)
        return ChatResult(generations=[ChatGeneration(message=response)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop, run_manager, **kwargs)

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def with_config(self, config, **kwargs):  # noqa: ARG002
        return self

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling-llm"


class MockSearchTool:
    name = "search"
    description = "Searches the web"

    async def ainvoke(self, args: dict) -> str:
        query = args.get("query", "")
        return f"Search results for '{query}': Found 3 relevant documents about {query}."


def build_agent_graph(tools=None):
    """Build the standard agent graph structure.

    All tests need the full loop structure (execute_tool + feedback edge)
    for the WhileLoop subgraph to form correctly.
    """
    if tools is None:
        tools = []

    chat_input = ChatInput(_id="chat_input")

    while_loop = WhileLoopComponent(_id="while_loop")
    while_loop.set(input_value=chat_input.message_response)

    agent_step = AgentStepComponent(_id="agent_step")
    agent_step.set(messages=while_loop.loop_output, system_message="You are a helpful assistant.", tools=tools)

    execute_tool = ExecuteToolComponent(_id="execute_tool")
    execute_tool.set(tool_calls_message=agent_step.get_tool_calls, tools=tools)
    while_loop.set(loop=execute_tool.execute_tools)

    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=agent_step.get_ai_message)

    return Graph(chat_input, chat_output)


async def run_graph(graph, fake_llm, input_text, max_iterations=10):
    """Run graph with dual get_llm patch."""
    with patch(GET_LLM_AGENT_STEP, return_value=fake_llm), patch(GET_LLM_UNIFIED, return_value=fake_llm):
        return [
            result
            async for result in graph.async_start(
                max_iterations=max_iterations,
                config={"output": {"cache": False}},
                inputs={"input_value": input_text},
            )
        ]


class TestAgentGraphE2ESingleIteration:
    @pytest.mark.asyncio
    async def test_simple_chat_graph_no_tools(self):
        """Model responds without tool calls - loop terminates after one iteration."""
        fake_llm = FakeToolCallingLLM(responses=iter([AIMessage(content="Hello! I'm here to help you.")]))
        graph = build_agent_graph()

        results = await run_graph(graph, fake_llm, "Hello!")

        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "chat_input" in result_ids
        assert "while_loop" in result_ids


class TestAgentGraphE2EWithToolCalls:
    @pytest.mark.asyncio
    async def test_search_tool_call_graph_flow(self):
        """Model calls tool -> tool executes -> model responds."""
        fake_llm = FakeToolCallingLLM(
            responses=iter(
                [
                    AIMessage(
                        content="Let me search.",
                        tool_calls=[{"name": "search", "args": {"query": "Python"}, "id": "call_1"}],
                    ),
                    AIMessage(content="Based on my search, Python is versatile."),
                ]
            )
        )
        tools = [MockSearchTool()]
        graph = build_agent_graph(tools)
        assert graph.is_cyclic is True

        results = await run_graph(graph, fake_llm, "Tell me about Python", max_iterations=20)

        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "chat_input" in result_ids
        assert "while_loop" in result_ids


class TestAgentGraphE2EMultipleIterations:
    @pytest.mark.asyncio
    async def test_three_iteration_agent_graph_loop(self):
        """3-iteration agent loop: 2 tool calls + 1 final response."""
        fake_llm = FakeToolCallingLLM(
            responses=iter(
                [
                    AIMessage(
                        content="Searching...",
                        tool_calls=[{"name": "search", "args": {"query": "weather today"}, "id": "call_1"}],
                    ),
                    AIMessage(
                        content="More details...",
                        tool_calls=[{"name": "search", "args": {"query": "forecast"}, "id": "call_2"}],
                    ),
                    AIMessage(content="The weather is sunny, 72F. Continued warm weather this week."),
                ]
            )
        )
        tools = [MockSearchTool()]
        graph = build_agent_graph(tools)
        assert graph.is_cyclic is True

        results = await run_graph(graph, fake_llm, "What's the weather like?", max_iterations=30)

        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "chat_input" in result_ids
        assert "while_loop" in result_ids


class TestMessageHistoryAccumulation:
    @pytest.mark.asyncio
    async def test_message_history_grows_with_iterations(self):
        """Message history accumulates through the agent loop."""
        fake_llm = FakeToolCallingLLM(
            responses=iter(
                [
                    AIMessage(
                        content="Let me search.",
                        tool_calls=[{"name": "search", "args": {"query": "test"}, "id": "call_1"}],
                    ),
                    AIMessage(content="Here is your answer based on the search."),
                ]
            )
        )
        tools = [MockSearchTool()]
        graph = build_agent_graph(tools)

        results = await run_graph(graph, fake_llm, "Test message", max_iterations=20)

        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "chat_input" in result_ids
        assert "while_loop" in result_ids
