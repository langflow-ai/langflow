# OpenAI Responses API

> Part of **Langflow**

---

## `POST` /api/v1/responses

> Create Response


Create a response using OpenAI Responses API format.&lt;br&gt;&lt;br&gt;This endpoint accepts a flow_id in the model parameter and processes&lt;br&gt;the input through the specified Langflow flow.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    request: OpenAI Responses API request with model (flow_id) and input&lt;br&gt;    background_tasks: FastAPI background task manager&lt;br&gt;    api_key_user: Authenticated user from API key&lt;br&gt;    http_request: The incoming HTTP request&lt;br&gt;    telemetry_service: Telemetry service for logging&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    OpenAI-compatible response or streaming response&lt;br&gt;&lt;br&gt;Raises:&lt;br&gt;    HTTPException: For validation errors or flow execution issues


**Operation ID:** `create_response_api_v1_responses_post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
