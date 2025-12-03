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

import math
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from lfx.base.models.language_model_mixin import LanguageModelMixin
from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, MultilineInput, Output
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict  # noqa: TC001
from lfx.schema.message import Message


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

    def _pre_run_setup(self):
        """Clear cached result before each run to ensure fresh LLM call in cycles."""
        super()._pre_run_setup()
        self._cached_result = None

    def _convert_to_lc_messages(self, messages: list[Message] | DataFrame) -> list[BaseMessage]:
        """Convert Langflow Messages or DataFrame to LangChain BaseMessages."""
        lc_messages: list[BaseMessage] = []

        # Handle DataFrame input
        if isinstance(messages, DataFrame):
            for _, row in messages.iterrows():
                sender = row.get("sender", "User")
                text = row.get("text", "")
                is_tool_result = row.get("is_tool_result")
                tool_call_id = row.get("tool_call_id", "")
                tool_calls = row.get("tool_calls")

                # Check explicitly for True (nan from DataFrame is truthy but not True)
                if is_tool_result is True:
                    # Tool result message
                    lc_messages.append(ToolMessage(content=text, tool_call_id=tool_call_id or ""))
                elif sender == "Machine":
                    # AI message - may have tool_calls
                    ai_msg = AIMessage(content=text)
                    # Check for valid tool_calls (not None and not NaN from DataFrame)
                    is_nan = isinstance(tool_calls, float) and math.isnan(tool_calls)
                    if tool_calls is not None and not is_nan:
                        ai_msg.tool_calls = tool_calls
                    lc_messages.append(ai_msg)
                elif sender == "System":
                    lc_messages.append(SystemMessage(content=text))
                else:
                    # User or unknown -> HumanMessage
                    lc_messages.append(HumanMessage(content=text))
            return lc_messages

        # Handle list of Message objects (or strings)
        for msg in messages:
            # Handle string inputs (e.g., from ChatInput)
            if isinstance(msg, str):
                lc_messages.append(HumanMessage(content=msg))
                continue

            is_tool_result = msg.data.get("is_tool_result", False) if msg.data else False
            tool_call_id = msg.data.get("tool_call_id", "") if msg.data else ""
            tool_calls = msg.data.get("tool_calls") if msg.data else None

            if is_tool_result:
                lc_messages.append(ToolMessage(content=msg.text or "", tool_call_id=tool_call_id or ""))
            elif msg.sender == "Machine":
                ai_msg = AIMessage(content=msg.text or "")
                if tool_calls:
                    ai_msg.tool_calls = tool_calls
                lc_messages.append(ai_msg)
            elif msg.sender == "System":
                lc_messages.append(SystemMessage(content=msg.text or ""))
            else:
                # User or unknown -> HumanMessage
                lc_messages.append(HumanMessage(content=msg.text or ""))

        return lc_messages

    async def _call_model_internal(self) -> Message:
        """Internal method to call the language model. Caches result for both outputs."""
        # Check if we already have a cached result
        if hasattr(self, "_cached_result") and self._cached_result is not None:
            return self._cached_result

        # Build the LLM using the mixin
        llm = self.build_llm()

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

        # Bind tools if provided
        if self.tools:
            tools = self.tools if isinstance(self.tools, list) else [self.tools]
            if tools:
                llm = llm.bind_tools(tools)

        # Invoke the model
        response: AIMessage = await llm.ainvoke(lc_messages)

        # Convert response to Langflow Message
        result = Message(
            text=response.content if isinstance(response.content, str) else str(response.content),
            sender="Machine",
            sender_name="AI",
        )

        # Store tool_calls in the message data if present
        if hasattr(response, "tool_calls") and response.tool_calls:
            result.data["tool_calls"] = response.tool_calls
            result.data["has_tool_calls"] = True
        else:
            result.data["has_tool_calls"] = False

        # Store the original AIMessage for downstream processing
        result.data["ai_message"] = response

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

        # Continue loop - stop the ai_message branch
        self.stop("ai_message")
        self.graph.exclude_branch_conditionally(self._vertex.id, output_name="ai_message")
        return result
