---
title: API Reference
slug: /api-reference
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
   -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
   -d '{
       // Flow creation details
     }'
```

   </TabItem>
   <TabItem value="result" label="Result">

```plain
result
```

   </TabItem>
</Tabs>

### Read Flows

Retrieve a list of flows with pagination support.

<Tabs>
   <TabItem value="curl" label="curl" default>

```bash
curl -X GET "$LANGFLOW_URL/api/v1/flows/"
-H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

   </TabItem>

<TabItem value="result" label="Result">

```plain
result
```

   </TabItem>
</Tabs>

### Read Flow

Read a specific flow by its ID.

<Tabs>
<TabItem value="curl" label="curl" default>

```bash
 curl-X GET "$ LANGFLOW_URL /api /v1 /flows /{flow_id}"
-H “ Authorization : Bearer YOUR_ACCESS_TOKEN”
 ```

</TabItem>

<TabItem value="result" label="Result">

```plain
result
```

   </TabItem>
</Tabs>

### Update Flow

Update an existing flow by its ID.

<Tabs>
<TabItem value="curl" label="curl" default>

 ```bash
 curl-X PATCH "$ LANGFLOW_URL /api /v1 /flows /{flow_id}"
-H “ Authorization : Bearer YOUR_ACCESS_TOKEN”
-d '{
      // Updated flow details
}'
 ```

</TabItem>
<TabItem value="result" label="Result">

```plain
result
```

   </TabItem>
</Tabs>

### Delete Flow

Delete a specific flow by its ID.

<Tabs>
    <TabItem value="curl" label="curl" default>

 ```bash
 curl-X DELETE "$ LANGFLOW_URL /api /v1 /flows /{flow_id}"
-H “ Authorization : Bearer YOUR_ACCESS_TOKEN”
 ```

</TabItem>

<TabItem value="result" label="Result">

```plain
result
```

   </TabItem>
</Tabs>

### Create Flows

Create multiple new flows.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/flows/batch/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // FlowListCreate object
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
  {
    // FlowRead objects
  }
]
```

  </TabItem>
</Tabs>

### Upload File

Upload flows from a file.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/flows/upload/?folder_id=OPTIONAL_FOLDER_ID' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/path/to/your/file'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
  {
    // FlowRead objects
  }
]
```

  </TabItem>
</Tabs>

### Download Multiple Files

Download multiple flows as a zip file.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'POST' \
  '$LANGFLOW_URL/api/v1/flows/download/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '["FLOW_ID_1", "FLOW_ID_2"]'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
// Binary file content (ZIP)
```

  </TabItem>
</Tabs>

### Read Basic Examples

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

## Monitor

### Get Vertex Builds

Retrieve Vertex Builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/monitor/builds?flow_id=YOUR_FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // VertexBuildMapModel
}
```

  </TabItem>
</Tabs>

### Delete Vertex Builds

Delete Vertex Builds for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/monitor/builds?flow_id=YOUR_FLOW_ID' \
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

### Get Messages

Retrieve messages with optional filters.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/monitor/messages?flow_id=YOUR_FLOW_ID&session_id=YOUR_SESSION_ID&sender=SENDER&sender_name=SENDER_NAME&order_by=timestamp' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
  {
    // MessageResponse
  }
]
```

  </TabItem>
</Tabs>

### Delete Messages

Delete specific messages by their IDs.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'DELETE' \
  '$LANGFLOW_URL/api/v1/monitor/messages' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '["MESSAGE_ID_1", "MESSAGE_ID_2"]'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
204 No Content
```

  </TabItem>
</Tabs>

### Update Message

Update a specific message by its ID.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PUT' \
  '$LANGFLOW_URL/api/v1/monitor/messages/MESSAGE_ID' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -d '{
    // MessageUpdate object
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  // MessageRead object
}
```

  </TabItem>
</Tabs>

### Update Session ID

Update the session ID for messages.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'PATCH' \
  '$LANGFLOW_URL/api/v1/monitor/messages/session/OLD_SESSION_ID?new_session_id=NEW_SESSION_ID' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
  {
    // MessageResponse
  }
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
  '$LANGFLOW_URL/api/v1/monitor/messages/session/SESSION_ID' \
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

### Get Transactions

Retrieve transactions for a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/monitor/transactions?flow_id=YOUR_FLOW_ID' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
TransactionReadResponse
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


