---
title: API examples
slug: /api-reference-api-examples
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This page provides examples and practices for managing Langflow using the Langflow API.

The Langflow API's OpenAPI spec can be viewed and tested at your Langflow deployment's `docs` endpoint.
For example, `http://127.0.0.1:7860/docs`.

## Export values (optional)

You might find it helpful to set the following environment variables:

* Export your Langflow URL in your terminal.
Langflow starts by default at `http://127.0.0.1:7860`.
```plain
export LANGFLOW_URL="http://127.0.0.1:7860"
```

* Export the `flow-id` in your terminal.
The `flow-id` is found in the [API pane](/concepts-api) or in the flow's URL.
```plain
export FLOW_ID="359cd752-07ea-46f2-9d3b-a4407ef618da"
```

* Export the `folder-id` in your terminal.
To find your folder ID, call the Langflow [/api/v1/folders/](#read-folders) endpoint for a list of folders.
<Tabs>
  <TabItem value="curl" label="curl" default>
```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/folders/" \
  -H 'accept: application/json'
```
  </TabItem>
  <TabItem value="result" label="Result">
```plain
[
  {
    "name": "My Projects",
    "description": "Manage your own projects. Download and upload folders.",
    "id": "1415de42-8f01-4f36-bf34-539f23e47466",
    "parent_id": null
  }
]
```
  </TabItem>
</Tabs>
Export the `folder-id` as an environment variable.
```plain
export FOLDER_ID="1415de42-8f01-4f36-bf34-539f23e47466"
```

* Export the Langflow API key as an environment variable.
To create a Langflow API key, run the following command in the Langflow CLI.
<Tabs>
  <TabItem value="curl" label="curl" default>
```plain
langflow api-key
```
  </TabItem>
  <TabItem value="result" label="Result">
```plain
API Key Created Successfully:
sk-...
```
  </TabItem>
</Tabs>
Export the generated API key as an environment variable.
```plain
export LANGFLOW_API_KEY="sk-..."
```

The examples in this guide use environment variables for these values.

## Build

Use the `/build` endpoint to build vertices and flows.

### Build flow

This example builds a flow with a given `flow_id`.

LLM chat responses are streamed back as `token` events until the `end` event closes the connection.

<Tabs>
   <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"message": "hello, how are you doing?"}'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
{"event": "vertices_sorted", "data": {"ids": ["Prompt-CDhMB", "ChatInput-8VNJS"], "to_run": ["ChatOutput-Up0tW", "OpenAIModel-mXCyV", "Prompt-CDhMB", "ChatInput-8VNJS"]}}

{"event": "add_message", "data": {"timestamp": "2025-01-13T21:27:27", "sender": "User", "sender_name": "User", "session_id": "b68d9bfb-6382-455a-869b-b99a3a3a3cf6", "text": "", "files": [], "error": false, "edit": false, "properties": {"text_color": "", "background_color": "", "edited": false, "source": {"id": null, "display_name": null, "source": null}, "icon": "", "allow_markdown": false, "positive_feedback": null, "state": "complete", "targets": []}, "category": "message", "content_blocks": [], "id": "3942f4e3-4fff-4507-bb58-c96c7b6b8515", "flow_id": "b68d9bfb-6382-455a-869b-b99a3a3a3cf6"}}

{"event": "end_vertex", "data": {"build_data": {"id": "Prompt-CDhMB", "inactivated_vertices": [], "next_vertices_ids": [], "top_level_vertices": [], "valid": true, "params": "None", "data": {"results": {}, "outputs": {"prompt": {"message": "You are a helpful AI assistant", "type": "text"}}, "logs": {"prompt": []}, "message": {"prompt": {"repr": "You are a helpful AI assistant", "raw": "You are a helpful AI assistant", "type": "text"}}, "artifacts": {"prompt": {"repr": "You are a helpful AI assistant", "raw": "You are a helpful AI assistant", "type": "text"}}, "timedelta": 0.007543042069301009, "duration": "8 ms", "used_frozen_result": false}, "timestamp": "2025-01-13T21:27:27.231841Z"}}}

{"event": "token", "data": {"chunk": "", "id": "fda55d2e-d24c-498e-92a8-03ca2141265e", "timestamp": "2025-01-13 21:27:27 UTC"}}

{"event": "token", "data": {"chunk": "Hello", "id": "fda55d2e-d24c-498e-92a8-03ca2141265e", "timestamp": "2025-01-13 21:27:27 UTC"}}

{"event": "token", "data": {"chunk": "!", "id": "fda55d2e-d24c-498e-92a8-03ca2141265e", "timestamp": "2025-01-13 21:27:27 UTC"}}

{"event": "end", "data": {}}
```

   </TabItem>
</Tabs>

This output is abbreviated, but the order of events illustrates how Langflow runs components.

1. Langflow first sorts the vertices by dependencies (edges) in the `vertices_sorted` event:
```
ChatInput-8VNJS → Prompt-CDhMB → OpenAIModel-mXCyV → ChatOutput-Up0tW
```
2. The Chat Input component receives user input in the `add_message` event.
3. The Prompt component is built and executed with the received input in the `end_vertex` event.
4. The Open AI model's responses stream as `token` events.
The `token` event represents individual pieces of text as they're generated by an LLM.
5. The clean `end` event tells you the flow executed with no errors.
If your flow executes with errors, the `error` event handler prints the errors to the playground.

You can also pass values for `start_component_id` and `stop_component_id` in the body of the command to control where the flow run will start and stop.
For example, to stop flow execution at the Open AI model component, run the following command:

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/build/$FLOW_ID/flow" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{"stop_component_id": "OpenAIModel-Uksag"}'
```

## Flows

Use the `/flows` endpoint to create, read, update, and delete flows.

### Create flow

Create a new flow.

<Tabs>
   <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/flows/" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
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
  ],
  "locked": false,
  "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
{
    "name": "Untitled document (2)",
    "description": "Conversational Cartography Unlocked.",
    "icon": null,
    "icon_bg_color": null,
    "gradient": null,
    "data": {
        "nodes": [],
        "edges": [],
        "viewport": {
            "zoom": 1,
            "x": 0,
            "y": 0
        }
    },
    "is_component": false,
    "updated_at": "2024-12-30T15:48:53+00:00",
    "webhook": false,
    "endpoint_name": null,
    "tags": null,
    "locked": false,
    "id": "91be355a-3cd1-46b2-89c0-6b416391ad95",
    "user_id": "f58396d4-a387-4bb8-b749-f40825c3d9f3",
    "folder_id": "1415de42-8f01-4f36-bf34-539f23e47466"
}
```

   </TabItem>
</Tabs>

### Read flows

Retrieve a list of flows with pagination support.

<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/flows/?remove_example_flows=false&components_only=false&get_all=true&header_flows=false&page=1&size=50" \
  -H 'accept: application/json'
```

   </TabItem>

<TabItem value="result" label="Result">

```plain
A JSON object containing a list of flows.
```
   </TabItem>
</Tabs>

To retrieve only the flows from a specific folder, pass `folder_id` in the query string.


<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/flows/?remove_example_flows=true&components_only=false&get_all=false&folder_id=$FOLDER_ID&header_flows=false&page=1&size=1" \
  -H 'accept: application/json'
```

   </TabItem>

<TabItem value="result" label="Result">

```plain
A JSON object containing a list of flows.
```

   </TabItem>
</Tabs>

### Read flow

Read a specific flow by its ID.

<Tabs>
<TabItem value="curl" label="curl" default>

```bash
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/flows/$FLOW_ID" \
  -H 'accept: application/json'
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
curl -X 'PATCH' \
  "$LANGFLOW_URL/api/v1/flows/$FLOW_ID" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "string",
  "description": "string",
  "data": {},
  "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
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
  "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

   </TabItem>
</Tabs>

### Delete flow

Delete a specific flow by its ID.

<Tabs>
    <TabItem value="curl" label="curl" default>

```bash
curl -X 'DELETE' \
  "$LANGFLOW_URL/api/v1/flows/$FLOW_ID" \
  -H 'accept: application/json'
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

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/flows/batch/" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
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
      "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
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
      "folder_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
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

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/flows/upload/?folder_id=$FOLDER_ID" \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@agent-with-astra-db-tool.json;type=application/json'
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

To specify a target folder for the flow, include the query parameter `folder_id`.
The target `folder_id` must already exist before uploading a flow. Call the [/api/v1/folders/](#read-folders) endpoint for a list of available folders.

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/flows/upload/?folder_id=$FOLDER_ID" \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@agent-with-astra-db-tool.json;type=application/json'
```

### Download all flows

Download all flows as a ZIP file.

This endpoint downloads a ZIP file containing flows for all `flow-id` values listed in the command's body.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/flows/download/" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '[
  "e1e40c77-0541-41a9-88ab-ddb3419398b5", "92f9a4c5-cfc8-4656-ae63-1f0881163c28"
]' \
  --output langflow-flows.zip
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/flows/basic_examples/" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
A list of example flows.
```

  </TabItem>
</Tabs>


## Monitor

Use the `/monitor` endpoint to monitor and modify messages passed between Langflow components, vertex builds, and transactions.

### Get Vertex builds

Retrieve Vertex builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{"vertex_builds":{"ChatInput-NCmix":[{"data":{"results":{"message":{"text_key":"text","data":{"timestamp":"2024-12-23 19:10:57","sender":"User","sender_name":"User","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello","files":[],"error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"None","display_name":"None","source":"None"},"icon":"","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"c95bed34-f906-4aa6-84e4-68553f6db772","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"default_value":"","text":"Hello","sender":"User","sender_name":"User","files":[],"session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","timestamp":"2024-12-23 19:10:57+00:00","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"None","display_name":"None","source":"None"},"icon":"","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[]}},"outputs":{"message":{"message":{"timestamp":"2024-12-23T19:10:57","sender":"User","sender_name":"User","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":null,"display_name":null,"source":null},"icon":"","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"c95bed34-f906-4aa6-84e4-68553f6db772","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"type":"object"}},"logs":{"message":[]},"message":{"message":"Hello","sender":"User","sender_name":"User","files":[],"type":"object"},"artifacts":{"message":"Hello","sender":"User","sender_name":"User","files":[],"type":"object"},"timedelta":0.015060124918818474,"duration":"15 ms","used_frozen_result":false},"artifacts":{"message":"Hello","sender":"User","sender_name":"User","files":[],"type":"object"},"params":"- Files: []\n  Message: Hello\n  Sender: User\n  Sender Name: User\n  Type: object\n","valid":true,"build_id":"40aa200e-74db-4651-b698-f80301d2b26b","id":"ChatInput-NCmix","timestamp":"2024-12-23T19:10:58.772766Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}],"Prompt-BEn9c":[{"data":{"results":{},"outputs":{"prompt":{"message":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"logs":{"prompt":[]},"message":{"prompt":{"repr":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","raw":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"artifacts":{"prompt":{"repr":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","raw":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"timedelta":0.0057758750626817346,"duration":"6 ms","used_frozen_result":false},"artifacts":{"prompt":{"repr":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","raw":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"params":"None","valid":true,"build_id":"39bbbfde-97fd-42a5-a9ed-d42a5c5d532b","id":"Prompt-BEn9c","timestamp":"2024-12-23T19:10:58.781019Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}],"OpenAIModel-7AjrN":[{"data":{"results":{},"outputs":{"text_output":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"},"model_output":{"message":"","type":"unknown"}},"logs":{"text_output":[]},"message":{"text_output":{"repr":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","raw":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"}},"artifacts":{"text_output":{"repr":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","raw":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"}},"timedelta":1.034765167045407,"duration":"1.03 seconds","used_frozen_result":false},"artifacts":{"text_output":{"repr":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","raw":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"}},"params":"None","valid":true,"build_id":"4f0ae730-a266-4d35-b89f-7b825c620a0f","id":"OpenAIModel-7AjrN","timestamp":"2024-12-23T19:10:58.790484Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}],"ChatOutput-sfUhT":[{"data":{"results":{"message":{"text_key":"text","data":{"timestamp":"2024-12-23 19:10:58","sender":"Machine","sender_name":"AI","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","files":[],"error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"OpenAIModel-7AjrN","display_name":"OpenAI","source":"gpt-4o-mini"},"icon":"OpenAI","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"5688356d-9f30-40ca-9907-79a7a2fc16fd","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"default_value":"","text":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","timestamp":"2024-12-23 19:10:58+00:00","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"OpenAIModel-7AjrN","display_name":"OpenAI","source":"gpt-4o-mini"},"icon":"OpenAI","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[]}},"outputs":{"message":{"message":{"timestamp":"2024-12-23T19:10:58","sender":"Machine","sender_name":"AI","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"OpenAIModel-7AjrN","display_name":"OpenAI","source":"gpt-4o-mini"},"icon":"OpenAI","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"5688356d-9f30-40ca-9907-79a7a2fc16fd","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"type":"object"}},"logs":{"message":[]},"message":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"artifacts":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"timedelta":0.017838125000707805,"duration":"18 ms","used_frozen_result":false},"artifacts":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"params":"- Files: []\n  Message: Hello! 🌟 I'm excited to help you get started on your journey to building\n    something fresh! What do you have in mind? Whether it's a project, an idea, or\n    a concept, let's dive in and make it happen!\n  Sender: Machine\n  Sender Name: AI\n  Type: object\n","valid":true,"build_id":"1e8b908b-aba7-403b-9e9b-eca92bb78668","id":"ChatOutput-sfUhT","timestamp":"2024-12-23T19:10:58.813268Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}]}}
```

  </TabItem>
</Tabs>

### Delete Vertex builds

Delete Vertex builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  "$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID" \
  -H 'accept: */*'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
204 No Content
```

  </TabItem>
</Tabs>

### Get messages

Retrieve messages with optional filters.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  'http://127.0.0.1:7860/api/v1/monitor/messages' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
A list of all messages.
```

 </TabItem>
</Tabs>

You can filter messages by `flow_id`, `session_id`, `sender`, and `sender_name`.
Results can be ordered with the `order_by` query string.

This example retrieves messages sent by `Machine` and `AI` in a given chat session (`session_id`) and orders the messages by timestamp.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X "GET" \
  "$LANGFLOW_URL/api/v1/monitor/messages?flow_id=$FLOW_ID&session_id=01ce083d-748b-4b8d-97b6-33adbb6a528a&sender=Machine&sender_name=AI&order_by=timestamp" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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

```curl
curl -v -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/monitor/messages' \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  -d '[
  "1c1d6134-9b8b-4079-931c-84dcaddf19ba"
]'
```
  </TabItem>
  <TabItem value="result" label="Result">

```plain
204 No Content
```

  </TabItem>
</Tabs>

To delete multiple messages, list the IDs within the array.

```curl
curl -v -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/monitor/messages' \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  -d '["MESSAGE_ID_1", "MESSAGE_ID_2"]'
```

### Update message

Update a specific message by its ID.

This example updates the `text` value of message `3ab66cc6-c048-48f8-ab07-570f5af7b160`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PUT' \
  "$LANGFLOW_URL/api/v1/monitor/messages/3ab66cc6-c048-48f8-ab07-570f5af7b160" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "text": "testing 1234"
}'
```

</TabItem>
  <TabItem value="result" label="Result">

```plain
{"timestamp":"2024-12-23T18:49:06","sender":"string","sender_name":"string","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"testing 1234","files":["string"],"error":true,"edit":true,"properties":{"text_color":"string","background_color":"string","edited":false,"source":{"id":"string","display_name":"string","source":"string"},"icon":"string","allow_markdown":false,"positive_feedback":true,"state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"3ab66cc6-c048-48f8-ab07-570f5af7b160","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}
```

  </TabItem>
</Tabs>


### Update session ID

Update the session ID for messages.

This example updates the `session_ID` value `01ce083d-748b-4b8d-97b6-33adbb6a528a` to `different_session_id`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  "$LANGFLOW_URL/api/v1/monitor/messages/session/01ce083d-748b-4b8d-97b6-33adbb6a528a?new_session_id=different_session_id" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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
  },
]
```

  </TabItem>
</Tabs>

### Delete messages by session

Delete all messages for a specific session.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/monitor/messages/session/different_session_id_2' \
  -H 'accept: */*'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
HTTP/1.1 204 No Content
```

  </TabItem>
</Tabs>

### Get transactions

Retrieve all transactions (interactions between components) for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/monitor/transactions?flow_id=$FLOW_ID&page=1&size=50' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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


## Folders

Use the `/folders` endpoint to create, read, update, and delete folders.

Folders store your flows and components.

### Read folders

Get a list of Langflow folders.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/folders/' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
  {
    "name": "My Projects",
    "description": "Manage your own projects. Download and upload folders.",
    "id": "1415de42-8f01-4f36-bf34-539f23e47466",
    "parent_id": null
  }
]
```

  </TabItem>
</Tabs>

### Create folder

Create a new folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/folders/" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "new_folder_name",
  "description": "string",
  "components_list": [],
  "flows_list": []
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "name": "new_folder_name",
  "description": "string",
  "id": "b408ddb9-6266-4431-9be8-e04a62758331",
  "parent_id": null
}
```

  </TabItem>
</Tabs>

To add flows and components at folder creation, retrieve the `components_list` and `flows_list` values from the [/api/v1/store/components](#get-all-components) and [/api/v1/flows/read](#read-flows) endpoints and add them to the request body.

Adding a flow to a folder moves the flow from its previous location. The flow is not copied.

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/folders/" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "new_folder_name",
  "description": "string",
  "components_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
}'
```

### Read folder

Retrieve details of a specific folder.

To find the UUID of your folder, call the [read folders](#read-folders) endpoint.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/folders/$FOLDER_ID' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
    {
        "name": "My Projects",
        "description": "Manage your own projects. Download and upload folders.",
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "parent_id": null
    }
]
```

  </TabItem>
</Tabs>

### Update folder

Update the information of a specific folder with a `PATCH` request.

Each PATCH request updates the folder with the values you send.
Only the fields you include in your request are updated.
If you send the same values multiple times, the update is still processed, even if the values are unchanged.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  '$LANGFLOW_URL/api/v1/folders/b408ddb9-6266-4431-9be8-e04a62758331' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
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

```plain
{
  "name": "string",
  "description": "string",
  "id": "b408ddb9-6266-4431-9be8-e04a62758331",
  "parent_id": null
}
```

  </TabItem>
</Tabs>

### Delete folder

Delete a specific folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/folders/$FOLDER_ID' \
  -H 'accept: */*'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
204 No Content
```

  </TabItem>
</Tabs>

### Download folder

Download all flows from a folder as a zip file.

The `--output` flag is optional.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/folders/download/b408ddb9-6266-4431-9be8-e04a62758331' \
  -H 'accept: application/json' \
  --output langflow-folder.zip
```

  </TabItem>
    <TabItem value="result" label="Result">

```plain
The folder contents.
```

  </TabItem>
</Tabs>

### Upload folder

Upload a folder to Langflow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/folders/upload/' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@20241230_135006_langflow_flows.zip;type=application/zip'
```

  </TabItem>

  <TabItem value="result" label="Result">

```plain
The folder contents are uploaded to Langflow.
```

  </TabItem>
</Tabs>

## Files

Use the `/files` endpoint to add or delete files between your local machine and Langflow.

### Upload file

Upload a file to an existing flow.

This example uploads `the_oscar_award.csv`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/files/upload/$FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@the_oscar_award.csv'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "flowId": "92f9a4c5-cfc8-4656-ae63-1f0881163c28",
  "file_path": "92f9a4c5-cfc8-4656-ae63-1f0881163c28/2024-12-30_15-19-43_the_oscar_award.csv"
}
```

  </TabItem>
</Tabs>

#### Upload image files

Send image files to the Langflow API for AI analysis.

The default file limit is 100 MB. To configure this value, change the `LANGFLOW_MAX_FILE_SIZE_UPLOAD` environment variable.
For more information, see [Supported environment variables](/environment-variables#supported-variables).

1. To send an image to your flow with the API, POST the image file to the `v1/files/upload/<YOUR-FLOW-ID>` endpoint of your flow.

```curl
curl -X POST "$LANGFLOW_URL/api/v1/files/upload/a430cc57-06bb-4c11-be39-d3d4de68d2c4" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image-file.png"
```

The API returns the image file path in the format `"file_path":"<YOUR-FLOW-ID>/<TIMESTAMP>_<FILE-NAME>"}`.

```json
{"flowId":"a430cc57-06bb-4c11-be39-d3d4de68d2c4","file_path":"a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png"}
```

2. Post the image file to the **Chat Input** component of a **Basic prompting** flow.
Pass the file path value as an input in the **Tweaks** section of the curl call to Langflow.

```curl
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

```plain
"text": "This flowchart appears to represent a complex system for processing financial inquiries using various AI agents and tools. Here's a breakdown of its components and how they might work together..."
```


### List files

List all files associated with a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/files/list/$FLOW_ID" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "files": [
    "2024-12-30_15-19-43_the_oscar_award.csv"
  ]
}
```

  </TabItem>
</Tabs>

### Download file

Download a specific file for a given flow.

To look up the file name in Langflow, use the `/list` endpoint.

This example downloads the `2024-12-30_15-19-43_the_oscar_award.csv` file from Langflow to a file named `output-file.csv`.

The `--output` flag is optional.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/files/download/$FLOW_ID/2024-12-30_15-19-43_the_oscar_award.csv" \
  -H 'accept: application/json' \
  --output output-file.csv
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
The file contents.
```

  </TabItem>
</Tabs>

### Download image

Download an image file for a given flow.

To look up the file name in Langflow, use the `/list` endpoint.

This example downloads the `2024-12-30_15-42-44_image-file.png` file from Langflow to a file named `output-image.png`.

The `--output` flag is optional.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/files/images/$FLOW_ID/2024-12-30_15-42-44_image-file.png" \
  -H 'accept: application/json' \
  --output output-image.png
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
Image file content.
```

  </TabItem>
</Tabs>


### Delete file

Delete a specific file from a flow.

This example deletes the `2024-12-30_15-42-44_image-file.png` file from Langflow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  "$LANGFLOW_URL/api/v1/files/delete/$FLOW_ID/2024-12-30_15-42-44_image-file.png" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "message": "File 2024-12-30_15-42-44_image-file.png deleted successfully"
}
```

  </TabItem>
</Tabs>

## Logs

Retrieve logs for your Langflow flow.

This endpoint requires log retrieval to be enabled in your Langflow application.

To enable log retrieval, include these values in your `.env` file:

```plain
LANGFLOW_ENABLE_LOG_RETRIEVAL=true
LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE=10000
LANGFLOW_LOG_LEVEL=DEBUG
```

For log retrieval to function, `LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE` needs to be greater than 0. The default value is `10000`.

Start Langflow with this `.env`:

```plain
uv run langflow run --env-file .env
```

### Stream logs

Stream logs in real-time using Server-Sent Events (SSE).

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/logs-stream" \
  -H 'accept: text/event-stream'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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

* `lines_before`: The number of logs before the timestamp or the last log.
* `lines_after`: The number of logs after the timestamp.
* `timestamp`: The timestamp to start getting logs from.

The default values for all three parameters is `0`.
With these values, the endpoint returns the last 10 lines of logs.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/logs?lines_before=0&lines_after=0&timestamp=0" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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

## Base

Use the base Langflow API for running your flow and retrieving configuration information.

### Get all components

This operation returns a dictionary of all Langflow components.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/all" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">
```result
A dictionary of all Langflow components.
```
  </TabItem>
</Tabs>

### Run flow

Execute a specified flow by ID or name.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  "$LANGFLOW_URL/api/v1/run/$FLOW_ID?stream=false" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input_value": "string",
  "input_type": "chat",
  "output_type": "chat",
  "output_component": "",
  "tweaks": {
    "Component Name": {
      "parameter_name": "value"
    },
    "component_id": {
      "parameter_name": "value"
    },
    "parameter_name": "value"
  },
  "session_id": "string"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "result": "Flow execution result",
  "session_id": "session_uuid"
}
```

  </TabItem>
</Tabs>

### Webhook run flow

The webhook endpoint triggers flow execution with an HTTP POST request.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X POST \
  "$LANGFLOW_URL/api/v1/webhook/$FLOW_ID" \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test_file.txt"}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
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

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/task/TASK_ID" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
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

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/version" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
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

```curl
curl -X 'GET' \
  "$LANGFLOW_URL/api/v1/config" \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
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


