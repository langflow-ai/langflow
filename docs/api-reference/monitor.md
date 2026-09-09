# Monitor

> Part of **Langflow**

---

## `GET` /api/v1/monitor/builds

> Get Vertex Builds


**Operation ID:** `get_vertex_builds_api_v1_monitor_builds_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `vertex_builds` | object | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `DELETE` /api/v1/monitor/builds

> Delete Vertex Builds


**Operation ID:** `delete_vertex_builds_api_v1_monitor_builds_delete`


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
## `GET` /api/v1/monitor/messages/sessions

> Get Message Sessions


**Operation ID:** `get_message_sessions_api_v1_monitor_messages_sessions_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ❌ No | - |



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
## `GET` /api/v1/monitor/messages

> Get Messages


**Operation ID:** `get_messages_api_v1_monitor_messages_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ❌ No | - |
| `session_id` | **query** | string | ❌ No | - |
| `sender` | **query** | string | ❌ No | - |
| `sender_name` | **query** | string | ❌ No | - |
| `order_by` | **query** | string | ❌ No | - |



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
## `DELETE` /api/v1/monitor/messages

> Delete Messages


**Operation ID:** `delete_messages_api_v1_monitor_messages_delete`



### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` / API Key (`x-api-key`) | ✅ |
| Content-Type | `application/json` | ✅ |

### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`



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
## `PUT` /api/v1/monitor/messages/{message_id}

> Update Message


**Operation ID:** `update_message_api_v1_monitor_messages__message_id__put`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `message_id` | **path** | string (uuid) | ✅ Yes | - |


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
  | `text` | string | ❌ No | - |
  | `sender` | string | ❌ No | - |
  | `sender_name` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |
  | `context_id` | string | ❌ No | - |
  | `files` | array[string] | ❌ No | - |
  | `edit` | boolean | ❌ No | - |
  | `error` | boolean | ❌ No | - |
  | `properties` | object | ❌ No | - |
  **`properties`** ❌

  **`source`** ❌

  **`usage`** ❌ — Token usage information from LLM responses.





### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `timestamp` | string (date-time) | - |
| `sender` | string | - |
| `sender_name` | string | - |
| `session_id` | string | - |
| `context_id` | string | - |
| `text` | string | - |
| `files` | array[string] | - |
| `error` | boolean | - |
| `edit` | boolean | - |
| `properties` | object | - |
| `category` | string | - |
| `content_blocks` | array[object] | - |
| `id` | string (uuid) | - |
| `flow_id` | string (uuid) | - |
**`properties`** ❌

  **`source`** ❌

  **`usage`** ❌ — Token usage information from LLM responses.

**`content_blocks`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `PATCH` /api/v1/monitor/messages/session/{old_session_id}

> Update Session Id


**Operation ID:** `update_session_id_api_v1_monitor_messages_session__old_session_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `old_session_id` | **path** | string | ✅ Yes | - |
| `new_session_id` | **query** | string | ✅ Yes | The new session ID to update to |



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
## `DELETE` /api/v1/monitor/messages/session/{session_id}

> Delete Messages Session


**Operation ID:** `delete_messages_session_api_v1_monitor_messages_session__session_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `session_id` | **path** | string | ✅ Yes | - |



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
## `GET` /api/v1/monitor/transactions

> Get Transactions


**Operation ID:** `get_transactions_api_v1_monitor_transactions_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **query** | string (uuid) | ✅ Yes | - |
| `page` | **query** | integer | ❌ No | Page number |
| `size` | **query** | integer | ❌ No | Page size |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `items` | array[object] | - |
| `total` | integer | - |
| `page` | integer | - |
| `size` | integer | - |
| `pages` | integer | - |
**`items`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
