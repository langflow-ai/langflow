from abc import abstractmethod
from typing import List, Optional, Union, cast

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.agents.agent import RunnableAgent
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from langflow.base.agents.callback import AgentAsyncHandler
from langflow.base.agents.utils import data_to_messages
from langflow.custom import Component
from langflow.field_typing import Text
from langflow.inputs.inputs import InputTypes
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.template import Output
from langflow.utils.constants import MESSAGE_SENDER_AI


class LCAgentComponent(Component):
    trace_type = "agent"
    _base_inputs: List[InputTypes] = [
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
        pass

    async def message_response(self) -> Message:
        """Run the agent and return the response."""
        agent = self.build_agent()
        result = await self.run_agent(agent=agent)

        if isinstance(result, list):
            result = "\n".join([result_dict["text"] for result_dict in result])
        message = Message(text=result, sender=MESSAGE_SENDER_AI)
        self.status = message
        return message

    def _validate_outputs(self):
        required_output_methods = ["build_agent"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    def get_agent_kwargs(self, flatten: bool = False) -> dict:
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

    def get_chat_history_data(self) -> Optional[List[Data]]:
        # might be overridden in subclasses
        return None

    async def run_agent(self, agent: AgentExecutor) -> Text:
        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        self.chat_history = self.get_chat_history_data()
        if self.chat_history:
            input_dict["chat_history"] = data_to_messages(self.chat_history)
        result = await agent.ainvoke(input_dict, config={"callbacks": [AgentAsyncHandler(self.log)]})
        self.status = result
        if "output" not in result:
            raise ValueError("Output key not found in result. Tried 'output'.")

        return cast(str, result.get("output"))


class LCToolsAgentComponent(LCAgentComponent):
    _base_inputs = LCAgentComponent._base_inputs + [
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool", "BaseTool"],
            is_list=True,
        ),
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
        agent: Union[Runnable, BaseSingleActionAgent, BaseMultiActionAgent, AgentExecutor],
    ) -> Text:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,  # type: ignore
                tools=self.tools,
                handle_parsing_errors=self.handle_parsing_errors,
                verbose=self.verbose,
                max_iterations=self.max_iterations,
            )
        input_dict: dict[str, str | list[BaseMessage]] = {"input": self.input_value}
        if self.chat_history:
            input_dict["chat_history"] = data_to_messages(self.chat_history)
        result = await runnable.ainvoke(input_dict, config={"callbacks": [AgentAsyncHandler(self.log)]})
        self.status = result
        if "output" not in result:
            raise ValueError("Output key not found in result. Tried 'output'.")

        return cast(str, result.get("output"))

    @abstractmethod
    def create_agent_runnable(self) -> Runnable:
        """Create the agent."""
        pass
