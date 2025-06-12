---
title: Simple agent
slug: /starter-projects-simple-agent
---

Build a **Simple Agent** flow for an agentic application using the [Agent](/agents) component.

An **agent** uses an LLM as its "brain" to select among the connected tools and complete its tasks.

In this flow, the **Tool-calling agent** reasons using an **Open AI** LLM.
The agent selects the **Calculator** tool for simple math problems and the **URL** tool to search a URL for content.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Open Langflow and start a new flow

Click **New Flow**, and then select the **Simple Agent** flow.

This opens a starter flow with the necessary components to run an agentic application using the Tool-calling agent.

## Simple Agent flow

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

The **Simple Agent** flow consists of these components:

* The **Tool calling agent** component uses the connected LLM to reason through the user's input and select among the connected tools to complete its task.
* The **URL** tool component searches a list of URLs for content.
* The **Calculator** component performs basic arithmetic operations.
* The **Chat Input** component accepts user input to the chat.
* The **Chat Output** component prints the flow's output to the chat.

## Run the Simple Agent flow

1. Add your credentials to the **Agent** component.
2. Click **Playground** to start a chat session.
3. To confirm the tools are connected, ask the agent, `What tools are available to you?`
The response is similar to the following:
```text
I have access to the following tools:
Calculator: Perform basic arithmetic operations.
fetch_content: Load and retrieve data from specified URLs.
fetch_content_text: Load and retrieve text data from specified URLs.
as_dataframe: Load and retrieve data in a structured format (dataframe) from specified URLs.
get_current_date: Returns the current date and time in a selected timezone.
```
4. Ask the agent a question. For example, ask it to create a tabletop character using your favorite rules set.
The agent tells you when it's using the `URL-fetch_content_text` tool to search for rules information, and when it's using `CalculatorComponent-evaluate_expression` to generate attributes with dice rolls.
The final output should be similar to this:

```text
Final Attributes
Strength (STR): 10
Constitution (CON): 12
Size (SIZ): 14
Dexterity (DEX): 9
Intelligence (INT): 11
Power (POW): 13
Charisma (CHA): 8
```

Now that your query has completed the journey from **Chat input** to **Chat output**, you have completed the **Simple Agent** flow.
