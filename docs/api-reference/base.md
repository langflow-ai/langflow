# Base

> Part of **Langflow**

---

## `GET` /api/v1/all

> Get All


Retrieve all component types with compression for better performance.

Returns a compressed response containing all available component types.


**Operation ID:** `get_all_api_v1_all_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `POST` /api/v1/run/{flow_id_or_name}

> Simplified Run Flow


Executes a specified flow by ID with support for streaming and telemetry (API key auth).

This endpoint executes a flow identified by ID or name, with options for streaming the response
and tracking execution metrics. It handles both streaming and non-streaming execution modes.
This endpoint uses API key authentication (Bearer token).

Args:
    background_tasks (BackgroundTasks): FastAPI background task manager
    flow (FlowRead | None): The flow to execute, loaded via dependency
    input_request (SimplifiedAPIRequest | None): Input parameters for the flow
    stream (bool): Whether to stream the response
    api_key_user (UserRead): Authenticated user from API key
    context (dict | None): Optional context to pass to the flow
    http_request (Request): The incoming HTTP request for extracting global variables

Returns:
    Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results
    or a RunResponse with the complete execution results

Raises:
    HTTPException: For flow not found (404) or invalid input (400)
    APIException: For internal execution errors (500)

Notes:
    - Supports both streaming and non-streaming execution modes
    - Tracks execution time and success/failure via telemetry
    - Handles graceful client disconnection in streaming mode
    - Provides detailed error handling with appropriate HTTP status codes
    - Extracts global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*
    - Merges extracted variables with the context parameter as "request_variables"
    - In streaming mode, uses EventManager to handle events:
        - "add_message": New messages during execution
        - "token": Individual tokens during streaming
        - "end": Final execution result
    - Authentication: Requires API key (Bearer token)


**Operation ID:** `simplified_run_flow_api_v1_run__flow_id_or_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** | string | ✅ Yes | - |
| `stream` | **query** | boolean | ❌ No | - |
| `user_id` | **query** | string | ❌ No | - |


### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` / API Key (`x-api-key`) | ✅ |
| Content-Type | `application/json` | ✅ |

### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `input_request` | object | ❌ No | - |
  | `context` | object | ❌ No | - |
  **`input_request`** ❌





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
## `POST` /api/v1/webhook/{flow_id_or_name}

> Webhook Run Flow


Run a flow using a webhook request.

Args:
    flow_id_or_name: The flow ID or endpoint name (used by dependency).
    flow: The flow to be executed.
    request: The incoming HTTP request.

Returns:
    A dictionary containing the status of the task.

Raises:
    HTTPException: If the flow is not found or if there is an error processing the request.


**Operation ID:** `webhook_run_flow_api_v1_webhook__flow_id_or_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** | string | ✅ Yes | - |
| `user_id` | **query** | string | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **202** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `POST` /api/v1/run/advanced/{flow_id_or_name}

> Experimental Run Flow


Executes a specified flow by ID with optional input values, output selection, tweaks, and streaming capability.

This endpoint supports running flows with caching to enhance performance and efficiency.

### Parameters:
- `flow` (Flow): The flow object to be executed, resolved via dependency injection.
- `inputs` (List[InputValueRequest], optional): A list of inputs specifying the input values and components
  for the flow. Each input can target specific components and provide custom values.
- `outputs` (List[str], optional): A list of output names to retrieve from the executed flow.
  If not provided, all outputs are returned.
- `tweaks` (Optional[Tweaks], optional): A dictionary of tweaks to customize the flow execution.
  The tweaks can be used to modify the flow's parameters and components.
  Tweaks can be overridden by the input values.
- `stream` (bool, optional): Specifies whether the results should be streamed. Defaults to False.
- `session_id` (Union[None, str], optional): An optional session ID to utilize existing session data for the flow
  execution.
- `api_key_user` (User): The user associated with the current API key. Automatically resolved from the API key.

### Returns:
A `RunResponse` object containing the selected outputs (or all if not specified) of the executed flow
and the session ID.
The structure of the response accommodates multiple inputs, providing a nested list of outputs for each input.

### Raises:
HTTPException: Indicates issues with finding the specified flow, invalid input formats, or internal errors during
flow execution.

### Example usage:
```json
POST /run/flow_id
x-api-key: YOUR_API_KEY
Payload:
{
    "inputs": [
        {"components": ["component1"], "input_value": "value1"},
        {"components": ["component3"], "input_value": "value2"}
    ],
    "outputs": ["Component Name", "component_id"],
    "tweaks": {"parameter_name": "value", "Component Name": {"parameter_name": "value"}, "component_id": {"parameter_name": "value"}},    "stream": false
}
```

This endpoint facilitates complex flow executions with customized inputs, outputs, and configurations,
catering to diverse application requirements.


**Operation ID:** `experimental_run_flow_api_v1_run_advanced__flow_id_or_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** | string | ✅ Yes | - |
| `user_id` | **query** | string | ❌ No | - |


### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` / API Key (`x-api-key`) | ✅ |
| Content-Type | `application/json` | ✅ |

### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `inputs` | array[object] | ❌ No | - |
  | `outputs` | array[string] | ❌ No | - |
  | `tweaks` | object | ❌ No | A dictionary of tweaks to adjust the flow's execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values. |
  | `stream` | boolean | ❌ No | - |
  | `session_id` | string | ❌ No | - |
  **`inputs`** — Array of `object`





### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `outputs` | array[object] | - |
| `session_id` | string | - |
**`outputs`** — Array of `object`

  **`outputs`** — Array of `object`

    **`messages`** — Array of `object`

      **`files`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/version

> Get Version


**Operation ID:** `get_version_api_v1_version_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `GET` /api/v1/config

> Get Config


Retrieve application configuration settings.

Returns different configuration based on authentication status:
- Authenticated users: Full ConfigResponse with all settings
- Unauthenticated users: PublicConfigResponse with limited, safe-to-expose settings

Args:
    user: The authenticated user, or None if unauthenticated.

Returns:
    ConfigResponse | PublicConfigResponse: Configuration settings appropriate for the user's auth status.

Raises:
    HTTPException: If an error occurs while retrieving the configuration.


**Operation ID:** `get_config_api_v1_config_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `max_file_size_upload` | integer | - |
| `event_delivery` | string = `polling` \| `streaming` \| `direct` | - |
| `voice_mode_available` | boolean | - |
| `frontend_timeout` | integer | - |
| `type` | string | - |
| `feature_flags` | object | - |
| `serialization_max_items_length` | integer | - |
| `serialization_max_text_length` | integer | - |
| `auto_saving` | boolean | - |
| `auto_saving_interval` | integer | - |
| `health_check_max_retries` | integer | - |
| `webhook_polling_interval` | integer | - |
| `public_flow_cleanup_interval` | integer | - |
| `public_flow_expiration` | integer | - |
| `webhook_auth_enable` | boolean | - |
| `default_folder_name` | string | - |
| `hide_getting_started_progress` | boolean | - |
**`feature_flags`** ✅




---
