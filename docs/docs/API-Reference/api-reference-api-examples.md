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




## Chat

### Retrieve vertices order

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X POST "$LANGFLOW_URL/api/v1/build/$FLOW_ID/vertices" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "input_keys": ["key1", "key2"],
      "input_values": ["value1", "value2"]
    },
    "stop_component_id": "component123",
    "start_component_id": "component456"
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
text
```

  </TabItem>
</Tabs>


### Build flow

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X POST "$LANGFLOW_URL/api/v1/build/$FLOW_ID/vertices" \
  -H "Content-Type: application/json" \
  -d '{}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
text
```

  </TabItem>
</Tabs>

### Build vertex

Build a vertex instead of the entire graph.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X POST "$LANGFLOW_URL/api/v1/build/$FLOW_ID/vertices/{vertex_id}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
text
```

  </TabItem>
</Tabs>

### Build vertex stream

Build a vertex instead of the entire graph.

Returns: A StreamingResponse object with the streamed vertex data in text/event-stream format.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X POST "$LANGFLOW_URL/api/v1/build/$FLOW_ID/vertices/{vertex_id}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```result
text
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
  '$LANGFLOW_URL/api/v1/run/$FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: YOUR_API_KEY' \
  -d '{
  "input_value": "Sample input",
  "input_type": "chat",
  "output_type": "chat",
  "tweaks": {}
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

## Validate

### Post Validate Code

Validate the provided code.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/validate/code' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "code": "Your code to validate"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "valid": true,
  "message": "Validation message"
}
```

  </TabItem>
</Tabs>

### Post Validate Prompt

Validate the provided prompt.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/validate/prompt' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "template": "Your prompt template to validate"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "valid": true,
  "message": "Validation message"
}
```

  </TabItem>
</Tabs>

## Components store

### Check If Store Is Enabled

Check if the component store is enabled.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/store/check/' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "enabled": true
}
```

  </TabItem>
</Tabs>

### Check If Store Has API Key

Check if the component store has an API key.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/store/check/api_key' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "has_api_key": false,
    "is_valid": false
}
```

  </TabItem>
</Tabs>

### Share Component

Share a component to the store.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/store/components/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
  "name": "Component name",
  "description": "Component description",
  "component_code": "Your component code"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "id": "Component ID",
  "name": "Component name",
  "description": "Component description"
}
```

  </TabItem>
</Tabs>

### Get Components

Retrieve components from the store.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/store/components/' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "components": [
    {
      "id": "Component ID",
      "name": "Component name",
      "description": "Component description"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

  </TabItem>
</Tabs>

### Update Shared Component

Update a shared component by its ID.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
   '$LANGFLOW_URL/api/v1/store/components/{component_id}' \
   -H 'accept: application/json' \
   -H 'Content-Type: application/json' \
   -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
   -d '{
     "name": "Updated Component Name",
     "description": "Updated description",
     ...
}'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
{
    "id": "Updated Component ID",
    ...
}
```

   </TabItem>
</Tabs>

### Download Component

Download a specific component by its ID.

<Tabs>
   <TabItem value="curl" label="curl">

```curl
curl -X 'GET' \
   '$LANGFLOW_URL/api/v1/store/components/{component_id}' \
   -H 'accept: application/json' \
   -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
{
    ...
}
```

   </TabItem>
</Tabs>

### Get Tags

Retrieve available tags in the component store.

<Tabs>
   <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
   '$LANGFLOW_URL/api/v1/store/tags' \
   -H 'accept: application/json'
```

   </TabItem>
   <TabItem value="result" label="Result">

```json
[
    {
        "id": "ccabb590-c9e8-4e56-9d6c-309955936c6c",
        "name": "Agent"
    },
    {
        "id": "e660a9ea-35fb-4587-bfbd-13dba4c556d1",
        "name": "Memory"
    },
    {
        "id": "d442c88b-f8d0-4010-8752-16a644c7ac8e",
        "name": "Chain"
    },
    {
        "id": "cd614b49-dd57-4c8b-a5eb-f8bb5f957b9a",
        "name": "Vector Store"
    },
    {
        "id": "57f5c681-a1f5-4053-be33-e9525e7eb00a",
        "name": "Prompt"
    }
]
```

   </TabItem>
</Tabs>

### Get List Of Components Liked By User

Retrieve a list of components that a user has liked.

<Tabs>
   <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
   '$LANGFLOW_URL/api/v1/store/users/likes' \
   -H 'accept: application/json' \
   -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
{
    "detail": "You must have a store API key set."
}
```

   </TabItem>
</Tabs>

### Like Component

Like a specific component by its ID.

<Tabs>
   <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
   '$LANGFLOW_URL/api/v1/store/users/likes/{component_id}' \
   -H 'accept: application/json' \
   -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
reuslt
```

   </TabItem>
</Tabs>


## Users

### Add User

Add a new user to the database.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/users/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // UserCreate object
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // UserRead object
}
```

  </TabItem>
</Tabs>

### Read All Users

Retrieve a list of users from the database with pagination.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/users/?skip=0&limit=10' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "total_count": 2,
    "users": [
        {
            "id": "aa8ac16d-8400-459d-b683-f6ae72b22469",
            "username": "langflow",
            "profile_image": null,
            "store_api_key": null,
            "is_active": true,
            "is_superuser": true,
            "create_at": "2024-12-02T20:03:38.395299",
            "updated_at": "2024-12-04T21:43:59.385038",
            "last_login_at": "2024-12-04T21:43:59.384330"
        },
        {
            "id": "941f6379-5689-42c9-8ced-7c1e8366ff12",
            "username": "<string>",
            "profile_image": null,
            "store_api_key": null,
            "is_active": false,
            "is_superuser": false,
            "create_at": "2024-12-04T21:42:29.102577",
            "updated_at": "2024-12-04T21:42:29.102585",
            "last_login_at": null
        }
    ]
}
```

  </TabItem>
</Tabs>

### Read Current User

Retrieve the current user's data.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/users/whoami' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "id": "aa8ac16d-8400-459d-b683-f6ae72b22469",
    "username": "langflow",
    "profile_image": null,
    "store_api_key": null,
    "is_active": true,
    "is_superuser": true,
    "create_at": "2024-12-02T20:03:38.395299",
    "updated_at": "2024-12-04T21:43:59.385038",
    "last_login_at": "2024-12-04T21:43:59.384330"
}
```

  </TabItem>
</Tabs>

### Patch User

Update an existing user's data.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  '$LANGFLOW_URL/api/v1/users/{user_id}' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // UserUpdate object
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // UserRead object
}
```

  </TabItem>
</Tabs>

### Delete User

Delete a user from the database.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/users/{user_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
<TabItem value="result" label="Result">

```plain
{
  // UserRead object
}
```

  </TabItem>
</Tabs>

### Reset Password

Reset a user's password.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  '$LANGFLOW_URL/api/v1/users/{user_id}/reset-password' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // UserUpdate object for password reset
  }'
```

  </TabItem>
<TabItem value="result" label="Result">

```plain
{
  // UserRead object
}
```

  </TabItem>
</Tabs>

## APIKey

### Get API Keys

Retrieve a list of API keys.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/api_key/' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "total_count": 2,
    "user_id": "aa8ac16d-8400-459d-b683-f6ae72b22469",
    "api_keys": [
        {
            "name": "test",
            "last_used_at": null,
            "total_uses": 0,
            "is_active": true,
            "id": "6a554940-bbb2-4108-81eb-995712d6d6de",
            "api_key": "sk-bfAnq**************************************",
            "user_id": "aa8ac16d-8400-459d-b683-f6ae72b22469",
            "created_at": "2024-12-04T21:15:28.096576"
        },
        {
            "name": "another-key",
            "last_used_at": null,
            "total_uses": 0,
            "is_active": true,
            "id": "f322a178-b808-42cf-b9fa-7564afc177cd",
            "api_key": "sk-VVH6_**************************************",
            "user_id": "aa8ac16d-8400-459d-b683-f6ae72b22469",
            "created_at": "2024-12-04T22:13:09.128912"
        }
    ]
}
```

  </TabItem>
</Tabs>

### Create API Key

Create a new API key.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/api_key/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // ApiKeyCreate object
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // UnmaskedApiKeyRead object
}
```

  </TabItem>
</Tabs>

### Delete API Key

Delete a specific API key.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/api_key/{api_key_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // UnmaskedApiKeyRead object
}
```

  </TabItem>
</Tabs>

### Save Store API Key

Save an API key to the store.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/api_key/store' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // ApiKeyCreateRequest object
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // UnmaskedApiKeyRead object
}
```

  </TabItem>
</Tabs>

## Login

### Login To Get Access Token

Obtain an access token by logging in.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=YOUR_USERNAME&password=YOUR_PASSWORD'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // Token object
}
```

  </TabItem>
</Tabs>

### Auto Login

Perform an automatic login.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/auto_login' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "access_token": "ey...",
    "refresh_token": null,
    "token_type": "bearer"
}
```

  </TabItem>
</Tabs>

### Refresh Token

Refresh the current access token.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/refresh' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// Response content
```

  </TabItem>
</Tabs>

### Logout

Perform a logout operation.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/logout' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "message": "Logout successful"
}
```

  </TabItem>
</Tabs>

## Variables

### Update Variable

Update a variable.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  '$LANGFLOW_URL/api/v1/variables/{variable_id}' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
  "name": "updated_variable_name",
  "value": "updated_value"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "id": "variable_id",
  "name": "updated_variable_name",
  "value": "updated_value"
}
```

  </TabItem>
</Tabs>

### Delete Variable

Delete a variable.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/variables/{variable_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "message": "Variable deleted successfully"
}
```

  </TabItem>
</Tabs>

## Files

### Upload File

Upload a file to a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/files/upload/{flow_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/your/file'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // UploadFileResponse object
}
```

  </TabItem>
</Tabs>

### Download File

Download a specific file for a given flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/download/{flow_id}/{file_name}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// File content
```

  </TabItem>
</Tabs>

### Download Image

Download an image file for a given flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/images/{flow_id}/{file_name}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// Image file content
```

  </TabItem>
</Tabs>

### Download Profile Picture

Download a profile picture from a specific folder.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/profile_pictures/{folder_name}/{file_name}' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// Profile picture file content
```

  </TabItem>
</Tabs>

### List Profile Pictures

Retrieve a list of available profile pictures.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/profile_pictures/list' \
  -H 'accept: application/json'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
    "files": [
        "People/People Avatar-01-20.svg",
        "People/People Avatar-01-08.svg",
        "People/People Avatar-01-09.svg",
    ...
    ]
}
```

  </TabItem>
</Tabs>

### List Files

List all files associated with a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/files/list/{flow_id}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// List of files
```

  </TabItem>
</Tabs>

### Delete File

Delete a specific file from a flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/files/delete/{flow_id}/{file_name}' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// Deletion confirmation
```

  </TabItem>
</Tabs>



