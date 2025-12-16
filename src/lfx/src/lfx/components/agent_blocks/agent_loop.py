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
    ModelInput,
    MultilineInput,
    Output,
    SecretStrInput,
    SliderInput,
)
from lfx.schema.content_block import ContentBlock
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
            name="initial_state",
            display_name="Message History",
            info="Optional conversation history (DataFrame) to provide context.",
            input_types=["DataFrame"],
            required=False,
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

    async def run_agent(self) -> Message:
        """Run the agent and return the final response.

        This method:
        1. Creates and sends initial message IMMEDIATELY for UI feedback
        2. Gathers execution context from the parent component
        3. Builds the internal agent graph with all configuration
        4. Executes the graph with event_manager for UI updates
        5. Returns the final AI message from AgentStep's cached result
        """
        # Import here to avoid circular import
        from lfx.base.agents.agent_graph import GraphExecutionContext
        from lfx.components.agent_blocks.agent_step import AgentStepComponent
        from lfx.components.agent_blocks.execute_tool import ExecuteToolComponent
        from lfx.components.flow_controls.while_loop import WhileLoopComponent
        from lfx.graph.graph.base import Graph

        # Gather execution context from this component
        execution_context = GraphExecutionContext.from_component(self)

        # Create and send the initial message IMMEDIATELY for UI feedback
        # This follows the pattern from ALTKBaseAgentComponent
        agent_message: Message | None = None
        if execution_context.stream_to_playground:
            agent_message = Message(
                sender=MESSAGE_SENDER_AI,
                sender_name="AI",
                properties={"icon": "Bot", "state": "partial"},
                content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
                session_id=execution_context.session_id,
            )
            # Send immediately so UI shows the message right away
            agent_message = await self.send_message(agent_message)

        # Build components with unique IDs
        component_id_prefix = f"{self._id}_internal"
        while_loop = WhileLoopComponent(_id=f"{component_id_prefix}_while_loop")
        agent_step = AgentStepComponent(_id=f"{component_id_prefix}_agent_step")
        execute_tool = ExecuteToolComponent(_id=f"{component_id_prefix}_execute_tool")

        # Set stream_to_playground on inner components based on parent's connection
        # This enables streaming when AgentLoop is connected to ChatOutput
        for component in [while_loop, agent_step, execute_tool]:
            component._stream_to_playground = execution_context.stream_to_playground  # noqa: SLF001
            # Pass the parent message so inner components can update it instead of creating new ones
            if agent_message:
                component._parent_message = agent_message  # noqa: SLF001

        # Configure WhileLoop
        while_loop_config = {
            "max_iterations": self.max_iterations,
            "loop": execute_tool.execute_tools,
        }
        if self.input_value is not None:
            while_loop_config["input_value"] = self.input_value
        if self.initial_state is not None:
            while_loop_config["initial_state"] = self.initial_state
        while_loop.set(**while_loop_config)

        # Configure AgentStep
        tools = self.tools if self.tools else []
        agent_step_config = {
            "system_message": self.system_message,
            "temperature": self.temperature,
            "include_think_tool": self.include_think_tool,
            "messages": while_loop.loop_output,
        }
        if self.model:
            agent_step_config["model"] = self.model
        if self.api_key:
            agent_step_config["api_key"] = self.api_key
        if tools:
            agent_step_config["tools"] = tools
        agent_step.set(**agent_step_config)

        # Configure ExecuteTool
        execute_tool_config = {"ai_message": agent_step.get_tool_calls}
        if tools:
            execute_tool_config["tools"] = tools
        execute_tool.set(**execute_tool_config)

        # Extract context values for Graph construction
        flow_id = execution_context.flow_id
        flow_name = f"{execution_context.flow_name}_agent_loop" if execution_context.flow_name else "agent_loop"
        user_id = execution_context.user_id
        context = execution_context.context

        # Create graph
        graph = Graph(
            start=while_loop,
            end=agent_step,
            flow_id=flow_id,
            flow_name=flow_name,
            user_id=user_id,
            context=context,
        )

        # Set session_id if available
        if execution_context.session_id:
            graph.session_id = execution_context.session_id

        # Execute the graph
        iteration_count = 0
        async for result in graph.async_start(
            max_iterations=self.max_iterations * 3,  # Allow for loop iterations
            config={"output": {"cache": False}},
            event_manager=execution_context.event_manager,
        ):
            iteration_count += 1
            self.log(f"Graph iteration {iteration_count}: {type(result).__name__}")

        self.log(f"Graph completed after {iteration_count} iterations")
        self.log(f"Graph vertices: {[v.id for v in graph.vertices]}")
        self.log(f"Agent step outputs: {list(agent_step._outputs_map.keys())}")  # noqa: SLF001

        # Get the result from agent_step's output
        output = agent_step.get_output_by_method(agent_step.get_ai_message)
        self.log(f"ai_message output value type: {type(output.value).__name__ if output else 'None'}")

        has_valid_output = (
            output is not None
            and hasattr(output, "value")
            and output.value is not None
            and output.value is not UNDEFINED
        )
        if has_valid_output:
            result = output.value
            if isinstance(result, Message):
                # If we have a parent message, update it with final content and mark complete
                if agent_message:
                    agent_message.text = result.text
                    agent_message.properties.state = "complete"
                    # Merge content_blocks if result has any
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

        # Also check tool_calls output
        tool_calls_output = agent_step.get_output_by_method(agent_step.get_tool_calls)
        tc_type = type(tool_calls_output.value).__name__ if tool_calls_output else "None"
        self.log(f"tool_calls output value type: {tc_type}")

        # If we have a parent message but no result, mark it complete with error
        if agent_message:
            agent_message.text = "Agent completed without producing a response."
            agent_message.properties.state = "complete"
            return agent_message
        return Message(text="Agent completed without producing a response.")
