# Monitor

> Part of **Langflow**

---

## `GET` /api/v1/monitor/builds

> Get Vertex Builds


**Operation ID:** `get_vertex_builds_api_v1_monitor_builds_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/monitor/builds

> Delete Vertex Builds


**Operation ID:** `delete_vertex_builds_api_v1_monitor_builds_delete`


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
## `GET` /api/v1/monitor/messages/sessions

> Get Message Sessions


**Operation ID:** `get_message_sessions_api_v1_monitor_messages_sessions_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/monitor/messages

> Get Messages


**Operation ID:** `get_messages_api_v1_monitor_messages_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  | ❌ No | - |
| `session_id` | **query** |  | ❌ No | - |
| `sender` | **query** |  | ❌ No | - |
| `sender_name` | **query** |  | ❌ No | - |
| `order_by` | **query** |  | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/monitor/messages

> Delete Messages


**Operation ID:** `delete_messages_api_v1_monitor_messages_delete`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `PUT` /api/v1/monitor/messages/{message_id}

> Update Message


**Operation ID:** `update_message_api_v1_monitor_messages__message_id__put`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `message_id` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `PATCH` /api/v1/monitor/messages/session/{old_session_id}

> Update Session Id


**Operation ID:** `update_session_id_api_v1_monitor_messages_session__old_session_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `old_session_id` | **path** |  (string) | ✅ Yes | - |
| `new_session_id` | **query** |  (string) | ✅ Yes | The new session ID to update to |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/monitor/messages/session/{session_id}

> Delete Messages Session


**Operation ID:** `delete_messages_session_api_v1_monitor_messages_session__session_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `session_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/monitor/transactions

> Get Transactions


**Operation ID:** `get_transactions_api_v1_monitor_transactions_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** |  (string) | ✅ Yes | - |
| `page` | **query** |  (integer) | ❌ No | Page number |
| `size` | **query** |  (integer) | ❌ No | Page size |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
