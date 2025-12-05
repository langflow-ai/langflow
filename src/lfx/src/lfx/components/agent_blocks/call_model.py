"""CallModel component - sends messages to an LLM and returns the response.

This is a primitive building block for creating agents. It takes a list of messages
and optional tools, sends them to a language model, and returns the response message.

The component has two outputs that act like a conditional router:
- AI Message: Fires when the model is done (no tool calls)
- Tool Calls: Fires when the model wants to call tools

This enables visual agent loops:
ChatInput → WhileLoop → CallModel → [Tool Calls] → ExecuteTool → FormatResult → WhileLoop
                              ↓ [AI Message - done]
                         ChatOutput
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage

if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler

from lfx.base.agents.message_utils import (
    convert_to_lc_messages,
    extract_content_blocks_from_dataframe,
    extract_message_id_from_dataframe,
    sanitize_tool_calls,
)
from lfx.base.models.language_model_mixin import LanguageModelMixin
from lfx.components.agent_blocks.think_tool import ThinkToolComponent
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, HandleInput, MultilineInput, Output
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict  # noqa: TC001
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


class CallModelComponent(LanguageModelMixin, Component):
    """Sends messages to an LLM and routes based on tool calls.

    This component is a building block for agent workflows. It:
    1. Takes messages (conversation history) as input (DataFrame or Message)
    2. Optionally binds tools to the LLM for function calling
    3. Invokes the LLM and routes the response:
       - If has tool_calls → outputs on "tool_calls" (continue loop)
       - If no tool_calls → outputs on "ai_message" (done, exit loop)

    Connect "tool_calls" to ExecuteTool for agent loops.
    Connect "ai_message" to ChatOutput for final response.
    """

    display_name = "Call Model"
    description = "Send messages to a language model. Routes to tool_calls or ai_message based on response."
    icon = "brain"
    category = "agent_blocks"

    inputs = [
        *LanguageModelMixin.get_llm_inputs(
            include_input_value=False,
            include_system_message=False,
            include_stream=False,
            include_temperature=True,
        ),
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Initial user input (Message or string). Used for the first call.",
            input_types=["Message"],
            required=False,
        ),
        HandleInput(
            name="messages",
            display_name="Message History",
            info="Conversation history as DataFrame. Used in loop iterations.",
            input_types=["DataFrame"],
            required=False,
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Optional system message to set the behavior of the assistant.",
            advanced=False,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            info="Optional tools to bind to the model for function calling.",
            input_types=["Tool"],
            is_list=True,
            required=False,
        ),
        BoolInput(
            name="include_think_tool",
            display_name="Include Think Tool",
            info="Add a 'think' tool that lets the model reason step-by-step before responding.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="AI Message",
            name="ai_message",
            method="get_ai_message",
            info="Fires when the model is done (no tool calls). Connect to ChatOutput.",
            group_outputs=True,
        ),
        Output(
            display_name="Tool Calls",
            name="tool_calls",
            method="get_tool_calls",
            info="Fires when the model wants to call tools. Connect to ExecuteTool.",
            group_outputs=True,
        ),
    ]

    async def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict:
        return await self.update_llm_provider_config(build_config, field_value, field_name)

    def _get_callbacks(self) -> list[BaseCallbackHandler]:
        """Get all callbacks for LLM invocation.

        Returns LangChain callbacks from tracing service.
        """
        return self.get_langchain_callbacks()

    def _pre_run_setup(self):
        """Clear cached result before each run to ensure fresh LLM call in cycles."""
        super()._pre_run_setup()
        self._cached_result = None

    def _convert_to_lc_messages(self, messages: list[Message] | DataFrame) -> list[BaseMessage]:
        """Convert Langflow Messages or DataFrame to LangChain BaseMessages.

        Delegates to the convert_to_lc_messages function in message_utils.
        """
        return convert_to_lc_messages(messages)

    async def _call_model_internal(self) -> Message:
        """Internal method to call the language model with streaming support.

        Uses the same streaming pattern as LCModelComponent: pass the async stream
        to send_message which handles token streaming via _stream_message.
        """
        # Check if we already have a cached result
        if hasattr(self, "_cached_result") and self._cached_result is not None:
            return self._cached_result

        # Build the LLM using the mixin
        runnable = self.build_llm()

        lc_messages: list[BaseMessage] = []

        # Add system message if provided
        if self.system_message:
            lc_messages.append(SystemMessage(content=self.system_message))

        # Check if we have messages DataFrame (from loop iteration)
        if self.messages is not None and isinstance(self.messages, DataFrame) and not self.messages.empty:
            # Use messages from DataFrame (loop iteration)
            lc_messages.extend(self._convert_to_lc_messages(self.messages))
        elif self.input_value is not None:
            # First call - use input_value
            if isinstance(self.input_value, Message):
                lc_messages.append(HumanMessage(content=self.input_value.text or ""))
            elif isinstance(self.input_value, str):
                lc_messages.append(HumanMessage(content=self.input_value))
            else:
                # Try to convert to string
                lc_messages.append(HumanMessage(content=str(self.input_value)))

        # Collect tools to bind
        tools_to_bind = []
        if self.tools:
            tools_to_bind = self.tools if isinstance(self.tools, list) else [self.tools]

        # Add think tool if enabled
        if getattr(self, "include_think_tool", False):
            think_tool_component = ThinkToolComponent()
            tools_to_bind.append(think_tool_component.build_tool())

        # Bind tools if any
        if tools_to_bind:
            runnable = runnable.bind_tools(tools_to_bind)

        # Configure runnable with callbacks for tracing (exactly like LCModelComponent)
        runnable = runnable.with_config(
            {
                "run_name": self.display_name,
                "callbacks": self._get_callbacks(),
            }
        )

        # Get session_id for the message (exactly like LCModelComponent)
        if hasattr(self, "graph") and self.graph:
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        # Check for existing message ID and content_blocks from previous iteration (passed via DataFrame)
        # This allows us to continue updating the same message in the UI and preserve tool steps
        existing_message_id = None
        existing_content_blocks = None
        if self.messages is not None and isinstance(self.messages, DataFrame) and not self.messages.empty:
            existing_message_id = extract_message_id_from_dataframe(self.messages)
            existing_content_blocks = extract_content_blocks_from_dataframe(self.messages)

        # Use closure to capture tool_calls while streaming
        # Tool calls come incrementally during streaming and need to be aggregated
        # AIMessageChunk supports __add__ for merging, but AIMessage (from non-streaming fallback) doesn't
        aggregated_chunk: AIMessage | None = None

        async def stream_and_capture():
            """Stream chunks to frontend while capturing tool_calls."""
            nonlocal aggregated_chunk
            async for chunk in runnable.astream(lc_messages):
                # Aggregate chunks to get complete tool_calls at the end
                # Only AIMessageChunk supports proper + aggregation
                # AIMessage + AIMessage returns ChatPromptTemplate (wrong type)
                if aggregated_chunk is None:
                    aggregated_chunk = chunk
                elif isinstance(aggregated_chunk, AIMessageChunk) and isinstance(chunk, AIMessageChunk):
                    # Safe to add AIMessageChunk objects
                    aggregated_chunk = aggregated_chunk + chunk
                elif hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    # For non-chunk messages, keep the one with tool_calls
                    aggregated_chunk = chunk
                yield chunk

        # Create message with the async stream as text (exactly like LCModelComponent._handle_stream)
        # If we have existing content_blocks from a previous iteration (tool execution steps),
        # preserve them so the UI continues to show the agent's previous steps
        model_message = Message(
            text=stream_and_capture(),
            sender=MESSAGE_SENDER_AI,
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            session_id=session_id,
            content_blocks=existing_content_blocks if existing_content_blocks else [],
        )

        # If we have an existing message ID from a previous iteration, reuse it
        # This ensures all updates go to the same message in the UI
        if existing_message_id is not None:
            model_message.id = existing_message_id

        # send_message handles streaming via _stream_message -> _process_chunk -> on_token
        result = await self.send_message(model_message)

        # If send_message didn't consume the stream (no event_manager), we need to consume it
        # This can happen in tests or when running without event streaming
        if hasattr(result.text, "__anext__"):
            full_text = ""
            async for chunk in result.text:
                if aggregated_chunk is None:
                    aggregated_chunk = chunk
                elif isinstance(aggregated_chunk, AIMessageChunk) and isinstance(chunk, AIMessageChunk):
                    aggregated_chunk = aggregated_chunk + chunk
                elif hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    aggregated_chunk = chunk
                if hasattr(chunk, "content"):
                    full_text += chunk.content or ""
            result.text = full_text

        # Get tool_calls from the aggregated chunk (properly merged)
        # Use sanitize_tool_calls to filter out incomplete tool_calls from streaming
        captured_tool_calls = []
        if aggregated_chunk is not None and hasattr(aggregated_chunk, "tool_calls") and aggregated_chunk.tool_calls:
            captured_tool_calls = sanitize_tool_calls(aggregated_chunk.tool_calls)

        # Build AI response with captured tool_calls
        ai_response = AIMessage(content=result.text or "")
        if captured_tool_calls:
            ai_response.tool_calls = captured_tool_calls

        # Store tool_calls in the message data if present
        if captured_tool_calls:
            result.data["tool_calls"] = captured_tool_calls
            result.data["has_tool_calls"] = True
        else:
            result.data["has_tool_calls"] = False

        # Store the original AIMessage for downstream processing
        result.data["ai_message"] = ai_response

        log_truncate_len = 100
        self.log(
            f"Model response: {result.text[:log_truncate_len]}..."
            if len(result.text or "") > log_truncate_len
            else f"Model response: {result.text}"
        )
        self._cached_result = result
        return result

    async def get_ai_message(self) -> Message:
        """Return AI message when model is done (no tool calls).

        This output fires when the model has finished and doesn't need to call any tools.
        Connect this to ChatOutput for the final response.
        """
        result = await self._call_model_internal()

        # Only output if there are NO tool calls (model is done)
        if result.data.get("has_tool_calls", False):
            # Stop this output - model wants to call tools
            # Use both stop() and exclude_branch_conditionally() for proper cycle handling
            self.stop("ai_message")
            self.graph.exclude_branch_conditionally(self._vertex.id, output_name="ai_message")
            return Message(text="")

        # Model is done - stop the tool_calls branch to break the cycle
        self.stop("tool_calls")
        self.graph.exclude_branch_conditionally(self._vertex.id, output_name="tool_calls")
        return result

    async def get_tool_calls(self) -> Message:
        """Return AI message when model wants to call tools.

        This output fires when the model has tool_calls to execute.
        Connect this to ExecuteTool to continue the agent loop.
        """
        result = await self._call_model_internal()

        # Only output if there ARE tool calls (continue loop)
        if not result.data.get("has_tool_calls", False):
            # Stop this output - model is done
            # Use both stop() and exclude_branch_conditionally() for proper cycle handling
            self.stop("tool_calls")
            self.graph.exclude_branch_conditionally(self._vertex.id, output_name="tool_calls")
            return Message(text="")

        # Pass stream_events flag to ExecuteTool
        # CallModel knows if it's connected to ChatOutput (ai_message output goes to ChatOutput)
        # ExecuteTool should show events if this agent flow ends at a ChatOutput
        result.data["should_stream_events"] = self.is_connected_to_chat_output()

        # Continue loop - stop the ai_message branch
        self.stop("ai_message")
        self.graph.exclude_branch_conditionally(self._vertex.id, output_name="ai_message")
        return result
