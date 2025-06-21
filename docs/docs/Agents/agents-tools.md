---
title: Configure tools for agents
slug: /agents-tools
---

import Icon from "@site/src/components/icon";

Configure tools connected to agents to extend their capabilities.

## Edit a tool component's actions

To edit a tool's actions, in the tool component, click <Icon name="SlidersHorizontal" aria-hidden="true"/> **Edit Tools** to modify its `name`, `description`, or `enabled` metadata.
These fields help connected agents understand how to use the action, without having to modify the agent's prompt instructions.

For example, the [URL](/components-data#url) component has two actions available when **Tool Mode** is enabled:

| Tool Name | Description | Enabled |
|-----------|-------------|---------|
| `fetch_content` | Fetch content from web pages recursively | true |
| `fetch_content_as_message` | Fetch web content formatted as messages | true |

A Langflow Agent has a clear idea of each tool's capabilities based on the `name` and `description` metadata. The `enabled` boolean controls the tool's availability to the agent. If you think an agent is using a tool incorrectly, edit a tool's `description` metadata to help the agent better understand the tool.

Tool names and descriptions can be edited, but the default tool identifiers cannot be changed. If you want to change the tool identifier, create a custom component.

## Use an agent as a tool

The agent component itself also supports **Tool Mode** for creating multi-agent flows.

Add an agent to your flow that uses a different OpenAI model for a larger context window.

1. Create the [Simple agent starter flow](/simple-agent).
2. Add a second agent component to the flow.
3. Add your **Open AI API Key** to the **Agent** component.
4. In the **Model Name** field, select `gpt-4.1`.
5. Click **Tool Mode** to use this new agent as a tool.
6. Connect the new agent's **Toolset** port to the previously created agent's **Tools** port.
The new agent will use `gpt-4.1` for the larger tasks of scraping and searching information that require large context windows.
The previously created agent will now use this agent as a tool, with its unique LLM and toolset.

![Agent as a tool](/img/agent-example-agent-as-tool.png)

7. The new agent's actions can be edited to help the agent understand how to use it.
Click <Icon name="SlidersHorizontal" aria-hidden="true"/> **Edit Tools** to modify its `name`, `description`, or `enabled` metadata.
For example, the default tool name is `Agent`. Edit the name to `Agent-gpt-41`, and edit the description to `Use the gpt-4.1 model for complex problem solving`. The connected agent will understand that this is the `gpt-4.1` agent, and will use it for tasks requiring a larger context window.

## Add custom components as tools {#components-as-tools}

An agent can use custom components as tools.

1. To add a custom component to the agent flow, click **New Custom Component**.

2. Add custom Python code to the custom component.
For example, to create a text analyzer component, paste the below code into the custom component's **Code** pane.

<details open>
<summary>Python</summary>

```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
import re

class TextAnalyzerComponent(Component):
    display_name = "Text Analyzer"
    description = "Analyzes and transforms input text."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "chart-bar"
    name = "TextAnalyzerComponent"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="Enter text to analyze",
            value="Hello, World!",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Analysis Result", name="output", method="analyze_text"),
    ]

    def analyze_text(self) -> Data:
        text = self.input_text

        # Perform text analysis
        word_count = len(text.split())
        char_count = len(text)
        sentence_count = len(re.findall(r'\w+[.!?]', text))

        # Transform text
        reversed_text = text[::-1]
        uppercase_text = text.upper()

        analysis_result = {
            "original_text": text,
            "word_count": word_count,
            "character_count": char_count,
            "sentence_count": sentence_count,
            "reversed_text": reversed_text,
            "uppercase_text": uppercase_text
        }

        data = Data(value=analysis_result)
        self.status = data
        return data
```
</details>

3. To use the custom component as a tool, click **Tool Mode**.
4. Connect the custom component's tool output to the agent's tools input.
5. Open the <Icon name="Play" aria-hidden="true" /> **Playground** and instruct the agent, `Use the text analyzer on this text: "Agents really are thinking machines!"`

<details open>
<summary>Response</summary>
```
AI
gpt-4o
Finished
0.6s
Here is the analysis of the text "Agents really are thinking machines!":
Original Text: Agents really are thinking machines!
Word Count: 5
Character Count: 36
Sentence Count: 1
Reversed Text: !senihcam gnikniht era yllaer stnegA
Uppercase Text: AGENTS REALLY ARE THINKING MACHINES!
```
</details>

The agent correctly calls the `analyze_text` action and returns the result to the Playground.

## Make any component a tool

If the component you want to use as a tool doesn't have a **Tool Mode** button, add `tool_mode=True` to one of the component's inputs, and connect the new **Toolset** output to the agent's **Tools** input.

Langflow supports **Tool Mode** for the following data types:

* `DataInput`
* `DataFrameInput`
* `PromptInput`
* `MessageTextInput`
* `MultilineInput`
* `DropdownInput`

For example, the [components as tools](#components-as-tools) example above adds `tool_mode=True` to the `MessageTextInput` input so the custom component can be used as a tool.

```python
inputs = [
    MessageTextInput(
        name="input_text",
        display_name="Input Text",
        info="Enter text to analyze",
        value="Hello, World!",
        tool_mode=True,
    ),
]
```

## Use flows as tools

An agent can use flows that are saved in your workspace as tools with the [Run flow](/components-logic#run-flow) component.

1. To add a **Run flow** component, click and drag a **Run flow** component to your workspace.
2. Select the flow you want the agent to use as a tool.
3. Enable **Tool Mode** in the component.
The **Run flow** component displays your flow as an available action.
4. Connect the **Run flow** component's tool output to the agent's tools input.
5. Ask the agent, `What tools are you using to answer my questions?`
Your flow should be visible in the response as a tool.
6. Ask the agent to specifically use the connected tool to answer your question.
The connected flow returns an answer based on your question.
For example, a Basic Prompting flow connected as a tool returns a different result depending upon its LLM and prompt instructions.

![Run Flow as tool connected to agnet](/img/agent-example-run-flow-as-tool.png)