# OpenAI Responses API

> Part of **Langflow**

---

## `POST` /api/v1/responses

> Create Response


Create a response using OpenAI Responses API format.

This endpoint accepts a flow_id in the model parameter and processes
the input through the specified Langflow flow.

Args:
    request: OpenAI Responses API request with model (flow_id) and input
    background_tasks: FastAPI background task manager
    api_key_user: Authenticated user from API key
    http_request: The incoming HTTP request
    telemetry_service: Telemetry service for logging

Returns:
    OpenAI-compatible response or streaming response

Raises:
    HTTPException: For validation errors or flow execution issues


**Operation ID:** `create_response_api_v1_responses_post`



### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` / API Key (`x-api-key`) | ✅ |
| Content-Type | `application/json` | ✅ |

### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `model` | string | ✅ Yes | The flow ID to execute (used instead of OpenAI model) |
  | `input` | string | ✅ Yes | The input text to process |
  | `stream` | boolean | ❌ No | Whether to stream the response |
  | `background` | boolean | ❌ No | Whether to process in background |
  | `tools` | array[object] | ❌ No | Tools are not supported yet |
  | `previous_response_id` | string | ❌ No | ID of previous response to continue conversation |
  | `include` | array[string] | ❌ No | Additional response data to include, e.g., ['tool_call.results'] |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
