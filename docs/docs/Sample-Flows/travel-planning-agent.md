---
title: Travel planning agent
slug: /travel-planning-agent
---

Build a **Travel Planning Agent** flow for an agentic application using the multiple Tool-calling agents.

An **agent** uses an LLM as its "brain" to select among the connected tools and complete its tasks.

In this flow, multiple **Tool-calling agents** reason using an **Open AI** LLM to plan a travel journey. Each agent is given a different responsibility defined by its **System Prompt** field.

The **Chat input** defines where the user wants to go, and passes the result to the **City Selection** agent. The **Local Expert** agent then adds information based on the selected cities, and the **Travel Concierge** assembles a seven day travel plan in Markdown.

All agents have access to the **Search API** and **URL Content Fetcher** components, while only the Travel Concierge can use the **Calculator** for computing the trip costs.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)
- [A Search API key](https://www.searchapi.io/)

## Open Langflow and start a new flow

Click **New Flow**, and then select the **Travel Planning Agent** flow.

This opens a starter flow with the necessary components to run an agentic application using multiple Tool-calling agents.

## Create the travel planning agent flow

![](/img/starter-flow-travel-agent.png)

The **Travel Planning Agent** flow consists of these components:

* Multiple **Tool calling agent** components that use the connected LLM to reason through the user's input and select among the connected tools to complete their tasks.
* The **Calculator** component performs basic arithmetic operations.
* The **URL Content Fetcher** component scrapes content from a given URL.
* The **Chat Input** component accepts user input to the chat.
* The **Chat Output** component prints the flow's output to the chat.
* The **OpenAI** model component sends the user input and prompt to the OpenAI API and receives a response.

## Run the travel planning agent flow

1. Add your credentials to the Open AI and Search API components.
2. Click **Playground** to start a chat session.
You should receive a detailed, helpful answer to the journey defined in the **Chat input** component.

Now that your query has completed the journey from **Chat input** to **Chat output**, you have completed the **Travel Planning Agent** flow.
