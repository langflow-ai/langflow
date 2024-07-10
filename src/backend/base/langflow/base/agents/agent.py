from abc import abstractmethod
from typing import List

from langchain.agents.agent import RunnableAgent

from langchain.agents import AgentExecutor
from langchain_core.runnables import Runnable

from langflow.custom import Component
from langflow.inputs import BoolInput, IntInput, HandleInput
from langflow.inputs.inputs import InputTypes
from langflow.template import Output


class LCAgentComponent(Component):
    trace_type = "agent"
    _base_inputs: List[InputTypes] = [
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
    ]

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


class LCToolsAgentComponent(LCAgentComponent):
    _base_inputs = LCAgentComponent._base_inputs + [
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
        ),
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
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
