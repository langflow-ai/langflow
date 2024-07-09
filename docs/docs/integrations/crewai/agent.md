import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Agent Component

The `CrewAIAgent` component represents an agent of CrewAI. It provides a convenient way to integrate CrewAI agent data into your Langflow workflows.

[CrewAI Reference](https://docs.crewai.com/how-to/LLM-Connections/)

The `CrewAIAgent` component enables you to:

- Define the role, goal, and backstory of the agent
- Specify tools and language models for the agent
- Configure advanced settings such as memory, verbosity, and delegation

## Component Usage

To use the `CrewAIAgent` component in a Langflow flow, follow these steps:

1. Add the `CrewAIAgent` component to your flow.
2. Configure the component by providing the required inputs such as role, goal, and backstory.
3. Connect the component to other nodes in your flow as needed.

## Component Python code

```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from langflow.io import BoolInput, DictInput, DropdownInput, MessageTextInput, HandleInput
from crewai import Agent


class CrewAIAgent(Component):
    display_name = "CrewAIAgent"
    description = "Represents an agent of CrewAI."
    documentation: str = "https://docs.crewai.com/how-to/LLM-Connections/"
    icon = "CrewAI"

    inputs = [
        MessageTextInput(name="role", display_name="Role", info="The role of the agent."),
        MessageTextInput(name="goal", display_name="Goal", info="The objective of the agent."),
        MessageTextInput(name="backstory", display_name="Backstory", info="The backstory of the agent."),
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
        DictInput(
            name="kwargs",
            display_name="kwargs",
            info="kwargs of agent.",
            is_list=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
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
            **kwargs
        )
        self.status = agent
        return agent

```

## Example Usage

Here's an example of how to use the `CrewAIAgent` component in a Langflow flow, connecting the `OpenAI` component's output to the CrewAIAgent component.

<ZoomableImage
alt="CrewAIAgent Flow Example"
sources={{
      light: "img/crewai/CrewAIAgent_flow_example.png",
      dark: "img/crewai/CrewAIAgent_flow_example_dark.png",
  }}
style={{ width: "100%", margin: "20px 0" }}
/>

## Best Practices

When using the `CrewAIAgent` component, consider the following best practices:

- Ensure that you have configured the agent's role, goal, and backstory appropriately.

The `CrewAIAgent` component provides a seamless way to integrate CrewAI agent data into your Langflow workflows. By leveraging this component, you can easily define and utilize agent information from CrewAI, enhancing the capabilities of your Langflow applications. Feel free to explore and experiment with the `CrewAIAgent` component to unlock new possibilities in your Langflow projects!

## Troubleshooting

If you encounter any issues while using the `CrewAIAgent` component, consider the following:

- Double-check that your inputs such as role, goal, and backstory are correctly configured.
- Verify that you have installed the necessary dependencies for the component to function properly.
- Check the CrewAI documentation for any updates or changes that may affect the component's functionality.
