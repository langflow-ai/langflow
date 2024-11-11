from langflow.base.agents.crewai.tasks import SequentialTask
from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, MultilineInput, Output


class SequentialTaskComponent(Component):
    display_name: str = "Sequential Task"
    description: str = "Each task must have a description, an expected output and an agent responsible for execution."
    icon = "CrewAI"
    inputs = [
        MultilineInput(
            name="task_description",
            display_name="Description",
            info="Descriptive text detailing task's purpose and execution.",
        ),
        MultilineInput(
            name="expected_output",
            display_name="Expected Output",
            info="Clear definition of expected task outcome.",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            info="List of tools/resources limited for task execution. Uses the Agent tools by default.",
            required=False,
            advanced=True,
        ),
        HandleInput(
            name="agent",
            display_name="Agent",
            input_types=["Agent"],
            info="CrewAI Agent that will perform the task",
            required=True,
        ),
        HandleInput(
            name="task",
            display_name="Task",
            input_types=["SequentialTask"],
            info="CrewAI Task that will perform the task",
        ),
        BoolInput(
            name="async_execution",
            display_name="Async Execution",
            value=True,
            advanced=True,
            info="Boolean flag indicating asynchronous task execution.",
        ),
    ]

    outputs = [
        Output(display_name="Task", name="task_output", method="build_task"),
    ]

    def build_task(self) -> list[SequentialTask]:
        tasks: list[SequentialTask] = []
        task = SequentialTask(
            description=self.task_description,
            expected_output=self.expected_output,
            tools=self.agent.tools,
            async_execution=False,
            agent=self.agent,
        )
        tasks.append(task)
        self.status = task
        if self.task:
            if isinstance(self.task, list) and all(isinstance(task, SequentialTask) for task in self.task):
                tasks = self.task + tasks
            elif isinstance(self.task, SequentialTask):
                tasks = [self.task, *tasks]
        return tasks
