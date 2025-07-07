---
title: Sequential tasks agent
slug: /sequential-agent
---

Build a **Sequential Tasks Agent** flow for a multi-agent application using multiple **Agent** components.

Each agent has an LLM model and a unique set of tools at its disposal, with **Prompt** components connected to the **Agent Instructions** fields to control the agent's behavior. For example, the **Researcher Agent** has a **Tavily AI Search** component connected as a tool. The **Prompt** instructs the agent how to answer your query, format the response, and pass the query and research results on to the next agent in the flow.

Each successive agent in the flow builds on the work of the previous agent, creating a chain of reasoning for solving complex problems.

## Prerequisites

- [A running Langflow instance](/docs/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)
- [A Tavily AI API key](https://www.tavily.com/)

## Open Langflow and create a new flow

1. Click **New Flow**, and then select **Sequential Tasks Agent**.
This opens a starter template with the necessary components to run the flow.

![Starter flow for Sequential Tasks Agent](/img/starter-flow-sequential-agent.png)

The Sequential Tasks Agent flow consists of these components:

* The **Agent** components use the connected LLM to analyze the user's input and select among the connected tools to complete the tasks.
* The **Chat Input** component accepts user input to the chat.
* The **Prompt** component combines the user input with a user-defined prompt.
* The **Chat Output** component prints the flow's output to the chat.
* The **YFinance** tool component provides access to financial data from Yahoo Finance.
* The **Tavily AI Search** tool component performs AI-powered web searches.
* The **Calculator** tool component performs mathematical calculations.

## Run the Sequential Tasks Agent flow

1. Add your OpenAI API key to the **Agent** components.
2. Add your Tavily API key to the **Tavily** component.
3. Click **Playground** to start a chat session with the template's default question.

```text
Should I invest in Tesla (TSLA) stock right now?
Please analyze the company's current position, market trends,
financial health, and provide a clear investment recommendation.
```

This question provides clear instructions to the agents about how to proceed and what question to answer.

4. In the **Playground**, inspect the answers to see how the agents use the **Tavily AI Search** tool to research the query, the **YFinance** tool to analyze the stock data, and the **Calculator** to determine if the stock is a wise investment.
5. Ask similar questions to see how the agents use the tools to answer your queries.

## Next steps

To create your own multi-agent flow, see [Create a problem solving agent](/docs/agents).