---
title: Projects endpoints
slug: /api-projects
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/projects` endpoint to create, read, update, and delete projects.

Projects store your flows and components.

## Read projects

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

## Create project

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

## Read project

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

## Update project

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

## Delete project

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

## Download project

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

## Upload project

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