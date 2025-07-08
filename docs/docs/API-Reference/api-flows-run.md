---
title: Flow trigger endpoints
slug: /api-flows-run
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/run` and `/webhook` endpoints to run flows.

To create, read, update, and delete flows, see [Flow management endpoints](/api-flows).

## Run flow

Execute a specified flow by ID or name.
Flow IDs can be found on the code snippets on the [**API access** pane](/concepts-publish#api-access) or in a flow's URL.

The following example runs a [Basic Prompting](/basic-prompting) flow with flow parameters passed in the request body.
This flow requires a chat input string (`input_value`), and uses default values for all other parameters.

```bash
curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "input_value": "Tell me about something interesting!",
    "session_id": "chat-123",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "",
    "tweaks": null
  }'
```

The response from `/v1/run/$FLOW_ID` includes metadata, inputs, and outputs for the run.

<details>
  <summary>Result</summary>

The following example illustrates a response from a Basic Prompting flow:

```json
{
  "session_id": "chat-123",
  "outputs": [{
    "inputs": {
      "input_value": "Tell me about something interesting!"
    },
    "outputs": [{
      "results": {
        "message": {
          "text": "Sure! Have you ever heard of the phenomenon known as \"bioluminescence\"? It's a fascinating natural occurrence where living organisms produce and emit light. This ability is found in various species, including certain types of jellyfish, fireflies, and deep-sea creatures like anglerfish.\n\nBioluminescence occurs through a chemical reaction in which a light-emitting molecule called luciferin reacts with oxygen, catalyzed by an enzyme called luciferase. The result is a beautiful glow that can serve various purposes, such as attracting mates, deterring predators, or luring prey.\n\nOne of the most stunning displays of bioluminescence can be seen in the ocean, where certain plankton emit light when disturbed, creating a mesmerizing blue glow in the water. This phenomenon is often referred to as \"sea sparkle\" and can be seen in coastal areas around the world.\n\nBioluminescence not only captivates our imagination but also has practical applications in science and medicine, including the development of biosensors and imaging techniques. It's a remarkable example of nature's creativity and complexity!",
          "sender": "Machine",
          "sender_name": "AI",
          "session_id": "chat-123",
          "timestamp": "2025-03-03T17:17:37+00:00",
          "flow_id": "d2bbd92b-187e-4c84-b2d4-5df365704201",
          "properties": {
            "source": {
              "id": "OpenAIModel-d1wOZ",
              "display_name": "OpenAI",
              "source": "gpt-4o-mini"
            },
            "icon": "OpenAI"
          },
          "component_id": "ChatOutput-ylMzN"
        }
      }
    }]
  }]
}
```
</details>

If you are parsing the response in an application, you most likely need to extract the relevant content from the response, rather than pass the entire response back to the user.
For an example of a script that extracts data from a Langflow API response, see the [Quickstart](/get-started-quickstart).

### Stream LLM token responses

With `/v1/run/$FLOW_ID`, the flow is executed as a batch with optional LLM token response streaming.

To stream LLM token responses, append the `?stream=true` query parameter to the request:

```bash
curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID?stream=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "message": "Tell me something interesting!",
    "session_id": "chat-123"
  }'
```

LLM chat responses are streamed back as `token` events, culminating in a final `end` event that closes the connection.

<details>
  <summary>Result</summary>

The following example is truncated to illustrate a series of `token` events as well as the final `end` event that closes the LLM's token streaming response:

```text
{"event": "add_message", "data": {"timestamp": "2025-03-03T17:20:18", "sender": "User", "sender_name": "User", "session_id": "chat-123", "text": "Tell me about something interesting!", "files": [], "error": false, "edit": false, "properties": {"text_color": "", "background_color": "", "edited": false, "source": {"id": null, "display_name": null, "source": null}, "icon": "", "allow_markdown": false, "positive_feedback": null, "state": "complete", "targets": []}, "category": "message", "content_blocks": [], "id": "0103a21b-ebf7-4c02-9d72-017fb297f812", "flow_id": "d2bbd92b-187e-4c84-b2d4-5df365704201"}}

{"event": "add_message", "data": {"timestamp": "2025-03-03T17:20:18", "sender": "Machine", "sender_name": "AI", "session_id": "chat-123", "text": "", "files": [], "error": false, "edit": false, "properties": {"text_color": "", "background_color": "", "edited": false, "source": {"id": "OpenAIModel-d1wOZ", "display_name": "OpenAI", "source": "gpt-4o-mini"}, "icon": "OpenAI", "allow_markdown": false, "positive_feedback": null, "state": "complete", "targets": []}, "category": "message", "content_blocks": [], "id": "27b66789-e673-4c65-9e81-021752925161", "flow_id": "d2bbd92b-187e-4c84-b2d4-5df365704201"}}

{"event": "token", "data": {"chunk": " Have", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "token", "data": {"chunk": " you", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "token", "data": {"chunk": " ever", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "token", "data": {"chunk": " heard", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "token", "data": {"chunk": " of", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "token", "data": {"chunk": " the", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "token", "data": {"chunk": " phenomenon", "id": "27b66789-e673-4c65-9e81-021752925161", "timestamp": "2025-03-03 17:20:18 UTC"}}

{"event": "end", "data": {"result": {"session_id": "chat-123", "message": "Sure! Have you ever heard of the phenomenon known as \"bioluminescence\"?..."}}}
```
</details>

### Run endpoint headers

| Header | Info | Example |
|--------|------|---------|
| Content-Type | Required. Specifies the JSON format. | "application/json" |
| accept | Optional. Specifies the response format. | "application/json" |
| x-api-key | Optional. Required only if authentication is enabled. | "sk-..." |

### Run endpoint parameters

<!-- TODO: Can there be other parameters depending on the components in the flow? -->

| Parameter | Type | Info |
|-----------|------|------|
| flow_id | UUID/string | Required. Part of URL: `/run/$FLOW_ID` |
| stream | boolean | Optional. Query parameter: `/run/$FLOW_ID?stream=true` |
| input_value | string | Optional. JSON body field. Main input text/prompt. Default: `null` |
| input_type | string | Optional. JSON body field. Input type ("chat" or "text"). Default: `"chat"` |
| output_type | string | Optional. JSON body field. Output type ("chat", "any", "debug"). Default: `"chat"` |
| output_component | string | Optional. JSON body field. Target component for output. Default: `""` |
| tweaks | object | Optional. JSON body field. Component adjustments. Default: `null` |
| session_id | string | Optional. JSON body field. Conversation context ID. See [Session ID](/session-id). Default: `null` |

### Request example with all headers and parameters

```bash
curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID?stream=true" \
  -H "Content-Type: application/json" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "input_value": "Tell me a story",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "chat_output",
    "session_id": "chat-123",
    "tweaks": {
      "component_id": {
        "parameter_name": "value"
      }
    }
  }'
```

## Webhook run flow

Use the `/webhook` endpoint to start a flow by sending an HTTP `POST` request.

:::tip
After you add a **Webhook** component to a flow, open the [**API access** pane](/concepts-publish), and then click the **Webhook cURL** tab to get an automatically generated `POST /webhook` request for your flow.
:::

```bash
curl -X POST \
  "$LANGFLOW_SERVER_URL/api/v1/webhook/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"data": "example-data"}'
```

<details>
<summary>Result</summary>
```json
{
  "message": "Task started in the background",
  "status": "in progress"
}
```
</details>

For more information, see [Webhook component](/components-data#webhook) and [Trigger flows with webhooks](/webhook).

## Deprecated flow trigger endpoints

The following endpoints are deprecated and replaced by the `/run` endpoint:

* `/process`
* `/predict`