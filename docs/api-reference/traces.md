# Traces

> Part of **Langflow**

---

## `GET` /api/v1/monitor/traces

> Get Traces


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


### Parameters

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



### Responses

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
**`traces`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `DELETE` /api/v1/monitor/traces

> Delete Traces By Flow


Delete all traces for a flow.

Args:
    flow_id: The ID of the flow whose traces should be deleted.
    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_traces_by_flow_api_v1_monitor_traces_delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/monitor/traces/{trace_id}

> Get Trace


Get a single trace with its hierarchical span tree.

Args:
    trace_id: The ID of the trace to retrieve.
    current_user: The authenticated user (required for authorization).

Returns:
    TraceRead containing the trace and its hierarchical span tree.


**Operation ID:** `get_trace_api_v1_monitor_traces__trace_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `name` | string | - |
| `status` | string = `unset` \| `ok` \| `error` | OpenTelemetry status codes.

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
**`spans`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `DELETE` /api/v1/monitor/traces/{trace_id}

> Delete Trace


Delete a trace and all its spans.

Args:
    trace_id: The ID of the trace to delete.
    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_trace_api_v1_monitor_traces__trace_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
