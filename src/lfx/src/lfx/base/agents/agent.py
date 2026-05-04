import re
import uuid
from abc import abstractmethod
from typing import TYPE_CHECKING, cast

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables import Runnable

from lfx.base.agents.callback import AgentAsyncHandler
from lfx.base.agents.events import ExceptionWithMessageError, process_agent_events
from lfx.base.agents.messages_input_builder import build_initial_messages
from lfx.base.agents.token_callback import TokenUsageCallbackHandler
from lfx.base.agents.utils import get_chat_output_sender_name
from lfx.custom.custom_component.component import Component, _get_component_toolkit
from lfx.field_typing import Tool
from lfx.inputs.inputs import InputTypes, MultilineInput
from lfx.io import BoolInput, HandleInput, IntInput, MessageInput
from lfx.log.logger import logger
from lfx.memory import delete_message
from lfx.schema.content_block import ContentBlock
from lfx.schema.data import Data
from lfx.schema.log import OnTokenFunctionType
from lfx.schema.message import Message
from lfx.template.field.base import Output
from lfx.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from lfx.schema.log import OnTokenFunctionType, SendMessageFunctionType


DEFAULT_TOOLS_DESCRIPTION = "A helpful assistant with access to the following tools:"
DEFAULT_AGENT_NAME = "Agent ({tools_names})"


class LCAgentComponent(Component):
    trace_type = "agent"
    _base_inputs: list[InputTypes] = [
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The input provided by the user for the agent to process.",
            tool_mode=True,
        ),
        BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
            info="Should the Agent fix errors when reading user input for better processing?",
        ),
        BoolInput(name="verbose", display_name="Verbose", value=True, advanced=True),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=15,
            advanced=True,
            info="The maximum number of attempts the agent can make to complete its task before it stops.",
        ),
        MultilineInput(
            name="agent_description",
            display_name="Agent Description [Deprecated]",
            info=(
                "The description of the agent. This is only used when in Tool Mode. "
                f"Defaults to '{DEFAULT_TOOLS_DESCRIPTION}' and tools are added dynamically. "
                "This feature is deprecated and will be removed in future versions."
            ),
            advanced=True,
            value=DEFAULT_TOOLS_DESCRIPTION,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="message_response"),
        Output(display_name="Agent", name="agent", method="build_agent", tool_mode=False),
    ]

    # Get shared callbacks for tracing and save them to self.shared_callbacks
    def _get_shared_callbacks(self) -> list[BaseCallbackHandler]:
        if not hasattr(self, "shared_callbacks"):
            self.shared_callbacks = self.get_langchain_callbacks()
        return self.shared_callbacks

    @abstractmethod
    def build_agent(self) -> Runnable:
        """Create the agent."""

    async def message_response(self) -> Message:
        """Run the agent and return the response."""
        agent = self.build_agent()
        message = await self.run_agent(agent=agent)

        self.status = message
        return message

    def _validate_outputs(self) -> None:
        required_output_methods = ["build_agent"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                msg = f"Output with name '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)

    def get_agent_kwargs(self, *, flatten: bool = False) -> dict:
        base = {
            "handle_parsing_errors": self.handle_parsing_errors,
            "verbose": self.verbose,
            "allow_dangerous_code": True,
        }
        agent_kwargs = {
            "handle_parsing_errors": self.handle_parsing_errors,
            "max_iterations": self.max_iterations,
        }
        if flatten:
            return {
                **base,
                **agent_kwargs,
            }
        return {**base, "agent_executor_kwargs": agent_kwargs}

    def get_chat_history_data(self) -> list[Data] | None:
        # might be overridden in subclasses
        return None

    async def run_agent(
        self,
        agent: Runnable,
    ) -> Message:
        runnable = self._resolve_runnable(agent)
        graph_input = self._build_graph_input()

        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        sender_name = get_chat_output_sender_name(self) or self.display_name or "AI"
        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=sender_name,
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id or uuid.uuid4(),
        )

        # Create token callback if event_manager is available
        # This wraps the event_manager's on_token method to match OnTokenFunctionType Protocol
        on_token_callback: OnTokenFunctionType | None = None
        if self._event_manager:
            on_token_callback = cast("OnTokenFunctionType", self._event_manager.on_token)

        token_usage_handler = TokenUsageCallbackHandler()

        try:
            result = await process_agent_events(
                runnable.astream_events(
                    graph_input,
                    config={
                        "callbacks": [
                            AgentAsyncHandler(self.log),
                            token_usage_handler,
                            *self._get_shared_callbacks(),
                        ]
                    },
                    version="v2",
                ),
                agent_message,
                cast("SendMessageFunctionType", self.send_message),
                on_token_callback,
            )
        except ExceptionWithMessageError as e:
            # Only delete message from database if it has an ID (was stored)
            if hasattr(e, "agent_message"):
                msg_id = e.agent_message.get_id()
                if msg_id:
                    await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            logger.error(f"ExceptionWithMessageError: {e}")
            raise
        except Exception as e:
            # Log or handle any other exceptions
            logger.error(f"Error: {e}")
            raise

        # Extract accumulated token usage from callback handler
        usage_data = token_usage_handler.get_usage()
        if usage_data:
            self._token_usage = usage_data
            result.properties.usage = usage_data
            # Only update DB and send event if the message was stored (has an ID)
            if result.get_id():
                stored_result = await self._update_stored_message(result)
                await self._send_message_event(stored_result)
                result = stored_result

        self.status = result
        return result

    def _resolve_runnable(self, agent: Runnable) -> Runnable:
        """Return the agent as-is.

        Kept as a thin pass-through hook so subclasses can intercept the runnable
        before it is fed to `astream_events` (e.g., to wrap with extra middleware).
        Under create_agent the input is always already a `Runnable`
        (`CompiledStateGraph`); the legacy wrapping path was removed.
        """
        return agent

    def _build_graph_input(self) -> dict:
        """Construct the `{"messages": [...]}` payload expected by `create_agent` graphs."""
        chat_history = getattr(self, "chat_history", None)
        messages = build_initial_messages(
            input_value=self.input_value,
            chat_history=chat_history,
        )
        return {"messages": messages}

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""

    def validate_tool_names(self) -> None:
        """Validate tool names to ensure they match the required pattern."""
        pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
        if hasattr(self, "tools") and self.tools:
            for tool in self.tools:
                if not pattern.match(tool.name):
                    msg = (
                        f"Invalid tool name '{tool.name}': must only contain letters, numbers, underscores, dashes,"
                        " and cannot contain spaces."
                    )
                    raise ValueError(msg)


class LCToolsAgentComponent(LCAgentComponent):
    _base_inputs = [
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="These are the tools that the agent can use to help with tasks.",
        ),
        *LCAgentComponent.get_base_inputs(),
    ]

    def build_agent(self) -> Runnable:
        """Return the agent runnable consumed by the "Agent" output port.

        Under the create_agent migration `create_agent_runnable()` returns a
        `CompiledStateGraph` whose input shape is `{"messages": [...]}`. The
        previous implementation wrapped that graph in
        `RunnableAgent(input_keys_arg=["input"]) + AgentExecutor`, producing a
        key-mismatched executor that silently broke any downstream consumer
        of this output port.
        """
        self.validate_tool_names()
        return self.create_agent_runnable()

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""

    def get_tool_name(self) -> str:
        return self.display_name or "Agent"

    def get_tool_description(self) -> str:
        return self.agent_description or DEFAULT_TOOLS_DESCRIPTION

    def _build_tools_names(self):
        tools_names = ""
        if self.tools:
            tools_names = ", ".join([tool.name for tool in self.tools])
        return tools_names

    # Set shared callbacks for tracing
    def set_tools_callbacks(self, tools_list: list[Tool], callbacks_list: list[BaseCallbackHandler]):
        """Set shared callbacks for tracing to the tools.

        If we do not pass down the same callbacks to each tool
        used by the agent, then each tool will instantiate a new callback.
        For some tracing services, this will cause
        the callback handler to lose the id of its parent run (Agent)
        and thus throw an error in the tracing service client.

        Args:
            tools_list: list of tools to set the callbacks for
            callbacks_list: list of callbacks to set for the tools
        Returns:
            None
        """
        for tool in tools_list or []:
            if hasattr(tool, "callbacks"):
                tool.callbacks = callbacks_list

    async def _get_tools(self) -> list[Tool]:
        component_toolkit = _get_component_toolkit()
        tools_names = self._build_tools_names()
        agent_description = self.get_tool_description()
        # TODO: Agent Description Depreciated Feature to be removed
        description = f"{agent_description}{tools_names}"

        tools = component_toolkit(component=self).get_tools(
            tool_name=self.get_tool_name(),
            tool_description=description,
            # here we do not use the shared callbacks as we are exposing the agent as a tool
            callbacks=self.get_langchain_callbacks(),
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)

        return tools
