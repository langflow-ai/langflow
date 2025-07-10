---
title: Playground
slug: /concepts-playground
---

import Icon from "@site/src/components/icon";

The **Playground** is a dynamic interface designed for real-time interaction with LLMs, allowing users to chat, access memories, and monitor inputs and outputs. Here, users can directly prototype their models, making adjustments and observing different outcomes.

As long as you have a [Chat Input](/components-io) component in your flow, you can run and chat with your flow by clicking the **Playground** button.

## Run a flow in the playground

To run a flow in the **Playground**, click **Playground**.

For example, click **Playground** in a flow that includes connected **Chat Input**, **Language Model**, and **Chat Output** components to chat with the LLM.

![Playground window](/img/playground.png)

If you have an **Agent** in your flow, the **Playground** displays its tool calls and outputs, so you can monitor the agent's tool use and understand how it came to the answer it returns.
This agent used a connected `fetch_content` tool to perform a web search.

![Playground window with agent response](/img/playground-with-agent.png)

When you run a flow in the **Playground**, Langflow calls the `/build/{flow_id}/flow` endpoint in [chat.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/api/v1/chat.py#L143). This call retrieves the flow data, builds a graph, and executes the graph. As each component (or node) is executed, the `build_vertex` function calls `build_and_run`, which may call the individual components' `def_build` method, if it exists. If a component doesn't have a `def_build` function, the build still returns a component.

The `build` function allows components to execute logic at runtime. For example, the [Recursive character text splitter](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/components/langchain_utilities/recursive_character.py) is a child of the `LCTextSplitterComponent` class. When text needs to be processed, the parent class's `build` method is called, which creates a `RecursiveCharacterTextSplitter` object and uses it to split the text according to the defined parameters. The split text is then passed on to the next component. This all occurs when the component is built.

## View playground messages by session ID

When you send a message from the **Playground** interface, the interactions are stored in the **Message Logs** by `session_id`.
A single flow can have multiple chats, and different flows can share the same chat. Each chat session has a different `session_id`.

To view messages by `session_id` within the Playground, click the <Icon name="Ellipsis" aria-hidden="true"/> **Options** menu of any chat session, and then select **Message Logs**.

![Playground logs](/img/messages-logs.png)

Individual messages in chat memory can be edited or deleted. Modifying these memories influences the behavior of the chatbot responses.

To learn more about managing sessions in Langflow, see [Session ID](/session-id).

To learn more about how chat memory is stored in Langflow, see [Memory components](/memory).

## Use custom session IDs for multiple user interactions

`session_id` values are used to track user interactions in a flow.
By default, if the `session_id` value is empty, it is set to the same value as the `flow_id`. In this case, every chat call uses the same `session_id`, and you effectively have one chat session.

The `session_id` value can be configured in the **Controls** of the **Chat Input** and **Chat Output** components.

To have more than one session in a single flow, pass a specific session ID to a flow with the `session_id` parameter in the URL. All the components in the flow will automatically use this `session_id` value.


To post a message to a flow with a specific Session ID with curl, enter the following command.
Replace `LANGFLOW_SERVER_ADDRESS`, `FLOW_ID`, and `LANGFLOW_API_KEY` with the values from your Langflow deployment.

```bash
   curl -X POST "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID" \
   -H "Content-Type: application/json" \
   -H "x-api-key: LANGFLOW_API_KEY" \
   -d '{
       "session_id": "CUSTOM_SESSION_VALUE",
       "input_value": "message",
       "input_type": "chat",
       "output_type": "chat"
   }'
```

Check your flow's **Playground**. In addition to the messages stored for the default session, a new session is started with your custom session ID.

## Work with images in the Playground

The Playground supports handling images in base64 format, allowing you to work with image data directly in your flows.

The Playground accepts the following image formats:

* PNG
* JPG/JPEG
* GIF
* BMP
* WebP

You can work with base64 images in the Playground in several ways:

* **Direct Upload**: Use the image upload button in the chat interface to upload images directly.
* **Drag and Drop**: Drag and drop image files into the chat interface.
* **Programmatic Input**: Send base64-encoded images through the API.

This example sends a base64-encoded image to the Playground using curl:
Replace `LANGFLOW_SERVER_ADDRESS`, `FLOW_ID`, and `LANGFLOW_API_KEY` with the values from your Langflow deployment.
```bash
curl -X POST "http://localhost:7860/api/v1/run/FLOW_ID" \
-H "Content-Type: application/json" \
-H "x-api-key: LANGFLOW_API_KEY" \
-d '{
    "session_id": "custom_session_123",
    "input_value": "What is in this image?",
    "input_type": "chat",
    "output_type": "chat",
    "files": ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."]
}'
```

The image is displayed in the chat interface and can be processed by your flow components.