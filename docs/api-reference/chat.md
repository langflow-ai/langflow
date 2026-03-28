# Chat

> Part of **Langflow**

---

## `POST` /api/v1/build/{flow_id}/flow

> Build Flow


Build and process a flow, returning a job ID for event polling.&lt;br&gt;&lt;br&gt;This endpoint requires authentication through the CurrentActiveUser dependency.&lt;br&gt;For public flows that don&#x27;t require authentication, use the /build_public_tmp/flow_id/flow endpoint.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id: UUID of the flow to build&lt;br&gt;    background_tasks: Background tasks manager&lt;br&gt;    inputs: Optional input values for the flow&lt;br&gt;    data: Optional flow data&lt;br&gt;    files: Optional files to include&lt;br&gt;    stop_component_id: Optional ID of component to stop at&lt;br&gt;    start_component_id: Optional ID of component to start from&lt;br&gt;    log_builds: Whether to log the build process&lt;br&gt;    current_user: The authenticated user&lt;br&gt;    queue_service: Queue service for job management&lt;br&gt;    flow_name: Optional name for the flow&lt;br&gt;    event_delivery: Optional event delivery type - default is streaming&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    Dict with job_id that can be used to poll for build status


**Operation ID:** `build_flow_api_v1_build__flow_id__flow_post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |
| `stop_component_id` | **query** |  | ❌ No | - |
| `start_component_id` | **query** |  | ❌ No | - |
| `log_builds` | **query** |  (boolean) | ❌ No | - |
| `flow_name` | **query** |  | ❌ No | - |
| `event_delivery` | **query** |  (string) | ❌ No | - |


### Request Body

- **Required:** No


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/build/{job_id}/events

> Get Build Events


Get events for a specific build job.&lt;br&gt;&lt;br&gt;Requires authentication to prevent unauthorized access to build events.


**Operation ID:** `get_build_events_api_v1_build__job_id__events_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** |  (string) | ✅ Yes | - |
| `event_delivery` | **query** |  (string) | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/build/{job_id}/cancel

> Cancel Build


Cancel a specific build job.&lt;br&gt;&lt;br&gt;Requires authentication to prevent unauthorized build cancellation.


**Operation ID:** `cancel_build_api_v1_build__job_id__cancel_post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/build_public_tmp/{flow_id}/flow

> Build Public Tmp


Build a public flow without requiring authentication.&lt;br&gt;&lt;br&gt;This endpoint is specifically for public flows that don&#x27;t require authentication.&lt;br&gt;It uses a client_id cookie to create a deterministic flow ID for tracking purposes.&lt;br&gt;&lt;br&gt;The endpoint:&lt;br&gt;1. Verifies the requested flow is marked as public in the database&lt;br&gt;2. Creates a deterministic UUID based on client_id and flow_id&lt;br&gt;3. Uses the flow owner&#x27;s permissions to build the flow&lt;br&gt;&lt;br&gt;Requirements:&lt;br&gt;- The flow must be marked as PUBLIC in the database&lt;br&gt;- The request must include a client_id cookie&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id: UUID of the public flow to build&lt;br&gt;    background_tasks: Background tasks manager&lt;br&gt;    inputs: Optional input values for the flow&lt;br&gt;    data: Optional flow data&lt;br&gt;    files: Optional files to include&lt;br&gt;    stop_component_id: Optional ID of component to stop at&lt;br&gt;    start_component_id: Optional ID of component to start from&lt;br&gt;    log_builds: Whether to log the build process&lt;br&gt;    flow_name: Optional name for the flow&lt;br&gt;    request: FastAPI request object (needed for cookie access)&lt;br&gt;    queue_service: Queue service for job management&lt;br&gt;    event_delivery: Optional event delivery type - default is streaming&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    Dict with job_id that can be used to poll for build status


**Operation ID:** `build_public_tmp_api_v1_build_public_tmp__flow_id__flow_post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |
| `stop_component_id` | **query** |  | ❌ No | - |
| `start_component_id` | **query** |  | ❌ No | - |
| `log_builds` | **query** |  | ❌ No | - |
| `flow_name` | **query** |  | ❌ No | - |
| `event_delivery` | **query** |  (string) | ❌ No | - |


### Request Body

- **Required:** No


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
