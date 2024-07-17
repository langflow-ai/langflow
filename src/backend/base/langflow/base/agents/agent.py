from abc import abstractmethod
from typing import List, Optional, Union, cast

from langchain.agents import AgentExecutor, BaseMultiActionAgent, BaseSingleActionAgent
from langchain.agents.agent import RunnableAgent
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from langflow.base.agents.callback import AgentAsyncHandler
from langflow.base.agents.utils import data_to_messages
from langflow.custom import Component
from langflow.field_typing import Text, Tool
from langflow.inputs.inputs import DataInput, InputTypes
from langflow.io import BoolInput, HandleInput, IntInput, MessageTextInput
from langflow.schema import Data
from langflow.schema.message import Message
from langflow.template import Output


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

    async def message_response(self) -> Message:
        agent = self.build_agent()
        result = await self.run_agent(
            agent=agent,
            inputs=self.input_value,
            tools=self.tools,
            message_history=self.chat_history,
            handle_parsing_errors=self.handle_parsing_errors,
        )
        if isinstance(result, list):
            result = "\n".join([result_dict["text"] for result_dict in result])
        message = Message(text=result, sender="Machine")
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

    async def run_agent(
        self,
        agent: Union[Runnable, BaseSingleActionAgent, BaseMultiActionAgent, AgentExecutor],
        inputs: str,
        tools: List[Tool],
        message_history: Optional[List[Data]] = None,
        handle_parsing_errors: bool = True,
    ) -> Text:
        if isinstance(agent, AgentExecutor):
            runnable = agent
        else:
            runnable = AgentExecutor.from_agent_and_tools(
                agent=agent,  # type: ignore
                tools=tools,
                verbose=True,
                handle_parsing_errors=handle_parsing_errors,
            )
        input_dict: dict[str, str | list[BaseMessage]] = {"input": inputs}
        if message_history:
            input_dict["chat_history"] = data_to_messages(message_history)
        result = await runnable.ainvoke(input_dict, config={"callbacks": [AgentAsyncHandler(self.log)]})
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
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel", "ToolEnabledLanguageModel"],
            required=True,
        ),
        DataInput(name="chat_history", display_name="Chat History", is_list=True),
    ]

    def build_agent(self) -> AgentExecutor:
        agent = self.creat_agent_runnable()
        return AgentExecutor.from_agent_and_tools(
            agent=RunnableAgent(runnable=agent, input_keys_arg=["input"], return_keys_arg=["output"]),
            tools=self.tools,
            **self.get_agent_kwargs(flatten=True),
        )

    @abstractmethod
    def creat_agent_runnable(self) -> Runnable:
        """Create the agent."""
        pass
