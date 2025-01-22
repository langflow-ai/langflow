---
title: Playground
slug: /concepts-playground
---

import Icon from "@site/src/components/icon";

The **Playground** is a dynamic interface designed for real-time interaction with LLMs, allowing users to chat, access memories, and monitor inputs and outputs. Here, users can directly prototype their models, making adjustments and observing different outcomes.

As long as you have an [Input or Output](/components-io) component working, you can open it by clicking the **Playground** button.
The Playground's window arrangement changes depending on what components are being used.

![](/img/playground.png)

## Run a flow in the playgound

When you run a flow in the **Playground**, Langflow calls the `/build/{flow_id}/flow` endpoint in [chat.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/api/v1/chat.py#L162). This call retrieves the flow data, builds a graph, and executes the graph. As each component (or node) is executed, the `build_vertex` function calls `build_and_run`, which may call the individual components' `def_build` method, if it exists. If a component doesn't have a `def_build` function, the build still returns a component.

The `build` function allows components to execute logic at runtime. For example, the [Recursive character text splitter](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/components/langchain_utilities/recursive_character.py) is a child of the `LCTextSplitterComponent` class. When text needs to be processed, the parent class's `build` method is called, which creates a `RecursiveCharacterTextSplitter` object and uses it to split the text according to the defined parameters. The split text is then passed on to the next component. This all occurs when the component is built.

## View playground messages by session ID

When you send a message from the **Playground** interface, the interactions are stored in the **Message Logs** by `session_id`.
A single flow can have multiple chats, and different flows can share the same chat. Each chat will have a different `session_id`.

To view messages by `session_id` within the Playground, click the <Icon name="Ellipsis" aria-label="Horizontal ellipsis" /> menu of any chat session, and then select **Message Logs**.

![](/img/messages-logs.png)

Individual messages in chat memory can be edited or deleted. Modifying these memories influences the behavior of the chatbot responses.

To learn more about chat memories in Langflow, see [Memory components](/components-memories).

## Use custom Session IDs for multiple user interactions

`session_id` values are used to track user interactions in a flow.
By default, if the `session_id` value is empty, it is set to the same value as the `flow_id`. In this case, every chat call uses the same `session_id`, and you effectively have one chat session.

The `session_id` value can be configured in the **Advanced Settings** of the **Chat Input** and **Chat Output** components.

To have more than one session in a single flow, pass a specific Session ID to a flow with the `session_id` parameter in the URL. All the components in the flow will automatically use this `session_id` value.

To post a message to a flow with a specific Session ID with curl, enter the following command:

```bash
   curl -X POST "http://127.0.0.1:7860/api/v1/run/$FLOW_ID" \
   -H 'Content-Type: application/json' \
   -d '{
       "session_id": "custom_session_123",
       "input_value": "message",
       "input_type": "chat",
       "output_type": "chat"
   }'
```

Check your flow's **Playground**. In addition to the messages stored for the Default Session, a new session is started with your custom Session ID.

