---
title: Playground
sidebar_position: 1
slug: /workspace-playground
---

import ReactPlayer from "react-player";

The **Playground** is a dynamic interface designed for real-time interaction with AIs, allowing users to chat, access memories and monitor inputs and outputs. Here, users can directly prototype and their models, making adjustments and observing different outcomes.


As long as you have an [Input or Output](/components-io) component working, you can open it up by clicking the **Playground** button.


![](./1109547993.png)


:::tip

Notice how the **Playground's** window arrangement changes depending on what components are being used. Langflow can be used for applications that go beyond chat-based interfaces.

:::




You can also open a flow's **Playground** without entering its workspace. From **My Collections** or **Langflow Store**, click the **Playground** in one of the projects card.


<ReactPlayer controls url="https://youtu.be/guaN0DOTxfo" />


## Memory Management {#821a5ee2a8a44d35b49943cba630511c}


---

Click the Memories tab to open a table of previous interactions for a specific flow.

Whenever you send a message from the **Playground** interface, under the **Memories** tab you'll see a table of previous interactions for that session.

Langflow allows every chat message to be stored, and a single flow can have multiple memory sessions.

Chat conversations store messages categorized by a Session ID. A single flow can host multiple Session IDs, and different flows can share the same Session ID.

Individual messages in chat memory can be edited or deleted. Modifying these memories will influence the behavior of the chatbot responses.

To learn more about memories in Langflow, see [Chat Memory](/guides-chat-memory).

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

Check your flow’s Memories tab. In addition to the messages stored for the Default Session, a new chat session is started with your new Session ID.

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

