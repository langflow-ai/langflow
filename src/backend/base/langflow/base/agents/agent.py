import re
from abc import abstractmethod
from typing import TYPE_CHECKING, cast

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.agents.agent import RunnableAgent
from langchain_core.runnables import Runnable

from langflow.base.agents.callback import AgentAsyncHandler
from langflow.base.agents.events import ExceptionWithMessageError, process_agent_events
from langflow.base.agents.utils import data_to_messages
from langflow.custom import Component
from langflow.custom.custom_component.component import _get_component_toolkit
from langflow.field_typing import Tool
from langflow.inputs.inputs import InputTypes, MultilineInput
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput
from langflow.memory import delete_message
from langflow.schema import Data
from langflow.schema.content_block import ContentBlock
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

    from langflow.schema.log import SendMessageFunctionType


DEFAULT_TOOLS_DESCRIPTION = "A helpful assistant with access to the following tools:"
TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class LCAgentComponent(Component):
    trace_type = "agent"
    _base_inputs: list[InputTypes] = [
        MessageTextInput(
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
        Output(display_name="Agent", name="agent", method="build_agent"),
        Output(display_name="Response", name="response", method="message_response"),
    ]

    @abstractmethod
    def build_agent(self) -> AgentExecutor:
        """Create the agent."""

    async def message_response(self) -> Message:
        """Run the agent and return the response."""
        agent = self.build_agent()
        message = await self.run_agent(agent=agent)
        self.status = message
        return message

    def get_agent_kwargs(self) -> dict:
        """Get agent configuration arguments."""
        return {
            "handle_parsing_errors": self.handle_parsing_errors,
            "verbose": self.verbose,
            "max_iterations": self.max_iterations,
            "allow_dangerous_code": True,
        }

    def get_chat_history_data(self) -> list[Data] | None:
        """Retrieve chat history data if available."""
        return None

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        """Run the agent and process its events."""
        if not hasattr(self, "tools") or not self.tools:
            raise ValueError("Tools are required to run the agent.")

        runnable = (
            agent
            if isinstance(agent, AgentExecutor)
            else AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=self.tools,
                **self.get_agent_kwargs(),
            )
        )

        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        if hasattr(self, "system_prompt"):
            input_dict["system_prompt"] = self.system_prompt

        if hasattr(self, "chat_history") and self.chat_history:
            messages = data_to_messages(self.chat_history)
            filtered_messages = [msg for msg in messages if msg.get("content", "").strip()]
            if not filtered_messages:
                raise ValueError("No valid messages to process in chat history.")
            input_dict["chat_history"] = filtered_messages

        session_id = getattr(self, "graph", getattr(self, "_session_id", None))
        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name=self.display_name or "Agent",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=session_id,
        )

        try:
            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]},
                    version="v2",
                ),
                agent_message,
                cast("SendMessageFunctionType", self.send_message),
            )
        except ExceptionWithMessageError as e:
            msg_id = e.agent_message.id
            await delete_message(id_=msg_id)
            await self._send_message_event(e.agent_message, category="remove_message")
            raise
        except Exception as e:
            self.log.error(f"An error occurred: {e}")
            raise

        self.status = result
        return result

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""

    def validate_tool_names(self) -> None:
        """Validate tool names to ensure they match the required pattern."""
        if hasattr(self, "tools") and self.tools:
            for tool in self.tools:
                if not TOOL_NAME_PATTERN.match(tool.name):
                    raise ValueError(
                        f"Invalid tool name '{tool.name}': must only contain letters, numbers, underscores, dashes, and cannot contain spaces."
                    )


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
        *LCAgentComponent._base_inputs,
    ]

    def build_agent(self) -> AgentExecutor:
        """Build the agent executor with tools."""
        self.validate_tool_names()
        agent = self.create_agent_runnable()
        return AgentExecutor.from_agent_and_tools(
            agent=RunnableAgent(runnable=agent, input_keys_arg=["input"], return_keys_arg=["output"]),
            tools=self.tools,
            **self.get_agent_kwargs(),
        )

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""

    def get_tool_name(self) -> str:
        """Get the name of the tool."""
        return self.display_name or "Agent"

    def get_tool_description(self) -> str:
        """Get the description of the tool."""
        return DEFAULT_TOOLS_DESCRIPTION

    def _build_tools_names(self) -> str:
        """Build a string of tool names."""
        return ", ".join(tool.name for tool in self.tools) if self.tools else ""

    def to_toolkit(self) -> list[Tool]:
        """Convert the component to a toolkit."""
        component_toolkit = _get_component_toolkit()
        tools_names = self._build_tools_names()
        description = f"{DEFAULT_TOOLS_DESCRIPTION}{tools_names}"
        tools = component_toolkit(component=self).get_tools(
            tool_name=self.get_tool_name(), tool_description=description, callbacks=self.get_langchain_callbacks()
        )
        if hasattr(self, "tools_metadata"):
            tools = component_toolkit(component=self, metadata=self.tools_metadata).update_tools_metadata(tools=tools)
        return tools
