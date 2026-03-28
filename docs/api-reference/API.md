# API Reference

> **Langflow** — Version 1.8.0

---

## `/api/v1/build/{flow_id}/flow`

### POST /api/v1/build/{flow_id}/flow

> **Build Flow**


Build and process a flow, returning a job ID for event polling.&lt;br&gt;&lt;br&gt;This endpoint requires authentication through the CurrentActiveUser dependency.&lt;br&gt;For public flows that don&#x27;t require authentication, use the /build_public_tmp/flow_id/flow endpoint.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id: UUID of the flow to build&lt;br&gt;    background_tasks: Background tasks manager&lt;br&gt;    inputs: Optional input values for the flow&lt;br&gt;    data: Optional flow data&lt;br&gt;    files: Optional files to include&lt;br&gt;    stop_component_id: Optional ID of component to stop at&lt;br&gt;    start_component_id: Optional ID of component to start from&lt;br&gt;    log_builds: Whether to log the build process&lt;br&gt;    current_user: The authenticated user&lt;br&gt;    queue_service: Queue service for job management&lt;br&gt;    flow_name: Optional name for the flow&lt;br&gt;    event_delivery: Optional event delivery type - default is streaming&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    Dict with job_id that can be used to poll for build status


**Operation ID:** `build_flow_api_v1_build__flow_id__flow_post`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |
| `stop_component_id` | **query** |  | ❌ No | - |
| `start_component_id` | **query** |  | ❌ No | - |
| `log_builds` | **query** |  (boolean) | ❌ No | - |
| `flow_name` | **query** |  | ❌ No | - |
| `event_delivery` | **query** |  (string) | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/build/{job_id}/events`

### GET /api/v1/build/{job_id}/events

> **Get Build Events**


Get events for a specific build job.&lt;br&gt;&lt;br&gt;Requires authentication to prevent unauthorized access to build events.


**Operation ID:** `get_build_events_api_v1_build__job_id__events_get`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** |  (string) | ✅ Yes | - |
| `event_delivery` | **query** |  (string) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/build/{job_id}/cancel`

### POST /api/v1/build/{job_id}/cancel

> **Cancel Build**


Cancel a specific build job.&lt;br&gt;&lt;br&gt;Requires authentication to prevent unauthorized build cancellation.


**Operation ID:** `cancel_build_api_v1_build__job_id__cancel_post`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/build_public_tmp/{flow_id}/flow`

### POST /api/v1/build_public_tmp/{flow_id}/flow

> **Build Public Tmp**


Build a public flow without requiring authentication.&lt;br&gt;&lt;br&gt;This endpoint is specifically for public flows that don&#x27;t require authentication.&lt;br&gt;It uses a client_id cookie to create a deterministic flow ID for tracking purposes.&lt;br&gt;&lt;br&gt;The endpoint:&lt;br&gt;1. Verifies the requested flow is marked as public in the database&lt;br&gt;2. Creates a deterministic UUID based on client_id and flow_id&lt;br&gt;3. Uses the flow owner&#x27;s permissions to build the flow&lt;br&gt;&lt;br&gt;Requirements:&lt;br&gt;- The flow must be marked as PUBLIC in the database&lt;br&gt;- The request must include a client_id cookie&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id: UUID of the public flow to build&lt;br&gt;    background_tasks: Background tasks manager&lt;br&gt;    inputs: Optional input values for the flow&lt;br&gt;    data: Optional flow data&lt;br&gt;    files: Optional files to include&lt;br&gt;    stop_component_id: Optional ID of component to stop at&lt;br&gt;    start_component_id: Optional ID of component to start from&lt;br&gt;    log_builds: Whether to log the build process&lt;br&gt;    flow_name: Optional name for the flow&lt;br&gt;    request: FastAPI request object (needed for cookie access)&lt;br&gt;    queue_service: Queue service for job management&lt;br&gt;    event_delivery: Optional event delivery type - default is streaming&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    Dict with job_id that can be used to poll for build status


**Operation ID:** `build_public_tmp_api_v1_build_public_tmp__flow_id__flow_post`


**Tags:** `Chat` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |
| `stop_component_id` | **query** |  | ❌ No | - |
| `start_component_id` | **query** |  | ❌ No | - |
| `log_builds` | **query** |  | ❌ No | - |
| `flow_name` | **query** |  | ❌ No | - |
| `event_delivery` | **query** |  (string) | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/all`

### GET /api/v1/all

> **Get All**


Retrieve all component types with compression for better performance.&lt;br&gt;&lt;br&gt;Returns a compressed response containing all available component types.


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


Executes a specified flow by ID with support for streaming and telemetry (API key auth).&lt;br&gt;&lt;br&gt;This endpoint executes a flow identified by ID or name, with options for streaming the response&lt;br&gt;and tracking execution metrics. It handles both streaming and non-streaming execution modes.&lt;br&gt;This endpoint uses API key authentication (Bearer token).&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    background_tasks (BackgroundTasks): FastAPI background task manager&lt;br&gt;    flow (FlowRead | None): The flow to execute, loaded via dependency&lt;br&gt;    input_request (SimplifiedAPIRequest | None): Input parameters for the flow&lt;br&gt;    stream (bool): Whether to stream the response&lt;br&gt;    api_key_user (UserRead): Authenticated user from API key&lt;br&gt;    context (dict | None): Optional context to pass to the flow&lt;br&gt;    http_request (Request): The incoming HTTP request for extracting global variables&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results&lt;br&gt;    or a RunResponse with the complete execution results&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: For flow not found (404) or invalid input (400)&lt;br&gt;    APIException: For internal execution errors (500)&lt;br&gt;&lt;br&gt;Notes:&lt;br&gt;    - Supports both streaming and non-streaming execution modes&lt;br&gt;    - Tracks execution time and success/failure via telemetry&lt;br&gt;    - Handles graceful client disconnection in streaming mode&lt;br&gt;    - Provides detailed error handling with appropriate HTTP status codes&lt;br&gt;    - Extracts global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*&lt;br&gt;    - Merges extracted variables with the context parameter as &quot;request_variables&quot;&lt;br&gt;    - In streaming mode, uses EventManager to handle events:&lt;br&gt;        - &quot;add_message&quot;: New messages during execution&lt;br&gt;        - &quot;token&quot;: Individual tokens during streaming&lt;br&gt;        - &quot;end&quot;: Final execution result&lt;br&gt;    - Authentication: Requires API key (Bearer token)


**Operation ID:** `simplified_run_flow_api_v1_run__flow_id_or_name__post`


**Tags:** `Base` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** |  (string) | ✅ Yes | - |
| `stream` | **query** |  (boolean) | ❌ No | - |
| `user_id` | **query** |  | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/webhook/{flow_id_or_name}`

### POST /api/v1/webhook/{flow_id_or_name}

> **Webhook Run Flow**


Run a flow using a webhook request.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id_or_name: The flow ID or endpoint name (used by dependency).&lt;br&gt;    flow: The flow to be executed.&lt;br&gt;    request: The incoming HTTP request.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    A dictionary containing the status of the task.&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: If the flow is not found or if there is an error processing the request.


**Operation ID:** `webhook_run_flow_api_v1_webhook__flow_id_or_name__post`


**Tags:** `Base` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** |  (string) | ✅ Yes | - |
| `user_id` | **query** |  | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **202** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/run/advanced/{flow_id_or_name}`

### POST /api/v1/run/advanced/{flow_id_or_name}

> **Experimental Run Flow**


Executes a specified flow by ID with optional input values, output selection, tweaks, and streaming capability.&lt;br&gt;&lt;br&gt;This endpoint supports running flows with caching to enhance performance and efficiency.&lt;br&gt;&lt;br&gt;### Parameters:&lt;br&gt;- &#x60;flow&#x60; (Flow): The flow object to be executed, resolved via dependency injection.&lt;br&gt;- &#x60;inputs&#x60; (List[InputValueRequest], optional): A list of inputs specifying the input values and components&lt;br&gt;  for the flow. Each input can target specific components and provide custom values.&lt;br&gt;- &#x60;outputs&#x60; (List[str], optional): A list of output names to retrieve from the executed flow.&lt;br&gt;  If not provided, all outputs are returned.&lt;br&gt;- &#x60;tweaks&#x60; (Optional[Tweaks], optional): A dictionary of tweaks to customize the flow execution.&lt;br&gt;  The tweaks can be used to modify the flow&#x27;s parameters and components.&lt;br&gt;  Tweaks can be overridden by the input values.&lt;br&gt;- &#x60;stream&#x60; (bool, optional): Specifies whether the results should be streamed. Defaults to False.&lt;br&gt;- &#x60;session_id&#x60; (Union[None, str], optional): An optional session ID to utilize existing session data for the flow&lt;br&gt;  execution.&lt;br&gt;- &#x60;api_key_user&#x60; (User): The user associated with the current API key. Automatically resolved from the API key.&lt;br&gt;&lt;br&gt;### Returns:&lt;br&gt;A &#x60;RunResponse&#x60; object containing the selected outputs (or all if not specified) of the executed flow&lt;br&gt;and the session ID.&lt;br&gt;The structure of the response accommodates multiple inputs, providing a nested list of outputs for each input.&lt;br&gt;&lt;br&gt;### Raises:&lt;br&gt;HTTPException: Indicates issues with finding the specified flow, invalid input formats, or internal errors during&lt;br&gt;flow execution.&lt;br&gt;&lt;br&gt;### Example usage:&lt;br&gt;&#x60;&#x60;&#x60;json&lt;br&gt;POST /run/flow_id&lt;br&gt;x-api-key: YOUR_API_KEY&lt;br&gt;Payload:&lt;br&gt;{&lt;br&gt;    &quot;inputs&quot;: [&lt;br&gt;        {&quot;components&quot;: [&quot;component1&quot;], &quot;input_value&quot;: &quot;value1&quot;},&lt;br&gt;        {&quot;components&quot;: [&quot;component3&quot;], &quot;input_value&quot;: &quot;value2&quot;}&lt;br&gt;    ],&lt;br&gt;    &quot;outputs&quot;: [&quot;Component Name&quot;, &quot;component_id&quot;],&lt;br&gt;    &quot;tweaks&quot;: {&quot;parameter_name&quot;: &quot;value&quot;, &quot;Component Name&quot;: {&quot;parameter_name&quot;: &quot;value&quot;}, &quot;component_id&quot;: {&quot;parameter_name&quot;: &quot;value&quot;}}&lt;br&gt;    &quot;stream&quot;: false&lt;br&gt;}&lt;br&gt;&#x60;&#x60;&#x60;&lt;br&gt;&lt;br&gt;This endpoint facilitates complex flow executions with customized inputs, outputs, and configurations,&lt;br&gt;catering to diverse application requirements.


**Operation ID:** `experimental_run_flow_api_v1_run_advanced__flow_id_or_name__post`


**Tags:** `Base` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** |  (string) | ✅ Yes | - |
| `user_id` | **query** |  | ❌ No | - |


#### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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


Retrieve application configuration settings.&lt;br&gt;&lt;br&gt;Returns different configuration based on authentication status:&lt;br&gt;- Authenticated users: Full ConfigResponse with all settings&lt;br&gt;- Unauthenticated users: PublicConfigResponse with limited, safe-to-expose settings&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    user: The authenticated user, or None if unauthenticated.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    ConfigResponse | PublicConfigResponse: Configuration settings appropriate for the user&#x27;s auth status.&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: If an error occurs while retrieving the configuration.


**Operation ID:** `get_config_api_v1_config_get`


**Tags:** `Base` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/flows/`

### POST /api/v1/flows/

> **Create Flow**


**Operation ID:** `create_flow_api_v1_flows__post`


**Tags:** `Flows` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
### GET /api/v1/flows/

> **Read Flows**


Retrieve a list of flows with pagination support.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    current_user (User): The current authenticated user.&lt;br&gt;    session (Session): The database session.&lt;br&gt;    settings_service (SettingsService): The settings service.&lt;br&gt;    components_only (bool, optional): Whether to return only components. Defaults to False.&lt;br&gt;&lt;br&gt;    get_all (bool, optional): Whether to return all flows without pagination. Defaults to True.&lt;br&gt;    **This field must be True because of backward compatibility with the frontend - Release: 1.0.20**&lt;br&gt;&lt;br&gt;    folder_id (UUID, optional): The project ID. Defaults to None.&lt;br&gt;    params (Params): Pagination parameters.&lt;br&gt;    remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.&lt;br&gt;    header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    list[FlowRead] | Page[FlowRead] | list[FlowHeader]&lt;br&gt;    A list of flows or a paginated response containing the list of flows or a list of flow headers.


**Operation ID:** `read_flows_api_v1_flows__get`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `remove_example_flows` | **query** |  (boolean) | ❌ No | - |
| `components_only` | **query** |  (boolean) | ❌ No | - |
| `get_all` | **query** |  (boolean) | ❌ No | - |
| `folder_id` | **query** |  | ❌ No | - |
| `header_flows` | **query** |  (boolean) | ❌ No | - |
| `page` | **query** |  (integer) | ❌ No | - |
| `size` | **query** |  (integer) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/flows/

> **Delete Multiple Flows**


Delete multiple flows by their IDs.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_ids (List[str]): The list of flow IDs to delete.&lt;br&gt;    user (User, optional): The user making the request. Defaults to the current active user.&lt;br&gt;    db (Session, optional): The database session.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    dict: A dictionary containing the number of flows deleted.


**Operation ID:** `delete_multiple_flows_api_v1_flows__delete`


**Tags:** `Flows` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `flow_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### PATCH /api/v1/flows/{flow_id}

> **Update Flow**


Update a flow.


**Operation ID:** `update_flow_api_v1_flows__flow_id__patch`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/flows/{flow_id}

> **Delete Flow**


Delete a flow.


**Operation ID:** `delete_flow_api_v1_flows__flow_id__delete`


**Tags:** `Flows` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `flow_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


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
| `folder_id` | **query** |  | ❌ No | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/flows/basic_examples/`

### GET /api/v1/flows/basic_examples/

> **Read Basic Examples**


Retrieve a list of basic example flows.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    session (Session): The database session.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    list[FlowRead]: A list of basic example flows.


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


Add a new user to the database.&lt;br&gt;&lt;br&gt;This endpoint allows public user registration (sign up).&lt;br&gt;User activation is controlled by the NEW_USER_IS_ACTIVE setting.


**Operation ID:** `add_user_api_v1_users__post`


**Tags:** `Users` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
### GET /api/v1/users/

> **Read All Users**


Retrieve a list of users from the database with pagination.


**Operation ID:** `read_all_users_api_v1_users__get`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `skip` | **query** |  (integer) | ❌ No | - |
| `limit` | **query** |  (integer) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/users/whoami`

### GET /api/v1/users/whoami

> **Read Current User**


Retrieve the current user&#x27;s data.


**Operation ID:** `read_current_user_api_v1_users_whoami_get`


**Tags:** `Users` 




#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `/api/v1/users/{user_id}`

### PATCH /api/v1/users/{user_id}

> **Patch User**


Update an existing user&#x27;s data.


**Operation ID:** `patch_user_api_v1_users__user_id__patch`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/users/{user_id}

> **Delete User**


Delete a user from the database.


**Operation ID:** `delete_user_api_v1_users__user_id__delete`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/users/{user_id}/reset-password`

### PATCH /api/v1/users/{user_id}/reset-password

> **Reset Password**


Reset a user&#x27;s password.


**Operation ID:** `reset_password_api_v1_users__user_id__reset_password_patch`


**Tags:** `Users` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/files/upload/{flow_id}`

### POST /api/v1/files/upload/{flow_id}

> **Upload File**


**Operation ID:** `upload_file_api_v1_files_upload__flow_id__post`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/files/download/{flow_id}/{file_name}`

### GET /api/v1/files/download/{flow_id}/{file_name}

> **Download File**


**Operation ID:** `download_file_api_v1_files_download__flow_id___file_name__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_name` | **path** |  (string) | ✅ Yes | - |
| `flow_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `flow_id` | **path** |  (string) | ✅ Yes | - |
| `file_name` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/files/profile_pictures/{folder_name}/{file_name}`

### GET /api/v1/files/profile_pictures/{folder_name}/{file_name}

> **Download Profile Picture**


Download profile picture from local filesystem.&lt;br&gt;&lt;br&gt;Profile pictures are first looked up in config_dir/profile_pictures/,&lt;br&gt;then fallback to the package&#x27;s bundled profile_pictures directory.


**Operation ID:** `download_profile_picture_api_v1_files_profile_pictures__folder_name___file_name__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `folder_name` | **path** |  (string) | ✅ Yes | - |
| `file_name` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/files/profile_pictures/list`

### GET /api/v1/files/profile_pictures/list

> **List Profile Pictures**


List profile pictures from local filesystem.&lt;br&gt;&lt;br&gt;Profile pictures are first looked up in config_dir/profile_pictures/,&lt;br&gt;then fallback to the package&#x27;s bundled profile_pictures directory.


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
| `flow_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/files/delete/{flow_id}/{file_name}`

### DELETE /api/v1/files/delete/{flow_id}/{file_name}

> **Delete File**


**Operation ID:** `delete_file_api_v1_files_delete__flow_id___file_name__delete`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_name` | **path** |  (string) | ✅ Yes | - |
| `flow_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/builds`

### GET /api/v1/monitor/builds

> **Get Vertex Builds**


**Operation ID:** `get_vertex_builds_api_v1_monitor_builds_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/monitor/builds

> **Delete Vertex Builds**


**Operation ID:** `delete_vertex_builds_api_v1_monitor_builds_delete`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/messages/sessions`

### GET /api/v1/monitor/messages/sessions

> **Get Message Sessions**


**Operation ID:** `get_message_sessions_api_v1_monitor_messages_sessions_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/messages`

### GET /api/v1/monitor/messages

> **Get Messages**


**Operation ID:** `get_messages_api_v1_monitor_messages_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  | ❌ No | - |
| `session_id` | **query** |  | ❌ No | - |
| `sender` | **query** |  | ❌ No | - |
| `sender_name` | **query** |  | ❌ No | - |
| `order_by` | **query** |  | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/monitor/messages

> **Delete Messages**


**Operation ID:** `delete_messages_api_v1_monitor_messages_delete`


**Tags:** `Monitor` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/messages/{message_id}`

### PUT /api/v1/monitor/messages/{message_id}

> **Update Message**


**Operation ID:** `update_message_api_v1_monitor_messages__message_id__put`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `message_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/messages/session/{old_session_id}`

### PATCH /api/v1/monitor/messages/session/{old_session_id}

> **Update Session Id**


**Operation ID:** `update_session_id_api_v1_monitor_messages_session__old_session_id__patch`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `old_session_id` | **path** |  (string) | ✅ Yes | - |
| `new_session_id` | **query** |  (string) | ✅ Yes | The new session ID to update to |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/messages/session/{session_id}`

### DELETE /api/v1/monitor/messages/session/{session_id}

> **Delete Messages Session**


**Operation ID:** `delete_messages_session_api_v1_monitor_messages_session__session_id__delete`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `session_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/transactions`

### GET /api/v1/monitor/transactions

> **Get Transactions**


**Operation ID:** `get_transactions_api_v1_monitor_transactions_get`


**Tags:** `Monitor` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |
| `page` | **query** |  (integer) | ❌ No | Page number |
| `size` | **query** |  (integer) | ❌ No | Page size |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/traces`

### GET /api/v1/monitor/traces

> **Get Traces**


Get list of traces for a flow.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    current_user: Authenticated user (required for authorization)&lt;br&gt;    flow_id: Filter by flow ID&lt;br&gt;    session_id: Filter by session ID&lt;br&gt;    status: Filter by trace status&lt;br&gt;    query: Search query for trace name/id/session id&lt;br&gt;    start_time: Filter traces starting on/after this time (ISO)&lt;br&gt;    end_time: Filter traces starting on/before this time (ISO)&lt;br&gt;    page: Page number (1-based)&lt;br&gt;    size: Page size&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    List of traces


**Operation ID:** `get_traces_api_v1_monitor_traces_get`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  | ❌ No | - |
| `session_id` | **query** |  | ❌ No | - |
| `status` | **query** |  | ❌ No | - |
| `query` | **query** |  | ❌ No | - |
| `start_time` | **query** |  | ❌ No | - |
| `end_time` | **query** |  | ❌ No | - |
| `page` | **query** |  (integer) | ❌ No | - |
| `size` | **query** |  (integer) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/monitor/traces

> **Delete Traces By Flow**


Delete all traces for a flow.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id: The ID of the flow whose traces should be deleted.&lt;br&gt;    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_traces_by_flow_api_v1_monitor_traces_delete`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/monitor/traces/{trace_id}`

### GET /api/v1/monitor/traces/{trace_id}

> **Get Trace**


Get a single trace with its hierarchical span tree.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    trace_id: The ID of the trace to retrieve.&lt;br&gt;    current_user: The authenticated user (required for authorization).&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    TraceRead containing the trace and its hierarchical span tree.


**Operation ID:** `get_trace_api_v1_monitor_traces__trace_id__get`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/monitor/traces/{trace_id}

> **Delete Trace**


Delete a trace and all its spans.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    trace_id: The ID of the trace to delete.&lt;br&gt;    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_trace_api_v1_monitor_traces__trace_id__delete`


**Tags:** `Traces` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/projects/{project_id}`

### GET /api/v1/projects/{project_id}

> **Read Project**


**Operation ID:** `read_project_api_v1_projects__project_id__get`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |
| `page` | **query** |  | ❌ No | - |
| `size` | **query** |  | ❌ No | - |
| `is_component` | **query** |  (boolean) | ❌ No | - |
| `is_flow` | **query** |  (boolean) | ❌ No | - |
| `search` | **query** |  (string) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### PATCH /api/v1/projects/{project_id}

> **Update Project**


**Operation ID:** `update_project_api_v1_projects__project_id__patch`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v1/projects/{project_id}

> **Delete Project**


**Operation ID:** `delete_project_api_v1_projects__project_id__delete`


**Tags:** `Projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |
| `mcp_enabled` | **query** |  (boolean) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### POST /api/v1/mcp/project/{project_id}

> **Handle Project Messages**


Handle POST messages for a project-specific MCP server.


**Operation ID:** `handle_project_messages_api_v1_mcp_project__project_id__post`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### PATCH /api/v1/mcp/project/{project_id}

> **Update Project Mcp Settings**


Update the MCP settings of all flows in a project and project-level auth settings.&lt;br&gt;&lt;br&gt;On MCP Composer failure, this endpoint should return with a 200 status code and an error message in&lt;br&gt;the body of the response to display to the user.


**Operation ID:** `update_project_mcp_settings_api_v1_mcp_project__project_id__patch`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### GET /api/v1/mcp/project/{project_id}/streamable

> **Handle Project Streamable Http**


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### POST /api/v1/mcp/project/{project_id}/streamable

> **Handle Project Streamable Http**


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/mcp/project/{project_id}/composer-url`

### GET /api/v1/mcp/project/{project_id}/composer-url

> **Get Project Composer Url**


Get the MCP Composer URL for a specific project.&lt;br&gt;&lt;br&gt;On failure, this endpoint should return with a 200 status code and an error message in&lt;br&gt;the body of the response to display to the user.


**Operation ID:** `get_project_composer_url_api_v1_mcp_project__project_id__composer_url_get`


**Tags:** `mcp_projects` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `project_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/responses`

### POST /api/v1/responses

> **Create Response**


Create a response using OpenAI Responses API format.&lt;br&gt;&lt;br&gt;This endpoint accepts a flow_id in the model parameter and processes&lt;br&gt;the input through the specified Langflow flow.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    request: OpenAI Responses API request with model (flow_id) and input&lt;br&gt;    background_tasks: FastAPI background task manager&lt;br&gt;    api_key_user: Authenticated user from API key&lt;br&gt;    http_request: The incoming HTTP request&lt;br&gt;    telemetry_service: Telemetry service for logging&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    OpenAI-compatible response or streaming response&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: For validation errors or flow execution issues


**Operation ID:** `create_response_api_v1_responses_post`


**Tags:** `OpenAI Responses API` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `flow_name` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v1/agentic/check-config`

### GET /api/v1/agentic/check-config

> **Check Assistant Config**


Check if the Langflow Assistant is properly configured.&lt;br&gt;&lt;br&gt;Returns available providers with their configured status and available models.


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `append` | **query** |  (boolean) | ❌ No | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


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
| `append` | **query** |  (boolean) | ❌ No | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v2/files/batch/

> **Delete Files Batch**


Delete multiple files by their IDs.


**Operation ID:** `delete_files_batch_api_v2_files_batch__delete`


**Tags:** `Files` 



#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `array`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `/api/v2/files/{file_id}`

### GET /api/v2/files/{file_id}

> **Download File**


Download a file by its ID or return its content as a string/bytes.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    file_id: UUID of the file.&lt;br&gt;    current_user: Authenticated user.&lt;br&gt;    session: Database session.&lt;br&gt;    storage_service: File storage service.&lt;br&gt;    return_content: If True, return raw content (str) instead of StreamingResponse.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    StreamingResponse for client downloads or str for internal use.


**Operation ID:** `download_file_api_v2_files__file_id__get`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** |  (string) | ✅ Yes | - |
| `return_content` | **query** |  (boolean) | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### PUT /api/v2/files/{file_id}

> **Edit File Name**


Edit the name of a file by its ID.


**Operation ID:** `edit_file_name_api_v2_files__file_id__put`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** |  (string) | ✅ Yes | - |
| `name` | **query** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v2/files/{file_id}

> **Delete File**


Delete a file by its ID.


**Operation ID:** `delete_file_api_v2_files__file_id__delete`


**Tags:** `Files` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `action_count` | **query** |  | ❌ No | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
| `server_name` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### POST /api/v2/mcp/servers/{server_name}

> **Add Server**


**Operation ID:** `add_server_api_v2_mcp_servers__server_name__post`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### PATCH /api/v2/mcp/servers/{server_name}

> **Update Server Endpoint**


**Operation ID:** `update_server_endpoint_api_v2_mcp_servers__server_name__patch`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** |  (string) | ✅ Yes | - |


#### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
### DELETE /api/v2/mcp/servers/{server_name}

> **Delete Server**


**Operation ID:** `delete_server_api_v2_mcp_servers__server_name__delete`


**Tags:** `MCP` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** |  (string) | ✅ Yes | - |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Workflow execution response |
| **422** | Validation Error |


---
### GET /api/v2/workflows

> **Get Workflow Status**


Get status of workflow job by job ID


**Operation ID:** `get_workflow_status_api_v2_workflows_get`


**Tags:** `Workflow` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **query** |  | ❌ No | Job ID to query |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Workflow status response |
| **422** | Validation Error |


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
  - **Schema:** `object`


#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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


---
## `/logs-stream`

### GET /logs-stream

> **Stream Logs**


HTTP/2 Server-Sent-Event (SSE) endpoint for streaming logs.&lt;br&gt;&lt;br&gt;Requires authentication to prevent exposure of sensitive log data.&lt;br&gt;It establishes a long-lived connection to the server and receives log messages in real-time.&lt;br&gt;The client should use the header &quot;Accept: text/event-stream&quot;.


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


Retrieve application logs with authentication required.&lt;br&gt;&lt;br&gt;SECURITY: Logs may contain sensitive information and require authentication.


**Operation ID:** `logs_logs_get`


**Tags:** `Log` 


#### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `lines_before` | **query** |  (integer) | ❌ No | The number of logs before the timestamp or the last log |
| `lines_after` | **query** |  (integer) | ❌ No | The number of logs after the timestamp |
| `timestamp` | **query** |  (integer) | ❌ No | The timestamp to start getting logs from |



#### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
