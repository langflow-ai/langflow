---
title: Create a problem-solving agent
sidebar_position: 2
slug: /agents-tool-calling-agent-component
---

Developing **agents** in Langchain is complex.

The `AgentComponent` is a component for easily creating an AI agent capable of analyzing tasks using tools you provide.

The component contains all of the elements you'll need for creating an agent. Instead of managing LLM models and providers, pick your model and enter your API key. Instead of connecting a **Prompt** component, enter instructions in the component's **Agent Instruction** fields.

<img src="/img/tool-calling-agent-component.png" alt="Prompt component" style={{display: 'block', margin: 'auto', width: 300}} />

Learn how to build a flow starting with the **Tool calling agent** component, and see how it can help you solve problems.

## Prerequisites

- [An OpenAI API key](https://platform.openai.com/)
- [A Search API key](https://www.searchapi.io/)

## Create a problem-solving agent with AgentComponent

Create a problem-solving agent in Langflow, starting with the **Tool calling agent**.

1. Click **New Flow**, and then click **Blank Flow**.
2. Click and drag an **Agent** component to your workspace.
The default settings are acceptable for now, so this guide assumes you're using **Open AI** for the LLM.
3. Add your **Open AI API Key** to the **Agent** component.
4. Add **Chat input** and **Chat output** components to your flow, and connect them to the tool calling agent.

<img src="/img/tool-calling-agent-add-chat.png" alt="Chat with agent component" style={{display: 'block', margin: 'auto', width: 600}} />

This basic flow enables you to chat with the agent with the **Playground** after you've connected some **Tools**.

5. Connect the **Search API** tool component to your agent.
6. Add your **Search API key** to the component.
Your agent can now query the Search API for information.
7. Connect a **Calculator** tool for solving basic math problems.
8. Connect an **API Request** component to the agent.
This component is not in the **Tools** category, but the agent can still use it as a tool by enabling **Tool Mode**.
**Tool Mode** makes a component into a tool by adding a **Toolset** port that can be connected to an agent's **Tools** port.
To enable **Tool Mode** on the component, click **Tool Mode**.
The component's fields change dynamically based on the mode it's in.

<img src="/img/tool-calling-agent-add-tools.png" alt="Chat with agent component" style={{display: 'block', margin: 'auto', width: 600}} />

## Solve problems with the agent

Your agent now has tools for performing a web search, doing basic math, and performing API requests. You can solve many problems with just these capabilities.

* Your tabletop game group cancelled, and you're stuck at home.
Point **API Request** to an online rules document, tell your agent `You are a fun game organizer who uses the tools at your disposal`, and play a game.
* You need to learn a new software language quickly.
Point **API Request** to some docs, tell your agent `You are a knowledgeable software developer who uses the tools at your disposal`, and start learning.

See what problems you can solve with this flow. As your problem becomes more specialized, add a tool. For example, the [simple agent starter project](/starter-projects-simple-agent) adds a Python REPL component to solve math problems that are too challenging for the calculator.

## Use an agent as a tool

The agent component itself also supports **Tool Mode** for creating multi-agent flows.

Add an agent to your problem-solving flow that uses a different OpenAI model for more specialized problem solving.

1. Click and drag an **Agent** component to your workspace.
2. Add your **Open AI API Key** to the **Agent** component.
3. In the **Model Name** field, select `gpt-4o`.
4. Click **Tool Mode** to use this new agent as a tool.
5. Connect the new agent's **Toolset** port to the previously created agent's **Tools** port.
6. Connect **Search API** and **API Request** to the new agent.
The new agent will use `gpt-4o` for the larger tasks of scraping and searching information that requires large context windows.
The problem-solving agent will now use this agent as a tool, with its unique LLM and toolset.

<img src="/img/tool-calling-agent-as-tool.png" alt="Chat with agent component" style={{display: 'block', margin: 'auto', width: 600}} />

## Add custom components as tools {#components-as-tools}

An agent can use custom components as tools.

1. To add a custom component to the problem-solving agent flow, click **New Custom Component**.

2. Add custom Python code to the custom component.
Here's an example text analyzer for sentiment analysis.

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

3. To enable the custom component as a tool, click **Tool Mode**.
4. Connect the tool output to the agent's tools input.
5. Ask the agent, `What tools are you using to answer my questions?`
Your response will be similar to the following, and will include your custom component.
```plain
I have access to several tools that assist me in answering your questions, including:
Search API: This allows me to search for recent information or results on the web.
HTTP Requests: I can make HTTP requests to various URLs to retrieve data or interact with APIs.
Calculator: I can evaluate basic arithmetic expressions.
Text Analyzer: I can analyze and transform input text.
Current Date and Time: I can retrieve the current date and time in various time zones.
```

## Make any component a tool

These components support **Tool Mode**:

* **URL**
* **API request**
* **Calculator**
* **Current date**

If the component you want to use as a tool doesn't have a **Tool Mode** button, add `tool_mode=True` to one of the component's inputs.

Langflow supports **Tool Mode** for the following data types:

* `DataInput`
* `DataFrameInput`
* `PromptInput`
* `MessageTextInput`
* `MultilineInput`
* `DropdownInput`

For example, in the [components as tools](#components-as-tools) example above, `tool_mode=True,` is added to the `MultilineInput` input so the custom component can be used as a tool.

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

## Add flows as tools

An agent can use flows that are saved in your workspace as tools with the [Flow as Tool](/components-logic#flow-as-tool) component.

1. To add a **Flow as Tool** component, click and drag a **Flow as Tool** component to your workspace.
2. Select the flow you want the agent to use as a tool.
3. Connect the tool output to the agent's tools input.
4. Ask the agent, `What tools are you using to answer my questions?`
Your **Flow as Tool** flow should be visible in the response.


