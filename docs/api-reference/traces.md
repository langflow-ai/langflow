# Traces

> Part of **Langflow**

---

## `GET` /api/v1/monitor/traces

> Get Traces


Get list of traces for a flow.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    current_user: Authenticated user (required for authorization)&lt;br&gt;    flow_id: Filter by flow ID&lt;br&gt;    session_id: Filter by session ID&lt;br&gt;    status: Filter by trace status&lt;br&gt;    query: Search query for trace name/id/session id&lt;br&gt;    start_time: Filter traces starting on/after this time (ISO)&lt;br&gt;    end_time: Filter traces starting on/before this time (ISO)&lt;br&gt;    page: Page number (1-based)&lt;br&gt;    size: Page size&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    List of traces


**Operation ID:** `get_traces_api_v1_monitor_traces_get`


### Parameters

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



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/monitor/traces

> Delete Traces By Flow


Delete all traces for a flow.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_id: The ID of the flow whose traces should be deleted.&lt;br&gt;    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_traces_by_flow_api_v1_monitor_traces_delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/monitor/traces/{trace_id}

> Get Trace


Get a single trace with its hierarchical span tree.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    trace_id: The ID of the trace to retrieve.&lt;br&gt;    current_user: The authenticated user (required for authorization).&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    TraceRead containing the trace and its hierarchical span tree.


**Operation ID:** `get_trace_api_v1_monitor_traces__trace_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/monitor/traces/{trace_id}

> Delete Trace


Delete a trace and all its spans.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    trace_id: The ID of the trace to delete.&lt;br&gt;    current_user: The authenticated user (required for authorization).


**Operation ID:** `delete_trace_api_v1_monitor_traces__trace_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `trace_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
