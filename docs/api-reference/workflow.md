# Workflow

> Part of **Langflow**

---

## `POST` /api/v2/workflows

> Execute Workflow


Execute a workflow with support for sync, stream, and background modes


**Operation ID:** `execute_workflow_api_v2_workflows_post`



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
  | `background` | boolean | ❌ No | - |
  | `stream` | boolean | ❌ No | - |
  | `flow_id` | string | ✅ Yes | - |
  | `inputs` | object | ❌ No | Component-specific inputs in flat format: 'component_id.param_name': value |
  



### Responses

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
| `status` | string = `queued` \| `in_progress` \| `completed` \| `failed` \| `cancelled` \| `timed_out` | Job execution status. |
| `errors` | array[object] | - |
| `inputs` | object | - |
| `outputs` | object | - |
**`errors`** — Array of `object`



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
**`detail`** — Array of `object`




---
## `GET` /api/v2/workflows

> Get Workflow Status


Get status of workflow job by job ID


**Operation ID:** `get_workflow_status_api_v2_workflows_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **query** | string | ❌ No | Job ID to query |



### Responses

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
| `status` | string = `queued` \| `in_progress` \| `completed` \| `failed` \| `cancelled` \| `timed_out` | Job execution status. |
| `errors` | array[object] | - |
| `inputs` | object | - |
| `outputs` | object | - |
**`errors`** — Array of `object`



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
**`detail`** — Array of `object`




---
## `POST` /api/v2/workflows/stop

> Stop Workflow


Stop a running workflow execution


**Operation ID:** `stop_workflow_api_v2_workflows_stop_post`



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
  | `job_id` | string | ✅ Yes | - |
  



### Responses

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
**`detail`** — Array of `object`




---
