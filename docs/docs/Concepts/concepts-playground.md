---
title: Playground
slug: /concepts-playground
---

import ReactPlayer from "react-player";

The **Playground** is a dynamic interface designed for real-time interaction with AIs, allowing users to chat, access memories, and monitor inputs and outputs. Here, users can directly prototype and their models, making adjustments and observing different outcomes.

As long as you have an [Input or Output](/components-io) component working, you can open it by clicking the **Playground** button.

![](/img/playground.png)

:::tip

Notice how the **Playground's** window arrangement changes depending on what components are being used. Langflow can be used for applications that go beyond chat-based interfaces.

:::

## Run a flow in the playgound

When you run a flow in the **Playground**, Langflow calls the `/build/{flow_id}/flow` endpoint in [chat.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/api/v1/chat.py#L162). This call retrieves the flow data, builds a graph, and executes the graph. As each component (or node) is executed, the `build_vertex` function calls `build_and_run`, which may call the individual components' `def_build` method, if it exists. If a component doesn't have a `def_build` function, the build will still return a component.

The `build` function allows components to execute logic at runtime. For example, the [Recursive character text splitter](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/components/langchain_utilities/recursive_character.py) is a child of the `LCTextSplitterComponent` class. When text needs to be processed, the parent class's `build` method is called, which creates a `RecursiveCharacterTextSplitter` object and uses it to split the text according to the defined parameters. The split text is then passed on to the next component. This all occurs when the component is built.

## Memory Management

When you send a message from the **Playground** interface, the interactions for that session are stored in the **Message Logs**.

Langflow allows every chat message to be stored, and a single flow can have multiple chat sessions.

Chat conversations store messages categorized by a Session ID. A single flow can host multiple Session IDs, and different flows can share the same Session ID.

To view messages by session ID, from the Playground, click the Options menu of any session, and then select Message Logs.

Individual messages in chat memory can be edited or deleted. Modifying these memories will influence the behavior of the chatbot responses.

To learn more about chat memories in Langflow, see [Memory components](/components-memories).

## Use custom Session IDs for multiple user interactions

Session ID values are used to track user interactions in a flow. They can be configured in the Advanced Settings of the Chat Input and Chat Output components.

By default, if the Session ID value is empty, it is set to the same value as the Flow ID. This means every API call will use the same Session ID, and you’ll effectively have one session.

To have more than one session in a single flow, pass a specific Session ID to a flow with the `session_id` parameter in the URL. All the components in the flow will automatically use this `session_id` value.

Post a message to a flow with a specific Session ID with curl:

```bash
curl -X POST \
    "http://127.0.0.1:7860/api/v1/run/4017e9f2-1fec-4643-bb05-165a8b50c4b3?stream=false" \
    -H 'Content-Type: application/json' \
    -d '{"input_value": "message",
    "output_type": "chat",
    "input_type": "chat",
    "session_id": "YOUR_SESSION_ID"
}'
```

Check your flow's **Playground**. In addition to the messages stored for the Default Session, a new session is started with your new Session ID.

**Chat Input** and **Chat Output** components can also store a `session_id` parameter as a **Tweak** for specific sessions. The Playground will still display all available sessions, but the flow will use the value stored in the `session_id` tweak.

```bash
curl -X POST \
    "http://127.0.0.1:7860/api/v1/run/4017e9f2-1fec-4643-bb05-165a8b50c4b3?stream=false" \
    -H 'Content-Type: application/json' \
    -d '{"input_value": "message",
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": {
        "session_id": "YOUR_SESSION_ID"
    }
}'
```
