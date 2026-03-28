# Log

> Part of **Langflow**

---

## `GET` /logs-stream

> Stream Logs


HTTP/2 Server-Sent-Event (SSE) endpoint for streaming logs.&lt;br&gt;&lt;br&gt;Requires authentication to prevent exposure of sensitive log data.&lt;br&gt;It establishes a long-lived connection to the server and receives log messages in real-time.&lt;br&gt;The client should use the header &quot;Accept: text/event-stream&quot;.


**Operation ID:** `stream_logs_logs_stream_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `GET` /logs

> Logs


Retrieve application logs with authentication required.&lt;br&gt;&lt;br&gt;SECURITY: Logs may contain sensitive information and require authentication.


**Operation ID:** `logs_logs_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `lines_before` | **query** |  (integer) | ❌ No | The number of logs before the timestamp or the last log |
| `lines_after` | **query** |  (integer) | ❌ No | The number of logs after the timestamp |
| `timestamp` | **query** |  (integer) | ❌ No | The timestamp to start getting logs from |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
