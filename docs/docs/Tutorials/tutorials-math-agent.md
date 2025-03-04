---
title: Math agent
slug: /tutorials-math-agent
---

import Icon from "@site/src/components/icon";

Build a **Math Agent** flow for an agentic application using the **Tool-calling agent** component.

In this flow, the **Tool-calling agent** reasons using an **Open AI** LLM to solve math problems.
It selects the **Calculator** tool for simpler math and the **Python REPL** tool (with the Python `math` library) for more complex problems.

## Prerequisites

To use this flow, you need an OpenAI API key.

## Open Langflow and start a new flow

Click **New Flow**, and then select the **Math Agent** flow.

This opens a starter flow with the necessary components to run an agentic application using the Tool-calling agent.

## Math Agent flow

![](/img/starter-flow-simple-agent-repl.png)

The **Math Agent** flow consists of these components:

* The **Tool calling agent** component uses the connected LLM to reason through the user's input and select among the connected tools to complete its task.
* The **Python REPL tool** component executes Python code in a REPL (Read-Evaluate-Print Loop) interpreter.
* The **Calculator** component performs basic arithmetic operations.
* The **Chat Input** component accepts user input to the chat.
* The **Prompt** component combines the user input with a user-defined prompt.
* The **Chat Output** component prints the flow's output to the chat.
* The **OpenAI** model component sends the user input and prompt to the OpenAI API and receives a response.

## Run the Math Agent flow

1. Add your credentials to the Open AI component.
2. Click **Playground** to start a chat session.
3. Enter a simple math problem, like `2 + 2`, and then make sure the bot responds with the correct answer.
4. To confirm the REPL interpreter is working, prompt the `math` library directly with `math.sqrt(4)` and see if the bot responds with `4`.
5. The agent will also reason through more complex word problems. For example, prompt the agent with the following math problem:

```plain
The equation 24x2+25x−47ax−2=−8x−3−53ax−2 is true for all values of x≠2a, where a is a constant.
What is the value of a?
A) -16
B) -3
C) 3
D) 16
```

The agent should respond with `B`.

Now that your query has completed the journey from **Chat input** to **Chat output**, you have completed the **Math Agent** flow.
