"""Integration tests for the agent loop with streaming.

This test builds the exact graph shown in the UI:
ChatInput → WhileLoop → CallModel → ExecuteTool → (loop back)
                          ↓
                     ChatOutput

It tests the full flow including:
- Streaming from CallModel
- Tool call capture during streaming
- Message history accumulation through the loop
- Proper tool_calls structure for OpenAI API
"""

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from lfx.components.agent_blocks import CallModelComponent, ExecuteToolComponent
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
from lfx.schema.message import Message


class FakeStreamingLLM(BaseChatModel):
    """A fake LLM that simulates streaming with tool_calls.

    This LLM returns responses as streaming chunks, properly simulating
    how OpenAI streams tool_calls incrementally.
    """

    responses: list[AIMessage]
    call_count: int = 0

    class Config:
        arbitrary_types_allowed = True

    def _generate(
        self,
        _messages: list[BaseMessage],
        _stop: list[str] | None = None,
        _run_manager: Any = None,
        **_kwargs: Any,
    ) -> ChatResult:
        """Generate a response (non-streaming)."""
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])

    async def _agenerate(
        self,
        _messages: list[BaseMessage],
        _stop: list[str] | None = None,
        _run_manager: Any = None,
        **_kwargs: Any,
    ) -> ChatResult:
        """Async generate (non-streaming)."""
        return self._generate(_messages, _stop, _run_manager, **_kwargs)

    def _stream(
        self,
        _messages: list[BaseMessage],
        _stop: list[str] | None = None,
        _run_manager: Any = None,
        **_kwargs: Any,
    ):
        """Sync stream - yields ChatGenerationChunk objects (required by LangChain's astream)."""
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        content = response.content or ""
        tool_calls = getattr(response, "tool_calls", None) or []

        # Stream content in chunks
        if content:
            chunk_size = 10
            for i in range(0, len(content), chunk_size):
                chunk_text = content[i : i + chunk_size]
                chunk = AIMessageChunk(content=chunk_text)
                yield ChatGenerationChunk(message=chunk)

        # Stream tool_calls (simulating OpenAI's incremental streaming)
        if tool_calls:
            import json

            for tc in tool_calls:
                chunk = AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "id": tc.get("id", ""),
                            "name": tc.get("name", ""),
                            "args": json.dumps(tc.get("args", {})),
                            "index": 0,
                        }
                    ],
                )
                yield ChatGenerationChunk(message=chunk)

    def bind_tools(self, _tools: list, **_kwargs: Any) -> "FakeStreamingLLM":
        """Return self - tools are ignored since responses are predefined."""
        return self

    def with_config(self, _config: dict, **_kwargs: Any) -> "FakeStreamingLLM":
        """Return self with config (no-op for fake LLM)."""
        return self

    @property
    def _llm_type(self) -> str:
        return "fake-streaming-llm"


# Global fake LLM instance stored in a dict to avoid global statement
_fake_llm_holder: dict[str, FakeStreamingLLM | None] = {"llm": None}


def set_fake_llm(llm: FakeStreamingLLM) -> None:
    """Set the global fake LLM."""
    _fake_llm_holder["llm"] = llm


class FakeCallModelComponent(CallModelComponent):
    """CallModelComponent that uses the fake streaming LLM."""

    def build_llm(self):
        """Return the global fake LLM."""
        llm = _fake_llm_holder["llm"]
        if llm is None:
            msg = "Fake LLM not set"
            raise ValueError(msg)
        return llm


class MockURLTool:
    """Mock URL tool that simulates fetching web content."""

    name = "fetch_url"
    description = "Fetch content from a URL"

    async def ainvoke(self, args: dict) -> str:
        """Execute the URL fetch."""
        url = args.get("url", "")
        return f"Content from {url}: This is mock documentation about Langflow."


class TestAgentLoopWithStreaming:
    """Tests for the complete agent loop with streaming."""

    @pytest.mark.asyncio
    async def test_simple_response_no_tools(self):
        """Test: User asks a question, model responds directly without tools."""
        # Setup fake LLM that responds without tool calls
        fake_llm = FakeStreamingLLM(
            responses=[AIMessage(content="Hello! I'm here to help you with Langflow documentation.")]
        )
        set_fake_llm(fake_llm)

        # Build graph: ChatInput → WhileLoop → CallModel → ChatOutput
        chat_input = ChatInput(_id="chat_input")

        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(input_value=chat_input.message_response)

        call_model = FakeCallModelComponent(_id="call_model")
        call_model.set(
            messages=while_loop.loop_output,
            system_message="You are a helpful assistant.",
        )

        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=call_model.get_ai_message)

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

        # Verify execution path
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        assert "chat_input" in result_ids
        assert "call_model" in result_ids
        assert "chat_output" in result_ids

    @pytest.mark.asyncio
    async def test_single_tool_call_loop(self):
        """Test: Model calls a tool once, then responds.

        Flow:
        1. User: "get me docs.langflow.org"
        2. Model: calls fetch_url tool
        3. Tool: returns content
        4. Model: provides final answer
        """
        # Setup fake LLM responses
        fake_llm = FakeStreamingLLM(
            responses=[
                # First call: model wants to fetch the URL
                AIMessage(
                    content="Let me fetch that documentation for you.",
                    tool_calls=[
                        {"name": "fetch_url", "args": {"url": "https://docs.langflow.org"}, "id": "call_abc123"}
                    ],
                ),
                # Second call: model provides final answer after seeing tool result
                AIMessage(content="Based on the documentation, Langflow is a visual workflow builder."),
            ]
        )
        set_fake_llm(fake_llm)

        tools = [MockURLTool()]

        # Build graph
        chat_input = ChatInput(_id="chat_input")

        while_loop = WhileLoopComponent(_id="while_loop")
        while_loop.set(input_value=chat_input.message_response)

        call_model = FakeCallModelComponent(_id="call_model")
        call_model.set(
            messages=while_loop.loop_output,
            system_message="You are a helpful assistant.",
            tools=tools,
        )

        execute_tool = ExecuteToolComponent(_id="execute_tool")
        execute_tool.set(
            ai_message=call_model.get_tool_calls,
            tools=tools,
        )

        # Connect loop
        while_loop.set(loop=execute_tool.execute_tools)

        chat_output = ChatOutput(_id="chat_output")
        chat_output.set(input_value=call_model.get_ai_message)

        # Build and run graph
        graph = Graph(chat_input, chat_output)
        assert graph.is_cyclic is True

        results = [
            result
            async for result in graph.async_start(
                max_iterations=20,
                config={"output": {"cache": False}},
                inputs={"input_value": "get me docs.langflow.org"},
            )
        ]

        # Verify execution path
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]

        # Should have: chat_input, while_loop, call_model (tool), execute_tool,
        # while_loop (again), call_model (final), chat_output
        assert "chat_input" in result_ids
        assert "while_loop" in result_ids
        assert "call_model" in result_ids
        assert "execute_tool" in result_ids
        assert "chat_output" in result_ids

        # call_model should appear at least twice
        call_model_count = result_ids.count("call_model")
        assert call_model_count >= 2, f"Expected call_model >= 2 times, got {call_model_count}"

    @pytest.mark.asyncio
    async def test_tool_calls_have_valid_structure(self):
        """Test that tool_calls captured during streaming have valid structure.

        This specifically tests that:
        - tool_calls have non-empty 'name'
        - tool_calls have non-null 'id'
        - tool_calls have proper 'args'
        """
        # Setup fake LLM with tool call
        fake_llm = FakeStreamingLLM(
            responses=[
                AIMessage(
                    content="Fetching...",
                    tool_calls=[{"name": "fetch_url", "args": {"url": "https://example.com"}, "id": "call_xyz789"}],
                ),
                AIMessage(content="Done!"),
            ]
        )
        set_fake_llm(fake_llm)

        # Create component and mock send_message
        call_model = FakeCallModelComponent(_id="test_call_model")

        sent_messages = []

        async def mock_send_message(msg, **_kwargs):
            sent_messages.append(msg)
            # Simulate what send_message does - consume the stream
            if hasattr(msg.text, "__anext__"):
                full_text = ""
                try:
                    async for chunk in msg.text:
                        if hasattr(chunk, "content"):
                            full_text += chunk.content or ""
                except AttributeError:
                    # Handle chunks that don't have 'content' attribute
                    pass
                msg.text = full_text
            return msg

        call_model.send_message = mock_send_message
        call_model.set(
            input_value=Message(text="test"),
            tools=[MockURLTool()],
        )

        # Run the internal call
        result = await call_model._call_model_internal()

        # Verify tool_calls structure
        assert result.data.get("has_tool_calls") is True
        tool_calls = result.data.get("tool_calls", [])
        assert len(tool_calls) > 0

        for tc in tool_calls:
            assert tc.get("name"), f"tool_call missing 'name': {tc}"
            assert tc.get("id"), f"tool_call missing 'id': {tc}"
            assert "args" in tc, f"tool_call missing 'args': {tc}"


class TestMessageHistoryThroughLoop:
    """Tests for message history accumulation through the agent loop."""

    @pytest.mark.asyncio
    async def test_message_history_includes_tool_results(self):
        """Test that message history properly includes AI message + tool results.

        After one tool call iteration, the history should contain:
        1. Original user message
        2. AI message with tool_calls
        3. Tool result message
        """
        # This tests the _convert_to_lc_messages function indirectly
        from lfx.schema.dataframe import DataFrame

        comp = CallModelComponent(_id="test")

        # Simulate DataFrame that would come from WhileLoop after one iteration
        df = DataFrame(
            [
                {
                    "text": "get me docs.langflow.org",
                    "sender": "User",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "is_tool_result": False,
                },
                {
                    "text": "Let me fetch that.",
                    "sender": "Machine",
                    "tool_calls": [
                        {"name": "fetch_url", "args": {"url": "https://docs.langflow.org"}, "id": "call_123"}
                    ],
                    "tool_call_id": None,
                    "is_tool_result": False,
                },
                {
                    "text": "Content from docs.langflow.org: Documentation here.",
                    "sender": "Tool",
                    "tool_calls": None,
                    "tool_call_id": "call_123",
                    "is_tool_result": True,
                },
            ]
        )

        lc_messages = comp._convert_to_lc_messages(df)

        # Verify message types
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        assert len(lc_messages) == 3
        assert isinstance(lc_messages[0], HumanMessage)
        assert isinstance(lc_messages[1], AIMessage)
        assert isinstance(lc_messages[2], ToolMessage)

        # Verify AI message has tool_calls
        ai_msg = lc_messages[1]
        assert hasattr(ai_msg, "tool_calls")
        assert len(ai_msg.tool_calls) == 1
        assert ai_msg.tool_calls[0]["name"] == "fetch_url"
        assert ai_msg.tool_calls[0]["id"] == "call_123"

        # Verify tool message has correct tool_call_id
        tool_msg = lc_messages[2]
        assert tool_msg.tool_call_id == "call_123"

    @pytest.mark.asyncio
    async def test_multiple_iterations_accumulate_correctly(self):
        """Test that multiple loop iterations accumulate messages correctly."""
        from lfx.schema.dataframe import DataFrame

        comp = CallModelComponent(_id="test")

        # Simulate DataFrame after TWO tool call iterations
        df = DataFrame(
            [
                # Initial user message
                {
                    "text": "research langflow",
                    "sender": "User",
                    "tool_calls": None,
                    "tool_call_id": None,
                    "is_tool_result": False,
                },
                # First AI + tool
                {
                    "text": "Searching...",
                    "sender": "Machine",
                    "tool_calls": [{"name": "search", "args": {"q": "langflow"}, "id": "call_1"}],
                    "tool_call_id": None,
                    "is_tool_result": False,
                },
                {
                    "text": "Search results...",
                    "sender": "Tool",
                    "tool_calls": None,
                    "tool_call_id": "call_1",
                    "is_tool_result": True,
                },
                # Second AI + tool
                {
                    "text": "Getting more info...",
                    "sender": "Machine",
                    "tool_calls": [{"name": "fetch_url", "args": {"url": "https://langflow.org"}, "id": "call_2"}],
                    "tool_call_id": None,
                    "is_tool_result": False,
                },
                {
                    "text": "Page content...",
                    "sender": "Tool",
                    "tool_calls": None,
                    "tool_call_id": "call_2",
                    "is_tool_result": True,
                },
            ]
        )

        lc_messages = comp._convert_to_lc_messages(df)

        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        assert len(lc_messages) == 5
        assert isinstance(lc_messages[0], HumanMessage)
        assert isinstance(lc_messages[1], AIMessage)
        assert isinstance(lc_messages[2], ToolMessage)
        assert isinstance(lc_messages[3], AIMessage)
        assert isinstance(lc_messages[4], ToolMessage)

        # Verify tool_call_ids match
        assert lc_messages[1].tool_calls[0]["id"] == "call_1"
        assert lc_messages[2].tool_call_id == "call_1"
        assert lc_messages[3].tool_calls[0]["id"] == "call_2"
        assert lc_messages[4].tool_call_id == "call_2"
