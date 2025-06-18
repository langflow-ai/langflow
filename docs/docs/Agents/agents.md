---
title: Langflow Agents
slug: /agents
---

import Icon from "@site/src/components/icon";

Agents use LLMs as a brain to autonomously analyze problems and select tools to solve them.

Langflow's [Agent component](/components-agents#agent-component) simplifies agent configuration so you can focus on application development.

The Agent component provides everything you need to create an agent, including multiple LLMs, custom instructions, and tool configuration.


## Prerequisites

- [An OpenAI API key](https://platform.openai.com/)

## Create a flow with the Agent component

Create a problem-solving agent in Langflow, starting with the **Agent** component and working outward.

1. Click **New Flow**, and then click **Blank Flow**.
2. Click and drag an **Agent** component to your workspace.
The default settings are acceptable for now. This guide assumes you're using **OpenAI** for the LLM, but other model providers are available.
3. Add your **OpenAI API Key** to the **Agent** component.
4. Add **Chat input** and **Chat output** components to your flow, and connect them to the tool calling agent.

![Chat with agent component](/img/agent-example-add-chat.png)

This basic flow allows you to chat with the agent in the **Playground**, but you're only chatting with the OpenAI LLM.
To unlock the power of the Agent component, connect some tools.

5. Add the **News Search**, **URL**, and **Calculator** components to your flow.
6. Enable **Tool Mode** in the **News Search**, **URL**, and **Calculator** components.
To enable **Tool Mode** in a component, in the component's configuration tab, click **Tool Mode**.
**Tool Mode** makes a component into a tool by adding a **Toolset** port that can be connected to an agent's **Tools** port.
Enabling **Tool Mode** modifies the component's inputs to accept requests from the Agent to use a tool's available actions.
7. Connect the **News Search**, **URL**, and **Calculator** tool components to your agent.

![Chat with agent component](/img/agent-example-add-tools.png)

8. Open the **Playground**. Ask the agent, `What tools are you using to answer my questions?`
The agent should respond with a list of the connected tools.

```text
I use a combination of my built-in knowledge (up to June 2024) and a set of external tools to answer your questions. Here are the main types of tools I can use:
Web Search & Content Fetching: I can fetch and summarize content from web pages, including crawling links recursively.
News Search: I can search for recent news articles using Google News via RSS feeds.
Calculator: I can perform arithmetic calculations and evaluate mathematical expressions.
Date & Time: I can provide the current date and time in various time zones.
These tools help me provide up-to-date information, perform calculations, and retrieve specific data from the internet when needed. If you have a specific question, let me know, and I’ll use the most appropriate tool(s) to help!
```

9. Ask the agent, `Summarize today's tech news`.
The Playground displays the agent's tool calls, what input was provided, and the raw output the agent received before performing the summary. The agent should call the News Search component's `search_news` action.

You've successfully constructed a flow with the Langflow Agent.
Connect more tools to solve more specialized problems.

### Edit a tool component's actions

To edit a tool's actions, in the tool component, click <Icon name="SlidersHorizontal" aria-hidden="true"/> **Edit Tools** to modify its `name`, `description`, or `enabled` metadata.
These fields help connected agents understand how to use the action, without having to modify the agent's prompt instructions.

For example, the [URL](/components-data#url) component has two actions available when **Tool Mode** is enabled.

| Tool Name | Description | Enabled |
|-----------|-------------|---------|
| `fetch_content` | Fetch content from web pages recursively | true |
| `fetch_content_as_message` | Fetch web content formatted as messages | true |

With these descriptions, a connected agent has a clear idea of each tool's capabilities based on the `name` and `description` metadata. The `enabled` boolean controls the tool's availability to the agent. If you think an agent is using a tool incorrectly, edit a tool's `description` metadata to help the agent better understand the tool.

Tool names and descriptions can be edited, but the default tool identifiers cannot be changed. If you want to change the tool identifier, create a custom component.

## Use an agent as a tool

The agent component itself also supports **Tool Mode** for creating multi-agent flows.

Add an agent to your flow that uses a different OpenAI model for a larger context window.

1. Click and drag an **Agent** component to your workspace.
2. Add your **Open AI API Key** to the **Agent** component.
3. In the **Model Name** field, select `gpt-4.1`.
4. Click **Tool Mode** to use this new agent as a tool.
5. Connect the new agent's **Toolset** port to the previously created agent's **Tools** port.
6. Connect the **Web Search**, **URL**, and **Calculator** to the new agent.
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
5. Open the Playground and instruct the agent, `Use the text analyzer on this text: "Agents really are thinking machines!"`

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

## Use the Run Flow component as a tool

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


