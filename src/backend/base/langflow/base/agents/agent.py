from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

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
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import ToolEndContent, ToolErrorContent, ToolStartContent
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

        result = await process_agent_events(
            runnable.astream_events(
                input_dict,
                config={"callbacks": [AgentAsyncHandler(self.log), *self.get_langchain_callbacks()]},
                version="v2",
            ),
            self.send_message,
        )

        self.status = result
        return result

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""


# Add this function near the top of the file, after the imports


async def process_agent_events(
    agent_executor: AsyncIterator[dict[str, Any]],
    send_message_method: SendMessageFunctionType,
) -> Message:
    """Process agent events and return the final output.

    Uses a single message that gets updated throughout the agent's execution.

    Args:
        agent_executor: An async iterator of agent events
        send_message_method: A callable function for sending messages
        on_token: A callable function for streaming tokens
    Returns:
        str: The final output from the agent
    """
    # Initialize a single message that will be updated throughout
    agent_message = Message(
        sender=MESSAGE_SENDER_AI,
        sender_name="Agent",
        properties={"icon": "🤖", "state": "partial"},
        content_blocks=[],
    )
    # Store the initial message
    agent_message = send_message_method(message=agent_message)

    async for event in agent_executor:
        match event["event"]:
            case "on_chain_start":
                if event["data"].get("input"):
                    agent_message.content_blocks.append(
                        ContentBlock(
                            title="Agent Input",
                            content={
                                "type": "text",
                                "text": f"Agent initiated with input: {event['data'].get('input')}",
                            },
                        )
                    )
                    agent_message.properties.icon = "🚀"
                    agent_message = send_message_method(message=agent_message)

            case "on_chain_end":
                data_output = event["data"].get("output", {})
                if data_output:
                    # Agent Strachpad floods the chat
                    # agent_scratchpad_messages = data_output["agent_scratchpad"]
                    # json_encoded_messages = jsonable_encoder(agent_scratchpad_messages)
                    # agent_message.content_blocks.extend(
                    #     [
                    #         ContentBlock(
                    #             title="Agent Scratchpad",
                    #             content=JSONContent(type="json", data=json_encoded_message),
                    #         )
                    #         for json_encoded_message in json_encoded_messages
                    #     ]
                    # )
                    if hasattr(data_output, "return_values") and data_output.return_values.get("output"):
                        agent_message.properties.state = "complete"
                        agent_message.text = data_output.return_values.get("output")
                        icon = "🤖"
                    else:
                        icon = "🔍"
                    agent_message.properties.icon = icon
                    agent_message = send_message_method(message=agent_message)

            case "on_tool_start":
                agent_message.content_blocks.append(
                    ContentBlock(
                        title="Tool Input",
                        content=ToolStartContent(
                            type="tool_start",
                            tool_name=event["name"],
                            tool_input=event["data"].get("input"),
                        ),
                    )
                )
                agent_message.properties.icon = "🔧"
                agent_message = send_message_method(message=agent_message)

            case "on_tool_end":
                agent_message.content_blocks.append(
                    ContentBlock(
                        title="Tool Output",
                        content=ToolEndContent(
                            type="tool_end",
                            tool_name=event["name"],
                            tool_output=event["data"].get("output"),
                        ),
                    )
                )
                agent_message = send_message_method(message=agent_message)

            case "on_tool_error":
                tool_name = event.get("name", "Unknown tool")
                error_message = event["data"].get("error", "Unknown error")
                agent_message.content_blocks.append(
                    ContentBlock(
                        title="Tool Error",
                        content=ToolErrorContent(
                            type="tool_error",
                            tool_name=tool_name,
                            tool_error=error_message,
                        ),
                    )
                )
                agent_message.properties.icon = "⚠️"
                agent_message = send_message_method(message=agent_message)

            case "on_chain_stream":
                # this is similar to the on_chain_end but here we stream tokens
                data_chunk = event["data"].get("chunk", {})
                if isinstance(data_chunk, dict) and data_chunk.get("output"):
                    agent_message.text = data_chunk.get("output")
                    agent_message.properties.state = "complete"
                    agent_message = send_message_method(message=agent_message)
            case _:
                # Handle any other event types or ignore them
                pass
    agent_message.properties.state = "complete"
    return Message(**agent_message.model_dump())
