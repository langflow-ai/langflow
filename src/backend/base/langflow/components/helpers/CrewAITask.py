from crewai import Task

from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, MessageTextInput, Output


class CrewAITask(Component):
    display_name: str = "CrewAITask"
    description: str = "Each task must have a description, an expected output and an agent responsible for execution."
    documentation: str = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"

    inputs = [
        MessageTextInput(
            name="description",
            display_name="Description",
            info="Descriptive text detailing task's purpose and execution.",
        ),
        MessageTextInput(
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
            info="Agent responsible for task execution. Represents entity performing task.",
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

    def build_task(self) -> Task:
        task = Task(
            description=self.description,
            expected_output=self.expected_output,
            tools=self.tools or [],
            async_execution=self.async_execution,
            agent=self.agent,
        )
        self.status = task
        return task
