# Agentic

> Part of **Langflow**

---

## `POST` /api/v1/agentic/execute/{flow_name}

> Execute Named Flow


Execute a named flow from the flows directory.


**Operation ID:** `execute_named_flow_api_v1_agentic_execute__flow_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_name` | **path** | string | ✅ Yes | - |


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
  | `flow_id` | string | ✅ Yes | - |
  | `component_id` | string | ❌ No | - |
  | `field_name` | string | ❌ No | - |
  | `input_value` | string | ❌ No | - |
  | `max_retries` | integer | ❌ No | - |
  | `model_name` | string | ❌ No | - |
  | `provider` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |
  



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
## `GET` /api/v1/agentic/check-config

> Check Assistant Config


Check if the Langflow Assistant is properly configured.

Returns available providers with their configured status and available models.


**Operation ID:** `check_assistant_config_api_v1_agentic_check_config_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `POST` /api/v1/agentic/assist

> Assist


Chat with the Langflow Assistant.


**Operation ID:** `assist_api_v1_agentic_assist_post`



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
  | `flow_id` | string | ✅ Yes | - |
  | `component_id` | string | ❌ No | - |
  | `field_name` | string | ❌ No | - |
  | `input_value` | string | ❌ No | - |
  | `max_retries` | integer | ❌ No | - |
  | `model_name` | string | ❌ No | - |
  | `provider` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |
  



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
## `POST` /api/v1/agentic/assist/stream

> Assist Stream


Chat with the Langflow Assistant with streaming progress updates.


**Operation ID:** `assist_stream_api_v1_agentic_assist_stream_post`



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
  | `flow_id` | string | ✅ Yes | - |
  | `component_id` | string | ❌ No | - |
  | `field_name` | string | ❌ No | - |
  | `input_value` | string | ❌ No | - |
  | `max_retries` | integer | ❌ No | - |
  | `model_name` | string | ❌ No | - |
  | `provider` | string | ❌ No | - |
  | `session_id` | string | ❌ No | - |
  



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
