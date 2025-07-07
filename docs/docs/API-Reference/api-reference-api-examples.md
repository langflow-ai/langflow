---
title: Get started with the Langflow API
slug: /api-reference-api-examples
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

You can use the Langflow API for programmatic interactions with Langflow, such as the following:

* Create and edit flows, including file management for flows.
* Develop applications that use your flows.
* Develop custom components.
* Build Langflow as a dependency of a larger project.
* Contribute to the overall Langflow project.

To view and test all available endpoints, you can access the Langflow API's OpenAPI specification at your Langflow deployment's `/docs` endpoint, such as `http://localhost:7860/docs`.

:::tip
For an example of the Langflow API in a script, see the [Langflow quickstart](/docs/get-started-quickstart).

The quickstart demonstrates how to get automatically generated code snippets for your flows, use a script to run a flow, and extract data from the Langfow API response.
:::

## Form Langflow API requests

While individual parameters vary by endpoint, all Langflow API requests share some commonalities.

### Base URL

Local deployments serve the Langflow API at `http://localhost:LANGFLOW_PORT/api`.
The default port is 7868 or 7860:

* Local Langflow Desktop: `http://localhost:7868/api`
* Local Langflow OSS: `http://localhost:7860/api`
* Local Langflow Docker image: `http://localhost:7860/api`

Remotely hosted Langflow deployments are available at the domain set by the hosting service.
For example:

* `https://UUID.ngrok.app/api`
* `http://IP_OR_DNS/api`
* `http://IP_OR_DNS:LANGFLOW_PORT/api`

:::tip
The Langflow port number is set in the `LANGFLOW_PORT` [environment variable](/docs/environment-variables).
::::

### Authentication

Your [Langflow deployment's authentication settings](/docs/configuration-authentication) determine whether Langflow API requests require explicit authentication with a Langflow API key.

If explicit authentication is required, you must provide a valid Langflow API key in either an `x-api-key` header or query parameter.
For more information, see [API keys](/docs/configuration-api-keys).

Because authentication isn't always required, Langflow API examples in the Langflow documentation often omit authentication.

### Methods, paths, and parameters

Langflow API requests use a variety of methods, paths, path parameters, query parameters, and body parameters.
The specific requirements and options depend on the endpoint that you want to call.

For example, to create a flow, you pass a JSON-formatted flow definition to `POST /v1/flows`.
Then, to run your flow, you call `POST /v1/run/$FLOW_ID` with optional run parameters in the request body.

### Versions

The Langflow API serves `/v1` and `/v2` endpoints.

Some endpoints only exist under a single version and some exist under both the `/v1` and `/v2` versions.

If a request fails or has an unexpected result, make sure your endpoint path has the correct version.

## Set environment variables

As a best practice with any API, store commonly used values in environment variables to facilitate reuse, simplify token rotation, and securely reference sensitive values.
You can use any method you prefer to set environment variables, such as `export`, `.env`, `zshrc`, or `.curlrc`.
Additionally, be sure to follow industry best practices when storing credentials and other sensitive values.

You might find it helpful to set environment variables for values like your Langflow server URL, Langflow API keys, flow IDs, and project IDs.
For example:

```bash
export LANGFLOW_URL="http://localhost:7860"
export FLOW_ID="359cd752-07ea-46f2-9d3b-a4407ef618da"
export PROJECT_ID="1415de42-8f01-4f36-bf34-539f23e47466"
export API_KEY="sk-..."
```

:::tip
- You can find flow IDs on the [Publish pane](/docs/concepts-publish), in a flow's URL, and with [`GET /flows`](/docs/api-flows#read-flows).
- You can retrieve project IDs with `GET /projects`(/api-projects#read-projects).
:::

## Try some Langflow API requests

Once you have your Langflow server URL, try calling these endpoints that return Langflow metadata.

If authentication is required, include an `x-api-key` header or query parameter with a valid [Langflow API key](/docs/configuration-api-keys), such as `-H 'x-api-key: $API_KEY'`.

### Get version

Returns the current Langflow API version:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/version" \
  -H "accept: application/json"
```

<details>
<summary>Result</summary>
```text
{
    "version": "1.1.1",
    "main_version": "1.1.1",
    "package": "Langflow"
}
```
</details>

### Get configuration

Returns configuration details for your Langflow deployment:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/config" \
  -H "accept: application/json"
```

<details>
<summary>Result</summary>
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
</details>

### Get all components

Returns a dictionary of all Langflow components:

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/all" \
  -H "accept: application/json"
```

## Next steps

- Use the Langflow API to [run a flow](/docs/api-flows-run).
- Use the Langflow API to [upload files](/docs/api-files).
- Use the Langflow API to [get flow logs](/docs/api-logs).
- Explore all endpoints in the [Langflow API specification](/api).