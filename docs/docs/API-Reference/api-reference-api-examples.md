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

:::tip Try it
For an example of the Langflow API in a script, see the [Langflow quickstart](/get-started-quickstart).

The quickstart demonstrates how to get automatically generated code snippets for your flows, use a script to run a flow, and extract data from the Langfow API response.
:::

## Form Langflow API requests

While individual options vary by endpoint, all Langflow API requests share some commonalities, like a URL, method, parameters, and authentication.

As an example of a Langflow API request, the following curl command calls the `/v1/run` endpoint, and it passes a runtime override (`tweaks`) to the flow's Chat Output component:

```bash
curl --request POST \
  --url "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID?stream=false" \
  --header "Content-Type: application/json" \
  --header "x-api-key: $LANGFLOW_API_KEY" \
  --data '{
  "input_value": "hello world!",
  "output_type": "chat",
  "input_type": "chat",
  "tweaks": {
    "ChatOutput-6zcZt": {
      "should_store_message": true
    }
  }
}'
```

### Base URL

By default, local deployments serve the Langflow API at `http://localhost:7860/api`.

Remotely hosted Langflow deployments are available at the domain set by the hosting service, such as `http://IP_OR_DNS/api` or `http://IP_OR_DNS:LANGFLOW_PORT/api`.

You can configure the Langflow port number in the `LANGFLOW_PORT` [environment variable](/environment-variables).

* `https://UUID.ngrok.app/api`
* `http://IP_OR_DNS/api`
* `http://IP_OR_DNS:LANGFLOW_PORT/api`

### Authentication

As of Langflow v1.5, all API requests require a Langflow API key, even when `AUTO_LOGIN` is enabled.

The only exceptions are the MCP endpoints at `/v1/mcp`, `/v1/mcp-projects`, and `/v2/mcp`.
These endpoints don't require authentication, regardless of the `AUTO_LOGIN` setting.

You must provide a valid Langflow API key in either an `x-api-key` header or a query parameter.
For more information, see [API keys](/configuration-api-keys).

<details closed>
<summary>Auto-login and API key authentication in earlier Langflow versions</summary>

Prior to Langflow v1.5, when `AUTO_LOGIN` was enabled with `AUTO_LOGIN=true`, Langflow automatically logged users in as a superuser without requiring authentication, and API requests could be made without a Langflow API key.

If you set `SKIP_AUTH_AUTO_LOGIN=true`, authentication will be skipped entirely, and API requests will not require a Langflow API key, regardless of the `AUTO_LOGIN` setting.

</details>

As with any API, follow industry best practices for storing and referencing sensitive credentials.
For example, you can [set environment variables](#set-environment-variables) for your API keys, and then reference those environment variables in your API requests.

### Methods, paths, and parameters

Langflow API requests use various methods, paths, path parameters, query parameters, and body parameters.
The specific requirements and options depend on the endpoint that you want to call.

For example, to create a flow, you pass a JSON-formatted flow definition to `POST /v1/flows`.
Then, to run your flow, you call `POST /v1/run/$FLOW_ID` with optional run parameters in the request body.

### API versions

The Langflow API serves `/v1` and `/v2` endpoints.

Some endpoints only exist under a single version and some exist under both the `/v1` and `/v2` versions.

If a request fails or has an unexpected result, make sure your endpoint path has the correct version.

## Set environment variables

You can store commonly used values in environment variables to facilitate reuse, simplify token rotation, and securely reference sensitive values.

You can use any method you prefer to set environment variables, such as `export`, `.env`, `zshrc`, or `.curlrc`.
Then, reference those environment variables in your API requests.
For example:

```bash
# Set environment variables
export LANGFLOW_API_KEY="sk..."
export LANGFLOW_SERVER_URL="https://localhost:7860"
export FLOW_ID="359cd752-07ea-46f2-9d3b-a4407ef618da"
export PROJECT_ID="1415de42-8f01-4f36-bf34-539f23e47466"
export LANGFLOW_API_KEY="sk-..."

# Use environment variables in API requests
curl --request POST \
  --url "$LANGFLOW_SERVER_URL/api/v1/run/$FLOW_ID$?stream=false" \
  --header "Content-Type: application/json" \
  --header "x-api-key: $LANGFLOW_API_KEY" \
  --data '{
  "input_value": "hello world!",
  "output_type": "chat",
  "input_type": "chat",
  "tweaks": {
    "ChatOutput-6zcZt": {
      "should_store_message": true
    }
  }
}'
```

Commonly used values in Langflow API requests include your [Langflow server URL](#base-url), [Langflow API keys](/configuration-api-keys), flow IDs, and [project IDs](/api-projects#read-projects).

You can retrieve flow IDs from the [**API access** pane](/concepts-publish#api-access), in a flow's URL, and with [`GET /flows`](/api-flows#read-flows).

## Try some Langflow API requests

Once you have your Langflow server URL, try calling these endpoints that return Langflow metadata.

### Get version

Returns the current Langflow API version:

```bash
curl -X GET \
  "$LANGFLOW_SERVER_URL/api/v1/version" \
  -H "accept: application/json"
  -H "x-api-key: $LANGFLOW_API_KEY"
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
  "$LANGFLOW_SERVER_URL/api/v1/config" \
  -H "accept: application/json"
  -H "x-api-key: $LANGFLOW_API_KEY"
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
  "$LANGFLOW_SERVER_URL/api/v1/all" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

## Next steps

- Use the Langflow API to [run a flow](/api-flows-run).
- Use the Langflow API to [upload files](/api-files).
- Use the Langflow API to [get flow logs](/api-logs).
- Explore all endpoints in the [Langflow API specification](/api).