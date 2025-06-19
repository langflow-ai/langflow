---
title: API examples
slug: /api-reference-api-examples
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This page provides examples and practices for managing Langflow using the Langflow API.

The Langflow API's OpenAPI spec can be viewed and tested at your Langflow deployment's `docs` endpoint.
For example, `http://localhost:7860/docs`.

<!-- Add base endpoints to their appropriate pages and replace w links -->
<!-- Make page for metadata endpoints (/all, /version /config) -->
<!-- Add deprecated endpoints to their closest relevant page? -->
<!-- add /task to monitoring? Combine monitoring and logs? -->
<!-- Separate page for /run and /webhook or put them on the flows page? Update links to api-flows if needed -->
<!-- delete or repurpose "base" page, update sidebar.js if needed -->

## Export values

You might find it helpful to set the following environment variables in your terminal.

The examples in this guide use environment variables for these values.

- Export your Langflow URL in your terminal.
  Langflow starts by default at `http://localhost:7860`.

```bash
export LANGFLOW_URL="http://localhost:7860"
```

- Export the `flow-id` in your terminal.
  The `flow-id` is found in the [Publish pane](/concepts-publish) or in the flow's URL.

```text
export FLOW_ID="359cd752-07ea-46f2-9d3b-a4407ef618da"
```

- Export the `project-id` in your terminal.
To find your project ID, call the Langflow [/api/v1/projects/](#read-projects) endpoint for a list of projects.
<Tabs>

  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/projects/" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">
```json
[
  {
    "name": "My Projects",
    "description": "Manage your own projects. Download and upload projects.",
    "id": "1415de42-8f01-4f36-bf34-539f23e47466",
    "parent_id": null
  }
]
```
  </TabItem>
</Tabs>

- Export the `project-id` as an environment variable.
```bash
export project_ID="1415de42-8f01-4f36-bf34-539f23e47466"
```

- Export the Langflow API key as an environment variable.
  To create a Langflow API key, run the following command in the Langflow CLI.

<Tabs>
  <TabItem value="curl" label="curl" default>

```text
langflow api-key
```

  </TabItem>
  <TabItem value="result" label="Result">
```text
API Key Created Successfully:
sk-...
```
  </TabItem>
</Tabs>
Export the generated API key as an environment variable.
```text
export LANGFLOW_API_KEY="sk-..."
```

## Base

Use the base Langflow API to run your flow and retrieve configuration information.

### Get all components

This operation returns a dictionary of all Langflow components.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/all" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">
```text
A dictionary of all Langflow components.
```
  </TabItem>
</Tabs>

### Run flow

See [Flows endpoints](/api-flows)

Execute a specified flow by ID or name.
The flow is executed as a batch, but LLM responses can be streamed.

This example runs a [Basic Prompting](/starter-projects-basic-prompting) flow with a given `flow_id` and passes a JSON object as the input value.

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

#### Run endpoint headers and parameters

Parameters can be passed to the `/run` endpoint in three ways:

- URL path: `flow_id` as part of the endpoint path
- Query string: `stream` parameter in the URL
- Request body: JSON object containing the remaining parameters

**Headers**
| Header | Info | Example |
|--------|------|---------|
| Content-Type | Required. Specifies the JSON format. | "application/json" |
| accept | Required. Specifies the response format. | "application/json" |
| x-api-key | Optional. Required only if authentication is enabled. | "sk-..." |

**Parameters**
| Parameter | Type | Info |
|-----------|------|------|
| flow_id | UUID/string | Required. Part of URL: `/run/{flow_id}` |
| stream | boolean | Optional. Query parameter: `/run/{flow_id}?stream=true` |
| input_value | string | Optional. JSON body field. Main input text/prompt. Default: `null` |
| input_type | string | Optional. JSON body field. Input type ("chat" or "text"). Default: `"chat"` |
| output_type | string | Optional. JSON body field. Output type ("chat", "any", "debug"). Default: `"chat"` |
| output_component | string | Optional. JSON body field. Target component for output. Default: `""` |
| tweaks | object | Optional. JSON body field. Component adjustments. Default: `null` |
| session_id | string | Optional. JSON body field. Conversation context ID. Default: `null` |

**Example request**

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

### Webhook run flow

The webhook endpoint triggers flow execution with an HTTP POST request.

When a **Webhook** component is added to the workspace, a new **Webhook cURL** tab becomes available in the **API** pane that contains an HTTP POST request for triggering the webhook component, similar to the call in this example.

To test the **Webhook** component in your flow, see the [Webhook component](/components-data#webhook).

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/webhook/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{"data": "example-data"}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
{
  {"message":"Task started in the background","status":"in progress"}
}
```

  </TabItem>
</Tabs>

### Process

:::info
This endpoint is deprecated. Use the `/run` endpoint instead.
:::

### Predict

:::info
This endpoint is deprecated. Use the `/run` endpoint instead.
:::

### Get task status

Get the status of a task.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/task/TASK_ID" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
{
  "status": "Task status",
  "result": "Task result if completed"
}
```

  </TabItem>
</Tabs>

### Create upload file (Deprecated)

:::info
This endpoint is deprecated. Use the `/file` endpoint instead.
:::

### Get version

Get the version of the Langflow API.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/version" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
{
    "version": "1.1.1",
    "main_version": "1.1.1",
    "package": "Langflow"
}
```

  </TabItem>
</Tabs>

### Get config

Retrieve the Langflow configuration information.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/config" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "feature_flags": {
    "mvp_components": false
  },
  "frontend_timeout": 0,
  "auto_saving": true,
  "auto_saving_interval": 1000,
  "health_check_max_retries": 5,
  "max_file_size_upload": 100
}
```

  </TabItem>
</Tabs>