"""AgentLoop component - a complete agent loop in a single component.

This component encapsulates a complete agent graph internally:
    WhileLoop → AgentStep → [ai_message] → Output
                      ↓ [tool_calls]
                ExecuteTool
                      ↓ (loop back)

It provides a simple interface (model, tools, system_message, input)
while handling all the complexity of the agent loop internally.
"""

from __future__ import annotations

from typing import Any

from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import (
    BoolInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    MultilineInput,
    Output,
    SecretStrInput,
    SliderInput,
)
from lfx.schema.content_block import ContentBlock
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict  # noqa: TC001
from lfx.schema.message import Message
from lfx.template.field.base import UNDEFINED
from lfx.utils.constants import MESSAGE_SENDER_AI


class AgentLoopComponent(Component):
    """A complete agent loop in a single component.

    This component builds an internal agent graph using:
    - WhileLoop: Manages state accumulation across iterations
    - AgentStep: Calls the LLM and routes based on tool calls
    - ExecuteTool: Executes tool calls and returns results

    The agent loop continues until the model stops calling tools
    or max_iterations is reached.

    Inputs:
        - model: The language model to use
        - tools: List of tools available to the agent
        - system_message: Instructions for the agent
        - input_value: The user message to process
        - initial_state: Optional conversation history (DataFrame)

    Output:
        - message: The final AI response after completing all tool calls
    """

    display_name = "Agent Loop"
    description = "A complete agent loop that processes messages and uses tools."
    icon = "Bot"
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
            name="tools",
            display_name="Tools",
            info="Tools available to the agent for accomplishing tasks.",
            input_types=["Tool"],
            is_list=True,
            required=False,
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Instructions that define the agent's behavior and capabilities.",
            value="You are a helpful assistant.",
        ),
        HandleInput(
            name="input_value",
            display_name="Input",
            info="The user message for the agent to process.",
            input_types=["Message"],
            required=True,
        ),
        HandleInput(
            name="message_history",
            display_name="Message History",
            info="Conversation history (DataFrame). Auto-fetches from session memory if not provided.",
            input_types=["DataFrame"],
            required=False,
            advanced=True,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Messages",
            value=100,
            info="Number of messages to retrieve from session memory (when auto-fetching).",
            advanced=True,
        ),
        MessageTextInput(
            name="context_id",
            display_name="Context ID",
            info="Optional context ID for memory isolation within the same session.",
            value="",
            advanced=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="Maximum number of tool call iterations to prevent infinite loops.",
            value=10,
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Controls randomness in responses. Lower = more focused, higher = more creative.",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        BoolInput(
            name="include_think_tool",
            display_name="Include Think Tool",
            info="Add a 'think' tool that lets the agent reason step-by-step before responding.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Message",
            name="message",
            method="run_agent",
        ),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Dynamically update build config with user-filtered model options."""
        return update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="agent_loop_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

    def _build_model(self):
        """Build the language model using the unified model API."""
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=self.api_key,
            temperature=self.temperature,
            stream=True,
        )

    async def get_memory_data(self) -> list[Message]:
        """Retrieve chat history from Langflow's built-in session memory.

        Returns:
            List of Message objects representing chat history.
        """
        from lfx.memory import aget_messages

        session_id = self.graph.session_id if hasattr(self, "graph") and self.graph else None
        context_id = self.context_id if self.context_id else None

        messages = await aget_messages(
            session_id=session_id,
            context_id=context_id,
            limit=self.n_messages,
            order="ASC",
        )

        # Filter out the current input message to avoid duplication
        if messages and self.input_value:
            input_id = getattr(self.input_value, "id", None)
            messages = [m for m in messages if getattr(m, "id", None) != input_id]

        return messages or []

    def _messages_to_dataframe(self, messages: list[Message]) -> DataFrame | None:
        """Convert a list of Messages to a DataFrame for the agent loop.

        Args:
            messages: List of Message objects

        Returns:
            DataFrame with message data, or None if no messages
        """
        if not messages:
            return None

        return DataFrame(messages)

    async def _create_initial_message(self, execution_context) -> Message | None:
        """Create and send initial message for UI feedback."""
        if not execution_context.stream_to_playground:
            return None

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name="AI",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=execution_context.session_id,
        )
        return await self.send_message(agent_message)

    def _build_internal_components(self, execution_context, agent_message: Message | None):
        """Build and configure internal graph components."""
        from lfx.components.agent_blocks.agent_step import AgentStepComponent
        from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
        from lfx.components.flow_controls.while_loop import WhileLoopComponent

        component_id_prefix = f"{self._id}_internal"
        while_loop = WhileLoopComponent(_id=f"{component_id_prefix}_while_loop")
        agent_step = AgentStepComponent(_id=f"{component_id_prefix}_agent_step")
        execute_tool = ExecuteToolComponent(_id=f"{component_id_prefix}_execute_tool")

        # Configure streaming on inner components
        # Agent Step uses explicit stream_events field instead of hidden flag
        agent_step.set(stream_events=execution_context.stream_to_playground)

        # Pass parent message for message continuity across iterations
        for component in [while_loop, agent_step, execute_tool]:
            if agent_message:
                component._parent_message = agent_message  # noqa: SLF001

        return while_loop, agent_step, execute_tool

    async def _configure_while_loop(self, while_loop, execute_tool):
        """Configure WhileLoop with input and memory."""
        config = {
            "max_iterations": self.max_iterations,
            "loop": execute_tool.execute_tools,
        }
        if self.input_value is not None:
            config["input_value"] = self.input_value

        # Use explicit message_history or fetch from session memory
        if self.message_history is not None:
            config["initial_state"] = self.message_history
        else:
            memory_messages = await self.get_memory_data()
            if memory_messages:
                config["initial_state"] = self._messages_to_dataframe(memory_messages)

        while_loop.set(**config)

    def _configure_agent_step(self, agent_step, while_loop):
        """Configure AgentStep with model and tools."""
        tools = self.tools or []
        config = {
            "system_message": self.system_message,
            "temperature": self.temperature,
            "include_think_tool": self.include_think_tool,
            "messages": while_loop.loop_output,
        }
        if self.model:
            config["model"] = self.model
        if self.api_key:
            config["api_key"] = self.api_key
        if tools:
            config["tools"] = tools

        agent_step.set(**config)

    def _configure_execute_tool(self, execute_tool, agent_step):
        """Configure ExecuteTool with tools."""
        config = {"tool_calls_message": agent_step.get_tool_calls}
        if self.tools:
            config["tools"] = self.tools
        execute_tool.set(**config)

    def _build_graph(self, while_loop, agent_step, execution_context):
        """Build the agent graph."""
        from lfx.graph.graph.base import Graph

        flow_name = f"{execution_context.flow_name}_agent_loop" if execution_context.flow_name else "agent_loop"

        graph = Graph(
            start=while_loop,
            end=agent_step,
            flow_id=execution_context.flow_id,
            flow_name=flow_name,
            user_id=execution_context.user_id,
            context=execution_context.context,
        )

        if execution_context.session_id:
            graph.session_id = execution_context.session_id

        return graph

    async def _execute_graph(self, graph, execution_context):
        """Execute the graph and log progress."""
        iteration_count = 0
        async for result in graph.async_start(
            max_iterations=self.max_iterations * 3,
            config={"output": {"cache": False}},
            event_manager=execution_context.event_manager,
        ):
            iteration_count += 1
            self.log(f"Graph iteration {iteration_count}: {type(result).__name__}")

        self.log(f"Graph completed after {iteration_count} iterations")

    def _extract_result(self, agent_step, agent_message: Message | None) -> Message:
        """Extract final result from agent_step output."""
        output = agent_step.get_output_by_method(agent_step.get_ai_message)

        has_valid_output = (
            output is not None
            and hasattr(output, "value")
            and output.value is not None
            and output.value is not UNDEFINED
        )

        if has_valid_output:
            result = output.value
            if isinstance(result, Message):
                if agent_message:
                    agent_message.text = result.text
                    agent_message.properties.state = "complete"
                    if result.content_blocks:
                        agent_message.content_blocks = result.content_blocks
                    return agent_message
                return result
            if hasattr(result, "get_text"):
                if agent_message:
                    agent_message.text = result.get_text()
                    agent_message.properties.state = "complete"
                    return agent_message
                return Message(text=result.get_text())
            msg = f"Unexpected result type from agent_step: {type(result)}"
            raise TypeError(msg)

        # No valid output - return error message
        if agent_message:
            agent_message.text = "Agent completed without producing a response."
            agent_message.properties.state = "complete"
            return agent_message
        return Message(text="Agent completed without producing a response.")

    async def run_agent(self) -> Message:
        """Run the agent and return the final response."""
        from lfx.graph import GraphExecutionContext

        # 1. Gather execution context
        execution_context = GraphExecutionContext.from_component(self)

        # 2. Create initial UI message
        agent_message = await self._create_initial_message(execution_context)

        # 3. Build internal components
        while_loop, agent_step, execute_tool = self._build_internal_components(execution_context, agent_message)

        # 4. Configure components
        await self._configure_while_loop(while_loop, execute_tool)
        self._configure_agent_step(agent_step, while_loop)
        self._configure_execute_tool(execute_tool, agent_step)

        # 5. Build and execute graph
        graph = self._build_graph(while_loop, agent_step, execution_context)
        await self._execute_graph(graph, execution_context)

        # 6. Extract and return result
        return self._extract_result(agent_step, agent_message)
