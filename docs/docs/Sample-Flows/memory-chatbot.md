---
title: Memory chatbot
slug: /memory-chatbot
---

import Icon from "@site/src/components/icon";

:::info
The **Chat memory** component is also known as the **Message history** component.
:::

This flow extends the [basic prompting flow](/starter-projects-basic-prompting) with a **Message history** component that stores up to 100 previous chat messages and uses them to provide context for the current conversation.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the memory chatbot flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Memory Chatbot**.
3. The **Memory Chatbot** flow is created.

![](/img/starter-flow-memory-chatbot.png)

This flow adds a **Message history** component to the Basic Prompting flow.
This component retrieves previous messages and sends them to the **Prompt** component to fill a part of the **Template** with context.

To examine the template, click the **Template** field in the **Prompt** component.
The **Prompt** tells the **OpenAI model** component how to respond to input.

```text
You are a helpful assistant that answers questions.

Use markdown to format your answer, properly embedding images and urls.

History:

{memory}
```

The `{memory}` code in the prompt creates a new input port in the component called **memory**.
The **Message history** component is connected to this port to store chat messages from the **Playground**, and provide the **OpenAI** component with a memory of previous chat messages.

## Run the memory chatbot flow

1. Open the **Playground**.
2. Enter multiple questions. For example, try entering this conversation:

```text
Hi, my name is Luca.
Please tell me about PostgreSQL.
What is my name?
What is the second subject I asked you about?
```

The chatbot remembers your name and previous questions.

3. To view the **Message Logs** pane, click <Icon name="Ellipsis" aria-label="Horizontal ellipsis" />, and then click **Message Logs**.
The **Message Logs** pane displays all previous messages, with each conversation sorted by `session_id`.

![](/img/messages-logs.png)

## Use Session ID with the memory chatbot flow

`session_id` is a unique identifier in Langflow that stores conversation sessions between the AI and a user. A `session_id` is created when a conversation is initiated, and then associated with all subsequent messages during that session.

In the **Memory Chatbot** flow you created, the **Message history** component references past interactions by **Session ID**. You can demonstrate this by modifying the **Session ID** value to switch between conversation histories.

1. In the **Session ID** field of the **Message history** and **Chat Input** components, add a **Session ID** value like `MySessionID`.
2. Now, once you send a new message the **Playground**, you should have a new memory created in the **Message Logs** pane.
3. Notice how your conversation is being stored in different memory sessions.

Learn more about chat memories in the [Memory](/components-memories) section.
