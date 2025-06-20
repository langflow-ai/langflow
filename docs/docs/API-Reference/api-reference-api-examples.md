---
title: Get started with the Langflow API
slug: /api-reference-api-examples
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

You can use the Langflow API to manage your Langflow deployment, build flows, and develop applications that use your flows.

:::tip
You can view and test the Langflow API's OpenAPI specification at your Langflow deployment's `/docs` endpoint, such as `http://localhost:7860/docs`.
:::

<!-- TODO: Add basic information: How to get an API key, flow IDs, component IDs, base url etc. -->
<!-- Bring aPI key and auth stuff from those topics in the Config section.-->
<!-- List all deprecated endpoints somewhere?-->

## Form requests
<!-- Forming requests: Authentication, Base urls, parameters -->
Langflow API requests ...

### Base URL

### Authentication

### Parameters

Langflow endpoints use URL path parameters, query parameters, and request body parameters.

The specific parameters and where you can declare them vary by endpoint and operation.

## Set environment variables
<!-- Rewrite "export values" section and update incoming links. -->
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
To find your project ID, call the Langflow [/api/v1/projects/](/api-projects#read-projects) endpoint for a list of projects.
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

## Send requests

Try sending some minimal requests to get Langflow configuration information.

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

### Get configuration

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

### Get all components

This operation returns a dictionary of all Langflow components.

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/all" \
  -H "accept: application/json"
```

## Next steps

- Use the Langflow API to [run a flow](/api-flows-run).
- Use the Langflow API to [upload files](/api-flows).
- Use the Langflow API to [get flow logs](/api-logs).
- Explore all endpoints in the [Langflow API specification](/api).