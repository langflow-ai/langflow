import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Task Component

The `CrewAITask` component represents a task in CrewAI. It allows you to define tasks with detailed descriptions, expected outputs, and the responsible agent, integrating seamlessly into your Langflow workflows.

[CrewAI Reference](https://docs.crewai.com/how-to/LLM-Connections/)

The `CrewAITask` component enables you to:

- Define the task's description and expected output
- Assign an agent responsible for executing the task
- Specify tools and resources for task execution
- Configure advanced settings such as asynchronous execution

## Component Usage

To use the `CrewAITask` component in a Langflow flow, follow these steps:

1. Add the `CrewAITask` component to your flow.
2. Configure the component by providing the required inputs such as description and expected output.
3. Connect the component to other nodes in your flow as needed.

## Component Python code

```python
from langflow.custom import Component
from langflow.io import BoolInput, DictInput, DropdownInput, MessageTextInput, HandleInput
from crewai import Task, Agent

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
            info="List of tools/resources limited for task execution.",
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
            value=False,
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
            tools=self.tools if self.tools else [],
            async_execution=self.async_execution,
            agent=self.agent
        )
        self.status = task
        return task
```

## Example Usage

Here's an example of how you can use the CrewAITask component in a Langflow flow, connecting the CrewAIAgent component to the CrewAITask component, and then passing the outputs to the CrewAICrew component:

<ZoomableImage
alt="CrewAITask Flow Example"
sources={{
light: "img/crewai/CrewAITask_flow_example.png",
dark: "img/crewai/CrewAITask_flow_example_dark.png",
}}
style={{ width: "100%", margin: "20px 0" }}
/>

## Best Practices

When using the CrewAITask component, consider the following best practices:

Ensure that you have defined the task's description and expected output clearly.
Assign the appropriate agent for task execution.
The CrewAITask component provides a streamlined way to define and manage tasks within your Langflow workflows. By leveraging this component, you can effectively organize and automate task execution, enhancing the efficiency of your Langflow projects. Feel free to explore and experiment with the CrewAITask component to unlock new possibilities in your Langflow projects!

## Troubleshooting

If you encounter any issues while using the CrewAITask component, consider the following:

Double-check that your inputs such as description and expected output are correctly configured.
Verify that you have installed the necessary dependencies for the component to function properly.
Check the CrewAI documentation for any updates or changes that may affect the component's functionality.
