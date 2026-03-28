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
| `flow_name` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/agentic/check-config

> Check Assistant Config


Check if the Langflow Assistant is properly configured.&lt;br&gt;&lt;br&gt;Returns available providers with their configured status and available models.


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



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/agentic/assist/stream

> Assist Stream


Chat with the Langflow Assistant with streaming progress updates.


**Operation ID:** `assist_stream_api_v1_agentic_assist_stream_post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
