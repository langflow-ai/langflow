---
title: Use Langflow Agents
slug: /agents
---

import Icon from "@site/src/components/icon";

Agents use LLMs as a brain to autonomously analyze problems and select tools to solve them.

Langflow's [Agent component](/components-agents#agent-component) simplifies agent configuration so you can focus on application development.

The Agent component provides everything you need to create an agent, including multiple LLMs, custom instructions, and tool configuration.

## Agent settings

You can configure the Agent component to use your preferred provider and model, custom instructions, and tools.

### Agent models and providers

Use the *Model Provider* and *Model Name* settings to select the LLM that you want the Agent to use.

You must provide an authentication key for the selected provider, such as an OpenAI API key for OpenAI models.

### Agent instructions and input

In the *Agent Instructions* field, you can provide custom instructions that you want the Agent to use for every conversation.

These instructions are applied in addition to the *Input*, which is provided at runtime.

### Agent tools

Agents are most useful when they have the appropriate tools available to complete requests.

An Agent component can use any Langflow component as a tool, as long as you attach it to the Agent component.

When you attach a component as a tool, you must configure the component as a tool by enabling *Tool Mode*.

For more information, see [Configure tools for agents](/)

## Use the Agent component in a flow

:::tip
For a pre-built demonstration, open the **Simple Agent** starter flow and follow along.
:::

Create an agent in Langflow, starting with the **Agent** component and working outward.

1. Click **New Flow**, and then click **Blank Flow**.
2. Click and drag an **Agent** component to your workspace.
3. Use the default model or select another provider and model. If you want to use the default model, you need an OpenAI API key to run the flow.
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

## See also

* [Configure tools for agents](/agents-tools)