from crewai import Agent  # type: ignore

from langflow.custom import Component
from langflow.io import BoolInput, DictInput, HandleInput, MultilineInput, Output


class CrewAIAgentComponent(Component):
    display_name = "CrewAI Agent"
    description = "Represents an agent of CrewAI."
    documentation: str = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"

    inputs = [
        MultilineInput(name="role", display_name="Role", info="The role of the agent."),
        MultilineInput(name="goal", display_name="Goal", info="The objective of the agent."),
        MultilineInput(name="backstory", display_name="Backstory", info="The backstory of the agent."),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            info="Tools at agents disposal",
            value=[],
        ),
        HandleInput(
            name="llm",
            display_name="Language Model",
            info="Language model that will run the agent.",
            input_types=["LanguageModel"],
        ),
        BoolInput(
            name="memory",
            display_name="Memory",
            info="Whether the agent should have memory or not",
            advanced=True,
            value=True,
        ),
        BoolInput(
            name="verbose",
            display_name="Verbose",
            advanced=True,
            value=False,
        ),
        BoolInput(
            name="allow_delegation",
            display_name="Allow Delegation",
            info="Whether the agent is allowed to delegate tasks to other agents.",
            value=True,
        ),
        BoolInput(
            name="allow_code_execution",
            display_name="Allow Code Execution",
            info="Whether the agent is allowed to execute code.",
            value=False,
            advanced=True,
        ),
        DictInput(
            name="kwargs",
            display_name="kwargs",
            info="kwargs of agent.",
            is_list=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Agent", name="output", method="build_output"),
    ]

    def build_output(self) -> Agent:
        kwargs = self.kwargs if self.kwargs else {}
        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            llm=self.llm,
            verbose=self.verbose,
            memory=self.memory,
            tools=self.tools if self.tools else [],
            allow_delegation=self.allow_delegation,
            allow_code_execution=self.allow_code_execution,
            **kwargs,
        )
        self.status = repr(agent)
        return agent
