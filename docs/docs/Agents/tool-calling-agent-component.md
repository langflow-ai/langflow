---
title: Tool calling agent component
sidebar_position: 2
slug: /agents-tool-calling-agent-component
---

Developing **agents** in Langchain is complex.

The `AgentComponent` is a tool for easily creating an AI agent capable of reasoning through tasks using tools you provide.

The component contains all of the elements you'll need for creating an Agent. Instead of managing LLM models and providers, pick your model and enter your API key. Instead of connecting a **Prompt** component, enter instructions in the component's **Agent Instruction** fields. It even includes an optional `current-date`

<img src="/img/tool-calling-agent-component.png" alt="Prompt component" style={{display: 'block', margin: 'auto', width: 300}} />

Learn how to build a flow starting with the **Tool calling agent** component, and see how it can help you solve problems.

## Prerequisites

- [Langflow installed and running](/getting-started-installation)
- [OpenAI API key created](https://platform.openai.com/)
- [Search API key created](https://www.searchapi.io/).

## Create a problem-solving agent

Create a problem-solving agent in Langflow, starting with the **Tool calling agent**.

1. Click **New Flow**, and then click **Blank Flow**.
2. Click and drag an **Agent** component on to your workspace.
The default settings are acceptable for now, so this guide assumes you're using **Open AI** for the LLM.
3. Add your **Open AI API Key** to the **Agent** component.
4. Add **Chat input** and **Chat output** components to your flow, and connect them to the tool calling agent.

<img src="/img/tool-calling-agent-add-chat.png" alt="Chat with agent component" style={{display: 'block', margin: 'auto', width: 600}} />

This basic flow enables you to chat with the agent with the **Playground**, once you've connected some **Tools**.

5. Connect the **Search API** tool component to your agent.
6. Add your **Search API key** to the component.
Your agent can now query the Search API for information.
7. Connect a **Calculator** tool for solving basic math problems.
8. Connect an **API Request** component to the agent.
This component is not in the **Tools** category, can still be used as a tool by the agent.
To enable **Tool Mode** on component, click **Tool Mode**.
The component's fields change dynamically based on the mode its in.

## Solve problems with the agent

Your agent now has tools for web search, doing basic math, and performing API requests. You can solve many problems with just these capabilities.

* Your tabletop game group cancelled, and you're stuck at home.
Point **API Request** to an online rules document, tell your agent `You are a fun Game Master who uses the tools at your disposal.` and play a game.

* You need to learn a new software language quickly.
Point **API Request** to some docs, tell your agent `You are a knowledgeable software developer who uses the tools at your disposal.` and start learning.

See what problems you can solve with this flow. As your problem becomes more specialized, add a tool. For example, the [simple agent starter project](/starter-projects-simple-agent) adds a Python REPL component to solve math problems too challenging for the calculator.



## Add flows as tools


## Add components as tools {#components-as-tools}

Components that are not in the **Tools** category can still be used as tools by an agent.

Click the **Tool Mode** button on a component to enable it.

For example, the **API Request** component makes a helpful tool for an agent. 
Here are a few examples to get you started.

### URL

### API

### CURRENT Date

### Custom Component
