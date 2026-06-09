from lfx.base.agents.crewai.tasks import SequentialTask
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DictInput, HandleInput, MultilineInput, Output


class SequentialTaskAgentComponent(Component):
    display_name = "Sequential Task Agent"
    description = "Creates a CrewAI Task and its associated Agent."
    documentation = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"
    legacy = True
    replacement = "agents.Agent"

    inputs = [
        # Agent inputs
        MultilineInput(name="role", display_name="Role", info="The role of the agent."),
        MultilineInput(name="goal", display_name="Goal", info="The objective of the agent."),
        MultilineInput(
            name="backstory",
            display_name="Backstory",
            info="The backstory of the agent.",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            info="Tools at agent's disposal",
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
            value=True,
        ),
        BoolInput(
            name="allow_delegation",
            display_name="Allow Delegation",
            info="Whether the agent is allowed to delegate tasks to other agents.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="allow_code_execution",
            display_name="Allow Code Execution",
            info="Whether the agent is allowed to execute code.",
            value=False,
            advanced=True,
        ),
        DictInput(
            name="agent_kwargs",
            display_name="Agent kwargs",
            info="Additional kwargs for the agent.",
            is_list=True,
            advanced=True,
        ),
        # Task inputs
        MultilineInput(
            name="task_description",
            display_name="Task Description",
            info="Descriptive text detailing task's purpose and execution.",
        ),
        MultilineInput(
            name="expected_output",
            display_name="Expected Task Output",
            info="Clear definition of expected task outcome.",
        ),
        BoolInput(
            name="async_execution",
            display_name="Async Execution",
            value=False,
            advanced=True,
            info="Boolean flag indicating asynchronous task execution.",
        ),
        # Chaining input
        HandleInput(
            name="previous_task",
            display_name="Previous Task",
            input_types=["SequentialTask"],
            info="The previous task in the sequence (for chaining).",
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Sequential Task",
            name="task_output",
            method="build_agent_and_task",
        ),
    ]

    def build_agent_and_task(self) -> list[SequentialTask]:
        try:
            from crewai import Agent, Task
        except ImportError as e:
            msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
            raise ImportError(msg) from e

        # Build the agent
        agent_kwargs = self.agent_kwargs or {}
        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            llm=self.llm,
            verbose=self.verbose,
            memory=self.memory,
            tools=self.tools or [],
            allow_delegation=self.allow_delegation,
            allow_code_execution=self.allow_code_execution,
            **agent_kwargs,
        )

        # Build the task
        task = Task(
            description=self.task_description,
            expected_output=self.expected_output,
            agent=agent,
            async_execution=self.async_execution,
        )

        # If there's a previous task, create a list of tasks
        if self.previous_task:
            tasks = [*self.previous_task, task] if isinstance(self.previous_task, list) else [self.previous_task, task]
        else:
            tasks = [task]

        self.status = f"Agent: {agent!r}\nTask: {task!r}"
        return tasks
