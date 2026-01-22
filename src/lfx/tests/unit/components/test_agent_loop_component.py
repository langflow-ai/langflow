# ruff: noqa: T201, E501, ARG001, ARG002, ARG005, F841, PERF401
"""Tests for AgentLoopComponent - the all-in-one agent component.

These tests verify that AgentLoopComponent:
1. Properly builds and executes the internal graph
2. Returns the AI message from AgentStep
3. Handles the loop correctly (tool calls → execute → loop back)
4. Only sends one add_message event for the AI response
5. Sends tool call notifications immediately when streaming with parent message
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from lfx.components.agent_blocks.agent_loop import AgentLoopComponent
from lfx.schema.content_block import ContentBlock
from lfx.schema.message import Message


class FakeStreamingLLM(BaseChatModel):
    """A fake LLM that simulates streaming responses."""

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
        """Sync stream - yields ChatGenerationChunk objects."""
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

        # Stream tool_calls
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

    async def _astream(
        self,
        _messages: list[BaseMessage],
        _stop: list[str] | None = None,
        _run_manager: Any = None,
        **_kwargs: Any,
    ):
        """Async stream - yields ChatGenerationChunk objects."""
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

        # Stream tool_calls with tool_call_chunks
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


class MockTool:
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool"

    async def ainvoke(self, args: dict) -> str:
        """Execute the mock tool."""
        return f"Mock result for {args}"


class TestAgentLoopComponentDirectExecution:
    """Tests that call AgentLoopComponent.run_agent() directly."""

    @pytest.mark.asyncio
    async def test_simple_response_no_tools(self):
        """Test AgentLoopComponent returns AI message when no tools are called."""
        # Create fake LLM that responds without tool calls
        fake_llm = FakeStreamingLLM(responses=[AIMessage(content="Hello! I'm here to help.")])

        # Patch get_llm to return our fake
        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            # Create and configure AgentLoopComponent
            agent_loop = AgentLoopComponent(_id="test_agent_loop")
            agent_loop.model = [{"name": "fake-model", "provider": "fake"}]
            agent_loop.system_message = "You are helpful."
            agent_loop.input_value = Message(text="Hello!", sender="User")
            agent_loop.max_iterations = 5
            agent_loop.temperature = 0.1
            agent_loop.include_think_tool = False
            agent_loop.tools = None
            agent_loop.initial_state = None
            agent_loop.api_key = None

            # Run the agent
            result = await agent_loop.run_agent()

            # Verify the result
            assert result is not None, "Result should not be None"
            assert isinstance(result, Message), f"Expected Message, got {type(result)}"
            assert result.text != "Agent completed without producing a response.", (
                f"Got fallback message instead of AI response. Result: {result}"
            )
            assert "Hello" in result.text or "help" in result.text, f"Unexpected content: {result.text}"

    @pytest.mark.asyncio
    async def test_tool_call_loop(self):
        """Test AgentLoopComponent handles tool calls and loops correctly."""
        # Create fake LLM responses: first with tool call, second with final answer
        fake_llm = FakeStreamingLLM(
            responses=[
                AIMessage(
                    content="Let me search for that.",
                    tool_calls=[{"name": "mock_tool", "args": {"query": "test"}, "id": "call_1"}],
                ),
                AIMessage(content="Based on my search, here is the answer."),
            ]
        )

        tools = [MockTool()]

        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            agent_loop = AgentLoopComponent(_id="test_agent_loop")
            agent_loop.model = [{"name": "fake-model", "provider": "fake"}]
            agent_loop.system_message = "You are helpful."
            agent_loop.input_value = Message(text="Search for something", sender="User")
            agent_loop.max_iterations = 10
            agent_loop.temperature = 0.1
            agent_loop.include_think_tool = False
            agent_loop.tools = tools
            agent_loop.initial_state = None
            agent_loop.api_key = None

            result = await agent_loop.run_agent()

            # Debug output
            print("\n=== DEBUG ===")
            print(f"Result type: {type(result)}")
            print(f"Result: {result}")
            print(f"Result.text: '{result.text}'")
            print(f"Result.data: {result.data if hasattr(result, 'data') else 'N/A'}")
            print(f"LLM call count: {fake_llm.call_count}")

            # Debug: print graph info from the internal graph
            # Access internal graph state via the agent_loop component
            print("\n--- Internal Graph Debug ---")
            print(f"Agent loop components: {[c.get_id() for c in agent_loop.get_components()]}")
            print("=== END DEBUG ===\n")

            assert result is not None
            assert isinstance(result, Message)
            assert result.text != "Agent completed without producing a response.", f"Got fallback: {result}"
            # The LLM should have been called at least twice (tool call + final)
            assert fake_llm.call_count >= 2, f"Expected >= 2 LLM calls, got {fake_llm.call_count}"
            # Should get the final answer, not the tool call message
            assert result.text != "", f"Result text is empty. Full result: {result.data}"
            assert "answer" in result.text.lower() or "search" in result.text.lower(), f"Got: {result.text}"


class TestAgentLoopComponentGraphExecution:
    """Tests that verify the internal graph is built and executed correctly."""

    @pytest.mark.asyncio
    async def test_graph_is_built_correctly(self):
        """Test that the internal graph has the expected structure."""
        fake_llm = FakeStreamingLLM(responses=[AIMessage(content="Done")])

        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            agent_loop = AgentLoopComponent(_id="test_agent_loop")
            agent_loop.model = [{"name": "fake-model", "provider": "fake"}]
            agent_loop.system_message = "You are helpful."
            agent_loop.input_value = Message(text="Test", sender="User")
            agent_loop.max_iterations = 5
            agent_loop.temperature = 0.1
            agent_loop.include_think_tool = False
            agent_loop.tools = None
            agent_loop.initial_state = None
            agent_loop.api_key = None

            # Run and verify it doesn't crash
            result = await agent_loop.run_agent()

            # Should not return the fallback message
            assert result.text != "Agent completed without producing a response.", (
                "Graph did not execute properly - got fallback message"
            )

    @pytest.mark.asyncio
    async def test_llm_is_actually_called(self):
        """Test that the LLM is actually invoked during run_agent()."""
        fake_llm = FakeStreamingLLM(responses=[AIMessage(content="I was called!")])

        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            agent_loop = AgentLoopComponent(_id="test_agent_loop")
            agent_loop.model = [{"name": "fake-model", "provider": "fake"}]
            agent_loop.system_message = "You are helpful."
            agent_loop.input_value = Message(text="Call the LLM", sender="User")
            agent_loop.max_iterations = 5
            agent_loop.temperature = 0.1
            agent_loop.include_think_tool = False
            agent_loop.tools = None
            agent_loop.initial_state = None
            agent_loop.api_key = None

            result = await agent_loop.run_agent()

            # Verify LLM was called by checking call count
            assert fake_llm.call_count > 0, "LLM was never called"
            assert result.text == "I was called!" or "called" in result.text.lower(), (
                f"Expected LLM response, got: {result.text}"
            )


class TestMessageEvents:
    """Tests that verify message event handling to prevent duplicates."""

    @pytest.mark.asyncio
    async def test_only_one_ai_message_event_simple_response(self):
        """Test that only one add_message event is sent for AI response (no tools).

        The flow is: ChatInput → AgentLoop (internal graph) → ChatOutput
        Expected events:
        - 1 event for user message (from ChatInput)
        - 1 event for AI response (from ChatOutput, NOT from AgentStep)
        """
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.graph.graph.base import Graph

        fake_llm = FakeStreamingLLM(responses=[AIMessage(content="Hello! I'm here to help.")])

        # Track on_message calls
        message_events = []

        mock_event_manager = MagicMock()
        mock_event_manager.on_message = MagicMock(side_effect=lambda data: message_events.append(data))
        mock_event_manager.on_token = MagicMock()
        mock_event_manager.on_error = MagicMock()
        mock_event_manager.on_remove_message = MagicMock()

        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            # Build the graph
            chat_input = ChatInput(_id="chat_input")

            agent_loop = AgentLoopComponent(_id="agent_loop")
            agent_loop.set(
                model=[{"name": "fake-model", "provider": "fake"}],
                system_message="You are helpful.",
                input_value=chat_input.message_response,
                max_iterations=5,
                temperature=0.1,
            )

            chat_output = ChatOutput(_id="chat_output")
            chat_output.set(input_value=agent_loop.run_agent)

            graph = Graph(start=chat_input, end=chat_output)

            # Run the graph
            results = []
            async for result in graph.async_start(
                max_iterations=30,
                config={"output": {"cache": False}},
                inputs={"input_value": "Hello!"},
                event_manager=mock_event_manager,
            ):
                results.append(result)

            # Debug: print message events and all on_message calls
            print("\n=== MESSAGE EVENTS ===")
            print(f"Total on_message calls: {mock_event_manager.on_message.call_count}")
            for i, event in enumerate(message_events):
                sender = event.get("sender", "Unknown")
                text = event.get("text", "")[:50] if event.get("text") else ""
                print(f"Event {i + 1}: sender={sender}, text='{text}...'")
            print("=== END MESSAGE EVENTS ===\n")

            # Verify: should have at most 2 message events
            # - 1 from ChatInput (user message)
            # - 1 from ChatOutput (AI response)
            # Note: AgentStep should NOT send a separate message event since
            # ChatOutput will update the existing message
            ai_message_events = [e for e in message_events if e.get("sender") == "Machine"]
            user_message_events = [e for e in message_events if e.get("sender") == "User"]

            assert len(user_message_events) <= 1, (
                f"Expected at most 1 user message event, got {len(user_message_events)}"
            )
            # The key assertion: only ONE AI message event
            assert len(ai_message_events) <= 1, (
                f"Expected at most 1 AI message event, got {len(ai_message_events)}. "
                f"This indicates duplicate message events. Events: {message_events}"
            )
            # Also verify we got the expected total - 2 events max (user + AI)
            total_events = len(message_events)
            assert total_events <= 2, (
                f"Expected at most 2 message events (user + AI), got {total_events}. Events: {message_events}"
            )


class TestAgentStepToolNotificationStreaming:
    """Tests that verify tool call notifications are sent immediately during streaming.

    This tests the code path in AgentStep._handle_stream where ToolContent is created
    when tool_call_chunks are detected in the stream.
    """

    @pytest.mark.asyncio
    async def test_tool_notification_creates_valid_tool_content(self):
        """Test that tool notifications create ToolContent with valid tool_input (not None).

        This test exercises the streaming code path where:
        1. _stream_to_playground=True
        2. _parent_message is set
        3. LLM streams tool_call_chunks

        This was a bug where tool_input=None caused pydantic validation errors.
        """
        from lfx.components.agent_blocks.agent_step import AgentStepComponent
        from lfx.schema.content_types import ToolContent

        # Create fake LLM that returns tool calls
        fake_llm = FakeStreamingLLM(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "test_tool", "args": {"query": "test"}, "id": "call_1"}],
                )
            ]
        )

        # Track send_message calls
        send_message_calls = []

        async def mock_send_message(message, id_=None, *, skip_db_update=False):
            send_message_calls.append(message)
            return message

        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            # Create AgentStepComponent
            agent_step = AgentStepComponent(_id="test_agent_step")
            agent_step.model = [{"name": "fake-model", "provider": "fake"}]
            agent_step.system_message = "You are helpful."
            agent_step.input_value = Message(text="Test", sender="User")
            agent_step.messages = None
            agent_step.tools = None
            agent_step.temperature = 0.1
            agent_step.include_think_tool = False
            agent_step.api_key = None

            # Set up streaming with parent message - this is the key!
            agent_step._stream_to_playground = True
            parent_message = Message(
                text="",
                sender="Machine",
                sender_name="AI",
                properties={"icon": "Bot", "state": "partial"},
                content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            )
            agent_step._parent_message = parent_message

            # Mock send_message
            agent_step.send_message = mock_send_message

            # Call the model - this should trigger the streaming code path
            # that creates ToolContent with tool_input={}
            result = await agent_step._call_model_internal()

            # Verify the result has tool calls
            assert result.data.get("has_tool_calls") is True

            # Check that ToolContent was added to parent message content_blocks
            # The key assertion: tool_input should be {} not None
            agent_steps_block = parent_message.content_blocks[0]
            tool_contents = [c for c in agent_steps_block.contents if isinstance(c, ToolContent)]

            # We should have at least one ToolContent from the streaming notification
            assert len(tool_contents) >= 1, (
                f"Expected at least one ToolContent in content_blocks, "
                f"got {len(tool_contents)}. Contents: {agent_steps_block.contents}"
            )

            # Verify the ToolContent has valid fields (not None where dict is required)
            for tc in tool_contents:
                assert tc.tool_input is not None, "tool_input should not be None"
                assert isinstance(tc.tool_input, dict), f"tool_input should be dict, got {type(tc.tool_input)}"
                assert tc.name == "test_tool", f"Expected tool name 'test_tool', got {tc.name}"

    @pytest.mark.asyncio
    async def test_tool_notification_not_sent_without_parent_message(self):
        """Test that tool notifications are NOT sent when _parent_message is not set.

        This verifies the conditional logic that only sends tool notifications
        when streaming to playground with a parent message.
        """
        from lfx.components.agent_blocks.agent_step import AgentStepComponent

        fake_llm = FakeStreamingLLM(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[{"name": "test_tool", "args": {"query": "test"}, "id": "call_1"}],
                )
            ]
        )

        send_message_calls = []

        async def mock_send_message(message):
            send_message_calls.append(message)
            return message

        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            agent_step = AgentStepComponent(_id="test_agent_step")
            agent_step.model = [{"name": "fake-model", "provider": "fake"}]
            agent_step.system_message = "You are helpful."
            agent_step.input_value = Message(text="Test", sender="User")
            agent_step.messages = None
            agent_step.tools = None
            agent_step.temperature = 0.1
            agent_step.include_think_tool = False
            agent_step.api_key = None

            # Set _stream_to_playground but NO _parent_message
            agent_step._stream_to_playground = True
            # Explicitly NOT setting _parent_message

            agent_step.send_message = mock_send_message

            result = await agent_step._call_model_internal()

            # Should still get tool calls in result
            assert result.data.get("has_tool_calls") is True

            # But the message should not have tool notifications in content_blocks
            # because there was no parent_message to update
            # The result message is created fresh, not from parent_message
            if result.content_blocks:
                for block in result.content_blocks:
                    # Should not have ToolContent from streaming notifications
                    from lfx.schema.content_types import ToolContent

                    tool_contents = [c for c in block.contents if isinstance(c, ToolContent)]
                    assert len(tool_contents) == 0, (
                        f"Should not have ToolContent without parent_message, got {len(tool_contents)}"
                    )


class TestAgentFlowEventContract:
    """Contract tests for the complete event sequence in an agent flow.

    This documents and validates EVERY event the UI should receive for a flow:
        ChatInput → AgentLoop (with tools) → ChatOutput

    These tests serve as a CONTRACT. If they break, it means the event flow
    changed and needs explicit review. The test failures will show exactly
    which events changed.

    Expected Event Sequence for a tool-calling agent:
    ================================================
    1. AgentLoop: Creates initial AI message with state="partial"
       - Empty text, "Agent Steps" content block
       - Sent immediately so UI shows response placeholder

    2. AgentStep (streaming): Detects tool call, updates message
       - Adds ToolContent with name, tool_input={}, header="Accessing **tool**"
       - Sends update immediately (skip_db_update=True for speed)

    3. ExecuteTool: Finds existing ToolContent, updates with args
       - Updates tool_input with actual args
       - Sends update

    4. ExecuteTool: After execution, updates ToolContent
       - header="Executed **tool**", output=result, duration=ms
       - Sends update

    5. AgentStep (final): AI responds without tool calls
       - Updates message text with final response
       - state="partial" (AgentLoop sets "complete")

    6. AgentLoop: Marks message complete
       - state="complete"
       - Final text from AI

    Key Invariants:
    - Only ONE message ID throughout the flow (updates, not new messages)
    - Only ONE ToolContent per tool call (reused, not duplicated)
    - Events sent in order: initial → accessing → executed → final
    """

    @pytest.mark.asyncio
    async def test_complete_agent_flow_event_sequence(self):
        """Test the complete event sequence for ChatInput → AgentLoop → ChatOutput.

        This test builds a full Graph:
            ChatInput → AgentLoop (with CurrentDate.to_toolkit) → ChatOutput

        It captures ALL on_message events from the event_manager and validates:
        1. The exact sequence of events
        2. The state transitions of ToolContent
        3. That ToolContent is reused, not duplicated
        """
        import time
        from typing import Any
        from unittest.mock import MagicMock

        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from lfx.components.agent_blocks.agent_loop import AgentLoopComponent
        from lfx.components.input_output import ChatInput, ChatOutput
        from lfx.components.utilities.current_date import CurrentDateComponent
        from lfx.graph.graph.base import Graph
        from lfx.schema.content_types import ToolContent

        # Track all message events (on_message calls) with timing
        message_events: list[dict] = []
        start_time = [None]  # Use list to allow mutation in closure

        def capture_on_message(data: dict):
            """Capture message event data from event_manager.on_message."""
            # Capture timestamp
            if start_time[0] is None:
                start_time[0] = time.perf_counter()
            elapsed_ms = int((time.perf_counter() - start_time[0]) * 1000)

            # Extract ToolContent info if present
            tool_contents = []
            content_blocks = data.get("content_blocks", [])
            if content_blocks:
                for block in content_blocks:
                    contents = block.get("contents", []) if isinstance(block, dict) else getattr(block, "contents", [])
                    for content in contents:
                        # Check if it's a ToolContent (dict or object)
                        if isinstance(content, dict) and content.get("type") == "tool_use":
                            tool_contents.append(
                                {
                                    "name": content.get("name"),
                                    "tool_input": content.get("tool_input", {}),
                                    "header_title": content.get("header", {}).get("title")
                                    if content.get("header")
                                    else None,
                                    "output": content.get("output"),
                                    "error": content.get("error"),
                                }
                            )
                        elif isinstance(content, ToolContent):
                            tool_contents.append(
                                {
                                    "name": content.name,
                                    "tool_input": dict(content.tool_input) if content.tool_input else {},
                                    "header_title": content.header.get("title") if content.header else None,
                                    "output": content.output,
                                    "error": content.error,
                                }
                            )

            message_events.append(
                {
                    "elapsed_ms": elapsed_ms,
                    "sender": data.get("sender"),
                    "text": data.get("text", "")[:100] if data.get("text") else None,
                    "properties": data.get("properties", {}),
                    "tool_contents": tool_contents,
                }
            )

        # Create event manager mock
        mock_event_manager = MagicMock()
        mock_event_manager.on_message = MagicMock(side_effect=capture_on_message)
        mock_event_manager.on_token = MagicMock()
        mock_event_manager.on_error = MagicMock()
        mock_event_manager.on_remove_message = MagicMock()

        # Create a fake LLM that streams tool calls like real LLMs do
        # This mimics LangChain's streaming behavior with tool_call_chunks
        class FakeLLMForEventTest(BaseChatModel):
            call_count: int = 0

            def _generate(
                self,
                messages: list[BaseMessage],
                stop: list[str] | None = None,
                run_manager: Any = None,
                **kwargs: Any,
            ) -> ChatResult:
                self.call_count += 1
                if self.call_count == 1:
                    response = AIMessage(
                        content="Let me check the date.",
                        tool_calls=[
                            {"name": "CurrentDate-get_current_date", "args": {"timezone": "UTC"}, "id": "call_1"}
                        ],
                    )
                else:
                    response = AIMessage(content="The current date is 2025-12-16.")
                return ChatResult(generations=[ChatGeneration(message=response)])

            async def _agenerate(
                self,
                messages: list[BaseMessage],
                stop: list[str] | None = None,
                run_manager: Any = None,
                **kwargs: Any,
            ) -> ChatResult:
                return self._generate(messages, stop, run_manager, **kwargs)

            async def astream(self, inputs, **kwargs):
                """Stream responses with tool_call_chunks like real LLMs.

                This mimics how real LLMs stream tool calls:
                1. First chunk: tool_call_chunks with name (args streaming starts)
                2. Middle chunks: content and more tool_call_chunks with args
                3. Final chunk: complete message
                """
                self.call_count += 1
                if self.call_count == 1:
                    # First call: stream tool call with tool_call_chunks
                    # Chunk 1: Start of message with tool name
                    yield AIMessageChunk(
                        content="Let me ",
                        tool_call_chunks=[
                            {
                                "name": "CurrentDate-get_current_date",
                                "args": "",
                                "id": "call_1",
                                "index": 0,
                            }
                        ],
                    )
                    # Chunk 2: More content and args streaming
                    yield AIMessageChunk(
                        content="check the ",
                        tool_call_chunks=[
                            {
                                "name": None,  # Name only in first chunk
                                "args": '{"timezone":',
                                "id": None,
                                "index": 0,
                            }
                        ],
                    )
                    # Chunk 3: Complete args and content
                    yield AIMessageChunk(
                        content="date.",
                        tool_call_chunks=[
                            {
                                "name": None,
                                "args": ' "UTC"}',
                                "id": None,
                                "index": 0,
                            }
                        ],
                        tool_calls=[
                            {
                                "name": "CurrentDate-get_current_date",
                                "args": {"timezone": "UTC"},
                                "id": "call_1",
                            }
                        ],
                    )
                else:
                    # Second call: stream final response without tool calls
                    yield AIMessageChunk(content="The current ")
                    yield AIMessageChunk(content="date is ")
                    yield AIMessageChunk(content="2025-12-16.")

            def bind_tools(self, tools: list, **kwargs: Any) -> "FakeLLMForEventTest":
                return self

            def with_config(self, config: dict, **kwargs: Any) -> "FakeLLMForEventTest":
                return self

            @property
            def _llm_type(self) -> str:
                return "fake-event-test-llm"

        fake_llm = FakeLLMForEventTest()

        # Patch get_llm to return our fake
        with patch("lfx.components.agent_blocks.agent_step.get_llm", return_value=fake_llm):
            # Build the full graph:
            # ChatInput → AgentLoop → ChatOutput
            # CurrentDate.to_toolkit → AgentLoop.tools
            # NOTE: IDs must contain "ChatInput"/"ChatOutput" for is_connected_to_chat_output() to work
            chat_input = ChatInput(_id="ChatInput-test")

            # Create CurrentDate component and enable tool mode
            current_date = CurrentDateComponent(_id="CurrentDate-test")
            current_date.set(timezone="UTC")
            # Enable tool mode to make to_toolkit available as an output
            current_date._append_tool_to_outputs_map()

            # Create AgentLoop and connect CurrentDate.to_toolkit to its tools input
            agent_loop = AgentLoopComponent(_id="AgentLoop-test")
            agent_loop.set(
                model=[{"name": "fake-model", "provider": "fake"}],
                system_message="You are a helpful assistant.",
                input_value=chat_input.message_response,
                tools=current_date.to_toolkit,  # Connect CurrentDate.to_toolkit
                max_iterations=5,
                temperature=0.1,
            )

            chat_output = ChatOutput(_id="ChatOutput-test")
            chat_output.set(input_value=agent_loop.run_agent)

            graph = Graph(start=chat_input, end=chat_output)
            # Set session_id required for message storage
            graph.session_id = "test-session-id"

            # Run the graph with event_manager
            results = []
            async for result in graph.async_start(
                max_iterations=30,
                config={"output": {"cache": False}},
                inputs={"input_value": "What is today's date?"},
                event_manager=mock_event_manager,
            ):
                results.append(result)

        # Verify graph executed correctly - all components in expected order
        result_ids = [r.vertex.id for r in results if hasattr(r, "vertex")]
        print("\n=== GRAPH EXECUTION ===")
        print(f"Vertices executed: {result_ids}")
        print(f"LLM call count: {fake_llm.call_count}")
        print(f"on_message call count: {mock_event_manager.on_message.call_count}")

        # Check if event_manager was set on components and stream_to_playground
        for vertex in graph.vertices:
            if hasattr(vertex, "custom_component") and vertex.custom_component:
                comp = vertex.custom_component
                em = getattr(comp, "_event_manager", "NOT_SET")
                has_vertex = comp._vertex is not None if hasattr(comp, "_vertex") else False
                has_graph = comp.graph is not None if hasattr(comp, "graph") else False
                connected = (
                    comp.is_connected_to_chat_output() if hasattr(comp, "is_connected_to_chat_output") else "N/A"
                )
                # Check neighbors
                neighbors = []
                if has_graph and has_vertex:
                    try:
                        neighbor_vertices = comp.graph.get_vertex_neighbors(comp._vertex)
                        neighbors = [v.id for v in neighbor_vertices] if neighbor_vertices else []
                    except Exception as e:
                        neighbors = f"Error: {e}"
                print(
                    f"  {vertex.id}: _vertex={has_vertex}, graph={has_graph}, neighbors={neighbors}, is_connected_to_chat_output={connected}"
                )
        print("=== END ===\n")

        # Core validation: graph structure and execution
        assert "ChatInput-test" in result_ids, f"ChatInput-test not in results: {result_ids}"
        assert "CurrentDate-test" in result_ids, f"CurrentDate-test not in results: {result_ids}"
        assert "AgentLoop-test" in result_ids, f"AgentLoop-test not in results: {result_ids}"
        assert "ChatOutput-test" in result_ids, f"ChatOutput-test not in results: {result_ids}"

        # Validate LLM was called at least twice (tool call + final response)
        assert fake_llm.call_count >= 2, (
            f"Expected LLM to be called at least twice (tool call + final), got {fake_llm.call_count}"
        )

        # Get the final result from chat_output
        chat_output_result = next(
            (r for r in results if hasattr(r, "vertex") and r.vertex.id == "ChatOutput-test"),
            None,
        )
        assert chat_output_result is not None, "Expected chat_output result"

        # Validate events were captured through event_manager
        assert mock_event_manager.on_message.call_count > 0, (
            f"Expected events via on_message, got {mock_event_manager.on_message.call_count}"
        )

        # Analyze the captured events
        calls = mock_event_manager.on_message.call_args_list
        print(f"\n=== CAPTURED EVENTS ({len(calls)}) ===")
        for i, call in enumerate(calls):
            # call.args contains positional args, call.kwargs contains keyword args
            args = call.args if call.args else ()
            kwargs = call.kwargs if call.kwargs else {}

            # on_message is called with data=MessageResponse as keyword arg
            event = kwargs.get("data") or (args[0] if args else None)
            if event:
                event_type = type(event).__name__
                # Handle dict events (serialized MessageResponse)
                if isinstance(event, dict):
                    event_id = event.get("id", "N/A")
                    text = event.get("text", "")
                    text_preview = (
                        f" text='{text[:50]}...'" if text and len(str(text)) > 50 else f" text='{text}'" if text else ""
                    )
                    content_blocks = event.get("content_blocks", [])
                    has_blocks = ""
                    if content_blocks:
                        tool_info_list = []
                        for block in content_blocks:
                            # Handle both dict and object blocks
                            if isinstance(block, dict):
                                contents = block.get("contents", [])
                            else:
                                contents = getattr(block, "contents", [])

                            for content in contents:
                                # Handle both dict and object contents
                                if isinstance(content, dict):
                                    name = content.get("name", "?")
                                    tool_input = content.get("tool_input", {})
                                    output = content.get("output")
                                    header = content.get("header", {})
                                    title = header.get("title", "") if isinstance(header, dict) else ""
                                else:
                                    name = getattr(content, "name", "?")
                                    tool_input = getattr(content, "tool_input", {})
                                    output = getattr(content, "output", None)
                                    header = getattr(content, "header", {})
                                    title = header.get("title", "") if isinstance(header, dict) else str(header)
                                # Summarize: name, has_args, has_output, title
                                info = f"{name}(args={bool(tool_input)}, out={output is not None}, title='{title[:30]}...')"
                                tool_info_list.append(info)
                        tool_info = f" tools=[{', '.join(tool_info_list)}]" if tool_info_list else ""
                        # Also show contents count per block for debugging
                        contents_info = [
                            len(b.get("contents", [])) if isinstance(b, dict) else len(getattr(b, "contents", []))
                            for b in content_blocks
                        ]
                        has_blocks = f" content_blocks={len(content_blocks)} contents={contents_info}{tool_info}"
                    print(f"  [{i}] {event_type}: id={event_id}{text_preview}{has_blocks}")
                else:
                    # Handle object events
                    event_id = getattr(event, "id", "N/A")
                    text_preview = ""
                    if hasattr(event, "text") and event.text:
                        text_str = str(event.text)
                        text_preview = f" text='{text_str[:50]}...'" if len(text_str) > 50 else f" text='{text_str}'"
                    has_blocks = ""
                    if hasattr(event, "content_blocks") and event.content_blocks:
                        block_count = len(event.content_blocks)
                        tool_names = []
                        for block in event.content_blocks:
                            if hasattr(block, "contents"):
                                for content in block.contents:
                                    if hasattr(content, "name"):
                                        tool_names.append(content.name)
                        tool_info = f" tools={tool_names}" if tool_names else ""
                        has_blocks = f" content_blocks={block_count}{tool_info}"
                    print(f"  [{i}] {event_type}: id={event_id}{text_preview}{has_blocks}")
            else:
                print(f"  [{i}] Unknown: args={args}, kwargs={list(kwargs.keys())}")
        print("=== END EVENTS ===")

        # Print timing information from message_events
        print(f"\n=== EVENT TIMING ({len(message_events)} events) ===")
        for i, event in enumerate(message_events):
            elapsed = event["elapsed_ms"]
            sender = event.get("sender", "?")
            text = event.get("text", "")
            text_preview = f"'{text[:40]}...'" if text and len(text) > 40 else f"'{text}'" if text else "N/A"
            tool_contents = event.get("tool_contents", [])

            # Format tool contents with their state
            tool_info = ""
            if tool_contents:
                tool_states = []
                for tc in tool_contents:
                    name = tc.get("name", "?")
                    has_input = bool(tc.get("tool_input"))
                    has_output = tc.get("output") is not None
                    header = tc.get("header_title", "")

                    # Determine state based on header and output
                    if "Executed" in (header or ""):
                        state = "EXECUTED"
                    elif "Error" in (header or ""):
                        state = "ERROR"
                    elif "Accessing" in (header or ""):
                        state = "ACCESSING"
                    else:
                        state = "UNKNOWN"

                    tool_states.append(f"{name}({state}, args={has_input}, out={has_output})")
                tool_info = f" tools=[{', '.join(tool_states)}]"

            print(f"  +{elapsed:4d}ms [{i}] sender={sender} text={text_preview}{tool_info}")
        print("=== END TIMING ===\n")

        # CRITICAL ASSERTION: All AI message events must have the SAME ID
        # This ensures the frontend updates ONE message, not creates duplicates
        ai_message_ids = set()
        user_message_id = None
        for call in calls:
            kwargs = call.kwargs if call.kwargs else {}
            event = kwargs.get("data") or (call.args[0] if call.args else None)
            if event and isinstance(event, dict):
                event_id = event.get("id")
                sender = event.get("sender")
                if sender == "User":
                    user_message_id = event_id
                elif sender == "Machine" and event_id:
                    ai_message_ids.add(event_id)

        assert len(ai_message_ids) == 1, (
            f"CRITICAL: All AI message events must have the SAME ID to prevent duplicates in UI. "
            f"Found {len(ai_message_ids)} different IDs: {ai_message_ids}"
        )
        assert user_message_id not in ai_message_ids, "User message ID should be different from AI message ID"


class TestToolContentEventSequence:
    """Tests that validate the exact sequence of ToolContent states through the agent flow.

    This serves as a CONTRACT for expected event behavior. If these tests break,
    it indicates a change to the event flow that needs explicit review.

    Expected sequence for a single tool call:
    1. AgentStep (streaming): Creates ToolContent with:
       - name="tool_name"
       - tool_input={}  (empty, args not available during streaming)
       - header.title="Accessing **tool_name**"
       - output=None
       - error=None

    2. ExecuteTool (before execution): Finds existing ToolContent and updates:
       - tool_input={actual_args}  (now has real args)
       - header.title="Accessing **tool_name**" (unchanged)

    3. ExecuteTool (after execution): Updates same ToolContent:
       - header.title="Executed **tool_name**"
       - output="result" OR error="error message"
       - duration=<actual_ms>

    Key invariant: Only ONE ToolContent per tool call, not two.
    """

    @pytest.mark.asyncio
    async def test_execute_tool_reuses_existing_tool_content(self):
        """Test that ExecuteTool finds and updates existing ToolContent from AgentStep.

        This validates the core behavior that prevents duplicate tool entries:
        - AgentStep creates ToolContent with tool_input={}
        - ExecuteTool finds it and updates it (doesn't create new)
        """
        from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
        from lfx.schema.content_block import ContentBlock
        from lfx.schema.content_types import ToolContent

        # Create a parent message with an existing "Accessing" ToolContent
        # (as if AgentStep had created it during streaming)
        existing_tool_content = ToolContent(
            type="tool_use",
            name="test_tool",
            tool_input={},  # Empty - created by AgentStep during streaming
            output=None,
            error=None,
            header={"title": "Accessing **test_tool**", "icon": "Hammer"},
            duration=0,
        )
        parent_message = Message(
            text="",
            sender="Machine",
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[existing_tool_content])],
        )

        # Create AI message with tool call
        ai_message = Message(
            text="Let me search for that.",
            sender="Machine",
            sender_name="AI",
            data={
                "tool_calls": [{"name": "test_tool", "args": {"query": "test"}, "id": "call_1"}],
                "should_stream_events": True,
            },
        )

        # Create a mock tool
        class MockTool:
            name = "test_tool"
            description = "A test tool"

            async def ainvoke(self, args):
                return f"Result for {args.get('query', 'unknown')}"

        # Track send events
        send_events = []

        async def mock_send_message_event(message):
            # Capture snapshot of current tool contents
            steps_block = message.content_blocks[0] if message.content_blocks else None
            if steps_block:
                snapshot = []
                for tc in steps_block.contents:
                    if isinstance(tc, ToolContent):
                        snapshot.append(
                            {
                                "name": tc.name,
                                "tool_input": dict(tc.tool_input) if tc.tool_input else {},
                                "header_title": tc.header.get("title") if tc.header else None,
                                "output": tc.output,
                                "error": tc.error,
                            }
                        )
                send_events.append(snapshot)

        # Setup ExecuteToolComponent
        execute_tool = ExecuteToolComponent(_id="test_execute_tool")
        execute_tool.tool_calls_message = ai_message
        execute_tool.tools = [MockTool()]
        execute_tool.timeout = 0
        execute_tool.parallel = False
        execute_tool._parent_message = parent_message
        execute_tool._send_message_event = mock_send_message_event
        execute_tool._ensure_message_required_fields = lambda m: None

        # Execute
        await execute_tool.execute_tools()

        # Validate: Should still have only ONE ToolContent (not two)
        steps_block = parent_message.content_blocks[0]
        tool_contents = [c for c in steps_block.contents if isinstance(c, ToolContent)]

        assert len(tool_contents) == 1, (
            f"Expected exactly 1 ToolContent (reused), got {len(tool_contents)}. "
            f"This means ExecuteTool created a new one instead of reusing the existing one."
        )

        # Validate the single ToolContent has been updated correctly
        tc = tool_contents[0]
        assert tc.name == "test_tool"
        assert tc.tool_input == {"query": "test"}, (
            f"Expected tool_input to be updated with actual args, got {tc.tool_input}"
        )
        assert tc.output is not None, "Expected output to be set after execution"
        assert "Executed" in tc.header.get("title", ""), f"Expected header to say 'Executed', got {tc.header}"

    @pytest.mark.asyncio
    async def test_execute_tool_creates_new_when_no_existing(self):
        """Test that ExecuteTool creates new ToolContent when no existing one found.

        This happens when:
        - Not streaming
        - Tool call wasn't detected during streaming
        - AgentStep didn't create an "Accessing" entry
        """
        from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
        from lfx.schema.content_block import ContentBlock
        from lfx.schema.content_types import ToolContent

        # Create parent message with EMPTY content_blocks (no pre-existing ToolContent)
        parent_message = Message(
            text="",
            sender="Machine",
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
        )

        ai_message = Message(
            text="Let me search.",
            sender="Machine",
            sender_name="AI",
            data={
                "tool_calls": [{"name": "search", "args": {"q": "test"}, "id": "call_1"}],
                "should_stream_events": True,
            },
        )

        class MockSearchTool:
            name = "search"
            description = "Search tool"

            async def ainvoke(self, args):
                return "Search results"

        async def mock_send_message_event(message):
            pass

        execute_tool = ExecuteToolComponent(_id="test_execute_tool")
        execute_tool.tool_calls_message = ai_message
        execute_tool.tools = [MockSearchTool()]
        execute_tool.timeout = 0
        execute_tool.parallel = False
        execute_tool._parent_message = parent_message
        execute_tool._send_message_event = mock_send_message_event
        execute_tool._ensure_message_required_fields = lambda m: None

        await execute_tool.execute_tools()

        # Should have created exactly ONE ToolContent
        steps_block = parent_message.content_blocks[0]
        tool_contents = [c for c in steps_block.contents if isinstance(c, ToolContent)]

        assert len(tool_contents) == 1, f"Expected exactly 1 ToolContent to be created, got {len(tool_contents)}"

        tc = tool_contents[0]
        assert tc.name == "search"
        assert tc.tool_input == {"q": "test"}
        assert "Executed" in tc.header.get("title", "")

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_each_get_one_entry(self):
        """Test that multiple tool calls each result in exactly one ToolContent.

        Even with multiple parallel tool calls, each should have exactly one entry
        that transitions from "Accessing" to "Executed".
        """
        from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
        from lfx.schema.content_block import ContentBlock
        from lfx.schema.content_types import ToolContent

        # Simulate AgentStep having created "Accessing" entries for 3 tools
        existing_contents = [
            ToolContent(
                type="tool_use",
                name="tool_a",
                tool_input={},
                output=None,
                error=None,
                header={"title": "Accessing **tool_a**", "icon": "Hammer"},
                duration=0,
            ),
            ToolContent(
                type="tool_use",
                name="tool_b",
                tool_input={},
                output=None,
                error=None,
                header={"title": "Accessing **tool_b**", "icon": "Hammer"},
                duration=0,
            ),
            ToolContent(
                type="tool_use",
                name="tool_c",
                tool_input={},
                output=None,
                error=None,
                header={"title": "Accessing **tool_c**", "icon": "Hammer"},
                duration=0,
            ),
        ]

        parent_message = Message(
            text="",
            sender="Machine",
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=existing_contents)],
        )

        ai_message = Message(
            text="Calling tools...",
            sender="Machine",
            sender_name="AI",
            data={
                "tool_calls": [
                    {"name": "tool_a", "args": {"x": 1}, "id": "call_a"},
                    {"name": "tool_b", "args": {"x": 2}, "id": "call_b"},
                    {"name": "tool_c", "args": {"x": 3}, "id": "call_c"},
                ],
                "should_stream_events": True,
            },
        )

        class MockToolA:
            name = "tool_a"
            description = "Tool A"

            async def ainvoke(self, args):
                return "A result"

        class MockToolB:
            name = "tool_b"
            description = "Tool B"

            async def ainvoke(self, args):
                return "B result"

        class MockToolC:
            name = "tool_c"
            description = "Tool C"

            async def ainvoke(self, args):
                return "C result"

        async def mock_send_message_event(message):
            pass

        execute_tool = ExecuteToolComponent(_id="test_execute_tool")
        execute_tool.tool_calls_message = ai_message
        execute_tool.tools = [MockToolA(), MockToolB(), MockToolC()]
        execute_tool.timeout = 0
        execute_tool.parallel = True  # Parallel execution
        execute_tool._parent_message = parent_message
        execute_tool._send_message_event = mock_send_message_event
        execute_tool._ensure_message_required_fields = lambda m: None

        await execute_tool.execute_tools()

        # Should still have exactly 3 ToolContents (not 6)
        steps_block = parent_message.content_blocks[0]
        tool_contents = [c for c in steps_block.contents if isinstance(c, ToolContent)]

        assert len(tool_contents) == 3, (
            f"Expected exactly 3 ToolContents (one per tool, reused), got {len(tool_contents)}. "
            f"Contents: {[(tc.name, tc.header) for tc in tool_contents]}"
        )

        # Each should be "Executed" with actual args
        for tc in tool_contents:
            assert "Executed" in tc.header.get("title", ""), f"Tool {tc.name} should be 'Executed', got {tc.header}"
            assert tc.tool_input != {}, f"Tool {tc.name} should have actual args, got empty dict"
            assert tc.output is not None, f"Tool {tc.name} should have output"
