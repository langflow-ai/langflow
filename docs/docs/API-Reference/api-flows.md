---
title: Flow management endpoints
slug: /api-flows
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/flows` endpoint to create, read, update, and delete flows.

If you want to use the Langflow API to run a flow, see [Flow trigger endpoints](/docs/api-flows-run).

## Create flow

Creates a new flow.

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

## Create flows

Creates multiple new flows, returning an array of flow objects.

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
    }
  ]
}'
```

## Read flow

Retrieves a specific flow by its ID.

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

## Read flows

Returns a JSON object containing a list of flows.

Retrieve all flows with pagination:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/?remove_example_flows=false&components_only=false&get_all=true&header_flows=false&page=1&size=50" \
  -H "accept: application/json"
```

To retrieve flows from a specific project, use the `project_id` query parameter:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/?remove_example_flows=true&components_only=false&get_all=false&project_id=$PROJECT_ID&header_flows=false&page=1&size=1" \
  -H "accept: application/json"
```

## Read sample flows

Retrieves a list of sample flows:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/flows/basic_examples/" \
  -H "accept: application/json"
```

## Update flow

Updates an existing flow by its ID.

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
}
```

  </TabItem>
</Tabs>

## Delete flow

Deletes a specific flow by its ID.

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

## Export flows

Exports specified flows to a ZIP file.

This endpoint downloads a ZIP file containing [Langflow JSON files](/docs/concepts-flows#langflow-json-file-contents) for each flow ID listed in the request body.

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

## Import flows

Imports flows by uploading a [Langflow-compatible JSON file](/docs/concepts-flows#langflow-json-file-contents).

To specify a target project for the flow, include the query parameter `project_id`.
The target `project_id` must already exist before uploading a flow. Call the [/api/v1/projects/](/docs/api-projects#read-projects) endpoint for a list of available projects.

This example uploads a local file named `agent-with-astra-db-tool.json` to a project specified by a `PROJECT_ID` variable.

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