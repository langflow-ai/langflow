---
title: Basic prompting
slug: /basic-prompting
---

import Icon from "@site/src/components/icon";

Build a **Basic prompting** flow with [Language model](/components-models), [Prompt](/components-prompts), and [Chat I/O](/components-io) components.

Prompts serve as the inputs to a large language model (LLM), acting as the interface between human instructions and computational tasks.

By submitting natural language requests in a prompt to an LLM, you can obtain answers, generate text, and solve problems.

This article demonstrates how to use Langflow's prompt tools to issue basic prompts to an LLM, and how various prompting strategies can affect your outcomes.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the basic prompting flow

1. From the Langflow dashboard, click **New Flow**.

2. Select **Basic Prompting**.

The **Basic Prompting** flow is created.

![Basic prompting flow](/img/starter-flow-basic-prompting.png)

This flow allows you to chat with the **Language model** component.
The model responds according to the prompt **Template** constructed in the **Prompt** component.

4. To examine the **Template**, in the **Prompt** component, click the **Template** field.

```text
Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.
```

5. Add your **OpenAI API key** to the **Language model** component.

	Optionally, create a [global variable](/configuration-global-variables) for the **OpenAI API key**.

	1. In the **OpenAI API Key** field, click <Icon name="Globe" aria-hidden="True" /> **Globe**, and then click **Add New Variable**.
	2. In the **Variable Name** field, enter `openai_api_key`.
	3. In the **Value** field, paste your OpenAI API Key (`sk-...`).
	4. Click **Save Variable**.

## Run the basic prompting flow

1. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**.
2. Enter a message and press <kbd>Enter</kbd>.
The bot responds to your request according to the instructions defined in the **Prompt** component.

## Modify the prompt for a different result

1. To modify your prompt results, in the **Prompt** component, click the **Template** field. The **Edit Prompt** window opens.
2. Change the existing prompt to a different character, such as `Answer the user as if you were Hermione Granger.`
3. Run the flow again, and notice how the prompt changes the model's response.
