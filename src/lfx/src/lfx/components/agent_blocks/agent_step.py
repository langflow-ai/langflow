"""AgentStep component - the reasoning core of an agent loop.

A building block for creating agents. Takes messages and optional tools,
sends them to a language model, and routes based on the response.

The component has two outputs:
- Response: Fires when the model is done (no tool calls requested)
- Tool Calls: Fires when the model wants to execute tools

This enables visual agent loops:
ChatInput → WhileLoop → AgentStep → [Tool Calls] → ExecuteTool → WhileLoop
                              ↓ [Response - done]
                         ChatOutput
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, SystemMessage

from lfx.base.agents.message_utils import (
    convert_to_lc_messages,
    extract_content_blocks_from_dataframe,
    extract_message_id_from_dataframe,
    sanitize_tool_calls,
)
from lfx.base.models.model import LCModelComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.components.agent_blocks.think_tool import ThinkToolComponent
from lfx.field_typing import LanguageModel  # noqa: TC001
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, HandleInput, ModelInput, MultilineInput, Output, SecretStrInput, SliderInput
from lfx.schema.content_block import ContentBlock
from lfx.schema.content_types import ToolContent
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict  # noqa: TC001
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI


class AgentStepComponent(LCModelComponent):
    """The reasoning core of an agent - sends messages to LLM and routes based on response.

    This component is a building block for agent workflows. It:
    1. Takes messages (conversation history) as input
    2. Optionally binds tools to the LLM for function calling
    3. Invokes the LLM and routes the response:
       - Response output: fires when the model is done (no tools requested)
       - Tool Calls output: fires when the model wants to execute tools

    The `stream_events` field controls whether messages are created and streamed.
    When disabled, the component is a pure function with no storage side effects.

    Connect Tool Calls output to Execute Tool for agent loops.
    Connect Response output to Chat Output for the final response.
    """

    display_name = "Agent Step"
    description = "Sends messages to an LLM. Outputs to Response (done) or Tool Calls (continue loop)."
    icon = "brain"
    category = "agent_blocks"

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            required=False,
            show=True,
            real_time_refresh=True,
            advanced=True,
        ),
        HandleInput(
            name="messages",
            display_name="Messages",
            info="Conversation history as DataFrame.",
            input_types=["DataFrame"],
            required=True,
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
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Controls randomness in responses",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        BoolInput(
            name="stream_events",
            display_name="Stream Events",
            info="When enabled, streams messages and events. Disable for pure LLM calls.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Response",
            name="ai_message",
            method="get_ai_message",
            group_outputs=True,
        ),
        Output(
            display_name="Tool Calls",
            name="tool_calls",
            method="get_tool_calls",
            group_outputs=True,
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Dynamically update build config with user-filtered model options."""
        return update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="call_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

    def _pre_run_setup(self):
        """Clear cached result before each run to ensure fresh LLM call in cycles."""
        super()._pre_run_setup()
        self._cached_result = None

    def _convert_to_lc_messages(self, messages: list[Message] | DataFrame) -> list[BaseMessage]:
        """Convert Langflow Messages or DataFrame to LangChain BaseMessages."""
        return convert_to_lc_messages(messages)

    def build_model(self) -> LanguageModel:
        """Build the language model using the unified model API."""
        # Handle various model formats that can come from .set() or UI
        # get_llm expects a list of model dicts
        model = self.model
        if isinstance(model, str):
            # String model name - convert to dict format
            from lfx.base.models.unified_models import normalize_model_names_to_dicts

            model = normalize_model_names_to_dicts(model)
        elif isinstance(model, dict):
            model = [model]
        return get_llm(
            model=model,
            user_id=self.user_id,
            api_key=self.api_key,
            temperature=self.temperature,
            stream=True,  # Always stream for CallModel to enable token streaming
        )

    def _build_messages(self) -> list[BaseMessage]:
        """Build the list of LangChain messages from inputs.

        Returns messages in order: [system_message, ...conversation_history]
        """
        lc_messages: list[BaseMessage] = []

        # Add system message if provided
        if self.system_message:
            lc_messages.append(SystemMessage(content=self.system_message))

        # Add conversation history from messages DataFrame
        if self.messages is not None and isinstance(self.messages, DataFrame) and not self.messages.empty:
            lc_messages.extend(self._convert_to_lc_messages(self.messages))

        return lc_messages

    def _bind_tools(self, runnable: LanguageModel) -> LanguageModel:
        """Bind tools to the model if any are provided."""
        tools_to_bind = []
        if self.tools:
            tools_to_bind = self.tools if isinstance(self.tools, list) else [self.tools]

        # Add think tool if enabled
        if getattr(self, "include_think_tool", False):
            think_tool_component = ThinkToolComponent()
            tools_to_bind.append(think_tool_component.build_tool())

        if tools_to_bind:
            return runnable.bind_tools(tools_to_bind)
        return runnable

    async def _handle_stream(self, runnable, inputs) -> tuple[Message | None, AIMessage | None]:
        """Handle streaming with tool call capture and immediate tool notifications.

        Overrides LCModelComponent._handle_stream to aggregate chunks and capture tool_calls.
        If a _parent_message is available (from AgentLoop), uses it instead of creating new message.
        Sends tool call notifications immediately when tool_call_chunks are detected.

        Returns:
            tuple: (Message for UI, AIMessage with tool_calls)
        """
        # Get session_id
        if hasattr(self, "graph") and self.graph:
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        # Check for existing message ID and content_blocks from previous iteration
        existing_message_id = None
        existing_content_blocks = None
        if self.messages is not None and isinstance(self.messages, DataFrame) and not self.messages.empty:
            existing_message_id = extract_message_id_from_dataframe(self.messages)
            existing_content_blocks = extract_content_blocks_from_dataframe(self.messages)

        # Check if we have a parent message from AgentLoop
        parent_message: Message | None = getattr(self, "_parent_message", None)
        should_stream = self.stream_events

        # Closure to capture tool_calls while streaming
        aggregated_chunk: AIMessage | None = None
        start_time = perf_counter()

        # When we have a parent_message AND should_stream, we manually iterate to send
        # immediate tool notifications. This avoids the reentrancy issue where
        # send_message tries to iterate a generator we're already inside of.
        if parent_message and should_stream:
            return await self._handle_stream_with_immediate_notifications(runnable, inputs, parent_message, start_time)

        # Standard streaming path (no parent message or no streaming)
        async def stream_and_capture():
            """Stream chunks to frontend while capturing tool_calls."""
            nonlocal aggregated_chunk
            async for chunk in runnable.astream(inputs):
                if aggregated_chunk is None:
                    aggregated_chunk = chunk
                elif isinstance(aggregated_chunk, AIMessageChunk) and isinstance(chunk, AIMessageChunk):
                    aggregated_chunk = aggregated_chunk + chunk
                elif hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    aggregated_chunk = chunk
                yield chunk

        # Create new message with the async stream
        model_message = Message(
            text=stream_and_capture(),
            sender=MESSAGE_SENDER_AI,
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            session_id=session_id,
            content_blocks=existing_content_blocks if existing_content_blocks else [],
        )
        # Reuse existing message ID for UI continuity
        if existing_message_id is not None:
            model_message.id = existing_message_id

        # send_message handles streaming
        lf_message = await self.send_message(model_message)

        # If stream wasn't consumed (no event_manager), consume it
        # Note: We check model_message.text because lf_message is the stored message
        # which may have lost the generator reference after serialization
        if hasattr(model_message.text, "__anext__"):
            full_text = ""
            # Just consume the generator to accumulate text - aggregation already
            # happens inside stream_and_capture() via the nonlocal aggregated_chunk
            async for chunk in model_message.text:
                if hasattr(chunk, "content"):
                    full_text += chunk.content or ""
            lf_message.text = full_text

        return lf_message, aggregated_chunk

    async def _handle_stream_with_immediate_notifications(
        self,
        runnable,
        inputs,
        parent_message: Message,
        start_time: float,
    ) -> tuple[Message, AIMessage | None]:
        """Handle streaming with immediate tool notifications for parent message.

        This method manually iterates the stream instead of assigning the generator
        to parent_message.text. This allows us to call send_message for immediate
        tool notifications without causing reentrancy issues.
        """
        aggregated_chunk: AIMessage | None = None
        tool_names_notified: set[str] = set()
        full_text = ""

        # Ensure content_blocks exists on parent message
        if not parent_message.content_blocks:
            parent_message.content_blocks = [ContentBlock(title="Agent Steps", contents=[])]

        async for chunk in runnable.astream(inputs):
            # Aggregate chunks for tool_calls extraction
            if aggregated_chunk is None:
                aggregated_chunk = chunk
            elif isinstance(aggregated_chunk, AIMessageChunk) and isinstance(chunk, AIMessageChunk):
                aggregated_chunk = aggregated_chunk + chunk
            elif hasattr(chunk, "tool_calls") and chunk.tool_calls:
                aggregated_chunk = chunk

            # Accumulate text content
            if hasattr(chunk, "content") and chunk.content:
                full_text += chunk.content

            # Send immediate tool call notification when we detect tool_call_chunks
            if hasattr(chunk, "tool_call_chunks"):
                for tc_chunk in chunk.tool_call_chunks:
                    tool_name = tc_chunk.get("name") if isinstance(tc_chunk, dict) else getattr(tc_chunk, "name", None)
                    if tool_name and tool_name not in tool_names_notified:
                        tool_names_notified.add(tool_name)
                        # Add tool notification to parent message content_blocks
                        duration = int((perf_counter() - start_time) * 1000)
                        tool_content = ToolContent(
                            type="tool_use",
                            name=tool_name,
                            tool_input={},  # Input not yet available during streaming
                            output=None,
                            error=None,
                            header={"title": f"Accessing **{tool_name}**", "icon": "Hammer"},
                            duration=duration,
                        )
                        parent_message.content_blocks[0].contents.append(tool_content)
                        # Send update to UI immediately - safe because parent_message.text
                        # is NOT an async generator, it's just accumulated text
                        parent_message.text = full_text
                        # Use skip_db_update=True to avoid slow DB writes on each update
                        # The message was already created by AgentLoop, so we just need to send events
                        await self.send_message(parent_message, skip_db_update=True)
                        start_time = perf_counter()  # Reset timer for next operation

        # Set final text
        parent_message.text = full_text
        # Final update - still skip DB since AgentLoop will handle the final state
        await self.send_message(parent_message, skip_db_update=True)

        return parent_message, aggregated_chunk

    async def _call_model_internal(self) -> Message:
        """Internal method to call the language model with streaming support."""
        # Check for cached result
        if hasattr(self, "_cached_result") and self._cached_result is not None:
            return self._cached_result

        # Build model and bind tools
        runnable = self.build_model()
        runnable = self._bind_tools(runnable)

        # Configure with callbacks (inherited pattern from LCModelComponent)
        runnable = runnable.with_config(
            {
                "run_name": self.display_name,
                "project_name": self.get_project_name(),
                "callbacks": self.get_langchain_callbacks(),
            }
        )

        # Build messages
        lc_messages = self._build_messages()

        # Stream and capture tool_calls
        result, aggregated_chunk = await self._handle_stream(runnable, lc_messages)

        # Extract tool_calls from aggregated response
        captured_tool_calls = []
        if aggregated_chunk is not None and hasattr(aggregated_chunk, "tool_calls") and aggregated_chunk.tool_calls:
            captured_tool_calls = sanitize_tool_calls(aggregated_chunk.tool_calls)

        # Build AI response with captured tool_calls
        ai_response = AIMessage(content=result.text or "")
        if captured_tool_calls:
            ai_response.tool_calls = captured_tool_calls

        # Store tool_calls in message data
        if captured_tool_calls:
            result.data["tool_calls"] = captured_tool_calls
            result.data["has_tool_calls"] = True
        else:
            result.data["has_tool_calls"] = False

        result.data["ai_message"] = ai_response

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
            self.stop("ai_message")
            self.graph.exclude_branch_conditionally(self._vertex.id, output_name="ai_message")
            return Message(text="")

        # Model is done - stop the tool_calls branch
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
            self.stop("tool_calls")
            self.graph.exclude_branch_conditionally(self._vertex.id, output_name="tool_calls")
            return Message(text="")

        # Pass stream_events flag to ExecuteTool
        result.data["should_stream_events"] = self.stream_events

        # Continue loop - stop the ai_message branch
        self.stop("ai_message")
        self.graph.exclude_branch_conditionally(self._vertex.id, output_name="ai_message")
        return result
