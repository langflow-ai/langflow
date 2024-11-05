from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from fastapi.encoders import jsonable_encoder
from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.agents.agent import RunnableAgent
from langchain_core.runnables import Runnable

from langflow.base.agents.callback import AgentAsyncHandler
from langflow.base.agents.utils import data_to_messages
from langflow.custom import Component
from langflow.field_typing import Text
from langflow.inputs.inputs import InputTypes
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput
from langflow.schema import Data
from langflow.schema.log import LogFunctionType
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
        result = await self.run_agent(agent=agent)

        if isinstance(result, list):
            result = "\n".join([result_dict["text"] for result_dict in result])
        message = Message(text=result, sender=MESSAGE_SENDER_AI)
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

    async def run_agent(self, agent: AgentExecutor) -> Text:
        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        self.chat_history = self.get_chat_history_data()
        if self.chat_history:
            input_dict["chat_history"] = data_to_messages(self.chat_history)
        result = agent.invoke(
            input_dict, config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]}
        )
        self.status = result
        if "output" not in result:
            msg = "Output key not found in result. Tried 'output'."
            raise ValueError(msg)

        return cast(str, result)

    async def handle_chain_start(self, event: dict[str, Any]) -> None:
        if event["name"] == "Agent":
            self.log(f"Starting agent: {event['name']} with input: {event['data'].get('input')}")

    async def handle_chain_end(self, event: dict[str, Any]) -> None:
        if event["name"] == "Agent":
            self.log(f"Done agent: {event['name']} with output: {event['data'].get('output', {}).get('output', '')}")

    async def handle_tool_start(self, event: dict[str, Any]) -> None:
        self.log(f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}")

    async def handle_tool_end(self, event: dict[str, Any]) -> None:
        self.log(f"Done tool: {event['name']}")
        self.log(f"Tool output was: {event['data'].get('output')}")

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

    async def run_agent(
        self,
        agent: Runnable | BaseSingleActionAgent | BaseMultiActionAgent | AgentExecutor,
    ) -> Text:
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

        result = await process_agent_events(
            runnable.astream_events(
                input_dict,
                config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]},
                version="v2",
            ),
            self.log,
        )

        self.status = result
        return cast(str, result)

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""


# Add this function near the top of the file, after the imports


async def process_agent_events(agent_executor: AsyncIterator[dict[str, Any]], log_callback: LogFunctionType) -> str:
    """Process agent events and return the final output.

    Args:
        agent_executor: An async iterator of agent events
        log_callback: A callable function for logging messages

    Returns:
        str: The final output from the agent
    """
    final_output = ""
    async for event in agent_executor:
        match event["event"]:
            case "on_chain_start":
                if event["data"].get("input"):
                    log_callback(f"Agent initiated with input: {event['data'].get('input')}", name="🚀 Agent Start")

            case "on_chain_end":
                data_output = event["data"].get("output", {})
                if data_output and "output" in data_output:
                    final_output = data_output["output"]
                    log_callback(f"{final_output}", name="✅ Agent End")
                elif data_output and "agent_scratchpad" in data_output and data_output["agent_scratchpad"]:
                    agent_scratchpad_messages = data_output["agent_scratchpad"]
                    json_encoded_messages = jsonable_encoder(agent_scratchpad_messages)
                    log_callback(json_encoded_messages, name="🔍 Agent Scratchpad")

            case "on_tool_start":
                log_callback(
                    f"Initiating tool: '{event['name']}' with inputs: {event['data'].get('input')}",
                    name="🔧 Tool Start",
                )

            case "on_tool_end":
                log_callback(f"Tool '{event['name']}' execution completed", name="🏁 Tool End")
                log_callback(f"{event['data'].get('output')}", name="📊 Tool Output")

            case "on_tool_error":
                tool_name = event.get("name", "Unknown tool")
                error_message = event["data"].get("error", "Unknown error")
                log_callback(f"Tool '{tool_name}' failed with error: {error_message}", name="❌ Tool Error")

                if "stack_trace" in event["data"]:
                    log_callback(f"{event['data']['stack_trace']}", name="🔍 Tool Error")

                if "recovery_attempt" in event["data"]:
                    log_callback(f"{event['data']['recovery_attempt']}", name="🔄 Tool Error")

            case _:
                # Handle any other event types or ignore them
                pass

    return final_output
