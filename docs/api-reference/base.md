# Base

> Part of **Langflow**

---

## `GET` /api/v1/all

> Get All


Retrieve all component types with compression for better performance.&lt;br&gt;&lt;br&gt;Returns a compressed response containing all available component types.


**Operation ID:** `get_all_api_v1_all_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `POST` /api/v1/run/{flow_id_or_name}

> Simplified Run Flow


Executes a specified flow by ID with support for streaming and telemetry (API key auth).&lt;br&gt;&lt;br&gt;This endpoint executes a flow identified by ID or name, with options for streaming the response&lt;br&gt;and tracking execution metrics. It handles both streaming and non-streaming execution modes.&lt;br&gt;This endpoint uses API key authentication (Bearer token).&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    background_tasks (BackgroundTasks): FastAPI background task manager&lt;br&gt;    flow (FlowRead | None): The flow to execute, loaded via dependency&lt;br&gt;    input_request (SimplifiedAPIRequest | None): Input parameters for the flow&lt;br&gt;    stream (bool): Whether to stream the response&lt;br&gt;    api_key_user (UserRead): Authenticated user from API key&lt;br&gt;    context (dict | None): Optional context to pass to the flow&lt;br&gt;    http_request (Request): The incoming HTTP request for extracting global variables&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results&lt;br&gt;    or a RunResponse with the complete execution results&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: For flow not found (404) or invalid input (400)&lt;br&gt;    APIException: For internal execution errors (500)&lt;br&gt;&lt;br&gt;Notes:&lt;br&gt;    - Supports both streaming and non-streaming execution modes&lt;br&gt;    - Tracks execution time and success/failure via telemetry&lt;br&gt;    - Handles graceful client disconnection in streaming mode&lt;br&gt;    - Provides detailed error handling with appropriate HTTP status codes&lt;br&gt;    - Extracts global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*&lt;br&gt;    - Merges extracted variables with the context parameter as &quot;request_variables&quot;&lt;br&gt;    - In streaming mode, uses EventManager to handle events:&lt;br&gt;        - &quot;add_message&quot;: New messages during execution&lt;br&gt;        - &quot;token&quot;: Individual tokens during streaming&lt;br&gt;        - &quot;end&quot;: Final execution result&lt;br&gt;    - Authentication: Requires API key (Bearer token)


**Operation ID:** `simplified_run_flow_api_v1_run__flow_id_or_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** |  (string) | ✅ Yes | - |
| `stream` | **query** |  (boolean) | ❌ No | - |
| `user_id` | **query** |  | ❌ No | - |


### Request Body

- **Required:** No


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/webhook/{flow_id_or_name}

> Webhook Run Flow


Run a flow using a webhook request.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id_or_name: The flow ID or endpoint name (used by dependency).&lt;br&gt;    flow: The flow to be executed.&lt;br&gt;    request: The incoming HTTP request.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    A dictionary containing the status of the task.&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: If the flow is not found or if there is an error processing the request.


**Operation ID:** `webhook_run_flow_api_v1_webhook__flow_id_or_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** |  (string) | ✅ Yes | - |
| `user_id` | **query** |  | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **202** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/run/advanced/{flow_id_or_name}

> Experimental Run Flow


Executes a specified flow by ID with optional input values, output selection, tweaks, and streaming capability.&lt;br&gt;&lt;br&gt;This endpoint supports running flows with caching to enhance performance and efficiency.&lt;br&gt;&lt;br&gt;### Parameters:&lt;br&gt;- &#x60;flow&#x60; (Flow): The flow object to be executed, resolved via dependency injection.&lt;br&gt;- &#x60;inputs&#x60; (List[InputValueRequest], optional): A list of inputs specifying the input values and components&lt;br&gt;  for the flow. Each input can target specific components and provide custom values.&lt;br&gt;- &#x60;outputs&#x60; (List[str], optional): A list of output names to retrieve from the executed flow.&lt;br&gt;  If not provided, all outputs are returned.&lt;br&gt;- &#x60;tweaks&#x60; (Optional[Tweaks], optional): A dictionary of tweaks to customize the flow execution.&lt;br&gt;  The tweaks can be used to modify the flow&#x27;s parameters and components.&lt;br&gt;  Tweaks can be overridden by the input values.&lt;br&gt;- &#x60;stream&#x60; (bool, optional): Specifies whether the results should be streamed. Defaults to False.&lt;br&gt;- &#x60;session_id&#x60; (Union[None, str], optional): An optional session ID to utilize existing session data for the flow&lt;br&gt;  execution.&lt;br&gt;- &#x60;api_key_user&#x60; (User): The user associated with the current API key. Automatically resolved from the API key.&lt;br&gt;&lt;br&gt;### Returns:&lt;br&gt;A &#x60;RunResponse&#x60; object containing the selected outputs (or all if not specified) of the executed flow&lt;br&gt;and the session ID.&lt;br&gt;The structure of the response accommodates multiple inputs, providing a nested list of outputs for each input.&lt;br&gt;&lt;br&gt;### Raises:&lt;br&gt;HTTPException: Indicates issues with finding the specified flow, invalid input formats, or internal errors during&lt;br&gt;flow execution.&lt;br&gt;&lt;br&gt;### Example usage:&lt;br&gt;&#x60;&#x60;&#x60;json&lt;br&gt;POST /run/flow_id&lt;br&gt;x-api-key: YOUR_API_KEY&lt;br&gt;Payload:&lt;br&gt;{&lt;br&gt;    &quot;inputs&quot;: [&lt;br&gt;        {&quot;components&quot;: [&quot;component1&quot;], &quot;input_value&quot;: &quot;value1&quot;},&lt;br&gt;        {&quot;components&quot;: [&quot;component3&quot;], &quot;input_value&quot;: &quot;value2&quot;}&lt;br&gt;    ],&lt;br&gt;    &quot;outputs&quot;: [&quot;Component Name&quot;, &quot;component_id&quot;],&lt;br&gt;    &quot;tweaks&quot;: {&quot;parameter_name&quot;: &quot;value&quot;, &quot;Component Name&quot;: {&quot;parameter_name&quot;: &quot;value&quot;}, &quot;component_id&quot;: {&quot;parameter_name&quot;: &quot;value&quot;}}&lt;br&gt;    &quot;stream&quot;: false&lt;br&gt;}&lt;br&gt;&#x60;&#x60;&#x60;&lt;br&gt;&lt;br&gt;This endpoint facilitates complex flow executions with customized inputs, outputs, and configurations,&lt;br&gt;catering to diverse application requirements.


**Operation ID:** `experimental_run_flow_api_v1_run_advanced__flow_id_or_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id_or_name` | **path** |  (string) | ✅ Yes | - |
| `user_id` | **query** |  | ❌ No | - |


### Request Body

- **Required:** No


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


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


Retrieve application configuration settings.&lt;br&gt;&lt;br&gt;Returns different configuration based on authentication status:&lt;br&gt;- Authenticated users: Full ConfigResponse with all settings&lt;br&gt;- Unauthenticated users: PublicConfigResponse with limited, safe-to-expose settings&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    user: The authenticated user, or None if unauthenticated.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    ConfigResponse | PublicConfigResponse: Configuration settings appropriate for the user&#x27;s auth status.&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: If an error occurs while retrieving the configuration.


**Operation ID:** `get_config_api_v1_config_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
