import asyncio
from abc import abstractmethod
from typing import TYPE_CHECKING, cast

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.agents.agent import RunnableAgent
from langchain_core.runnables import Runnable

from langflow.base.agents.callback import AgentAsyncHandler
from langflow.base.agents.events import ExceptionWithMessageError, process_agent_events
from langflow.base.agents.utils import data_to_messages
from langflow.custom import Component
from langflow.inputs.inputs import InputTypes
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput
from langflow.memory import delete_message
from langflow.schema import Data
from langflow.schema.content_block import ContentBlock
from langflow.schema.log import SendMessageFunctionType
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class LCAgentComponent(Component):
    trace_type = "agent"
    _base_inputs: list[InputTypes] = [
        MessageTextInput(name="input_value", display_name="Input"),
        BoolInput(
            name="handle_parsing_errors",
            display_name="Handle Parse Errors",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="verbose",
            display_name="Verbose",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            value=15,
            advanced=True,
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
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Message:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=self.tools,
                handle_parsing_errors=self.handle_parsing_errors,
                verbose=self.verbose,
                max_iterations=self.max_iterations,
            )
        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        if self.chat_history:
            input_dict["chat_history"] = data_to_messages(self.chat_history)

        agent_message = Message(
            sender=MESSAGE_SENDER_AI,
            sender_name="Agent",
            properties={"icon": "Bot", "state": "partial"},
            content_blocks=[ContentBlock(title="Agent Steps", contents=[])],
            session_id=self.graph.session_id,
        )
        try:
            result = await process_agent_events(
                runnable.astream_events(
                    input_dict,
                    config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]},
                    version="v2",
                ),
                agent_message,
                cast(SendMessageFunctionType, self.send_message),
            )
        except ExceptionWithMessageError as e:
            msg_id = e.agent_message.id
            await asyncio.to_thread(delete_message, id_=msg_id)
            self._send_message_event(e.agent_message, category="remove_message")
            raise e.exception  # noqa: B904
        except Exception:
            raise

        self.status = result
        return result

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""


class LCToolsAgentComponent(LCAgentComponent):
    _base_inputs = [
        HandleInput(
            name="tools", display_name="Tools", input_types=["Tool", "BaseTool", "StructuredTool"], is_list=True
        ),
        *LCAgentComponent._base_inputs,
    ]

    def build_agent(self) -> AgentExecutor:
        agent = self.create_agent_runnable()
        return AgentExecutor.from_agent_and_tools(
            agent=RunnableAgent(runnable=agent, input_keys_arg=["input"], return_keys_arg=["output"]),
            tools=self.tools,
            **self.get_agent_kwargs(flatten=True),
        )

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""
