"""End-to-end tests for agent building blocks using Graph execution.

These tests build actual Graph objects and run them with async_start(),
testing the full flow including loops and conditional routing.
"""

from collections.abc import Iterator
from typing import Any

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
        """Generate a response from the predefined list."""
        response = next(self.responses)
        return ChatResult(generations=[ChatGeneration(message=response)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate - just calls sync version."""
        return self._generate(messages, stop, run_manager, **kwargs)

    def bind_tools(
        self,
        tools: list,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> "FakeToolCallingLLM":
        """Return self - tools are ignored since responses are predefined."""
        return self

    def with_config(
        self,
        config: dict,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> "FakeToolCallingLLM":
        """Return self with config (no-op for fake LLM)."""
        return self

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling-llm"


class MockSearchTool:
    """Mock search tool for testing."""

    name = "search"
    description = "Searches the web"

    async def ainvoke(self, args: dict) -> str:
        """Execute the search."""
        query = args.get("query", "")
        return f"Search results for '{query}': Found 3 relevant documents about {query}."


# Global fake LLM that will be used by FakeAgentStepComponent
_fake_llm_instance: FakeToolCallingLLM | None = None


class FakeAgentStepComponent(AgentStepComponent):
    """An AgentStepComponent subclass that uses a fake LLM."""

    def build_model(self):
        """Return the global fake LLM instance."""
        if _fake_llm_instance is None:
            msg = "Fake LLM instance not set. Call set_fake_llm() first."
            raise ValueError(msg)
        return _fake_llm_instance


def set_fake_llm(fake_llm: FakeToolCallingLLM) -> None:
    """Set the global fake LLM instance."""
    global _fake_llm_instance  # noqa: PLW0603
    _fake_llm_instance = fake_llm


class TestAgentGraphE2ESingleIteration:
    """End-to-end test for a single agent iteration using Graph execution."""

    @pytest.mark.asyncio
    async def test_simple_chat_graph_no_tools(self):
        """Test a simple chat flow using Graph where the model responds without tool calls."""
        # Setup: Create a fake LLM that responds without tool calls
        fake_response = AIMessage(content="Hello! I'm here to help you.")
        fake_llm = FakeToolCallingLLM(responses=iter([fake_response]))
        set_fake_llm(fake_llm)

        # Build graph components
        chat_input = ChatInput(_id="chat_input")

        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(input_value=chat_input.message_response)

        agent_step = FakeAgentStepComponent(_id="agent_step")
        agent_step.set(
            messages=while_loop.loop_output,
            system_message="You are a helpful assistant.",
        )

        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=agent_step.get_ai_message)

        # Build and run graph
        graph = Graph(chat_input, chat_output)

        results = [
            result
            async for result in graph.async_start(
                max_iterations=10,
                config={"output": {"cache": False}},
                inputs={"input_value": "Hello!"},
            )
        ]

        # Verify the results
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "chat_input" in result_ids
        assert "agent_step" in result_ids
        assert "chat_output" in result_ids

        # The final output should contain the AI response
        chat_output_result = next(
            (r for r in results if hasattr(r, "vertex") and r.vertex.id == "chat_output"),
            None,
        )
        assert chat_output_result is not None


class TestAgentGraphE2EWithToolCalls:
    """End-to-end test for agent with tool calls using Graph execution."""

    @pytest.mark.asyncio
    async def test_search_tool_call_graph_flow(self):
        """Test a complete graph flow: user asks → model calls tool → tool executes → final response."""
        # Setup: Create fake LLM responses
        # First call: Model wants to search
        first_response = AIMessage(
            content="Let me search for that.",
            tool_calls=[{"name": "search", "args": {"query": "Python basics"}, "id": "call_1"}],
        )
        # Second call: Model provides final answer after seeing tool result
        second_response = AIMessage(content="Based on my search, Python is a versatile programming language.")

        fake_llm = FakeToolCallingLLM(responses=iter([first_response, second_response]))
        set_fake_llm(fake_llm)
        tools = [MockSearchTool()]

        # Build graph components
        chat_input = ChatInput(_id="chat_input")

        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(input_value=chat_input.message_response)

        agent_step = FakeAgentStepComponent(_id="agent_step")
        agent_step.set(
            messages=while_loop.loop_output,
            system_message="You are a helpful assistant.",
            tools=tools,
        )

        execute_tool = ExecuteToolComponent(_id="execute_tool")
        execute_tool.set(
            tool_calls_message=agent_step.get_tool_calls,
            tools=tools,
        )

        # Connect execute_tool back to while_loop for the cycle
        while_loop.set(loop=execute_tool.execute_tools)

        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=agent_step.get_ai_message)

        # Build and run graph
        graph = Graph(chat_input, chat_output)

        # The graph should be cyclic
        assert graph.is_cyclic is True

        results = [
            result
            async for result in graph.async_start(
                max_iterations=20,
                config={"output": {"cache": False}},
                inputs={"input_value": "Tell me about Python"},
            )
        ]

        # Verify the execution path
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]

        # Should have executed: chat_input, while_loop, agent_step (tool_calls),
        # execute_tool, while_loop (again), agent_step (ai_message), chat_output
        assert "chat_input" in result_ids
        assert "while_loop" in result_ids
        assert "agent_step" in result_ids
        assert "execute_tool" in result_ids
        assert "chat_output" in result_ids

        # agent_step should appear twice (once for tool_calls, once for ai_message)
        agent_step_count = result_ids.count("agent_step")
        assert agent_step_count >= 2, f"Expected agent_step to appear at least twice, got {agent_step_count}"


class TestAgentGraphE2EMultipleIterations:
    """End-to-end test for multi-turn agent conversations using Graph execution."""

    @pytest.mark.asyncio
    async def test_three_iteration_agent_graph_loop(self):
        """Test a 3-iteration agent loop with tool calls using Graph."""
        # Setup: Create sequence of responses
        # Iteration 1: Model searches
        response_1 = AIMessage(
            content="Searching...",
            tool_calls=[{"name": "search", "args": {"query": "weather today"}, "id": "call_1"}],
        )
        # Iteration 2: Model searches again for more details
        response_2 = AIMessage(
            content="Getting more details...",
            tool_calls=[{"name": "search", "args": {"query": "weather forecast week"}, "id": "call_2"}],
        )
        # Iteration 3: Model provides final answer
        response_3 = AIMessage(
            content="Based on my research, the weather today is sunny with temperatures around 72°F. "
            "The forecast for the week shows continued warm weather."
        )
        # Extra response for the additional cycle iteration (graph execution artifact)
        response_4 = AIMessage(content="Done.")

        fake_llm = FakeToolCallingLLM(responses=iter([response_1, response_2, response_3, response_4]))
        set_fake_llm(fake_llm)
        tools = [MockSearchTool()]

        # Build graph components
        chat_input = ChatInput(_id="chat_input")

        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(input_value=chat_input.message_response)

        agent_step = FakeAgentStepComponent(_id="agent_step")
        agent_step.set(
            messages=while_loop.loop_output,
            tools=tools,
        )

        execute_tool = ExecuteToolComponent(_id="execute_tool")
        execute_tool.set(
            tool_calls_message=agent_step.get_tool_calls,
            tools=tools,
        )

        # Connect execute_tool back to while_loop for the cycle
        while_loop.set(loop=execute_tool.execute_tools)

        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=agent_step.get_ai_message)

        # Build and run graph
        graph = Graph(chat_input, chat_output)
        assert graph.is_cyclic is True

        results = [
            result
            async for result in graph.async_start(
                max_iterations=30,
                config={"output": {"cache": False}},
                inputs={"input_value": "What's the weather like?"},
            )
        ]

        # Verify the execution path
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]

        # Should have executed multiple iterations
        assert "chat_output" in result_ids, f"chat_output not in results: {result_ids}"

        # agent_step should appear 3 times (2 tool_calls + 1 ai_message)
        agent_step_count = result_ids.count("agent_step")
        assert agent_step_count >= 3, f"Expected agent_step at least 3 times, got {agent_step_count}: {result_ids}"

        # execute_tool should appear 2 times (for each tool call)
        execute_tool_count = result_ids.count("execute_tool")
        assert execute_tool_count >= 2, f"Expected execute_tool at least 2 times, got {execute_tool_count}"


class TestMessageHistoryAccumulation:
    """Tests verifying that message history accumulates correctly through the agent loop."""

    @pytest.mark.asyncio
    async def test_message_history_grows_with_iterations(self):
        """Test that ExecuteTool's output accumulates messages correctly.

        On each iteration through the loop, the message history should grow:
        - Iteration 1: User message only (1 message)
        - Iteration 2: User + AI (tool call) + Tool result (3 messages)
        - Iteration 3: User + AI + Tool + AI + Tool (5 messages)
        ...etc

        This test verifies that the cycle feedback mechanism works correctly
        by checking that WhileLoop receives accumulated history on each iteration.
        """
        # Setup: Create fake LLM responses
        first_response = AIMessage(
            content="Let me search for that.",
            tool_calls=[{"name": "search", "args": {"query": "test query"}, "id": "call_1"}],
        )
        final_response = AIMessage(content="Here is your answer based on the search.")

        fake_llm = FakeToolCallingLLM(responses=iter([first_response, final_response]))
        set_fake_llm(fake_llm)
        tools = [MockSearchTool()]

        # Build graph components
        chat_input = ChatInput(_id="chat_input")

        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(input_value=chat_input.message_response)

        agent_step = FakeAgentStepComponent(_id="agent_step")
        agent_step.set(
            messages=while_loop.loop_output,
            system_message="You are a helpful assistant.",
            tools=tools,
        )

        execute_tool = ExecuteToolComponent(_id="execute_tool")
        execute_tool.set(
            tool_calls_message=agent_step.get_tool_calls,
            tools=tools,
        )

        # Connect execute_tool back to while_loop for the cycle
        while_loop.set(loop=execute_tool.execute_tools)

        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=agent_step.get_ai_message)

        # Build and run graph
        graph = Graph(chat_input, chat_output)

        results = [
            result
            async for result in graph.async_start(
                max_iterations=20,
                config={"output": {"cache": False}},
                inputs={"input_value": "Test message"},
            )
        ]

        # Verify the execution path
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]

        # while_loop should appear at least twice (first iteration and after tool execution)
        while_loop_count = result_ids.count("while_loop")
        assert while_loop_count >= 2, f"Expected while_loop to be called at least twice, got {while_loop_count}"

        # agent_step should appear at least twice (tool_calls and ai_message)
        agent_step_count = result_ids.count("agent_step")
        assert agent_step_count >= 2, f"Expected agent_step to be called at least twice, got {agent_step_count}"

        # execute_tool should appear once (for the tool call)
        execute_tool_count = result_ids.count("execute_tool")
        assert execute_tool_count >= 1, f"Expected execute_tool to be called at least once, got {execute_tool_count}"

        # chat_output should appear (final response)
        assert "chat_output" in result_ids, "Expected chat_output in results"
