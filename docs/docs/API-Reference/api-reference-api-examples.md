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

1. Export your Langflow URL in your terminal.
Langflow starts by default at `http://127.0.0.1:7860`.
```plain
export LANGFLOW_URL="http://127.0.0.1:7860"
```

2. Export the `flow-id` in your terminal.
The `flow-id` can be found in the [API pane](/workspace-api) or in the flow's URL.
```plain
export FLOW_ID="359cd752-07ea-46f2-9d3b-a4407ef618da"
```

The examples in this guide use environment variables for these values.


## Flows

### Create Flow

Create a new flow.

<Tabs>
   <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/flows/' \
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

### Read Flows

Retrieve a list of flows with pagination support.

<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/flows/?remove_example_flows=false&components_only=false&get_all=true&header_flows=false&page=1&size=50' \
  -H 'accept: application/json'
```

   </TabItem>

<TabItem value="result" label="Result">

```plain
A JSON object containing a list of flows.
```
   </TabItem>
</Tabs>

To retrieve only the flows from a specific folder, pass `folder_id_` in the query string.


<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X 'GET' \
  'http://127.0.0.1:7863/api/v1/flows/?remove_example_flows=true&components_only=false&get_all=false&folder_id=1415de42-8f01-4f36-bf34-539f23e47466&header_flows=false&page=1&size=1' \
  -H 'accept: application/json'
```

   </TabItem>

<TabItem value="result" label="Result">

```plain
A JSON object containing a list of flows.
```

   </TabItem>
</Tabs>

### Read Flow

Read a specific flow by its ID.

<Tabs>
<TabItem value="curl" label="curl" default>

```bash
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/flows/$FLOW_ID' \
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
  'http://127.0.0.1:7860/api/v1/flows/01ce083d-748b-4b8d-97b6-33adbb6a528a' \
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

### Delete Flow

Delete a specific flow by its ID.

<Tabs>
    <TabItem value="curl" label="curl" default>

 ```bash
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/flows/$FLOW_ID' \
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
  'http://127.0.0.1:7860/api/v1/flows/batch/' \
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
  'http://127.0.0.1:7860/api/v1/flows/upload/' \
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

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/flows/upload/?folder_id=$FOLDER_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@agent-with-astra-db-tool.json;type=application/json'
```

### Download all flows

Download all flows as a ZIP file.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  'http://127.0.0.1:7860/api/v1/flows/download/' \
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
  '$LANGFLOW_URL/api/v1/flows/basic_examples/' \
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

### Get Vertex Builds

Retrieve Vertex Builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{"vertex_builds":{"ChatInput-NCmix":[{"data":{"results":{"message":{"text_key":"text","data":{"timestamp":"2024-12-23 19:10:57","sender":"User","sender_name":"User","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello","files":[],"error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"None","display_name":"None","source":"None"},"icon":"","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"c95bed34-f906-4aa6-84e4-68553f6db772","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"default_value":"","text":"Hello","sender":"User","sender_name":"User","files":[],"session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","timestamp":"2024-12-23 19:10:57+00:00","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"None","display_name":"None","source":"None"},"icon":"","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[]}},"outputs":{"message":{"message":{"timestamp":"2024-12-23T19:10:57","sender":"User","sender_name":"User","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":null,"display_name":null,"source":null},"icon":"","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"c95bed34-f906-4aa6-84e4-68553f6db772","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"type":"object"}},"logs":{"message":[]},"message":{"message":"Hello","sender":"User","sender_name":"User","files":[],"type":"object"},"artifacts":{"message":"Hello","sender":"User","sender_name":"User","files":[],"type":"object"},"timedelta":0.015060124918818474,"duration":"15 ms","used_frozen_result":false},"artifacts":{"message":"Hello","sender":"User","sender_name":"User","files":[],"type":"object"},"params":"- Files: []\n  Message: Hello\n  Sender: User\n  Sender Name: User\n  Type: object\n","valid":true,"build_id":"40aa200e-74db-4651-b698-f80301d2b26b","id":"ChatInput-NCmix","timestamp":"2024-12-23T19:10:58.772766Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}],"Prompt-BEn9c":[{"data":{"results":{},"outputs":{"prompt":{"message":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"logs":{"prompt":[]},"message":{"prompt":{"repr":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","raw":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"artifacts":{"prompt":{"repr":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","raw":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"timedelta":0.0057758750626817346,"duration":"6 ms","used_frozen_result":false},"artifacts":{"prompt":{"repr":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","raw":"Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.","type":"text"}},"params":"None","valid":true,"build_id":"39bbbfde-97fd-42a5-a9ed-d42a5c5d532b","id":"Prompt-BEn9c","timestamp":"2024-12-23T19:10:58.781019Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}],"OpenAIModel-7AjrN":[{"data":{"results":{},"outputs":{"text_output":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"},"model_output":{"message":"","type":"unknown"}},"logs":{"text_output":[]},"message":{"text_output":{"repr":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","raw":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"}},"artifacts":{"text_output":{"repr":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","raw":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"}},"timedelta":1.034765167045407,"duration":"1.03 seconds","used_frozen_result":false},"artifacts":{"text_output":{"repr":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","raw":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","type":"text"}},"params":"None","valid":true,"build_id":"4f0ae730-a266-4d35-b89f-7b825c620a0f","id":"OpenAIModel-7AjrN","timestamp":"2024-12-23T19:10:58.790484Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}],"ChatOutput-sfUhT":[{"data":{"results":{"message":{"text_key":"text","data":{"timestamp":"2024-12-23 19:10:58","sender":"Machine","sender_name":"AI","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","files":[],"error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"OpenAIModel-7AjrN","display_name":"OpenAI","source":"gpt-4o-mini"},"icon":"OpenAI","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"5688356d-9f30-40ca-9907-79a7a2fc16fd","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"default_value":"","text":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","timestamp":"2024-12-23 19:10:58+00:00","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","error":"False","edit":"False","properties":{"text_color":"","background_color":"","edited":"False","source":{"id":"OpenAIModel-7AjrN","display_name":"OpenAI","source":"gpt-4o-mini"},"icon":"OpenAI","allow_markdown":"False","positive_feedback":"None","state":"complete","targets":[]},"category":"message","content_blocks":[]}},"outputs":{"message":{"message":{"timestamp":"2024-12-23T19:10:58","sender":"Machine","sender_name":"AI","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","files":[],"error":false,"edit":false,"properties":{"text_color":"","background_color":"","edited":false,"source":{"id":"OpenAIModel-7AjrN","display_name":"OpenAI","source":"gpt-4o-mini"},"icon":"OpenAI","allow_markdown":false,"positive_feedback":null,"state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"5688356d-9f30-40ca-9907-79a7a2fc16fd","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"},"type":"object"}},"logs":{"message":[]},"message":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"artifacts":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"timedelta":0.017838125000707805,"duration":"18 ms","used_frozen_result":false},"artifacts":{"message":"Hello! 🌟 I'm excited to help you get started on your journey to building something fresh! What do you have in mind? Whether it's a project, an idea, or a concept, let's dive in and make it happen!","sender":"Machine","sender_name":"AI","files":[],"type":"object"},"params":"- Files: []\n  Message: Hello! 🌟 I'm excited to help you get started on your journey to building\n    something fresh! What do you have in mind? Whether it's a project, an idea, or\n    a concept, let's dive in and make it happen!\n  Sender: Machine\n  Sender Name: AI\n  Type: object\n","valid":true,"build_id":"1e8b908b-aba7-403b-9e9b-eca92bb78668","id":"ChatOutput-sfUhT","timestamp":"2024-12-23T19:10:58.813268Z","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}]}}
```

  </TabItem>
</Tabs>

### Delete Vertex Builds

Delete Vertex Builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/monitor/builds?flow_id=$FLOW_ID' \
  -H 'accept: */*'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
204 No Content
```

  </TabItem>
</Tabs>

### Get Messages

Retrieve messages with optional filters.

This example retrieves messages sent by `Machine` and `AI` in a given chat session.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/monitor/messages?flow_id=$FLOW_ID&session_id=01ce083d-748b-4b8d-97b6-33adbb6a528a&sender=Machine&sender_name=AI&order_by=timestamp' \
  -H 'accept: application/json'
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
    "text": "Hello! It’s great to see you here! What exciting project or idea are you thinking about diving into today? Whether it’s something fresh and innovative or a classic concept with a twist, I’m here to help you get started! Let’s brainstorm together!",
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

### Delete Messages

Delete specific messages by their IDs.

This example deletes the message retrieved in the previous Get Messages example.

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

### Update Message

Update a specific message by its ID.

This example updates the `text` value of message `3ab66cc6-c048-48f8-ab07-570f5af7b160`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PUT' \
  '$LANGFLOW_URL/api/v1/monitor/messages/3ab66cc6-c048-48f8-ab07-570f5af7b160' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "text": "testing 1234",
}'
```

</TabItem>
  <TabItem value="result" label="Result">

```plain
{"timestamp":"2024-12-23T18:49:06","sender":"string","sender_name":"string","session_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a","text":"testing 1234","files":["string"],"error":true,"edit":true,"properties":{"text_color":"string","background_color":"string","edited":false,"source":{"id":"string","display_name":"string","source":"string"},"icon":"string","allow_markdown":false,"positive_feedback":true,"state":"complete","targets":[]},"category":"message","content_blocks":[],"id":"3ab66cc6-c048-48f8-ab07-570f5af7b160","flow_id":"01ce083d-748b-4b8d-97b6-33adbb6a528a"}
```

  </TabItem>
</Tabs>


### Update Session ID

Update the session ID for messages.

This example updates `01ce083d-748b-4b8d-97b6-33adbb6a528a` to `different_session_id`.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  'http://127.0.0.1:7863/api/v1/monitor/messages/session/01ce083d-748b-4b8d-97b6-33adbb6a528a?new_session_id=different_session_id' \
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

### Delete Messages by Session

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

### Get Transactions

Retrieve all transactions (interactions with the LLM) for a specific flow.

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

### Create Folder

Create a new folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/folders/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    "name": "New Folder Name"
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "id": "new_folder_id",
  "name": "New Folder Name"
}
```

  </TabItem>
</Tabs>

### Read Folder

Retrieve details of a specific folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/folders/{folder_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
    {
        "name": "My Projects",
        "description": "Manage your own projects. Download and upload folders.",
        "id": "f1838e2e-f6a9-4f1f-be3f-3affc5ef1b4c",
        "parent_id": null
    }
]
```

  </TabItem>
</Tabs>

### Update Folder

Update the information of a specific folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  '$LANGFLOW_URL/api/v1/folders/{folder_id}' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    "name": "Updated Folder Name"
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "id": "folder_id",
  "name": "Updated Folder Name"
}
```

  </TabItem>
</Tabs>

### Delete Folder

Delete a specific folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/folders/{folder_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
204 No Content
```

  </TabItem>
</Tabs>

### Download File

Download all flows from a folder as a zip file.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/folders/download/{folder_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer $YOUR_ACCESS_TOKEN'
```

  </TabItem>
</Tabs>

### Upload File

Upload flows from a file to a folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/folders/upload/' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -F 'file=@/path/to/your/file.zip'
```

  </TabItem>
</Tabs>

## Health Check

### Health

Check the health status of the service.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/health' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "status": "ok"
}
```

  </TabItem>
</Tabs>

### Health Check

Perform a detailed health check of the service.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/health_check' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "status": "ok",
  "chat": "ok",
  "db": "ok"
}
```

  </TabItem>
</Tabs>


## Files

### Upload File

Upload a file to a specific flow.

This example uploads `the_oscar_award.csv`.
<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  'http://127.0.0.1:7860/api/v1/files/upload/92f9a4c5-cfc8-4656-ae63-1f0881163c28' \
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
curl -X POST "http://127.0.0.1:7860/api/v1/files/upload/a430cc57-06bb-4c11-be39-d3d4de68d2c4" \
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
    "http://127.0.0.1:7860/api/v1/run/a430cc57-06bb-4c11-be39-d3d4de68d2c4?stream=false" \
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
"text": "This flowchart appears to represent a complex system for processing financial inquiries using various AI agents and tools. Here’s a breakdown of its components and how they might work together..."
```


### List Files

List all files associated with a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/list/$FLOW_ID' \
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

### Download File

Download a specific file for a given flow.

To look up the file name in Langflow, use the `/list` endpoint.

This example downloads the `2024-12-30_15-19-43_the_oscar_award.csv` file from Langflow to a file named `output-file.csv`.

The `--output` flag is optional.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/download/$FLOW_ID/2024-12-30_15-19-43_the_oscar_award.csv' \
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

### Download Image

Download an image file for a given flow.

To look up the file name in Langflow, use the `/list` endpoint.

This example downloads the `2024-12-30_15-42-44_image-file.png` file from Langflow to a file named `output-image.png`.

The `--output` flag is optional.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/images/$FLOW_ID/2024-12-30_15-42-44_image-file.png' \
  -H 'accept: application/json'
  --output output-image.png
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
Image file content.
```

  </TabItem>
</Tabs>


### Delete File

Delete a specific file from a flow.

This example deletes the `2024-12-30_15-42-44_image-file.png` file from Langflow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/files/delete/$FLOW_ID/2024-12-30_15-42-44_image-file.png' \
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

## Log

### Stream Logs

Stream logs in real-time using Server-Sent Events (SSE).

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/logs-stream' \
  -H 'accept: text/event-stream'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "detail": "Log retrieval is disabled"
}
```

  </TabItem>
</Tabs>

### Logs

Retrieve logs with optional parameters.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/logs?lines_before=0&lines_after=0&timestamp=0' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "detail": "Log retrieval is disabled"
}
```

  </TabItem>
</Tabs>

## Get starter projects

Retrieve starter projects.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL//api/v1/starter-projects/' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
A list of starter projects.
```

  </TabItem>
</Tabs>


## Base

### Get all

This operation returns a dictionary of all Langflow components.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/all' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">
```result
A dictionary of all Langflow components.
```
  </TabItem>
</Tabs>

### Simplified Run Flow

Execute a specified flow by ID or name with simplified input.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/run/92f9a4c5-cfc8-4656-ae63-1f0881163c28?stream=false' \
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

### Webhook Run Flow

Run a flow using a webhook request.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/webhook/$FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "webhook_data": "Your webhook data here"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "status": "Task status"
}
```

  </TabItem>
</Tabs>

### Experimental Run Flow

Execute a specified flow by ID with advanced options.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/run/advanced/$FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: YOUR_API_KEY' \
  -d '{
  "inputs": [
    {"components": ["component1"], "input_value": "value1"},
    {"components": ["component2"], "input_value": "value2"}
  ],
  "outputs": ["Component Name", "component_id"],
  "tweaks": {"parameter_name": "value"},
  "stream": false
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "result": "Advanced flow execution result",
  "session_id": "session_uuid"
}
```

  </TabItem>
</Tabs>

### Process

Process an input with a given flow ID.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/process/$FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: YOUR_API_KEY' \
  -d '{
  "input": "Your input data here"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "result": "Processed output"
}
```

  </TabItem>
</Tabs>

### Predict

Process an input with a given flow (alternative endpoint).

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/predict/{flow_id}' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: YOUR_API_KEY' \
  -d '{
  "predict_input": "Your predict input here"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
null
```

  </TabItem>
</Tabs>

### Get Task Status

Get the status of a task.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/task/TASK_ID' \
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

### Create Upload File (Deprecated)

Upload a file for a specific flow (Deprecated).

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/upload/$FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@path/to/your/file'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "file_path": "Uploaded file path"
}
```

  </TabItem>
</Tabs>

### Get Version

Get the version of the Langflow API.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/version' \
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

### Custom Component

Create a custom component.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/custom_component' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
  "code": "Your custom component code here"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "custom_component": "Custom component details"
}
```

  </TabItem>
</Tabs>

### Custom Component Update

Update a custom component.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/custom_component/update' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
  "code": "Your updated custom component code here"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
{
  "updated_component": "Updated custom component details"
}
```

  </TabItem>
</Tabs>

### Get Config

Retrieve the configuration information.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/config' \
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




