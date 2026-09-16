# Chat

> Part of **Langflow**

---

## `POST` /api/v1/build/{flow_id}/flow

> Build Flow


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


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |
| `stop_component_id` | **query** | string | ❌ No | - |
| `start_component_id` | **query** | string | ❌ No | - |
| `log_builds` | **query** | boolean | ❌ No | - |
| `flow_name` | **query** | string | ❌ No | - |
| `event_delivery` | **query** | string | ❌ No | - |


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
  | `inputs` | object | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `files` | array[string] | ❌ No | - |
  **`inputs`** ❌

**`data`** ✅





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
## `GET` /api/v1/build/{job_id}/events

> Get Build Events


Get events for a specific build job.

Requires authentication to prevent unauthorized access to build events.


**Operation ID:** `get_build_events_api_v1_build__job_id__events_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** | string | ✅ Yes | - |
| `event_delivery` | **query** | string | ❌ No | - |



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
## `POST` /api/v1/build/{job_id}/cancel

> Cancel Build


Cancel a specific build job.

Requires authentication to prevent unauthorized build cancellation.


**Operation ID:** `cancel_build_api_v1_build__job_id__cancel_post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **path** | string | ✅ Yes | - |



### Responses

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
**`detail`** — Array of `object`




---
## `POST` /api/v1/build_public_tmp/{flow_id}/flow

> Build Public Tmp


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


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |
| `stop_component_id` | **query** | string | ❌ No | - |
| `start_component_id` | **query** | string | ❌ No | - |
| `log_builds` | **query** | boolean | ❌ No | - |
| `flow_name` | **query** | string | ❌ No | - |
| `event_delivery` | **query** | string | ❌ No | - |


### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Not required | - |
| Content-Type | `application/json` | ✅ |

### Request Body

- **Required:** No

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `inputs` | object | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `files` | array[string] | ❌ No | - |
  **`inputs`** ❌

**`data`** ✅





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
