---
title: Build endpoints
slug: /api-build
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/build` endpoint to build vertices and flows, and execute those flows with streaming event responses.

The `/build` endpoint offers additional configuration for running flows.

:::important
This `/build` endpoints are meant to be used by the frontend, and they aren't optimized for external use.

To run a flow, use the [`/run` endpoint](/api-flows-run#run-flow).
:::

## Build flow and stream events

This endpoint builds and executes a flow, returning a job ID that can be used to stream execution events.

1. Send a POST request to the `/build/$FLOW_ID/flow` endpoint.

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

2. After receiving a job ID from the build endpoint, use the `/build/$JOB_ID/events` endpoint to stream the execution results:

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

## Build headers

| Header | Info | Example |
|--------|------|---------|
| Content-Type | Required. Specifies the JSON format. | "application/json" |
| accept | Required. Specifies the response format. | "application/json" |
| x-api-key | Optional. Required only if authentication is enabled. | "sk-..." |

The `/build/$FLOW_ID/flow` endpoint accepts the following parameters in its request body:

## Build parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| inputs | object | Optional. Input values for flow components. |
| data | object | Optional. Flow data to override stored configuration. |
| files | array[string] | Optional. List of file paths to use. |
| start_component_id | string | Optional. ID of the component where the execution should start. Component `id` values can be found in a [Langflow JSON files](/concepts-flows#langflow-json-file-contents) |
| stop_component_id | string | Optional. ID of the component where the execution should stop. Component `id` values can be found in a [Langflow JSON files](/concepts-flows#langflow-json-file-contents).|
| log_builds | boolean | Optional. Control build logging. Default: `true`. |

### Set start and stop points

The `/build` endpoint accepts optional values for `start_component_id` and `stop_component_id` to control where the flow run starts and stops.
Setting `stop_component_id` for a component triggers the same behavior as clicking the **Play** button on that component, where all dependent components leading up to that component are also run.
For example, to stop flow execution at the Open AI model component, run the following command:

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"stop_component_id": "OpenAIModel-Uksag"}'
```

### Override flow parameters

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

## See also

- [Get Vertex builds](/api-monitor#get-vertex-builds)
- [Delete Vertex builds](/api-monitor#delete-vertex-builds)
- [Session ID](/session-id)