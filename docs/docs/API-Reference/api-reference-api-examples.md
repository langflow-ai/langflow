---
title: API examples
slug: /api-reference-api-examples
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

This page provides examples and practices for managing Langflow using the Langflow API.

The Langflow API's OpenAPI spec can be viewed and tested at your Langflow deployment's `docs` endpoint.
For example, `http://localhost:7860/docs`.

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

## Build

Use the `/build` endpoint to build vertices and flows, and execute those flows with streaming event responses.

The `/build` endpoint offers additional configuration for running flows.

For a simpler execution of your flows, use the [`/run` endpoint](/api-reference-api-examples#run-flow) instead.

### Build flow

:::important
This endpoint is meant to be used by the frontend and is not optimized for external use.
To run your flow, use the [`/run` endpoint](/api-reference-api-examples#run-flow) instead.
:::

This endpoint builds and executes a flow, returning a job ID that can be used to stream execution events.

1. Send a POST request to the `/build/{flow_id}/flow` endpoint.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "input_value": "Tell me a story"
    }
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

  </TabItem>
</Tabs>

2. After receiving a job ID from the build endpoint, use the `/build/{job_id}/events` endpoint to stream the execution results:

<Tabs>
   <TabItem value="curl" label="curl" default>

```text
curl -X GET \
  "$LANGFLOW_URL/api/v1/build/123e4567-e89b-12d3-a456-426614174000/events" \
  -H "accept: application/json"
```

   </TabItem>
   <TabItem value="result" label="Result">

```json
{"event": "vertices_sorted", "data": {"ids": ["ChatInput-XtBLx"], "to_run": ["Prompt-x74Ze", "ChatOutput-ylMzN", "ChatInput-XtBLx", "OpenAIModel-d1wOZ"]}}

{"event": "add_message", "data": {"timestamp": "2025-03-03T17:42:23", "sender": "User", "sender_name": "User", "session_id": "d2bbd92b-187e-4c84-b2d4-5df365704201", "text": "Tell me a story", "files": [], "error": false, "edit": false, "properties": {"text_color": "", "background_color": "", "edited": false, "source": {"id": null, "display_name": null, "source": null}, "icon": "", "allow_markdown": false, "positive_feedback": null, "state": "complete", "targets": []}, "category": "message", "content_blocks": [], "id": "28879bd8-6a68-4dd5-b658-74d643a4dd92", "flow_id": "d2bbd92b-187e-4c84-b2d4-5df365704201"}}

// ... Additional events as the flow executes ...

{"event": "end", "data": {}}
```

   </TabItem>
</Tabs>

The events endpoint accepts an optional `stream` query parameter which defaults to `true`.
To disable streaming and get all events at once, set `stream` to `false`.

```text
curl -X GET \
  "$LANGFLOW_URL/api/v1/build/123e4567-e89b-12d3-a456-426614174000/events?stream=false" \
  -H "accept: application/json"
```

### Build endpoint headers and parameters

**Headers**
| Header | Info | Example |
|--------|------|---------|
| Content-Type | Required. Specifies the JSON format. | "application/json" |
| accept | Required. Specifies the response format. | "application/json" |
| x-api-key | Optional. Required only if authentication is enabled. | "sk-..." |

The `/build/{flow_id}/flow` endpoint accepts the following parameters in its request body:

**Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| inputs | object | Optional. Input values for flow components. |
| data | object | Optional. Flow data to override stored configuration. |
| files | array[string] | Optional. List of file paths to use. |
| stop_component_id | string | Optional. ID of the component where the execution should stop. |
| start_component_id | string | Optional. ID of the component where the execution should start. |
| log_builds | boolean | Optional. Control build logging. Default: `true`. |

### Configure the build endpoint

The `/build` endpoint accepts optional values for `start_component_id` and `stop_component_id` to control where the flow run starts and stops.
Setting `stop_component_id` for a component triggers the same behavior as clicking <Icon name="Play" aria-hidden="True" /> **Run component** on that component, where all dependent components leading up to that component are also run.
For example, to stop flow execution at the Open AI model component, run the following command:

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"stop_component_id": "OpenAIModel-Uksag"}'
```

The `/build` endpoint also accepts inputs for `data` directly, instead of using the values stored in the Langflow database.
This is useful for running flows without having to pass custom values through the UI.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "nodes": [],
      "edges": []
    },
    "inputs": {
      "input_value": "Your custom input here",
      "session": "session_id"
    }
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{ "job_id": "0bcc7f23-40b4-4bfa-9b8a-a44181fd1175" }
```

  </TabItem>
</Tabs>

## Files

Use the `/files` endpoint to add or delete files between your local machine and Langflow.

There are `/v1` and `/v2` versions of the `/files` endpoints.
The `v2/files` version offers several improvements over `/v1`:

- In `v1`, files are organized by `flow_id`. In `v2`, files are organized by `user_id`.
  This means files are accessed based on user ownership, and not tied to specific flows.
  You can upload a file to Langflow one time, and use it with multiple flows.
- In `v2`, files are tracked in the Langflow database, and can be added or deleted in bulk, instead of one by one.
- Responses from the `/v2` endpoint contain more descriptive metadata.
- The `v2` endpoints require authentication by an API key or JWT.
- The `/v2/files` endpoint does not support sending **image** files to flows through the API. To send **image** files to your flows through the API, follow the procedure in [Upload image files (v1)](#upload-image-files-v1).

## Files/V1 endpoints

Use the `/files` endpoint to add or delete files between your local machine and Langflow.

- In `v1`, files are organized by `flow_id`.
- In `v2`, files are organized by `user_id` and tracked in the Langflow database, and can be added or deleted in bulk, instead of one by one.

### Upload file (v1)

Upload a file to the `v1/files/upload/<YOUR-FLOW-ID>` endpoint of your flow.
Replace **FILE_NAME** with the uploaded file name.

<Tabs>

  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/files/upload/$FLOW_ID" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@FILE_NAME.txt"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "flowId": "92f9a4c5-cfc8-4656-ae63-1f0881163c28",
  "file_path": "92f9a4c5-cfc8-4656-ae63-1f0881163c28/2024-12-30_15-19-43_your_file.txt"
}
```

  </TabItem>
</Tabs>

### Upload image files (v1)

Send image files to the Langflow API for AI analysis.

The default file limit is 100 MB. To configure this value, change the `LANGFLOW_MAX_FILE_SIZE_UPLOAD` environment variable.
For more information, see [Supported environment variables](/environment-variables#supported-variables).

1. To send an image to your flow with the API, POST the image file to the `v1/files/upload/<YOUR-FLOW-ID>` endpoint of your flow.
   Replace **FILE_NAME** with the uploaded file name.

```bash
curl -X POST "$LANGFLOW_URL/api/v1/files/upload/a430cc57-06bb-4c11-be39-d3d4de68d2c4" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@FILE_NAME.png"
```

The API returns the image file path in the format `"file_path":"<YOUR-FLOW-ID>/<TIMESTAMP>_<FILE-NAME>"}`.

```json
{
  "flowId": "a430cc57-06bb-4c11-be39-d3d4de68d2c4",
  "file_path": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png"
}
```

2. Post the image file to the **Chat Input** component of a **Basic prompting** flow.
   Pass the file path value as an input in the **Tweaks** section of the curl call to Langflow.
   To find your Chat input component's ID, use the [](#)

```bash
curl -X POST \
    "$LANGFLOW_URL/api/v1/run/a430cc57-06bb-4c11-be39-d3d4de68d2c4?stream=false" \
    -H 'Content-Type: application/json'\
    -d '{
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": {
  "ChatInput-b67sL": {
    "files": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png",
    "input_value": "what do you see?"
  }
}}'
```

Your chatbot describes the image file you sent.

```text
"text": "This flowchart appears to represent a complex system for processing financial inquiries using various AI agents and tools. Here's a breakdown of its components and how they might work together..."
```

### List files (v1)

List all files associated with a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/files/list/$FLOW_ID" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "files": ["2024-12-30_15-19-43_your_file.txt"]
}
```

  </TabItem>
</Tabs>

### Download file (v1)

Download a specific file from a flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/files/download/$FLOW_ID/2024-12-30_15-19-43_your_file.txt" \
  -H "accept: application/json" \
  --output downloaded_file.txt
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
File contents downloaded to downloaded_file.txt
```

  </TabItem>
</Tabs>

### Delete file (v1)

Delete a specific file from a flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/files/delete/$FLOW_ID/2024-12-30_15-19-43_your_file.txt" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "message": "File 2024-12-30_15-19-43_your_file.txt deleted successfully"
}
```

  </TabItem>
</Tabs>

## Files/V2 endpoints

In `v2`, files are organized by `user_id` and tracked in the Langflow database, and can be added or deleted in bulk, instead of one by one.
The `v2` endpoints require authentication by an API key or JWT.
To create a Langflow API key and export it as an environment variable, see [Export values](#export-values).

### Upload file (v2)

Upload a file to your user account. The file can be used across multiple flows.

The file is uploaded in the format `USER_ID/FILE_ID.FILE_EXTENSION`, such as `07e5b864-e367-4f52-b647-a48035ae7e5e/d44dc2e1-9ae9-4cf6-9114-8d34a6126c94.pdf`.

To retrieve your current `user_id`, call the `/whoami` endpoint.
```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/users/whoami" \
  -H "accept: application/json"
```

Result:
```
{"id":"07e5b864-e367-4f52-b647-a48035ae7e5e","username":"langflow","profile_image":null,"store_api_key":null,"is_active":true,"is_superuser":true,"create_at":"2025-05-08T17:59:07.855965","updated_at":"2025-05-28T19:00:42.556460","last_login_at":"2025-05-28T19:00:42.554338","optins":{"github_starred":false,"dialog_dismissed":true,"discord_clicked":false,"mcp_dialog_dismissed":true}}
```

In the POST request to `v2/files`, replace **@FILE_NAME.EXTENSION** with the uploaded file name and its extension.
You must include the ampersand (`@`) in the request to instruct curl to upload the contents of the file, not the string `FILE_NAME.EXTENSION`.

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@FILE_NAME.EXTENSION"
```

The file is uploaded in the format `USER_ID/FILE_ID.FILE_EXTENSION`, and the API returns metadata about the uploaded file:

```json
{
  "id":"d44dc2e1-9ae9-4cf6-9114-8d34a6126c94",
  "name":"engine_manual",
  "path":"07e5b864-e367-4f52-b647-a48035ae7e5e/d44dc2e1-9ae9-4cf6-9114-8d34a6126c94.pdf",
  "size":851160,
  "provider":null
}
```

### Send files to your flows (v2)

:::important
The `/v2/files` endpoint does not support sending **image** files to flows.
To send **image** files to your flows through the API, follow the procedure in [Upload image files (v1)](#upload-image-files-v1).
:::

Send a file to your flow for analysis using the [File](/components-data#file) component and the API.
Your flow must contain a [File](/components-data#file) component to receive the file.

The default file limit is 100 MB. To configure this value, change the `LANGFLOW_MAX_FILE_SIZE_UPLOAD` environment variable.
For more information, see [Supported environment variables](/environment-variables#supported-variables).

1. To send a file to your flow with the API, POST the file to the `/api/v2/files` endpoint.
   Replace **FILE_NAME** with the uploaded file name.
   This is the same step described in [Upload file (v2)](#upload-file-v2), but since you need the filename to upload to your flow, it is included here.

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@FILE_NAME.EXTENSION"
```

The file is uploaded in the format `USER_ID/FILE_ID.FILE_EXTENSION`, and the API returns metadata about the uploaded file:

```json
{
  "id":"d44dc2e1-9ae9-4cf6-9114-8d34a6126c94",
  "name":"engine_manual",
  "path":"07e5b864-e367-4f52-b647-a48035ae7e5e/d44dc2e1-9ae9-4cf6-9114-8d34a6126c94.pdf",
  "size":851160,
  "provider": null
}
```

2. To use this file in your flow, add a [File](/components-data#file) component to load a file into the flow.
3. To load the file into your flow, send it to the **File** component.
To retrieve the **File** component's full name with the UUID attached, call the [Read flow](#read-flow) endpoint, and then include your **File** component and the file path as a tweak with the `/v1/run` POST request.
In this example, the file uploaded to `/v2/files` is included with the `/v1/run` POST request.

```text
curl --request POST \
  --url "$LANGFLOW_URL/api/v1/run/$FLOW_ID" \
  --header "Content-Type: application/json" \
  --data '{
  "input_value": "what do you see?",
  "output_type": "chat",
  "input_type": "text",
  "tweaks": {
    "File-1olS3": {
      "path": [
        "07e5b864-e367-4f52-b647-a48035ae7e5e/3a290013-fe1e-4d3d-a454-cacae81288f3.pdf"
      ]
    }
  }
}'
```

Result:
```text
"text":"This document provides important safety information and instructions for selecting, installing, and operating Briggs & Stratton engines. It includes warnings and guidelines to prevent injury, fire, or damage, such as choosing the correct engine model, proper installation procedures, safe fuel handling, and correct engine operation. The document emphasizes following all safety precautions and using authorized parts to ensure safe and effective engine use."
```

### List files (v2)

List all files associated with your user account.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "id": "c7b22c4c-d5e0-4ec9-af97-5d85b7657a34",
    "name": "your_file",
    "path": "6f17a73e-97d7-4519-a8d9-8e4c0be411bb/c7b22c4c-d5e0-4ec9-af97-5d85b7657a34.txt",
    "size": 1234,
    "provider": null
  }
]
```

  </TabItem>
</Tabs>

### Download file (v2)

Download a specific file by its ID and file extension.

:::tip
You must specify the file type you expect in the `--output` value.
:::

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v2/files/c7b22c4c-d5e0-4ec9-af97-5d85b7657a34" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  --output downloaded_file.txt
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
File contents downloaded to downloaded_file.txt
```

  </TabItem>
</Tabs>

### Edit file name (v2)

Change a file name.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PUT \
  "$LANGFLOW_URL/api/v2/files/$FILE_ID?name=new_file_name" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "id": "76543e40-f388-4cb3-b0ee-a1e870aca3d3",
  "name": "new_file_name",
  "path": "6f17a73e-97d7-4519-a8d9-8e4c0be411bb/76543e40-f388-4cb3-b0ee-a1e870aca3d3.png",
  "size": 2728251,
  "provider": null
}
```

  </TabItem>
</Tabs>
### Delete file (v2)

Delete a specific file by its ID.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v2/files/$FILE_ID" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "message": "File deleted successfully"
}
```

  </TabItem>
</Tabs>

### Delete all files (v2)

Delete all files associated with your user account.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "message": "All files deleted successfully"
}
```

  </TabItem>
</Tabs>

## Flows

Use the `/flows` endpoint to create, read, update, and delete flows.

### Create flow

Create a new flow.

<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "string2",
  "description": "string",
  "icon": "string",
  "icon_bg_color": "#FF0000",
  "gradient": "string",
  "data": {},
  "is_component": false,
  "updated_at": "2024-12-30T15:48:01.519Z",
  "webhook": false,
  "endpoint_name": "string",
  "tags": [
    "string"
  ]
}'
```

   </TabItem>
   <TabItem value="result" label="Result">

```json
{
  "name": "string2",
  "description": "string",
  "icon": "string",
  "icon_bg_color": "#FF0000",
  "gradient": "string",
  "data": {},
  "is_component": false,
  "updated_at": "2025-02-04T21:07:36+00:00",
  "webhook": false,
  "endpoint_name": "string",
  "tags": ["string"],
  "locked": false,
  "id": "e8d81c37-714b-49ae-ba82-e61141f020ee",
  "user_id": "f58396d4-a387-4bb8-b749-f40825c3d9f3",
  "project_id": "1415de42-8f01-4f36-bf34-539f23e47466"
}
```

   </TabItem>
</Tabs>

### Read flows

Retrieve a list of flows with pagination support.

<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/?remove_example_flows=false&components_only=false&get_all=true&header_flows=false&page=1&size=50" \
  -H "accept: application/json"
```

   </TabItem>

<TabItem value="result" label="Result">

```text
A JSON object containing a list of flows.
```

   </TabItem>
</Tabs>

To retrieve only the flows from a specific project, pass `project_id` in the query string.

<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/?remove_example_flows=true&components_only=false&get_all=false&project_id=$PROJECT_ID&header_flows=false&page=1&size=1" \
  -H "accept: application/json"
```

   </TabItem>

<TabItem value="result" label="Result">

```text
A JSON object containing a list of flows.
```

   </TabItem>
</Tabs>

### Read flow

Read a specific flow by its ID.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/$FLOW_ID" \
  -H "accept: application/json"
```

  </TabItem>

  <TabItem value="result" label="Result">

```json
{
  "name": "Basic Prompting",
  "description": "Perform basic prompting with an OpenAI model.",
  "icon": "Braces",
  "icon_bg_color": null,
  "gradient": "2",
  "data": {
    "nodes": [
     ...
    ]
  }
}
```

  </TabItem>
</Tabs>

### Update flow

Update an existing flow by its ID.

This example changes the value for `endpoint_name` from a random UUID to `my_new_endpoint_name`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PATCH \
  "$LANGFLOW_URL/api/v1/flows/$FLOW_ID" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "string",
  "description": "string",
  "data": {},
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "endpoint_name": "my_new_endpoint_name",
  "locked": true
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "name": "string",
  "description": "string",
  "icon": "Braces",
  "icon_bg_color": null,
  "gradient": "2",
  "data": {},
  "is_component": false,
  "updated_at": "2024-12-30T18:30:22+00:00",
  "webhook": false,
  "endpoint_name": "my_new_endpoint_name",
  "tags": null,
  "locked": true,
  "id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
  "user_id": "f58396d4-a387-4bb8-b749-f40825c3d9f3",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

  </TabItem>
</Tabs>

### Delete flow

Delete a specific flow by its ID.

<Tabs>
    <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/flows/$FLOW_ID" \
  -H "accept: application/json"
```

</TabItem>

<TabItem value="result" label="Result">

```json
{
  "message": "Flow deleted successfully"
}
```

   </TabItem>
</Tabs>

### Create flows

Create multiple new flows.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/batch/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "flows": [
    {
      "name": "string",
      "description": "string",
      "icon": "string",
      "icon_bg_color": "string",
      "gradient": "string",
      "data": {},
      "is_component": false,
      "updated_at": "2024-12-30T18:36:02.737Z",
      "webhook": false,
      "endpoint_name": "string",
      "tags": [
        "string"
      ],
      "locked": false,
      "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    },
    {
      "name": "string",
      "description": "string",
      "icon": "string",
      "icon_bg_color": "string",
      "gradient": "string",
      "data": {},
      "is_component": false,
      "updated_at": "2024-12-30T18:36:02.737Z",
      "webhook": false,
      "endpoint_name": "string",
      "tags": [
        "string"
      ],
      "locked": false,
      "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
      "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
  ]
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    // FlowRead objects
  }
]
```

  </TabItem>
</Tabs>

### Upload flows

Upload flows from a file.

This example uploads a local file named `agent-with-astra-db-tool.json`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/upload/?project_id=$PROJECT_ID" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@agent-with-astra-db-tool.json;type=application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "name": "agent-with-astra-db-tool",
    "description": "",
    "icon": null,
    "icon_bg_color": null,
    "gradient": null,
    "data": {}
  ...
  }
]
```

  </TabItem>
</Tabs>

To specify a target project for the flow, include the query parameter `project_id`.
The target `project_id` must already exist before uploading a flow. Call the [/api/v1/projects/](#read-projects) endpoint for a list of available projects.
To specify a target project for the flow, include the query parameter `project_id`.
The target `project_id` must already exist before uploading a flow. Call the [/api/v1/projects/](#read-projects) endpoint for a list of available projects.

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/upload/?project_id=$PROJECT_ID" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@agent-with-astra-db-tool.json;type=application/json"
```

### Download all flows

Download all flows as a ZIP file.

This endpoint downloads a ZIP file containing flows for all `flow-id` values listed in the command's body.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/flows/download/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '[
  "e1e40c77-0541-41a9-88ab-ddb3419398b5",
  "92f9a4c5-cfc8-4656-ae63-1f0881163c28"
]' \
  --output langflow-flows.zip
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100 76437    0 76353  100    84  4516k   5088 --:--:-- --:--:-- --:--:-- 4665k
```

  </TabItem>
</Tabs>

### Read basic examples

Retrieve a list of basic example flows.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/basic_examples/" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
A list of example flows.
```

  </TabItem>
</Tabs>

## Projects

Use the `/projects` endpoint to create, read, update, and delete projects.

Projects store your flows and components.

### Read projects

Get a list of Langflow projects.

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

### Create project

Create a new project.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/projects/" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "new_project_name",
  "description": "string",
  "components_list": [],
  "flows_list": []
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "name": "new_project_name",
  "description": "string",
  "id": "b408ddb9-6266-4431-9be8-e04a62758331",
  "parent_id": null
}
```

  </TabItem>
</Tabs>

To add flows and components at project creation, retrieve the `components_list` and `flows_list` values from the [/api/v1/store/components](#get-all-components) and [/api/v1/flows/read](#read-flows) endpoints and add them to the request body.

Adding a flow to a project moves the flow from its previous location. The flow is not copied.

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/projects/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "new_project_name",
  "description": "string",
  "components_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}'
```

### Read project

Retrieve details of a specific project.

To find the UUID of your project, call the [read projects](#read-projects) endpoint.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/projects/$PROJECT_ID" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "name": "My Projects",
    "description": "Manage your own projects. Download and upload projects.",
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "parent_id": null
  }
]
```

  </TabItem>
</Tabs>

### Update project

Update the information of a specific project with a `PATCH` request.

Each PATCH request updates the project with the values you send.
Only the fields you include in your request are updated.
If you send the same values multiple times, the update is still processed, even if the values are unchanged.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PATCH \
  "$LANGFLOW_URL/api/v1/projects/b408ddb9-6266-4431-9be8-e04a62758331" \
  -H "accept: application/json" \
  -d '{
  "name": "string",
  "description": "string",
  "parent_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "components": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "name": "string",
  "description": "string",
  "id": "b408ddb9-6266-4431-9be8-e04a62758331",
  "parent_id": null
}
```

  </TabItem>
</Tabs>

### Delete project

Delete a specific project.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/projects/$PROJECT_ID" \
  -H "accept: */*"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
204 No Content
```

  </TabItem>
</Tabs>

### Download project

Download all flows from a project as a zip file.

The `--output` flag is optional.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/projects/download/b408ddb9-6266-4431-9be8-e04a62758331" \
  -H "accept: application/json" \
  --output langflow-project.zip
```

  </TabItem>
    <TabItem value="result" label="Result">

```text
The project contents.
```

  </TabItem>
</Tabs>

### Upload project

Upload a project to Langflow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/projects/upload/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@20241230_135006_langflow_flows.zip;type=application/zip"
```

  </TabItem>

  <TabItem value="result" label="Result">

```text
The project contents are uploaded to Langflow.
```

  </TabItem>
</Tabs>

## Logs

Retrieve logs for your Langflow flow.

This endpoint requires log retrieval to be enabled in your Langflow application.

To enable log retrieval, include these values in your `.env` file:

```text
LANGFLOW_ENABLE_LOG_RETRIEVAL=true
LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE=10000
LANGFLOW_LOG_LEVEL=DEBUG
```

For log retrieval to function, `LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE` needs to be greater than 0. The default value is `10000`.

Start Langflow with this `.env`:

```text
uv run langflow run --env-file .env
```

### Stream logs

Stream logs in real-time using Server-Sent Events (SSE).

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/logs-stream" \
  -H "accept: text/event-stream"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
keepalive

{"1736355791151": "2025-01-08T12:03:11.151218-0500 DEBUG Building Chat Input\n"}

{"1736355791485": "2025-01-08T12:03:11.485380-0500 DEBUG consumed event add_message-153bcd5d-ef4d-4ece-8cc0-47c6b6a9ef92 (time in queue, 0.0000, client 0.0001)\n"}

{"1736355791499": "2025-01-08T12:03:11.499704-0500 DEBUG consumed event end_vertex-3d7125cd-7b8a-44eb-9113-ed5b785e3cf3 (time in queue, 0.0056, client 0.0047)\n"}

{"1736355791502": "2025-01-08T12:03:11.502510-0500 DEBUG consumed event end-40d0b363-5618-4a23-bbae-487cd0b9594d (time in queue, 0.0001, client 0.0004)\n"}

{"1736355791513": "2025-01-08T12:03:11.513097-0500 DEBUG Logged vertex build: 729ff2f8-6b01-48c8-9ad0-3743c2af9e8a\n"}

{"1736355791834": "2025-01-08T12:03:11.834982-0500 DEBUG Telemetry data sent successfully.\n"}

{"1736355791941": "2025-01-08T12:03:11.941840-0500 DEBUG Telemetry data sent successfully.\n"}

keepalive
```

  </TabItem>
</Tabs>

### Retrieve logs with optional parameters

Retrieve logs with optional query parameters.

- `lines_before`: The number of logs before the timestamp or the last log.
- `lines_after`: The number of logs after the timestamp.
- `timestamp`: The timestamp to start getting logs from.

The default values for all three parameters is `0`.
With these values, the endpoint returns the last 10 lines of logs.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/logs?lines_before=0&lines_after=0&timestamp=0" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
{
  "1736354770500": "2025-01-08T11:46:10.500363-0500 DEBUG Creating starter project Document Q&A\n",
  "1736354770511": "2025-01-08T11:46:10.511146-0500 DEBUG Creating starter project Image Sentiment Analysis\n",
  "1736354770521": "2025-01-08T11:46:10.521018-0500 DEBUG Creating starter project SEO Keyword Generator\n",
  "1736354770532": "2025-01-08T11:46:10.532677-0500 DEBUG Creating starter project Sequential Tasks Agents\n",
  "1736354770544": "2025-01-08T11:46:10.544010-0500 DEBUG Creating starter project Custom Component Generator\n",
  "1736354770555": "2025-01-08T11:46:10.555513-0500 DEBUG Creating starter project Prompt Chaining\n",
  "1736354770588": "2025-01-08T11:46:10.588105-0500 DEBUG Create service ServiceType.CHAT_SERVICE\n",
  "1736354771021": "2025-01-08T11:46:11.021817-0500 DEBUG Telemetry data sent successfully.\n",
  "1736354775619": "2025-01-08T11:46:15.619545-0500 DEBUG Create service ServiceType.STORE_SERVICE\n",
  "1736354775699": "2025-01-08T11:46:15.699661-0500 DEBUG File 046-rocket.svg retrieved successfully from flow /Users/mendon.kissling/Library/Caches/langflow/profile_pictures/Space.\n"
}
```

  </TabItem>
</Tabs>

## Monitor

Use the `/monitor` endpoint to monitor and modify messages passed between Langflow components, vertex builds, and transactions.

### Get Vertex builds

Retrieve Vertex builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "vertex_builds": {
    "ChatInput-NCmix": [
      {
        "data": {
          "results": {
            "message": {
              "text_key": "text",
              "data": {
                "timestamp": "2024-12-23 19:10:57",
                "sender": "User",
                "sender_name": "User",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello",
                "files": [],
                "error": "False",
                "edit": "False",
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": "False",
                  "source": {
                    "id": "None",
                    "display_name": "None",
                    "source": "None"
                  },
                  "icon": "",
                  "allow_markdown": "False",
                  "positive_feedback": "None",
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "c95bed34-f906-4aa6-84e4-68553f6db772",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "default_value": "",
              "text": "Hello",
              "sender": "User",
              "sender_name": "User",
              "files": [],
              "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "timestamp": "2024-12-23 19:10:57+00:00",
              "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "error": "False",
              "edit": "False",
              "properties": {
                "text_color": "",
                "background_color": "",
                "edited": "False",
                "source": {
                  "id": "None",
                  "display_name": "None",
                  "source": "None"
                },
                "icon": "",
                "allow_markdown": "False",
                "positive_feedback": "None",
                "state": "complete",
                "targets": []
              },
              "category": "message",
              "content_blocks": []
            }
          },
          "outputs": {
            "message": {
              "message": {
                "timestamp": "2024-12-23T19:10:57",
                "sender": "User",
                "sender_name": "User",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello",
                "files": [],
                "error": false,
                "edit": false,
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": false,
                  "source": {
                    "id": null,
                    "display_name": null,
                    "source": null
                  },
                  "icon": "",
                  "allow_markdown": false,
                  "positive_feedback": null,
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "c95bed34-f906-4aa6-84e4-68553f6db772",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "type": "object"
            }
          },
          "logs": { "message": [] },
          "message": {
            "message": "Hello",
            "sender": "User",
            "sender_name": "User",
            "files": [],
            "type": "object"
          },
          "artifacts": {
            "message": "Hello",
            "sender": "User",
            "sender_name": "User",
            "files": [],
            "type": "object"
          },
          "timedelta": 0.015060124918818474,
          "duration": "15 ms",
          "used_frozen_result": false
        },
        "artifacts": {
          "message": "Hello",
          "sender": "User",
          "sender_name": "User",
          "files": [],
          "type": "object"
        },
        "params": "- Files: []\n  Message: Hello\n  Sender: User\n  Sender Name: User\n  Type: object\n",
        "valid": true,
        "build_id": "40aa200e-74db-4651-b698-f80301d2b26b",
        "id": "ChatInput-NCmix",
        "timestamp": "2024-12-23T19:10:58.772766Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ],
    "Prompt-BEn9c": [
      {
        "data": {
          "results": {},
          "outputs": {
            "prompt": {
              "message": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "type": "text"
            }
          },
          "logs": { "prompt": [] },
          "message": {
            "prompt": {
              "repr": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "raw": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "type": "text"
            }
          },
          "artifacts": {
            "prompt": {
              "repr": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "raw": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
              "type": "text"
            }
          },
          "timedelta": 0.0057758750626817346,
          "duration": "6 ms",
          "used_frozen_result": false
        },
        "artifacts": {
          "prompt": {
            "repr": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
            "raw": "Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.",
            "type": "text"
          }
        },
        "params": "None",
        "valid": true,
        "build_id": "39bbbfde-97fd-42a5-a9ed-d42a5c5d532b",
        "id": "Prompt-BEn9c",
        "timestamp": "2024-12-23T19:10:58.781019Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ],
    "OpenAIModel-7AjrN": [
      {
        "data": {
          "results": {},
          "outputs": {
            "text_output": {
              "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "type": "text"
            },
            "model_output": { "message": "", "type": "unknown" }
          },
          "logs": { "text_output": [] },
          "message": {
            "text_output": {
              "repr": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "raw": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "type": "text"
            }
          },
          "artifacts": {
            "text_output": {
              "repr": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "raw": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "type": "text"
            }
          },
          "timedelta": 1.034765167045407,
          "duration": "1.03 seconds",
          "used_frozen_result": false
        },
        "artifacts": {
          "text_output": {
            "repr": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "raw": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "type": "text"
          }
        },
        "params": "None",
        "valid": true,
        "build_id": "4f0ae730-a266-4d35-b89f-7b825c620a0f",
        "id": "OpenAIModel-7AjrN",
        "timestamp": "2024-12-23T19:10:58.790484Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ],
    "ChatOutput-sfUhT": [
      {
        "data": {
          "results": {
            "message": {
              "text_key": "text",
              "data": {
                "timestamp": "2024-12-23 19:10:58",
                "sender": "Machine",
                "sender_name": "AI",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
                "files": [],
                "error": "False",
                "edit": "False",
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": "False",
                  "source": {
                    "id": "OpenAIModel-7AjrN",
                    "display_name": "OpenAI",
                    "source": "gpt-4o-mini"
                  },
                  "icon": "OpenAI",
                  "allow_markdown": "False",
                  "positive_feedback": "None",
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "5688356d-9f30-40ca-9907-79a7a2fc16fd",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "default_value": "",
              "text": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
              "sender": "Machine",
              "sender_name": "AI",
              "files": [],
              "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "timestamp": "2024-12-23 19:10:58+00:00",
              "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
              "error": "False",
              "edit": "False",
              "properties": {
                "text_color": "",
                "background_color": "",
                "edited": "False",
                "source": {
                  "id": "OpenAIModel-7AjrN",
                  "display_name": "OpenAI",
                  "source": "gpt-4o-mini"
                },
                "icon": "OpenAI",
                "allow_markdown": "False",
                "positive_feedback": "None",
                "state": "complete",
                "targets": []
              },
              "category": "message",
              "content_blocks": []
            }
          },
          "outputs": {
            "message": {
              "message": {
                "timestamp": "2024-12-23T19:10:58",
                "sender": "Machine",
                "sender_name": "AI",
                "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
                "text": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
                "files": [],
                "error": false,
                "edit": false,
                "properties": {
                  "text_color": "",
                  "background_color": "",
                  "edited": false,
                  "source": {
                    "id": "OpenAIModel-7AjrN",
                    "display_name": "OpenAI",
                    "source": "gpt-4o-mini"
                  },
                  "icon": "OpenAI",
                  "allow_markdown": false,
                  "positive_feedback": null,
                  "state": "complete",
                  "targets": []
                },
                "category": "message",
                "content_blocks": [],
                "id": "5688356d-9f30-40ca-9907-79a7a2fc16fd",
                "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
              },
              "type": "object"
            }
          },
          "logs": { "message": [] },
          "message": {
            "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "sender": "Machine",
            "sender_name": "AI",
            "files": [],
            "type": "object"
          },
          "artifacts": {
            "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
            "sender": "Machine",
            "sender_name": "AI",
            "files": [],
            "type": "object"
          },
          "timedelta": 0.017838125000707805,
          "duration": "18 ms",
          "used_frozen_result": false
        },
        "artifacts": {
          "message": "Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!",
          "sender": "Machine",
          "sender_name": "AI",
          "files": [],
          "type": "object"
        },
        "params": "- Files: []\n  Message: Hello! 🌟 I'm excited to help you get started on your journey to building\n    something fresh! What do you have in mind? Whether it's a project, an idea, or\n    a concept, let's dive in and make it happen!\n  Sender: Machine\n  Sender Name: AI\n  Type: object\n",
        "valid": true,
        "build_id": "1e8b908b-aba7-403b-9e9b-eca92bb78668",
        "id": "ChatOutput-sfUhT",
        "timestamp": "2024-12-23T19:10:58.813268Z",
        "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
      }
    ]
  }
}
```

  </TabItem>
</Tabs>

### Delete Vertex builds

Delete Vertex builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H "accept: */*"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
204 No Content
```

  </TabItem>
</Tabs>

### Get messages

Retrieve messages with optional filters.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/messages" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
A list of all messages.
```

 </TabItem>
</Tabs>

You can filter messages by `flow_id`, `session_id`, `sender`, and `sender_name`.
Results can be ordered with the `order_by` query string.

This example retrieves messages sent by `Machine` and `AI` in a given chat session (`session_id`) and orders the messages by timestamp.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/messages?flow_id=$FLOW_ID&session_id=01ce083d-748b-4b8d-97b6-33adbb6a528a&sender=Machine&sender_name=AI&order_by=timestamp" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "id": "1c1d6134-9b8b-4079-931c-84dcaddf19ba",
    "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
    "timestamp": "2024-12-23 19:20:11 UTC",
    "sender": "Machine",
    "sender_name": "AI",
    "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
    "text": "Hello! It's great to see you here! What exciting project or idea are you thinking about diving into today? Whether it's something fresh and innovative or a classic concept with a twist, I'm here to help you get started! Let's brainstorm together!",
    "files": "[]",
    "edit": false,
    "properties": {
      "text_color": "",
      "background_color": "",
      "edited": false,
      "source": {
        "id": "OpenAIModel-7AjrN",
        "display_name": "OpenAI",
        "source": "gpt-4o-mini"
      },
      "icon": "OpenAI",
      "allow_markdown": false,
      "positive_feedback": null,
      "state": "complete",
      "targets": []
    },
    "category": "message",
    "content_blocks": []
  }
]
```

  </TabItem>
</Tabs>

### Delete messages

Delete specific messages by their IDs.

This example deletes the message retrieved in the previous Get messages example.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -v -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/messages" \
  -H "accept: */*" \
  -H "Content-Type: application/json" \
  -d '["MESSAGE_ID_1", "MESSAGE_ID_2"]'
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
204 No Content
```

  </TabItem>
</Tabs>

### Update message

Update a specific message by its ID.

This example updates the `text` value of message `3ab66cc6-c048-48f8-ab07-570f5af7b160`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PUT \
  "$LANGFLOW_URL/api/v1/monitor/messages/3ab66cc6-c048-48f8-ab07-570f5af7b160" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
  "text": "testing 1234"
}'
```

</TabItem>
  <TabItem value="result" label="Result">

```json
{
  "timestamp": "2024-12-23T18:49:06",
  "sender": "string",
  "sender_name": "string",
  "session_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
  "text": "testing 1234",
  "files": ["string"],
  "error": true,
  "edit": true,
  "properties": {
    "text_color": "string",
    "background_color": "string",
    "edited": false,
    "source": { "id": "string", "display_name": "string", "source": "string" },
    "icon": "string",
    "allow_markdown": false,
    "positive_feedback": true,
    "state": "complete",
    "targets": []
  },
  "category": "message",
  "content_blocks": [],
  "id": "3ab66cc6-c048-48f8-ab07-570f5af7b160",
  "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a"
}
```

  </TabItem>
</Tabs>

### Update session ID

Update the session ID for messages.

This example updates the `session_ID` value `01ce083d-748b-4b8d-97b6-33adbb6a528a` to `different_session_id`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PATCH \
  "$LANGFLOW_URL/api/v1/monitor/messages/session/01ce083d-748b-4b8d-97b6-33adbb6a528a?new_session_id=different_session_id" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "id": "8dd7f064-e63a-4773-b472-ca0475249dfd",
    "flow_id": "01ce083d-748b-4b8d-97b6-33adbb6a528a",
    "timestamp": "2024-12-23 18:49:55 UTC",
    "sender": "User",
    "sender_name": "User",
    "session_id": "different_session_id",
    "text": "message",
    "files": "[]",
    "edit": false,
    "properties": {
      "text_color": "",
      "background_color": "",
      "edited": false,
      "source": {
        "id": null,
        "display_name": null,
        "source": null
      },
      "icon": "",
      "allow_markdown": false,
      "positive_feedback": null,
      "state": "complete",
      "targets": []
    },
    "category": "message",
    "content_blocks": []
  }
]
```

  </TabItem>
</Tabs>

### Delete messages by session

Delete all messages for a specific session.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/monitor/messages/session/different_session_id_2" \
  -H "accept: */*"
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
HTTP/1.1 204 No Content
```

  </TabItem>
</Tabs>

### Get transactions

Retrieve all transactions (interactions between components) for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/monitor/transactions?flow_id=$FLOW_ID&page=1&size=50" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "items": [
    {
      "timestamp": "2024-12-23T20:05:01.061Z",
      "vertex_id": "string",
      "target_id": "string",
      "inputs": {},
      "outputs": {},
      "status": "string",
      "error": "string",
      "flow_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
  ],
  "total": 0,
  "page": 1,
  "size": 1,
  "pages": 0
}
```

  </TabItem>
</Tabs>
