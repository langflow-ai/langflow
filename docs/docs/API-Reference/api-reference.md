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
  -d '{
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
  -d '{
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
  -d '{
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

Get the version of the API.

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
  "version": "API version number"
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
  "config_data": "Configuration information"
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
true
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
true
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

```plain

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

## Delete Variable

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

## Folders

## Create Folder

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
  "name": "New Folder"
}'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
{
  "id": "folder_id",
  "name": "New Folder"
}
```

  </TabItem>
</Tabs>

### Read Folders

Retrieve a list of folders.

<Tabs>
  <TabItem value="curl" label="curl" default>

```curl
curl -X 'GET' \
  '$LANGFLOW_URL/api/v1/folders/' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

  </TabItem>
  <TabItem value="result" label="Result">

```plain
[
  {
    "id": "folder_id_1",
    "name": "Folder 1"
  },
  {
    "id": "folder_id_2",
    "name": "Folder 2"
  }
]
```

  </TabItem>
</Tabs>

### Update Folder

Update an existing folder.

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

## Delete Folder

Delete a folder.

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
{
  "message": "Folder deleted successfully"
}
```

  </TabItem>
</Tabs>







