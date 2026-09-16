# Data Schemas

> **Langflow** — Schema Definitions

---

## `AccessTypeEnum`


**Type:** `string`




---
## `AssistantRequest`

> Request model for assistant interactions.


**Type:** `object`

### Properties

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


**Required fields:** `flow_id`



---
## `AuthSettings`

> Model representing authentication settings for MCP.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `auth_type` | string | ❌ No | - |
| `oauth_host` | string | ❌ No | - |
| `oauth_port` | string | ❌ No | - |
| `oauth_server_url` | string | ❌ No | - |
| `oauth_callback_path` | string | ❌ No | - |
| `oauth_callback_url` | string | ❌ No | - |
| `oauth_client_id` | string | ❌ No | - |
| `oauth_client_secret` | string (password) | ❌ No | - |
| `oauth_auth_url` | string | ❌ No | - |
| `oauth_token_url` | string | ❌ No | - |
| `oauth_mcp_scope` | string | ❌ No | - |
| `oauth_provider_scope` | string | ❌ No | - |




---
## `Body_build_flow_api_v1_build__flow_id__flow_post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `files` | array[string] | ❌ No | - |




---
## `Body_build_public_tmp_api_v1_build_public_tmp__flow_id__flow_post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `files` | array[string] | ❌ No | - |




---
## `Body_experimental_run_flow_api_v1_run_advanced__flow_id_or_name__post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | array[object] | ❌ No | - |
| `outputs` | array[string] | ❌ No | - |
| `tweaks` | object | ❌ No | A dictionary of tweaks to adjust the flow&#x27;s execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values. |
| `stream` | boolean | ❌ No | - |
| `session_id` | string | ❌ No | - |




---
## `Body_simplified_run_flow_api_v1_run__flow_id_or_name__post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_request` | object | ❌ No | - |
| `context` | object | ❌ No | - |




---
## `Body_upload_file_api_v1_files_upload__flow_id__post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | string | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_file_api_v1_flows_upload__post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | string | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_file_api_v1_projects_upload__post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | string | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_user_file_api_v2_files__post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | string | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_user_file_api_v2_files_post`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | string | ✅ Yes | - |


**Required fields:** `file`



---
## `CancelFlowResponse`

> Response model for flow build cancellation.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `success` | boolean | ✅ Yes | - |
| `message` | string | ✅ Yes | - |


**Required fields:** `success`, `message`



---
## `ChatOutputResponse`

> Chat output response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `message` | string | ✅ Yes | - |
| `sender` | string | ❌ No | - |
| `sender_name` | string | ❌ No | - |
| `session_id` | string | ❌ No | - |
| `stream_url` | string | ❌ No | - |
| `component_id` | string | ❌ No | - |
| `files` | array[object] | ❌ No | - |
| `type` | string | ✅ Yes | - |


**Required fields:** `message`, `type`



---
## `CodeContent`


**Type:** `object`




---
## `ComposerUrlResponse`

> Response model for MCP Composer connection details.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | ✅ Yes | - |
| `uses_composer` | boolean | ✅ Yes | - |
| `streamable_http_url` | string | ❌ No | - |
| `legacy_sse_url` | string | ❌ No | - |
| `error_message` | string | ❌ No | - |


**Required fields:** `project_id`, `uses_composer`



---
## `ConfigResponse`

> Full configuration response for authenticated users.

The &#x27;type&#x27; field is a discriminator to distinguish from PublicConfigResponse.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `max_file_size_upload` | integer | ✅ Yes | - |
| `event_delivery` | string | ✅ Yes | - |
| `voice_mode_available` | boolean | ✅ Yes | - |
| `frontend_timeout` | integer | ✅ Yes | - |
| `type` | string | ❌ No | - |
| `feature_flags` | object | ✅ Yes | - |
| `serialization_max_items_length` | integer | ✅ Yes | - |
| `serialization_max_text_length` | integer | ✅ Yes | - |
| `auto_saving` | boolean | ✅ Yes | - |
| `auto_saving_interval` | integer | ✅ Yes | - |
| `health_check_max_retries` | integer | ✅ Yes | - |
| `webhook_polling_interval` | integer | ✅ Yes | - |
| `public_flow_cleanup_interval` | integer | ✅ Yes | - |
| `public_flow_expiration` | integer | ✅ Yes | - |
| `webhook_auth_enable` | boolean | ✅ Yes | - |
| `default_folder_name` | string | ✅ Yes | - |
| `hide_getting_started_progress` | boolean | ✅ Yes | - |


**Required fields:** `max_file_size_upload`, `event_delivery`, `voice_mode_available`, `frontend_timeout`, `feature_flags`, `serialization_max_items_length`, `serialization_max_text_length`, `auto_saving`, `auto_saving_interval`, `health_check_max_retries`, `webhook_polling_interval`, `public_flow_cleanup_interval`, `public_flow_expiration`, `webhook_auth_enable`, `default_folder_name`, `hide_getting_started_progress`



---
## `ContentBlock`

> A block of content that can contain different types of content.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | ✅ Yes | - |
| `contents` | array[object] | ✅ Yes | - |
| `allow_markdown` | boolean | ❌ No | - |
| `media_url` | array[string] | ❌ No | - |


**Required fields:** `title`, `contents`



---
## `ErrorContent`


**Type:** `object`




---
## `EventDeliveryType`


**Type:** `string`




---
## `FeatureFlags`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `mvp_components` | boolean | ❌ No | - |




---
## `Flow`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `icon` | string | ❌ No | - |
| `icon_bg_color` | string | ❌ No | - |
| `gradient` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | boolean | ❌ No | - |
| `updated_at` | string (date-time) | ❌ No | - |
| `webhook` | boolean | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | string | ❌ No | - |
| `tags` | array[string] | ❌ No | - |
| `locked` | boolean | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | Can be exposed in the MCP server |
| `action_name` | string | ❌ No | The name of the action associated with the flow |
| `action_description` | string | ❌ No | The description of the action associated with the flow |
| `access_type` | string | ❌ No | - |
| `id` | string (uuid) | ❌ No | - |
| `user_id` | string (uuid) | ✅ Yes | - |
| `folder_id` | string (uuid) | ❌ No | - |
| `fs_path` | string | ❌ No | - |


**Required fields:** `name`, `user_id`



---
## `FlowCreate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `icon` | string | ❌ No | - |
| `icon_bg_color` | string | ❌ No | - |
| `gradient` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | boolean | ❌ No | - |
| `updated_at` | string (date-time) | ❌ No | - |
| `webhook` | boolean | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | string | ❌ No | - |
| `tags` | array[string] | ❌ No | - |
| `locked` | boolean | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | Can be exposed in the MCP server |
| `action_name` | string | ❌ No | The name of the action associated with the flow |
| `action_description` | string | ❌ No | The description of the action associated with the flow |
| `access_type` | string | ❌ No | - |
| `user_id` | string (uuid) | ❌ No | - |
| `folder_id` | string (uuid) | ❌ No | - |
| `fs_path` | string | ❌ No | - |


**Required fields:** `name`



---
## `FlowDataRequest`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `nodes` | array[object] | ✅ Yes | - |
| `edges` | array[object] | ✅ Yes | - |
| `viewport` | object | ❌ No | - |


**Required fields:** `nodes`, `edges`



---
## `FlowHeader`

> Model representing a header for a flow - Without the data.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | Unique identifier for the flow |
| `name` | string | ✅ Yes | The name of the flow |
| `folder_id` | string (uuid) | ❌ No | The ID of the folder containing the flow. None if not associated with a folder |
| `is_component` | boolean | ❌ No | Flag indicating whether the flow is a component |
| `endpoint_name` | string | ❌ No | The name of the endpoint associated with this flow |
| `description` | string | ❌ No | A description of the flow |
| `data` | object | ❌ No | The data of the component, if is_component is True |
| `access_type` | string | ❌ No | The access type of the flow |
| `tags` | array[string] | ❌ No | The tags of the flow |
| `mcp_enabled` | boolean | ❌ No | Flag indicating whether the flow is exposed in the MCP server |
| `action_name` | string | ❌ No | The name of the action associated with the flow |
| `action_description` | string | ❌ No | The description of the action associated with the flow |


**Required fields:** `id`, `name`



---
## `FlowListCreate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flows` | array[object] | ✅ Yes | - |


**Required fields:** `flows`



---
## `FlowRead`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `icon` | string | ❌ No | - |
| `icon_bg_color` | string | ❌ No | - |
| `gradient` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | boolean | ❌ No | - |
| `updated_at` | string (date-time) | ❌ No | - |
| `webhook` | boolean | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | string | ❌ No | - |
| `tags` | array[string] | ❌ No | The tags of the flow |
| `locked` | boolean | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | Can be exposed in the MCP server |
| `action_name` | string | ❌ No | The name of the action associated with the flow |
| `action_description` | string | ❌ No | The description of the action associated with the flow |
| `access_type` | string | ❌ No | - |
| `id` | string (uuid) | ✅ Yes | - |
| `user_id` | string (uuid) | ✅ Yes | - |
| `folder_id` | string (uuid) | ✅ Yes | - |


**Required fields:** `name`, `id`, `user_id`, `folder_id`



---
## `FlowUpdate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ❌ No | - |
| `description` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `folder_id` | string (uuid) | ❌ No | - |
| `endpoint_name` | string | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | - |
| `locked` | boolean | ❌ No | - |
| `action_name` | string | ❌ No | - |
| `action_description` | string | ❌ No | - |
| `access_type` | string | ❌ No | - |
| `fs_path` | string | ❌ No | - |




---
## `FolderCreate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `components_list` | array[string] | ❌ No | - |
| `flows_list` | array[string] | ❌ No | - |


**Required fields:** `name`



---
## `FolderRead`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `id` | string (uuid) | ✅ Yes | - |
| `parent_id` | string (uuid) | ✅ Yes | - |


**Required fields:** `name`, `id`, `parent_id`



---
## `FolderReadWithFlows`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `id` | string (uuid) | ✅ Yes | - |
| `parent_id` | string (uuid) | ✅ Yes | - |
| `flows` | array[object] | ❌ No | - |


**Required fields:** `name`, `id`, `parent_id`



---
## `FolderUpdate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ❌ No | - |
| `description` | string | ❌ No | - |
| `parent_id` | string (uuid) | ❌ No | - |
| `components` | array[string] | ❌ No | - |
| `flows` | array[string] | ❌ No | - |
| `auth_settings` | object | ❌ No | - |




---
## `FolderWithPaginatedFlows`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `folder` | object | ✅ Yes | - |
| `flows` | object | ✅ Yes | - |


**Required fields:** `folder`, `flows`



---
## `GraphData`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `nodes` | array[object] | ✅ Yes | - |
| `edges` | array[object] | ✅ Yes | - |
| `viewport` | object | ❌ No | - |


**Required fields:** `nodes`, `edges`



---
## `GraphDumpResponse`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `data` | object | ✅ Yes | - |
| `is_component` | boolean | ❌ No | - |
| `name` | string | ❌ No | - |
| `description` | string | ❌ No | - |
| `endpoint_name` | string | ❌ No | - |


**Required fields:** `data`



---
## `HTTPValidationError`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `detail` | array[object] | ❌ No | - |




---
## `HealthResponse`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | ❌ No | - |
| `chat` | string | ❌ No | - |
| `db` | string | ❌ No | - |




---
## `InputValueRequest`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `components` | array[string] | ❌ No | - |
| `input_value` | string | ❌ No | - |
| `session` | string | ❌ No | - |
| `type` | string | ❌ No | Defines on which components the input value should be applied. &#x27;any&#x27; applies to all input components. |
| `client_request_time` | integer | ❌ No | Client-side timestamp in milliseconds when the request was initiated. Used to calculate accurate end-to-end duration. |




---
## `JSONContent`


**Type:** `object`




---
## `MCPInstallRequest`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client` | string | ✅ Yes | - |
| `transport` | string | ❌ No | - |


**Required fields:** `client`



---
## `MCPProjectUpdateRequest`

> Request model for updating MCP project settings including auth.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `settings` | array[object] | ✅ Yes | - |
| `auth_settings` | object | ❌ No | Model representing authentication settings for MCP. |


**Required fields:** `settings`



---
## `MCPServerConfig`

> Pydantic model for MCP server configuration.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | string | ❌ No | - |
| `args` | array[string] | ❌ No | - |
| `env` | object | ❌ No | - |
| `headers` | object | ❌ No | - |
| `url` | string | ❌ No | - |




---
## `MCPSettings`

> Model representing MCP settings for a flow.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `mcp_enabled` | boolean | ❌ No | - |
| `action_name` | string | ❌ No | - |
| `action_description` | string | ❌ No | - |
| `name` | string | ❌ No | - |
| `description` | string | ❌ No | - |


**Required fields:** `id`



---
## `MediaContent`


**Type:** `object`




---
## `MessageRead`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `timestamp` | string (date-time) | ❌ No | - |
| `sender` | string | ✅ Yes | - |
| `sender_name` | string | ✅ Yes | - |
| `session_id` | string | ✅ Yes | - |
| `context_id` | string | ❌ No | - |
| `text` | string | ✅ Yes | - |
| `files` | array[string] | ❌ No | - |
| `error` | boolean | ❌ No | - |
| `edit` | boolean | ❌ No | - |
| `properties` | object | ❌ No | - |
| `category` | string | ❌ No | - |
| `content_blocks` | array[object] | ❌ No | - |
| `id` | string (uuid) | ✅ Yes | - |
| `flow_id` | string (uuid) | ✅ Yes | - |


**Required fields:** `sender`, `sender_name`, `session_id`, `text`, `id`, `flow_id`



---
## `MessageResponse`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | ❌ No | - |
| `flow_id` | string (uuid) | ❌ No | - |
| `timestamp` | string (date-time) | ❌ No | - |
| `sender` | string | ✅ Yes | - |
| `sender_name` | string | ✅ Yes | - |
| `session_id` | string | ✅ Yes | - |
| `context_id` | string | ❌ No | - |
| `text` | string | ✅ Yes | - |
| `files` | array[string] | ❌ No | - |
| `edit` | boolean | ✅ Yes | - |
| `duration` | number | ❌ No | - |
| `properties` | object | ❌ No | - |
| `category` | string | ❌ No | - |
| `content_blocks` | array[object] | ❌ No | - |


**Required fields:** `sender`, `sender_name`, `session_id`, `text`, `edit`



---
## `MessageUpdate`


**Type:** `object`

### Properties

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




---
## `OpenAIResponsesRequest`

> OpenAI-compatible responses request with flow_id as model parameter.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `model` | string | ✅ Yes | The flow ID to execute (used instead of OpenAI model) |
| `input` | string | ✅ Yes | The input text to process |
| `stream` | boolean | ❌ No | Whether to stream the response |
| `background` | boolean | ❌ No | Whether to process in background |
| `tools` | array[object] | ❌ No | Tools are not supported yet |
| `previous_response_id` | string | ❌ No | ID of previous response to continue conversation |
| `include` | array[string] | ❌ No | Additional response data to include, e.g., [&#x27;tool_call.results&#x27;] |


**Required fields:** `model`, `input`



---
## `Page_FlowRead_`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | array[object] | ✅ Yes | - |
| `total` | integer | ✅ Yes | - |
| `page` | integer | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `pages` | integer | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Page_Flow_`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | array[object] | ✅ Yes | - |
| `total` | integer | ✅ Yes | - |
| `page` | integer | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `pages` | integer | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Page_TransactionLogsResponse_`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | array[object] | ✅ Yes | - |
| `total` | integer | ✅ Yes | - |
| `page` | integer | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `pages` | integer | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Properties`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `text_color` | string | ❌ No | - |
| `background_color` | string | ❌ No | - |
| `edited` | boolean | ❌ No | - |
| `source` | object | ❌ No | - |
| `icon` | string | ❌ No | - |
| `allow_markdown` | boolean | ❌ No | - |
| `positive_feedback` | boolean | ❌ No | - |
| `state` | string | ❌ No | - |
| `targets` | array[object] | ❌ No | - |
| `usage` | object | ❌ No | Token usage information from LLM responses. |
| `build_duration` | number | ❌ No | - |




---
## `PublicConfigResponse`

> Configuration response for public/unauthenticated endpoints like the public playground.

Contains only the configuration values needed for public features, without sensitive data.
The &#x27;type&#x27; field is a discriminator to distinguish from full ConfigResponse.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `max_file_size_upload` | integer | ✅ Yes | - |
| `event_delivery` | string | ✅ Yes | - |
| `voice_mode_available` | boolean | ✅ Yes | - |
| `frontend_timeout` | integer | ✅ Yes | - |
| `type` | string | ❌ No | - |


**Required fields:** `max_file_size_upload`, `event_delivery`, `voice_mode_available`, `frontend_timeout`



---
## `ResultData`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `results` | object | ❌ No | - |
| `artifacts` | object | ❌ No | - |
| `outputs` | object | ❌ No | - |
| `logs` | object | ❌ No | - |
| `messages` | array[object] | ❌ No | - |
| `timedelta` | number | ❌ No | - |
| `duration` | string | ❌ No | - |
| `component_display_name` | string | ❌ No | - |
| `component_id` | string | ❌ No | - |
| `used_frozen_result` | boolean | ❌ No | - |




---
## `RunOutputs`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `outputs` | array[object] | ❌ No | - |




---
## `RunResponse`

> Run response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `outputs` | array[object] | ❌ No | - |
| `session_id` | string | ❌ No | - |




---
## `SimplifiedAPIRequest`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_value` | string | ❌ No | The input value |
| `input_type` | string | ❌ No | The input type |
| `output_type` | string | ❌ No | The output type |
| `output_component` | string | ❌ No | If there are multiple output components, you can specify the component to get the output from. |
| `tweaks` | object | ❌ No | A dictionary of tweaks to adjust the flow&#x27;s execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values. |
| `session_id` | string | ❌ No | The session id |




---
## `Source`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string | ❌ No | The id of the source component. |
| `display_name` | string | ❌ No | The display name of the source component. |
| `source` | string | ❌ No | The source of the message. Normally used to display the model name (e.g. &#x27;gpt-4o&#x27;) |




---
## `SpanReadResponse`

> Response model for a single span, with nested children.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `type` | string | ✅ Yes | Types of spans that can be recorded. |
| `status` | string | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | string (date-time) | ✅ Yes | - |
| `endTime` | string (date-time) | ✅ Yes | - |
| `latencyMs` | integer | ✅ Yes | - |
| `inputs` | object | ✅ Yes | - |
| `outputs` | object | ✅ Yes | - |
| `error` | string | ✅ Yes | - |
| `modelName` | string | ✅ Yes | - |
| `tokenUsage` | object | ✅ Yes | - |
| `children` | array[object] | ❌ No | - |


**Required fields:** `id`, `name`, `type`, `status`, `startTime`, `endTime`, `latencyMs`, `inputs`, `outputs`, `error`, `modelName`, `tokenUsage`



---
## `SpanStatus`

> OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error


**Type:** `string`




---
## `SpanType`

> Types of spans that can be recorded.


**Type:** `string`




---
## `TextContent`


**Type:** `object`




---
## `ToolContent`


**Type:** `object`




---
## `TraceListResponse`

> Paginated list response for traces.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `traces` | array[object] | ✅ Yes | - |
| `total` | integer | ✅ Yes | - |
| `pages` | integer | ✅ Yes | - |


**Required fields:** `traces`, `total`, `pages`



---
## `TraceRead`

> Response model for a single trace with its hierarchical span tree.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `status` | string | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | string (date-time) | ✅ Yes | - |
| `endTime` | string (date-time) | ✅ Yes | - |
| `totalLatencyMs` | integer | ✅ Yes | - |
| `totalTokens` | integer | ✅ Yes | - |
| `flowId` | string (uuid) | ✅ Yes | - |
| `sessionId` | string | ✅ Yes | - |
| `input` | object | ❌ No | - |
| `output` | object | ❌ No | - |
| `spans` | array[object] | ❌ No | - |


**Required fields:** `id`, `name`, `status`, `startTime`, `endTime`, `totalLatencyMs`, `totalTokens`, `flowId`, `sessionId`



---
## `TraceSummaryRead`

> Lightweight trace model for list endpoint.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `status` | string | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | string (date-time) | ✅ Yes | - |
| `totalLatencyMs` | integer | ✅ Yes | - |
| `totalTokens` | integer | ✅ Yes | - |
| `flowId` | string (uuid) | ✅ Yes | - |
| `sessionId` | string | ✅ Yes | - |
| `input` | object | ❌ No | - |
| `output` | object | ❌ No | - |


**Required fields:** `id`, `name`, `status`, `startTime`, `totalLatencyMs`, `totalTokens`, `flowId`, `sessionId`



---
## `TransactionLogsResponse`

> Transaction response model for logs view - excludes error and flow_id fields.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `timestamp` | string (date-time) | ❌ No | - |
| `vertex_id` | string | ✅ Yes | - |
| `target_id` | string | ❌ No | - |
| `inputs` | object | ❌ No | - |
| `outputs` | object | ❌ No | - |
| `status` | string | ✅ Yes | - |


**Required fields:** `id`, `vertex_id`, `status`



---
## `Tweaks`

> A dictionary of tweaks to adjust the flow&#x27;s execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values.


**Type:** `object`




---
## `Usage`

> Token usage information from LLM responses.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_tokens` | integer | ❌ No | - |
| `output_tokens` | integer | ❌ No | - |
| `total_tokens` | integer | ❌ No | - |




---
## `UserCreate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | string | ✅ Yes | - |
| `password` | string | ✅ Yes | - |
| `optins` | object | ❌ No | - |


**Required fields:** `username`, `password`



---
## `UserRead`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ❌ No | - |
| `username` | string | ✅ Yes | - |
| `profile_image` | string | ✅ Yes | - |
| `store_api_key` | string | ✅ Yes | - |
| `is_active` | boolean | ✅ Yes | - |
| `is_superuser` | boolean | ✅ Yes | - |
| `create_at` | string (date-time) | ✅ Yes | - |
| `updated_at` | string (date-time) | ✅ Yes | - |
| `last_login_at` | string (date-time) | ✅ Yes | - |
| `optins` | object | ❌ No | - |


**Required fields:** `username`, `profile_image`, `store_api_key`, `is_active`, `is_superuser`, `create_at`, `updated_at`, `last_login_at`



---
## `UserUpdate`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | string | ❌ No | - |
| `profile_image` | string | ❌ No | - |
| `password` | string | ❌ No | - |
| `is_active` | boolean | ❌ No | - |
| `is_superuser` | boolean | ❌ No | - |
| `last_login_at` | string (date-time) | ❌ No | - |
| `optins` | object | ❌ No | - |




---
## `UsersResponse`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `total_count` | integer | ✅ Yes | - |
| `users` | array[object] | ✅ Yes | - |


**Required fields:** `total_count`, `users`



---
## `ValidationError`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `loc` | array[string] | ✅ Yes | - |
| `msg` | string | ✅ Yes | - |
| `type` | string | ✅ Yes | - |
| `input` | object | ❌ No | - |
| `ctx` | object | ❌ No | - |


**Required fields:** `loc`, `msg`, `type`



---
## `VertexBuildMapModel`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `vertex_builds` | object | ✅ Yes | - |


**Required fields:** `vertex_builds`



---
## `VertexBuildTable`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `timestamp` | string (date-time) | ❌ No | - |
| `id` | string | ✅ Yes | - |
| `data` | object | ❌ No | - |
| `artifacts` | object | ❌ No | - |
| `params` | string | ❌ No | - |
| `valid` | boolean | ✅ Yes | - |
| `flow_id` | string (uuid) | ✅ Yes | - |
| `job_id` | string (uuid) | ❌ No | - |
| `build_id` | string (uuid) | ❌ No | - |


**Required fields:** `id`, `valid`, `flow_id`



---
## `ViewPort`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `x` | number | ✅ Yes | - |
| `y` | number | ✅ Yes | - |
| `zoom` | number | ✅ Yes | - |


**Required fields:** `x`, `y`, `zoom`



---
## `WorkflowExecutionRequest`

> Request schema for workflow execution.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `background` | boolean | ❌ No | - |
| `stream` | boolean | ❌ No | - |
| `flow_id` | string | ✅ Yes | - |
| `inputs` | object | ❌ No | Component-specific inputs in flat format: &#x27;component_id.param_name&#x27;: value |


**Required fields:** `flow_id`



---
## `WorkflowStopRequest`

> Request schema for stopping workflow.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `job_id` | string | ✅ Yes | - |


**Required fields:** `job_id`



---
## `WorkflowStopResponse`

> Response schema for stopping workflow.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `job_id` | string | ✅ Yes | - |
| `message` | string | ❌ No | - |


**Required fields:** `job_id`



---
## `langflow__api__schemas__UploadFileResponse`

> File upload response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `path` | string (path) | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `provider` | string | ❌ No | - |


**Required fields:** `id`, `name`, `path`, `size`



---
## `langflow__api__v1__schemas__UploadFileResponse`

> Upload file response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flowId` | string | ✅ Yes | - |
| `file_path` | string (path) | ✅ Yes | - |


**Required fields:** `flowId`, `file_path`



---
## `langflow__services__database__models__file__model__File`


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ❌ No | - |
| `user_id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `path` | string | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `provider` | string | ❌ No | - |
| `created_at` | string (date-time) | ❌ No | - |
| `updated_at` | string (date-time) | ❌ No | - |


**Required fields:** `user_id`, `name`, `path`, `size`



---
## `lfx__utils__schemas__File`

> File schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `type` | string | ✅ Yes | - |


**Required fields:** `path`, `name`, `type`



---
## `Postapi_v1_build_flow_id_flowrequestSchema`

> Request body for POST /api/v1/build/{flow_id}/flow


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `files` | array[string] | ❌ No | - |




---
## `Postapi_v1_build_flow_id_flowresponse_422Schema`

> Response body for POST /api/v1/build/{flow_id}/flow → 422


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `detail` | array[object] | ❌ No | - |




---
## `Postapi_v1_build_job_id_cancelresponse_200Schema`

> Response model for flow build cancellation.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `success` | boolean | ✅ Yes | - |
| `message` | string | ✅ Yes | - |


**Required fields:** `success`, `message`



---
## `Postapi_v1_run_flow_id_or_namerequestSchema`

> Request body for POST /api/v1/run/{flow_id_or_name}


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_request` | object | ❌ No | - |
| `context` | object | ❌ No | - |




---
## `Postapi_v1_run_advanced_flow_id_or_namerequestSchema`

> Request body for POST /api/v1/run/advanced/{flow_id_or_name}


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | array[object] | ❌ No | - |
| `outputs` | array[string] | ❌ No | - |
| `tweaks` | object | ❌ No | A dictionary of tweaks to adjust the flow&#x27;s execution. Allows customizing flow behavior dynamically. All tweaks are overridden by the input values. |
| `stream` | boolean | ❌ No | - |
| `session_id` | string | ❌ No | - |




---
## `Postapi_v1_run_advanced_flow_id_or_nameresponse_200Schema`

> Run response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `outputs` | array[object] | ❌ No | - |
| `session_id` | string | ❌ No | - |




---
## `Getapi_v1_configresponse_200Schema`

> Full configuration response for authenticated users.

The &#x27;type&#x27; field is a discriminator to distinguish from PublicConfigResponse.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `max_file_size_upload` | integer | ✅ Yes | - |
| `event_delivery` | string | ✅ Yes | - |
| `voice_mode_available` | boolean | ✅ Yes | - |
| `frontend_timeout` | integer | ✅ Yes | - |
| `type` | string | ❌ No | - |
| `feature_flags` | object | ✅ Yes | - |
| `serialization_max_items_length` | integer | ✅ Yes | - |
| `serialization_max_text_length` | integer | ✅ Yes | - |
| `auto_saving` | boolean | ✅ Yes | - |
| `auto_saving_interval` | integer | ✅ Yes | - |
| `health_check_max_retries` | integer | ✅ Yes | - |
| `webhook_polling_interval` | integer | ✅ Yes | - |
| `public_flow_cleanup_interval` | integer | ✅ Yes | - |
| `public_flow_expiration` | integer | ✅ Yes | - |
| `webhook_auth_enable` | boolean | ✅ Yes | - |
| `default_folder_name` | string | ✅ Yes | - |
| `hide_getting_started_progress` | boolean | ✅ Yes | - |


**Required fields:** `max_file_size_upload`, `event_delivery`, `voice_mode_available`, `frontend_timeout`, `feature_flags`, `serialization_max_items_length`, `serialization_max_text_length`, `auto_saving`, `auto_saving_interval`, `health_check_max_retries`, `webhook_polling_interval`, `public_flow_cleanup_interval`, `public_flow_expiration`, `webhook_auth_enable`, `default_folder_name`, `hide_getting_started_progress`



---
## `Postapi_v1_flows_requestSchema`

> Request body for POST /api/v1/flows/


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `icon` | string | ❌ No | - |
| `icon_bg_color` | string | ❌ No | - |
| `gradient` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | boolean | ❌ No | - |
| `updated_at` | string (date-time) | ❌ No | - |
| `webhook` | boolean | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | string | ❌ No | - |
| `tags` | array[string] | ❌ No | - |
| `locked` | boolean | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | Can be exposed in the MCP server |
| `action_name` | string | ❌ No | The name of the action associated with the flow |
| `action_description` | string | ❌ No | The description of the action associated with the flow |
| `access_type` | string | ❌ No | - |
| `user_id` | string (uuid) | ❌ No | - |
| `folder_id` | string (uuid) | ❌ No | - |
| `fs_path` | string | ❌ No | - |


**Required fields:** `name`



---
## `Postapi_v1_flows_response_201Schema`

> Response body for POST /api/v1/flows/ → 201


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `icon` | string | ❌ No | - |
| `icon_bg_color` | string | ❌ No | - |
| `gradient` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | boolean | ❌ No | - |
| `updated_at` | string (date-time) | ❌ No | - |
| `webhook` | boolean | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | string | ❌ No | - |
| `tags` | array[string] | ❌ No | The tags of the flow |
| `locked` | boolean | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | Can be exposed in the MCP server |
| `action_name` | string | ❌ No | The name of the action associated with the flow |
| `action_description` | string | ❌ No | The description of the action associated with the flow |
| `access_type` | string | ❌ No | - |
| `id` | string (uuid) | ✅ Yes | - |
| `user_id` | string (uuid) | ✅ Yes | - |
| `folder_id` | string (uuid) | ✅ Yes | - |


**Required fields:** `name`, `id`, `user_id`, `folder_id`



---
## `Getapi_v1_flows_response_200Schema`

> Response body for GET /api/v1/flows/ → 200


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | array[object] | ✅ Yes | - |
| `total` | integer | ✅ Yes | - |
| `page` | integer | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `pages` | integer | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Patchapi_v1_flows_flow_idrequestSchema`

> Request body for PATCH /api/v1/flows/{flow_id}


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ❌ No | - |
| `description` | string | ❌ No | - |
| `data` | object | ❌ No | - |
| `folder_id` | string (uuid) | ❌ No | - |
| `endpoint_name` | string | ❌ No | - |
| `mcp_enabled` | boolean | ❌ No | - |
| `locked` | boolean | ❌ No | - |
| `action_name` | string | ❌ No | - |
| `action_description` | string | ❌ No | - |
| `access_type` | string | ❌ No | - |
| `fs_path` | string | ❌ No | - |




---
## `Postapi_v1_flows_batch_requestSchema`

> Request body for POST /api/v1/flows/batch/


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flows` | array[object] | ✅ Yes | - |


**Required fields:** `flows`



---
## `Postapi_v1_flows_upload_requestSchema`

> Request body for POST /api/v1/flows/upload/


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | string | ✅ Yes | - |


**Required fields:** `file`



---
## `Postapi_v1_users_requestSchema`

> Request body for POST /api/v1/users/


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | string | ✅ Yes | - |
| `password` | string | ✅ Yes | - |
| `optins` | object | ❌ No | - |


**Required fields:** `username`, `password`



---
## `Postapi_v1_users_response_201Schema`

> Response body for POST /api/v1/users/ → 201


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ❌ No | - |
| `username` | string | ✅ Yes | - |
| `profile_image` | string | ✅ Yes | - |
| `store_api_key` | string | ✅ Yes | - |
| `is_active` | boolean | ✅ Yes | - |
| `is_superuser` | boolean | ✅ Yes | - |
| `create_at` | string (date-time) | ✅ Yes | - |
| `updated_at` | string (date-time) | ✅ Yes | - |
| `last_login_at` | string (date-time) | ✅ Yes | - |
| `optins` | object | ❌ No | - |


**Required fields:** `username`, `profile_image`, `store_api_key`, `is_active`, `is_superuser`, `create_at`, `updated_at`, `last_login_at`



---
## `Getapi_v1_users_response_200Schema`

> Response body for GET /api/v1/users/ → 200


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `total_count` | integer | ✅ Yes | - |
| `users` | array[object] | ✅ Yes | - |


**Required fields:** `total_count`, `users`



---
## `Patchapi_v1_users_user_idrequestSchema`

> Request body for PATCH /api/v1/users/{user_id}


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | string | ❌ No | - |
| `profile_image` | string | ❌ No | - |
| `password` | string | ❌ No | - |
| `is_active` | boolean | ❌ No | - |
| `is_superuser` | boolean | ❌ No | - |
| `last_login_at` | string (date-time) | ❌ No | - |
| `optins` | object | ❌ No | - |




---
## `Postapi_v1_files_upload_flow_idresponse_201Schema`

> Upload file response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flowId` | string | ✅ Yes | - |
| `file_path` | string (path) | ✅ Yes | - |


**Required fields:** `flowId`, `file_path`



---
## `Getapi_v1_monitor_buildsresponse_200Schema`

> Response body for GET /api/v1/monitor/builds → 200


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `vertex_builds` | object | ✅ Yes | - |


**Required fields:** `vertex_builds`



---
## `Putapi_v1_monitor_messages_message_idrequestSchema`

> Request body for PUT /api/v1/monitor/messages/{message_id}


**Type:** `object`

### Properties

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




---
## `Putapi_v1_monitor_messages_message_idresponse_200Schema`

> Response body for PUT /api/v1/monitor/messages/{message_id} → 200


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `timestamp` | string (date-time) | ❌ No | - |
| `sender` | string | ✅ Yes | - |
| `sender_name` | string | ✅ Yes | - |
| `session_id` | string | ✅ Yes | - |
| `context_id` | string | ❌ No | - |
| `text` | string | ✅ Yes | - |
| `files` | array[string] | ❌ No | - |
| `error` | boolean | ❌ No | - |
| `edit` | boolean | ❌ No | - |
| `properties` | object | ❌ No | - |
| `category` | string | ❌ No | - |
| `content_blocks` | array[object] | ❌ No | - |
| `id` | string (uuid) | ✅ Yes | - |
| `flow_id` | string (uuid) | ✅ Yes | - |


**Required fields:** `sender`, `sender_name`, `session_id`, `text`, `id`, `flow_id`



---
## `Getapi_v1_monitor_tracesresponse_200Schema`

> Paginated list response for traces.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `traces` | array[object] | ✅ Yes | - |
| `total` | integer | ✅ Yes | - |
| `pages` | integer | ✅ Yes | - |


**Required fields:** `traces`, `total`, `pages`



---
## `Getapi_v1_monitor_traces_trace_idresponse_200Schema`

> Response model for a single trace with its hierarchical span tree.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `status` | string | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | string (date-time) | ✅ Yes | - |
| `endTime` | string (date-time) | ✅ Yes | - |
| `totalLatencyMs` | integer | ✅ Yes | - |
| `totalTokens` | integer | ✅ Yes | - |
| `flowId` | string (uuid) | ✅ Yes | - |
| `sessionId` | string | ✅ Yes | - |
| `input` | object | ❌ No | - |
| `output` | object | ❌ No | - |
| `spans` | array[object] | ❌ No | - |


**Required fields:** `id`, `name`, `status`, `startTime`, `endTime`, `totalLatencyMs`, `totalTokens`, `flowId`, `sessionId`



---
## `Postapi_v1_projects_requestSchema`

> Request body for POST /api/v1/projects/


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `components_list` | array[string] | ❌ No | - |
| `flows_list` | array[string] | ❌ No | - |


**Required fields:** `name`



---
## `Postapi_v1_projects_response_201Schema`

> Response body for POST /api/v1/projects/ → 201


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `id` | string (uuid) | ✅ Yes | - |
| `parent_id` | string (uuid) | ✅ Yes | - |


**Required fields:** `name`, `id`, `parent_id`



---
## `Getapi_v1_projects_project_idresponse_200Schema`

> Response body for GET /api/v1/projects/{project_id} → 200


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ✅ Yes | - |
| `description` | string | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `id` | string (uuid) | ✅ Yes | - |
| `parent_id` | string (uuid) | ✅ Yes | - |
| `flows` | array[object] | ❌ No | - |


**Required fields:** `name`, `id`, `parent_id`



---
## `Patchapi_v1_projects_project_idrequestSchema`

> Request body for PATCH /api/v1/projects/{project_id}


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | ❌ No | - |
| `description` | string | ❌ No | - |
| `parent_id` | string (uuid) | ❌ No | - |
| `components` | array[string] | ❌ No | - |
| `flows` | array[string] | ❌ No | - |
| `auth_settings` | object | ❌ No | - |




---
## `Patchapi_v1_mcp_project_project_idrequestSchema`

> Request model for updating MCP project settings including auth.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `settings` | array[object] | ✅ Yes | - |
| `auth_settings` | object | ❌ No | Model representing authentication settings for MCP. |


**Required fields:** `settings`



---
## `Postapi_v1_mcp_project_project_id_installrequestSchema`

> Request body for POST /api/v1/mcp/project/{project_id}/install


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client` | string | ✅ Yes | - |
| `transport` | string | ❌ No | - |


**Required fields:** `client`



---
## `Getapi_v1_mcp_project_project_id_composerurlresponse_200Schema`

> Response model for MCP Composer connection details.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_id` | string | ✅ Yes | - |
| `uses_composer` | boolean | ✅ Yes | - |
| `streamable_http_url` | string | ❌ No | - |
| `legacy_sse_url` | string | ❌ No | - |
| `error_message` | string | ❌ No | - |


**Required fields:** `project_id`, `uses_composer`



---
## `Postapi_v1_responsesrequestSchema`

> OpenAI-compatible responses request with flow_id as model parameter.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `model` | string | ✅ Yes | The flow ID to execute (used instead of OpenAI model) |
| `input` | string | ✅ Yes | The input text to process |
| `stream` | boolean | ❌ No | Whether to stream the response |
| `background` | boolean | ❌ No | Whether to process in background |
| `tools` | array[object] | ❌ No | Tools are not supported yet |
| `previous_response_id` | string | ❌ No | ID of previous response to continue conversation |
| `include` | array[string] | ❌ No | Additional response data to include, e.g., [&#x27;tool_call.results&#x27;] |


**Required fields:** `model`, `input`



---
## `Postapi_v1_agentic_execute_flow_namerequestSchema`

> Request model for assistant interactions.


**Type:** `object`

### Properties

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


**Required fields:** `flow_id`



---
## `Postapi_v2_files_response_201Schema`

> File upload response schema.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | string (uuid) | ✅ Yes | - |
| `name` | string | ✅ Yes | - |
| `path` | string (path) | ✅ Yes | - |
| `size` | integer | ✅ Yes | - |
| `provider` | string | ❌ No | - |


**Required fields:** `id`, `name`, `path`, `size`



---
## `Postapi_v2_mcp_servers_server_namerequestSchema`

> Pydantic model for MCP server configuration.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | string | ❌ No | - |
| `args` | array[string] | ❌ No | - |
| `env` | object | ❌ No | - |
| `headers` | object | ❌ No | - |
| `url` | string | ❌ No | - |




---
## `Postapi_v2_workflowsrequestSchema`

> Request schema for workflow execution.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `background` | boolean | ❌ No | - |
| `stream` | boolean | ❌ No | - |
| `flow_id` | string | ✅ Yes | - |
| `inputs` | object | ❌ No | Component-specific inputs in flat format: &#x27;component_id.param_name&#x27;: value |


**Required fields:** `flow_id`



---
## `Postapi_v2_workflowsresponse_200Schema`

> Streaming event response.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `type` | string | ✅ Yes | - |
| `run_id` | string | ✅ Yes | - |
| `timestamp` | integer | ✅ Yes | - |
| `raw_event` | object | ✅ Yes | - |


**Required fields:** `type`, `run_id`, `timestamp`, `raw_event`



---
## `Postapi_v2_workflows_stoprequestSchema`

> Request schema for stopping workflow.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `job_id` | string | ✅ Yes | - |


**Required fields:** `job_id`



---
## `Postapi_v2_workflows_stopresponse_200Schema`

> Response schema for stopping workflow.


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `job_id` | string | ✅ Yes | - |
| `message` | string | ❌ No | - |


**Required fields:** `job_id`



---
## `Gethealth_checkresponse_200Schema`

> Response body for GET /health_check → 200


**Type:** `object`

### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | ❌ No | - |
| `chat` | string | ❌ No | - |
| `db` | string | ❌ No | - |




---
