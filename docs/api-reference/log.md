# Log

> Part of **Langflow**

---

## `GET` /logs-stream

> Stream Logs


HTTP/2 Server-Sent-Event (SSE) endpoint for streaming logs.

Requires authentication to prevent exposure of sensitive log data.
It establishes a long-lived connection to the server and receives log messages in real-time.
The client should use the header "Accept: text/event-stream".


**Operation ID:** `stream_logs_logs_stream_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `GET` /logs

> Logs


Retrieve application logs with authentication required.

SECURITY: Logs may contain sensitive information and require authentication.


**Operation ID:** `logs_logs_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `lines_before` | **query** | integer | ❌ No | The number of logs before the timestamp or the last log |
| `lines_after` | **query** | integer | ❌ No | The number of logs after the timestamp |
| `timestamp` | **query** | integer | ❌ No | The timestamp to start getting logs from |



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
