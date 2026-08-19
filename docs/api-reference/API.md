# API Reference

> **Langflow** — Version 1.8.0

---

## `/api/v1/build/{flow_id}/flow`

### POST /api/v1/build/{flow_id}/flow

> **Build Flow**


Build and process a flow, returning a job ID for event polling.

This endpoint requires authentication through the CurrentActiveUser dependency.
For public flows that don't require authentication, use the /build_public_tmp/flow_id/flow endpoint.

Args:
    flow_id: UUID of the flow to build
    background_tasks: Background tasks manager
    inputs: Optional input values for the flow
    data: Optional flow data
    files: Optional files to include
    stop_component_id: Optional ID of component to stop at
    start_component_id: Optional ID of component to start from
    log_builds: Whether to log the build process
    current_user: The authenticated user
    queue_service: Queue service for job management
    flow_name: Optional name for the flow
    event_delivery: Optional event delivery type - default is streaming

Returns:
    Dict with job_id that can be used to poll for build status


**Operation ID:** `build_flow_api_v1_build__flow_id__flow_post`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |
| `stop_component_id` | **query** | string | ❌ No | - |
| `start_component_id` | **query** | string | ❌ No | - |
| `log_builds` | **query** | boolean | ❌ No | - |
| `flow_name` | **query** | string | ❌ No | - |
| `event_delivery` | **query** | string | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `inputs` | object | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `files` | array[string] | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/build/{job_id}/events`

### GET /api/v1/build/{job_id}/events

> **Get Build Events**


Get events for a specific build job.

Requires authentication to prevent unauthorized access to build events.


**Operation ID:** `get_build_events_api_v1_build__job_id__events_get`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** | string | ✅ Yes | - |
| `event_delivery` | **query** | string | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/build/{job_id}/cancel`

### POST /api/v1/build/{job_id}/cancel

> **Cancel Build**


Cancel a specific build job.

Requires authentication to prevent unauthorized build cancellation.


**Operation ID:** `cancel_build_api_v1_build__job_id__cancel_post`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `success` | boolean | - |
| `message` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/build_public_tmp/{flow_id}/flow`

### POST /api/v1/build_public_tmp/{flow_id}/flow

> **Build Public Tmp**


Build a public flow without requiring authentication.

This endpoint is specifically for public flows that don't require authentication.
It uses a client_id cookie to create a deterministic flow ID for tracking purposes.

The endpoint:
1. Verifies the requested flow is marked as public in the database
2. Creates a deterministic UUID based on client_id and flow_id
3. Uses the flow owner's permissions to build the flow

Requirements:
- The flow must be marked as PUBLIC in the database
- The request must include a client_id cookie

Args:
    flow_id: UUID of the public flow to build
    background_tasks: Background tasks manager
    inputs: Optional input values for the flow
    data: Optional flow data
    files: Optional files to include
    stop_component_id: Optional ID of component to stop at
    start_component_id: Optional ID of component to start from
    log_builds: Whether to log the build process
    flow_name: Optional name for the flow
    request: FastAPI request object (needed for cookie access)
    queue_service: Queue service for job management
    event_delivery: Optional event delivery type - default is streaming

Returns:
    Dict with job_id that can be used to poll for build status


**Operation ID:** `build_public_tmp_api_v1_build_public_tmp__flow_id__flow_post`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |
| `stop_component_id` | **query** | string | ❌ No | - |
| `start_component_id` | **query** | string | ❌ No | - |
| `log_builds` | **query** | boolean | ❌ No | - |
| `flow_name` | **query** | string | ❌ No | - |
| `event_delivery` | **query** | string | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `inputs` | object | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `files` | array[string] | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/all`

### GET /api/v1/all

> **Get All**


Retrieve all component types with compression for better performance.

Returns a compressed response containing all available component types.


**Operation ID:** `get_all_api_v1_all_get`


**Tags:** `Base` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/run/{flow_id_or_name}`

### POST /api/v1/run/{flow_id_or_name}

> **Simplified Run Flow**


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


**Tags:** `Base` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** | string | ✅ Yes | - |
| `stream` | **query** | boolean | ❌ No | - |
| `user_id` | **query** | string | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `input_request` | object | ❌ No | - |
  | `context` | object | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/webhook/{flow_id_or_name}`

### POST /api/v1/webhook/{flow_id_or_name}

> **Webhook Run Flow**


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


**Tags:** `Base` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** | string | ✅ Yes | - |
| `user_id` | **query** | string | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **202** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/run/advanced/{flow_id_or_name}`

### POST /api/v1/run/advanced/{flow_id_or_name}

> **Experimental Run Flow**


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


**Tags:** `Base` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** | string | ✅ Yes | - |
| `user_id` | **query** | string | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `inputs` | array[object] | ❌ No | - |
  | `outputs` | array[string] | ❌ No | - |
  | `tweaks` | object | ❌ No | A dictionary of tweaks to adjust the flow's execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values. |
  | `stream` | boolean | ❌ No | - |
  | `session_id` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `outputs` | array[object] | - |
| `session_id` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/version`

### GET /api/v1/version

> **Get Version**


**Operation ID:** `get_version_api_v1_version_get`


**Tags:** `Base` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/config`

### GET /api/v1/config

> **Get Config**


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


**Tags:** `Base` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `max_file_size_upload` | integer | - |
| `event_delivery` | string | - |
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


---
## `/api/v1/flows/`

### POST /api/v1/flows/

> **Create Flow**


**Operation ID:** `create_flow_api_v1_flows__post`


**Tags:** `Flows` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `name` | string | ✅ Yes | - |
  | `description` | string | ❌ No | - |
  | `icon` | string | ❌ No | - |
  | `icon_bg_color` | string | ❌ No | - |
  | `gradient` | string | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `is_component` | boolean | ❌ No | - |
  | `updated_at` | string (date-time) | ❌ No | - |
  | `webhook` | boolean | ❌ No | Can be used on the webhook endpoint |
  | `endpoint_name` | string | ❌ No | - |
  | `tags` | array[string] | ❌ No | - |
  | `locked` | boolean | ❌ No | - |
  | `mcp_enabled` | boolean | ❌ No | Can be exposed in the MCP server |
  | `action_name` | string | ❌ No | The name of the action associated with the flow |
  | `action_description` | string | ❌ No | The description of the action associated with the flow |
  | `access_type` | string | ❌ No | - |
  | `user_id` | string (uuid) | ❌ No | - |
  | `folder_id` | string (uuid) | ❌ No | - |
  | `fs_path` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### GET /api/v1/flows/

> **Read Flows**


Retrieve a list of flows with pagination support.

Args:
    current_user (User): The current authenticated user.
    session (Session): The database session.
    settings_service (SettingsService): The settings service.
    components_only (bool, optional): Whether to return only components. Defaults to False.

    get_all (bool, optional): Whether to return all flows without pagination. Defaults to True.
    **This field must be True because of backward compatibility with the frontend - Release: 1.0.20**

    folder_id (UUID, optional): The project ID. Defaults to None.
    params (Params): Pagination parameters.
    remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.
    header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.

Returns:
    list[FlowRead] | Page[FlowRead] | list[FlowHeader]
    A list of flows or a paginated response containing the list of flows or a list of flow headers.


**Operation ID:** `read_flows_api_v1_flows__get`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `remove_example_flows` | **query** | boolean | ❌ No | - |
| `components_only` | **query** | boolean | ❌ No | - |
| `get_all` | **query** | boolean | ❌ No | - |
| `folder_id` | **query** | string (uuid) | ❌ No | - |
| `header_flows` | **query** | boolean | ❌ No | - |
| `page` | **query** | integer | ❌ No | - |
| `size` | **query** | integer | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `items` | array[object] | - |
| `total` | integer | - |
| `page` | integer | - |
| `size` | integer | - |
| `pages` | integer | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/flows/

> **Delete Multiple Flows**


Delete multiple flows by their IDs.

Args:
    flow_ids (List[str]): The list of flow IDs to delete.
    user (User, optional): The user making the request. Defaults to the current active user.
    db (Session, optional): The database session.

Returns:
    dict: A dictionary containing the number of flows deleted.


**Operation ID:** `delete_multiple_flows_api_v1_flows__delete`


**Tags:** `Flows` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Type:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/flows/{flow_id}`

### GET /api/v1/flows/{flow_id}

> **Read Flow**


Read a flow.


**Operation ID:** `read_flow_api_v1_flows__flow_id__get`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### PATCH /api/v1/flows/{flow_id}

> **Update Flow**


Update a flow.


**Operation ID:** `update_flow_api_v1_flows__flow_id__patch`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `name` | string | ❌ No | - |
  | `description` | string | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `folder_id` | string (uuid) | ❌ No | - |
  | `endpoint_name` | string | ❌ No | - |
  | `mcp_enabled` | boolean | ❌ No | - |
  | `locked` | boolean | ❌ No | - |
  | `action_name` | string | ❌ No | - |
  | `action_description` | string | ❌ No | - |
  | `access_type` | string | ❌ No | - |
  | `fs_path` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/flows/{flow_id}

> **Delete Flow**


Delete a flow.


**Operation ID:** `delete_flow_api_v1_flows__flow_id__delete`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/flows/public_flow/{flow_id}`

### GET /api/v1/flows/public_flow/{flow_id}

> **Read Public Flow**


Read a public flow.


**Operation ID:** `read_public_flow_api_v1_flows_public_flow__flow_id__get`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/flows/batch/`

### POST /api/v1/flows/batch/

> **Create Flows**


Create multiple new flows.


**Operation ID:** `create_flows_api_v1_flows_batch__post`


**Tags:** `Flows` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `flows` | array[object] | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/flows/upload/`

### POST /api/v1/flows/upload/

> **Upload File**


Upload flows from a file.


**Operation ID:** `upload_file_api_v1_flows_upload__post`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `folder_id` | **query** | string (uuid) | ❌ No | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `file` | string | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/flows/download/`

### POST /api/v1/flows/download/

> **Download Multiple File**


Download all flows as a zip file.


**Operation ID:** `download_multiple_file_api_v1_flows_download__post`


**Tags:** `Flows` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Type:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/flows/basic_examples/`

### GET /api/v1/flows/basic_examples/

> **Read Basic Examples**


Retrieve a list of basic example flows.

Args:
    session (Session): The database session.

Returns:
    list[FlowRead]: A list of basic example flows.


**Operation ID:** `read_basic_examples_api_v1_flows_basic_examples__get`


**Tags:** `Flows` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/users/`

### POST /api/v1/users/

> **Add User**


Add a new user to the database.

This endpoint allows public user registration (sign up).
User activation is controlled by the NEW_USER_IS_ACTIVE setting.


**Operation ID:** `add_user_api_v1_users__post`


**Tags:** `Users` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `username` | string | ✅ Yes | - |
  | `password` | string | ✅ Yes | - |
  | `optins` | object | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### GET /api/v1/users/

> **Read All Users**


Retrieve a list of users from the database with pagination.


**Operation ID:** `read_all_users_api_v1_users__get`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `skip` | **query** | integer | ❌ No | - |
| `limit` | **query** | integer | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `total_count` | integer | - |
| `users` | array[object] | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/users/whoami`

### GET /api/v1/users/whoami

> **Read Current User**


Retrieve the current user's data.


**Operation ID:** `read_current_user_api_v1_users_whoami_get`


**Tags:** `Users` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |


---
## `/api/v1/users/{user_id}`

### PATCH /api/v1/users/{user_id}

> **Patch User**


Update an existing user's data.


**Operation ID:** `patch_user_api_v1_users__user_id__patch`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `username` | string | ❌ No | - |
  | `profile_image` | string | ❌ No | - |
  | `password` | string | ❌ No | - |
  | `is_active` | boolean | ❌ No | - |
  | `is_superuser` | boolean | ❌ No | - |
  | `last_login_at` | string (date-time) | ❌ No | - |
  | `optins` | object | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/users/{user_id}

> **Delete User**


Delete a user from the database.


**Operation ID:** `delete_user_api_v1_users__user_id__delete`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/users/{user_id}/reset-password`

### PATCH /api/v1/users/{user_id}/reset-password

> **Reset Password**


Reset a user's password.


**Operation ID:** `reset_password_api_v1_users__user_id__reset_password_patch`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `username` | string | ❌ No | - |
  | `profile_image` | string | ❌ No | - |
  | `password` | string | ❌ No | - |
  | `is_active` | boolean | ❌ No | - |
  | `is_superuser` | boolean | ❌ No | - |
  | `last_login_at` | string (date-time) | ❌ No | - |
  | `optins` | object | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/files/upload/{flow_id}`

### POST /api/v1/files/upload/{flow_id}

> **Upload File**


**Operation ID:** `upload_file_api_v1_files_upload__flow_id__post`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `file` | string | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `flowId` | string | - |
| `file_path` | string (path) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/files/download/{flow_id}/{file_name}`

### GET /api/v1/files/download/{flow_id}/{file_name}

> **Download File**


**Operation ID:** `download_file_api_v1_files_download__flow_id___file_name__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_name` | **path** | string | ✅ Yes | - |
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/files/images/{flow_id}/{file_name}`

### GET /api/v1/files/images/{flow_id}/{file_name}

> **Download Image**


Download image from storage for browser rendering.


**Operation ID:** `download_image_api_v1_files_images__flow_id___file_name__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |
| `file_name` | **path** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/files/profile_pictures/{folder_name}/{file_name}`

### GET /api/v1/files/profile_pictures/{folder_name}/{file_name}

> **Download Profile Picture**


Download profile picture from local filesystem.

Profile pictures are first looked up in config_dir/profile_pictures/,
then fallback to the package's bundled profile_pictures directory.


**Operation ID:** `download_profile_picture_api_v1_files_profile_pictures__folder_name___file_name__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `folder_name` | **path** | string | ✅ Yes | - |
| `file_name` | **path** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/files/profile_pictures/list`

### GET /api/v1/files/profile_pictures/list

> **List Profile Pictures**


List profile pictures from local filesystem.

Profile pictures are first looked up in config_dir/profile_pictures/,
then fallback to the package's bundled profile_pictures directory.


**Operation ID:** `list_profile_pictures_api_v1_files_profile_pictures_list_get`


**Tags:** `Files` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/files/list/{flow_id}`

### GET /api/v1/files/list/{flow_id}

> **List Files**


**Operation ID:** `list_files_api_v1_files_list__flow_id__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/files/delete/{flow_id}/{file_name}`

### DELETE /api/v1/files/delete/{flow_id}/{file_name}

> **Delete File**


**Operation ID:** `delete_file_api_v1_files_delete__flow_id___file_name__delete`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_name` | **path** | string | ✅ Yes | - |
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/builds`

### GET /api/v1/monitor/builds

> **Get Vertex Builds**


**Operation ID:** `get_vertex_builds_api_v1_monitor_builds_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `vertex_builds` | object | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/monitor/builds

> **Delete Vertex Builds**


**Operation ID:** `delete_vertex_builds_api_v1_monitor_builds_delete`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/messages/sessions`

### GET /api/v1/monitor/messages/sessions

> **Get Message Sessions**


**Operation ID:** `get_message_sessions_api_v1_monitor_messages_sessions_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/messages`

### GET /api/v1/monitor/messages

> **Get Messages**


**Operation ID:** `get_messages_api_v1_monitor_messages_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ❌ No | - |
| `session_id` | **query** | string | ❌ No | - |
| `sender` | **query** | string | ❌ No | - |
| `sender_name` | **query** | string | ❌ No | - |
| `order_by` | **query** | string | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/monitor/messages

> **Delete Messages**


**Operation ID:** `delete_messages_api_v1_monitor_messages_delete`


**Tags:** `Monitor` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Type:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/messages/{message_id}`

### PUT /api/v1/monitor/messages/{message_id}

> **Update Message**


**Operation ID:** `update_message_api_v1_monitor_messages__message_id__put`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `message_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `text` | string | ❌ No | - |
  | `sender` | string | ❌ No | - |
  | `sender_name` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |
  | `context_id` | string | ❌ No | - |
  | `files` | array[string] | ❌ No | - |
  | `edit` | boolean | ❌ No | - |
  | `error` | boolean | ❌ No | - |
  | `properties` | object | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `timestamp` | string (date-time) | - |
| `sender` | string | - |
| `sender_name` | string | - |
| `session_id` | string | - |
| `context_id` | string | - |
| `text` | string | - |
| `files` | array[string] | - |
| `error` | boolean | - |
| `edit` | boolean | - |
| `properties` | object | - |
| `category` | string | - |
| `content_blocks` | array[object] | - |
| `id` | string (uuid) | - |
| `flow_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/messages/session/{old_session_id}`

### PATCH /api/v1/monitor/messages/session/{old_session_id}

> **Update Session Id**


**Operation ID:** `update_session_id_api_v1_monitor_messages_session__old_session_id__patch`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `old_session_id` | **path** | string | ✅ Yes | - |
| `new_session_id` | **query** | string | ✅ Yes | The new session ID to update to |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/messages/session/{session_id}`

### DELETE /api/v1/monitor/messages/session/{session_id}

> **Delete Messages Session**


**Operation ID:** `delete_messages_session_api_v1_monitor_messages_session__session_id__delete`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `session_id` | **path** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/transactions`

### GET /api/v1/monitor/transactions

> **Get Transactions**


**Operation ID:** `get_transactions_api_v1_monitor_transactions_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |
| `page` | **query** | integer | ❌ No | Page number |
| `size` | **query** | integer | ❌ No | Page size |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `items` | array[object] | - |
| `total` | integer | - |
| `page` | integer | - |
| `size` | integer | - |
| `pages` | integer | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/traces`

### GET /api/v1/monitor/traces

> **Get Traces**


Get list of traces for a flow.

Args:
    current_user: Authenticated user (required for authorization)
    flow_id: Filter by flow ID
    session_id: Filter by session ID
    status: Filter by trace status
    query: Search query for trace name/id/session id
    start_time: Filter traces starting on/after this time (ISO)
    end_time: Filter traces starting on/before this time (ISO)
    page: Page number (1-based)
    size: Page size

Returns:
    List of traces


**Operation ID:** `get_traces_api_v1_monitor_traces_get`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ❌ No | - |
| `session_id` | **query** | string | ❌ No | - |
| `status` | **query** | string | ❌ No | - |
| `query` | **query** | string | ❌ No | - |
| `start_time` | **query** | string (date-time) | ❌ No | - |
| `end_time` | **query** | string (date-time) | ❌ No | - |
| `page` | **query** | integer | ❌ No | - |
| `size` | **query** | integer | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `traces` | array[object] | - |
| `total` | integer | - |
| `pages` | integer | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/monitor/traces

> **Delete Traces By Flow**


Delete all traces for a flow.

Args:
    flow_id: The ID of the flow whose traces should be deleted.
    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_traces_by_flow_api_v1_monitor_traces_delete`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/monitor/traces/{trace_id}`

### GET /api/v1/monitor/traces/{trace_id}

> **Get Trace**


Get a single trace with its hierarchical span tree.

Args:
    trace_id: The ID of the trace to retrieve.
    current_user: The authenticated user (required for authorization).

Returns:
    TraceRead containing the trace and its hierarchical span tree.


**Operation ID:** `get_trace_api_v1_monitor_traces__trace_id__get`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `name` | string | - |
| `status` | string | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | string (date-time) | - |
| `endTime` | string (date-time) | - |
| `totalLatencyMs` | integer | - |
| `totalTokens` | integer | - |
| `flowId` | string (uuid) | - |
| `sessionId` | string | - |
| `input` | object | - |
| `output` | object | - |
| `spans` | array[object] | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/monitor/traces/{trace_id}

> **Delete Trace**


Delete a trace and all its spans.

Args:
    trace_id: The ID of the trace to delete.
    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_trace_api_v1_monitor_traces__trace_id__delete`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/projects/`

### GET /api/v1/projects/

> **Read Projects**


**Operation ID:** `read_projects_api_v1_projects__get`


**Tags:** `Projects` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
### POST /api/v1/projects/

> **Create Project**


**Operation ID:** `create_project_api_v1_projects__post`


**Tags:** `Projects` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `name` | string | ✅ Yes | - |
  | `description` | string | ❌ No | - |
  | `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
  | `components_list` | array[string] | ❌ No | - |
  | `flows_list` | array[string] | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `auth_settings` | object | Authentication settings for the folder/project |
| `id` | string (uuid) | - |
| `parent_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/projects/{project_id}`

### GET /api/v1/projects/{project_id}

> **Read Project**


**Operation ID:** `read_project_api_v1_projects__project_id__get`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |
| `page` | **query** | integer | ❌ No | - |
| `size` | **query** | integer | ❌ No | - |
| `is_component` | **query** | boolean | ❌ No | - |
| `is_flow` | **query** | boolean | ❌ No | - |
| `search` | **query** | string | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `auth_settings` | object | Authentication settings for the folder/project |
| `id` | string (uuid) | - |
| `parent_id` | string (uuid) | - |
| `flows` | array[object] | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### PATCH /api/v1/projects/{project_id}

> **Update Project**


**Operation ID:** `update_project_api_v1_projects__project_id__patch`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `name` | string | ❌ No | - |
  | `description` | string | ❌ No | - |
  | `parent_id` | string (uuid) | ❌ No | - |
  | `components` | array[string] | ❌ No | - |
  | `flows` | array[string] | ❌ No | - |
  | `auth_settings` | object | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `auth_settings` | object | Authentication settings for the folder/project |
| `id` | string (uuid) | - |
| `parent_id` | string (uuid) | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v1/projects/{project_id}

> **Delete Project**


**Operation ID:** `delete_project_api_v1_projects__project_id__delete`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/projects/download/{project_id}`

### GET /api/v1/projects/download/{project_id}

> **Download File**


Download all flows from project as a zip file.


**Operation ID:** `download_file_api_v1_projects_download__project_id__get`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/projects/upload/`

### POST /api/v1/projects/upload/

> **Upload File**


Upload flows from a file.


**Operation ID:** `upload_file_api_v1_projects_upload__post`


**Tags:** `Projects` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `file` | string | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/starter-projects/`

### GET /api/v1/starter-projects/

> **Get Starter Projects**


Get a list of starter projects.


**Operation ID:** `get_starter_projects_api_v1_starter_projects__get`


**Tags:** `Flows` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/mcp/sse`

### GET /api/v1/mcp/sse

> **Handle Sse**


**Operation ID:** `handle_sse_api_v1_mcp_sse_get`


**Tags:** `mcp` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/mcp/`

### POST /api/v1/mcp/

> **Handle Messages**


**Operation ID:** `handle_messages_api_v1_mcp__post`


**Tags:** `mcp` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/mcp/streamable`

### GET /api/v1/mcp/streamable

> **Handle Streamable Http**


Streamable HTTP endpoint for MCP clients that support the new transport.


**Operation ID:** `handle_streamable_http_api_v1_mcp_streamable_delete`


**Tags:** `mcp` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
### POST /api/v1/mcp/streamable

> **Handle Streamable Http**


Streamable HTTP endpoint for MCP clients that support the new transport.


**Operation ID:** `handle_streamable_http_api_v1_mcp_streamable_delete`


**Tags:** `mcp` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
### DELETE /api/v1/mcp/streamable

> **Handle Streamable Http**


Streamable HTTP endpoint for MCP clients that support the new transport.


**Operation ID:** `handle_streamable_http_api_v1_mcp_streamable_delete`


**Tags:** `mcp` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/mcp/project/{project_id}`

### GET /api/v1/mcp/project/{project_id}

> **List Project Tools**


List project MCP tools.


**Operation ID:** `list_project_tools_api_v1_mcp_project__project_id__get`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |
| `mcp_enabled` | **query** | boolean | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### POST /api/v1/mcp/project/{project_id}

> **Handle Project Messages**


Handle POST messages for a project-specific MCP server.


**Operation ID:** `handle_project_messages_api_v1_mcp_project__project_id__post`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### PATCH /api/v1/mcp/project/{project_id}

> **Update Project Mcp Settings**


Update the MCP settings of all flows in a project and project-level auth settings.

On MCP Composer failure, this endpoint should return with a 200 status code and an error message in
the body of the response to display to the user.


**Operation ID:** `update_project_mcp_settings_api_v1_mcp_project__project_id__patch`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `settings` | array[object] | ✅ Yes | - |
  | `auth_settings` | object | ❌ No | Model representing authentication settings for MCP. |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/mcp/project/{project_id}/sse`

### GET /api/v1/mcp/project/{project_id}/sse

> **Handle Project Sse**


Handle SSE connections for a specific project.


**Operation ID:** `handle_project_sse_api_v1_mcp_project__project_id__sse_get`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/mcp/project/{project_id}/`

### POST /api/v1/mcp/project/{project_id}/

> **Handle Project Messages**


Handle POST messages for a project-specific MCP server.


**Operation ID:** `handle_project_messages_api_v1_mcp_project__project_id___post`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/mcp/project/{project_id}/streamable`

### DELETE /api/v1/mcp/project/{project_id}/streamable

> **Handle Project Streamable Http**


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### GET /api/v1/mcp/project/{project_id}/streamable

> **Handle Project Streamable Http**


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### POST /api/v1/mcp/project/{project_id}/streamable

> **Handle Project Streamable Http**


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/mcp/project/{project_id}/install`

### POST /api/v1/mcp/project/{project_id}/install

> **Install Mcp Config**


Install MCP server configuration for Cursor, Windsurf, or Claude.


**Operation ID:** `install_mcp_config_api_v1_mcp_project__project_id__install_post`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `client` | string | ✅ Yes | - |
  | `transport` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/mcp/project/{project_id}/composer-url`

### GET /api/v1/mcp/project/{project_id}/composer-url

> **Get Project Composer Url**


Get the MCP Composer URL for a specific project.

On failure, this endpoint should return with a 200 status code and an error message in
the body of the response to display to the user.


**Operation ID:** `get_project_composer_url_api_v1_mcp_project__project_id__composer_url_get`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `project_id` | string | - |
| `uses_composer` | boolean | - |
| `streamable_http_url` | string | - |
| `legacy_sse_url` | string | - |
| `error_message` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/mcp/project/{project_id}/installed`

### GET /api/v1/mcp/project/{project_id}/installed

> **Check Installed Mcp Servers**


Check if MCP server configuration is installed for this project in Cursor, Windsurf, or Claude.


**Operation ID:** `check_installed_mcp_servers_api_v1_mcp_project__project_id__installed_get`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/responses`

### POST /api/v1/responses

> **Create Response**


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


**Tags:** `OpenAI Responses API` 



#### Request Body

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


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/agentic/execute/{flow_name}`

### POST /api/v1/agentic/execute/{flow_name}

> **Execute Named Flow**


Execute a named flow from the flows directory.


**Operation ID:** `execute_named_flow_api_v1_agentic_execute__flow_name__post`


**Tags:** `Agentic` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_name` | **path** | string | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `flow_id` | string | ✅ Yes | - |
  | `component_id` | string | ❌ No | - |
  | `field_name` | string | ❌ No | - |
  | `input_value` | string | ❌ No | - |
  | `max_retries` | integer | ❌ No | - |
  | `model_name` | string | ❌ No | - |
  | `provider` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/agentic/check-config`

### GET /api/v1/agentic/check-config

> **Check Assistant Config**


Check if the Langflow Assistant is properly configured.

Returns available providers with their configured status and available models.


**Operation ID:** `check_assistant_config_api_v1_agentic_check_config_get`


**Tags:** `Agentic` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/agentic/assist`

### POST /api/v1/agentic/assist

> **Assist**


Chat with the Langflow Assistant.


**Operation ID:** `assist_api_v1_agentic_assist_post`


**Tags:** `Agentic` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `flow_id` | string | ✅ Yes | - |
  | `component_id` | string | ❌ No | - |
  | `field_name` | string | ❌ No | - |
  | `input_value` | string | ❌ No | - |
  | `max_retries` | integer | ❌ No | - |
  | `model_name` | string | ❌ No | - |
  | `provider` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v1/agentic/assist/stream`

### POST /api/v1/agentic/assist/stream

> **Assist Stream**


Chat with the Langflow Assistant with streaming progress updates.


**Operation ID:** `assist_stream_api_v1_agentic_assist_stream_post`


**Tags:** `Agentic` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `flow_id` | string | ✅ Yes | - |
  | `component_id` | string | ❌ No | - |
  | `field_name` | string | ❌ No | - |
  | `input_value` | string | ❌ No | - |
  | `max_retries` | integer | ❌ No | - |
  | `model_name` | string | ❌ No | - |
  | `provider` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v2/files/`

### POST /api/v2/files/

> **Upload User File**


Upload a file for the current user and track it in the database.


**Operation ID:** `upload_user_file_api_v2_files__post`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `append` | **query** | boolean | ❌ No | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `file` | string | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `name` | string | - |
| `path` | string (path) | - |
| `size` | integer | - |
| `provider` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### GET /api/v2/files/

> **List Files**


List the files available to the current user.


**Operation ID:** `list_files_api_v2_files__get`


**Tags:** `Files` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
### DELETE /api/v2/files/

> **Delete All Files**


Delete all files for the current user.


**Operation ID:** `delete_all_files_api_v2_files__delete`


**Tags:** `Files` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v2/files`

### POST /api/v2/files

> **Upload User File**


Upload a file for the current user and track it in the database.


**Operation ID:** `upload_user_file_api_v2_files_post`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `append` | **query** | boolean | ❌ No | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `file` | string | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `name` | string | - |
| `path` | string (path) | - |
| `size` | integer | - |
| `provider` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### GET /api/v2/files

> **List Files**


List the files available to the current user.


**Operation ID:** `list_files_api_v2_files_get`


**Tags:** `Files` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
### DELETE /api/v2/files

> **Delete All Files**


Delete all files for the current user.


**Operation ID:** `delete_all_files_api_v2_files_delete`


**Tags:** `Files` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v2/files/batch/`

### POST /api/v2/files/batch/

> **Download Files Batch**


Download multiple files as a zip file by their IDs.


**Operation ID:** `download_files_batch_api_v2_files_batch__post`


**Tags:** `Files` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Type:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v2/files/batch/

> **Delete Files Batch**


Delete multiple files by their IDs.


**Operation ID:** `delete_files_batch_api_v2_files_batch__delete`


**Tags:** `Files` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Type:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v2/files/{file_id}`

### GET /api/v2/files/{file_id}

> **Download File**


Download a file by its ID or return its content as a string/bytes.

Args:
    file_id: UUID of the file.
    current_user: Authenticated user.
    session: Database session.
    storage_service: File storage service.
    return_content: If True, return raw content (str) instead of StreamingResponse.

Returns:
    StreamingResponse for client downloads or str for internal use.


**Operation ID:** `download_file_api_v2_files__file_id__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** | string (uuid) | ✅ Yes | - |
| `return_content` | **query** | boolean | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### PUT /api/v2/files/{file_id}

> **Edit File Name**


Edit the name of a file by its ID.


**Operation ID:** `edit_file_name_api_v2_files__file_id__put`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** | string (uuid) | ✅ Yes | - |
| `name` | **query** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `name` | string | - |
| `path` | string (path) | - |
| `size` | integer | - |
| `provider` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v2/files/{file_id}

> **Delete File**


Delete a file by its ID.


**Operation ID:** `delete_file_api_v2_files__file_id__delete`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** | string (uuid) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v2/mcp/servers`

### GET /api/v2/mcp/servers

> **Get Servers**


Get the list of available servers.


**Operation ID:** `get_servers_api_v2_mcp_servers_get`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `action_count` | **query** | boolean | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v2/mcp/servers/{server_name}`

### GET /api/v2/mcp/servers/{server_name}

> **Get Server Endpoint**


Get a specific server.


**Operation ID:** `get_server_endpoint_api_v2_mcp_servers__server_name__get`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### POST /api/v2/mcp/servers/{server_name}

> **Add Server**


**Operation ID:** `add_server_api_v2_mcp_servers__server_name__post`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `command` | string | ❌ No | - |
  | `args` | array[string] | ❌ No | - |
  | `env` | object | ❌ No | - |
  | `headers` | object | ❌ No | - |
  | `url` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### PATCH /api/v2/mcp/servers/{server_name}

> **Update Server Endpoint**


**Operation ID:** `update_server_endpoint_api_v2_mcp_servers__server_name__patch`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `command` | string | ❌ No | - |
  | `args` | array[string] | ❌ No | - |
  | `env` | object | ❌ No | - |
  | `headers` | object | ❌ No | - |
  | `url` | string | ❌ No | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### DELETE /api/v2/mcp/servers/{server_name}

> **Delete Server**


**Operation ID:** `delete_server_api_v2_mcp_servers__server_name__delete`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v2/workflows`

### POST /api/v2/workflows

> **Execute Workflow**


Execute a workflow with support for sync, stream, and background modes


**Operation ID:** `execute_workflow_api_v2_workflows_post`


**Tags:** `Workflow` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `background` | boolean | ❌ No | - |
  | `stream` | boolean | ❌ No | - |
  | `flow_id` | string | ✅ Yes | - |
  | `inputs` | object | ❌ No | Component-specific inputs in flat format: 'component_id.param_name': value |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Workflow execution response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `flow_id` | string | - |
| `job_id` | string | - |
| `object` | string | - |
| `created_timestamp` | string | - |
| `status` | string | Job execution status. |
| `errors` | array[object] | - |
| `inputs` | object | - |
| `outputs` | object | - |

**Response Body** (text/event-stream):

| Name | Type | Description |
|------|------|-------------|
| `type` | string | - |
| `run_id` | string | - |
| `timestamp` | integer | - |
| `raw_event` | object | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
### GET /api/v2/workflows

> **Get Workflow Status**


Get status of workflow job by job ID


**Operation ID:** `get_workflow_status_api_v2_workflows_get`


**Tags:** `Workflow` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **query** | string | ❌ No | Job ID to query |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Workflow status response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `flow_id` | string | - |
| `job_id` | string | - |
| `object` | string | - |
| `created_timestamp` | string | - |
| `status` | string | Job execution status. |
| `errors` | array[object] | - |
| `inputs` | object | - |
| `outputs` | object | - |

**Response Body** (text/event-stream):

| Name | Type | Description |
|------|------|-------------|
| `type` | string | - |
| `run_id` | string | - |
| `timestamp` | integer | - |
| `raw_event` | object | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/api/v2/workflows/stop`

### POST /api/v2/workflows/stop

> **Stop Workflow**


Stop a running workflow execution


**Operation ID:** `stop_workflow_api_v2_workflows_stop_post`


**Tags:** `Workflow` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `job_id` | string | ✅ Yes | - |


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `job_id` | string | - |
| `message` | string | - |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
## `/health`

### GET /health

> **Health**


**Operation ID:** `health_health_get`


**Tags:** `Health Check` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/health_check`

### GET /health_check

> **Health Check**


**Operation ID:** `health_check_health_check_get`


**Tags:** `Health Check` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `status` | string | - |
| `chat` | string | - |
| `db` | string | - |


---
## `/logs-stream`

### GET /logs-stream

> **Stream Logs**


HTTP/2 Server-Sent-Event (SSE) endpoint for streaming logs.

Requires authentication to prevent exposure of sensitive log data.
It establishes a long-lived connection to the server and receives log messages in real-time.
The client should use the header "Accept: text/event-stream".


**Operation ID:** `stream_logs_logs_stream_get`


**Tags:** `Log` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/logs`

### GET /logs

> **Logs**


Retrieve application logs with authentication required.

SECURITY: Logs may contain sensitive information and require authentication.


**Operation ID:** `logs_logs_get`


**Tags:** `Log` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `lines_before` | **query** | integer | ❌ No | The number of logs before the timestamp or the last log |
| `lines_after` | **query** | integer | ❌ No | The number of logs after the timestamp |
| `timestamp` | **query** | integer | ❌ No | The timestamp to start getting logs from |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |


---
