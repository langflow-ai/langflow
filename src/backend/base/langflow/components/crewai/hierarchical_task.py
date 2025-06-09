from langflow.base.agents.crewai.tasks import HierarchicalTask
from langflow.custom.custom_component.component import Component
from langflow.io import HandleInput, MultilineInput, Output


class HierarchicalTaskComponent(Component):
    display_name: str = "Hierarchical Task"
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
    ]

    outputs = [
        Output(display_name="Task", name="task_output", method="build_task"),
    ]

    def build_task(self) -> HierarchicalTask:
        task = HierarchicalTask(
            description=self.task_description,
            expected_output=self.expected_output,
            tools=self.tools or [],
        )
        self.status = task
        return task
