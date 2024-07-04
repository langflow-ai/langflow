import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Crew Component

The `CrewAICrew` component represents a group of agents in CrewAI. It defines how agents collaborate and the tasks they perform, integrating seamlessly into your Langflow workflows.

[CrewAI Reference](https://docs.crewai.com/how-to/LLM-Connections/)

The `CrewAICrew` component enables you to:

- Define tasks and assign agents
- Specify the topic and collaboration process
- Configure advanced settings such as verbosity, memory, cache usage, and maximum RPM

## Component Usage

To use the `CrewAICrew` component in a Langflow flow, follow these steps:

1. Add the `CrewAICrew` component to your flow.
2. Configure the component by providing the required inputs such as tasks, agents, and topic.
3. Connect the component to other nodes in your flow as needed.

## Component Python code

```python
from langflow.custom import Component
from crewai import Crew, Task, Agent, Process
from typing import List, Optional
from langflow.field_typing import Text
from langflow.io import NestedDictInput, DropdownInput, MessageTextInput, HandleInput, IntInput, BoolInput
from langflow.schema.message import Message

class CrewAICrew(Component):
    display_name: str = "CrewAICrew"
    description: str = "Represents a group of agents, defining how they should collaborate and the tasks they should perform."
    documentation: str = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"

    inputs = [
        HandleInput(name="tasks", display_name="Tasks", input_types=["Task"], is_list=True),
        HandleInput(name="agents", display_name="Agents", input_types=["Agent"], is_list=True),
        MessageTextInput(name="topic", display_name="Topic"),
        IntInput(name="verbose", display_name="Verbose", value=0, advanced=True),
        BoolInput(name="memory", display_name="Memory", value=False, advanced=True),
        BoolInput(name="use_cache", display_name="Cache", value=True, advanced=True),
        IntInput(name="max_rpm", display_name="Max RPM", value=100, advanced=True),
        DropdownInput(name="process", display_name="Process", value=Process.sequential, options=[Process.sequential, Process.hierarchical]),
        BoolInput(name="share_crew", display_name="Share Crew", value=False, advanced=True),
        NestedDictInput(name="input", display_name="Input", value={"topic": ""}, is_list=True)
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Message:
        if not self.agents or not self.tasks:
            raise ValueError("No agents or tasks have been added.")

        response = Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=self.process,
            verbose=self.verbose,
            memory=self.memory,
            cache=self.use_cache,
            max_rpm=self.max_rpm,
            share_crew=self.share_crew,
        )
        message = await response.kickoff_async(inputs=self.input)
        self.status = message
        return message
```

Example Usage
Here's an example of how you can use the `CrewAICrew` component in a Langflow flow, connecting the CrewAIAgent component to the `CrewAITask`, `CrewAIAgent`, and `Chat Input`component, and then passing the output Chat Output component:

<ZoomableImage
alt="CrewAICrew Flow Example"
sources={{
light: "img/crewai/CrewAICrew_flow_example.png",
dark: "img/crewai/CrewAICrew_flow_example_dark.png",
}}
style={{ width: "100%", margin: "20px 0" }}
/>

## Best Practices

When using the `CrewAICrew` component, consider the following best practices:

Clearly define the tasks and assign the appropriate agents.
Configure the collaboration process and advanced settings according to your needs.
The `CrewAICrew` component provides a streamlined way to manage groups of agents and their tasks within your Langflow workflows. By leveraging this component, you can effectively organize and automate agent collaboration, enhancing the efficiency of your Langflow projects. Feel free to explore and experiment with the `CrewAICrew` component to unlock new possibilities in your Langflow projects!

## Troubleshooting

If you encounter any issues while using the `CrewAICrew` component, consider the following:

- Double-check that your inputs such as tasks and agents are correctly configured.
- Verify that you have installed the necessary dependencies for the component to function properly.
- Check the CrewAI documentation for any updates or changes that may affect the component's functionality.
