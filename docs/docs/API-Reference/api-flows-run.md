---
title: Flow trigger endpoints
slug: /api-flows-run
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/run` amd `/webhook` endpoints to run flows.

To create, read, update, and delete flows, see [Flow management endpoints](/api-flows).

## Run flow

Execute a specified flow by ID or name.
The flow is executed as a batch, but LLM responses can be streamed.

This example runs a [Basic Prompting](/basic-prompting) flow with a given flow ID and passes a JSON object as the input value.
Flow IDs can be found on the [Publish pane](/concepts-publish) or in a flow's URL.

The parameters are passed in the request body. In this example, the values are the default values.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/run/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "input_value": "Tell me about something interesting!",
    "session_id": "chat-123",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "",
    "tweaks": null
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
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

  </TabItem>
</Tabs>

### Stream LLM token responses

To stream LLM token responses, append the `?stream=true` query parameter to the request. LLM chat responses are streamed back as `token` events until the `end` event closes the connection.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/run/$FLOW_ID?stream=true" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me something interesting!",
    "session_id": "chat-123"
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

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

  </TabItem>
</Tabs>

This result is abbreviated, but illustrates where the `end` event completes the LLM's token streaming response.

### Run endpoint headers

| Header | Info | Example |
|--------|------|---------|
| Content-Type | Required. Specifies the JSON format. | "application/json" |
| accept | Required. Specifies the response format. | "application/json" |
| x-api-key | Optional. Required only if authentication is enabled. | "sk-..." |

### Run endpoint parameters

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
  "http://$LANGFLOW_URL/api/v1/run/$FLOW_ID?stream=true" \
  -H "Content-Type: application/json" \
  -H "accept: application/json" \
  -H "x-api-key: sk-..." \
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
  "$LANGFLOW_URL/api/v1/webhook/$FLOW_ID" \
  -H "Content-Type: application/json" \
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