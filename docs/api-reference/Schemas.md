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
| `flow_id` | `string` | ✅ Yes | - |
| `component_id` | object | ❌ No | - |
| `field_name` | object | ❌ No | - |
| `input_value` | object | ❌ No | - |
| `max_retries` | object | ❌ No | - |
| `model_name` | object | ❌ No | - |
| `provider` | object | ❌ No | - |
| `session_id` | object | ❌ No | - |


**Required fields:** `flow_id`



---
## `AuthSettings`

> Model representing authentication settings for MCP.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `auth_type` | `string` | ❌ No | - |
| `oauth_host` | object | ❌ No | - |
| `oauth_port` | object | ❌ No | - |
| `oauth_server_url` | object | ❌ No | - |
| `oauth_callback_path` | object | ❌ No | - |
| `oauth_callback_url` | object | ❌ No | - |
| `oauth_client_id` | object | ❌ No | - |
| `oauth_client_secret` | object | ❌ No | - |
| `oauth_auth_url` | object | ❌ No | - |
| `oauth_token_url` | object | ❌ No | - |
| `oauth_mcp_scope` | object | ❌ No | - |
| `oauth_provider_scope` | object | ❌ No | - |




---
## `Body_build_flow_api_v1_build__flow_id__flow_post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `files` | object | ❌ No | - |




---
## `Body_build_public_tmp_api_v1_build_public_tmp__flow_id__flow_post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `files` | object | ❌ No | - |




---
## `Body_experimental_run_flow_api_v1_run_advanced__flow_id_or_name__post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | object | ❌ No | - |
| `outputs` | object | ❌ No | - |
| `tweaks` | object | ❌ No | - |
| `stream` | `boolean` | ❌ No | - |
| `session_id` | object | ❌ No | - |




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
| `file` | `string` | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_file_api_v1_flows_upload__post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | `string` | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_file_api_v1_projects_upload__post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | `string` | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_user_file_api_v2_files__post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | `string` | ✅ Yes | - |


**Required fields:** `file`



---
## `Body_upload_user_file_api_v2_files_post`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | `string` | ✅ Yes | - |


**Required fields:** `file`



---
## `CancelFlowResponse`

> Response model for flow build cancellation.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `success` | `boolean` | ✅ Yes | - |
| `message` | `string` | ✅ Yes | - |


**Required fields:** `success`, `message`



---
## `ChatOutputResponse`

> Chat output response schema.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `message` | object | ✅ Yes | - |
| `sender` | object | ❌ No | - |
| `sender_name` | object | ❌ No | - |
| `session_id` | object | ❌ No | - |
| `stream_url` | object | ❌ No | - |
| `component_id` | object | ❌ No | - |
| `files` | `array` [object] | ❌ No | - |
| `type` | `string` | ✅ Yes | - |


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
| `project_id` | `string` | ✅ Yes | - |
| `uses_composer` | `boolean` | ✅ Yes | - |
| `streamable_http_url` | object | ❌ No | - |
| `legacy_sse_url` | object | ❌ No | - |
| `error_message` | object | ❌ No | - |


**Required fields:** `project_id`, `uses_composer`



---
## `ConfigResponse`

> Full configuration response for authenticated users.

The &#x27;type&#x27; field is a discriminator to distinguish from PublicConfigResponse.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `max_file_size_upload` | `integer` | ✅ Yes | - |
| `event_delivery` | `string` | ✅ Yes | - |
| `voice_mode_available` | `boolean` | ✅ Yes | - |
| `frontend_timeout` | `integer` | ✅ Yes | - |
| `type` | `string` | ❌ No | - |
| `feature_flags` | `object` | ✅ Yes | - |
| `serialization_max_items_length` | `integer` | ✅ Yes | - |
| `serialization_max_text_length` | `integer` | ✅ Yes | - |
| `auto_saving` | `boolean` | ✅ Yes | - |
| `auto_saving_interval` | `integer` | ✅ Yes | - |
| `health_check_max_retries` | `integer` | ✅ Yes | - |
| `webhook_polling_interval` | `integer` | ✅ Yes | - |
| `public_flow_cleanup_interval` | `integer` | ✅ Yes | - |
| `public_flow_expiration` | `integer` | ✅ Yes | - |
| `webhook_auth_enable` | `boolean` | ✅ Yes | - |
| `default_folder_name` | `string` | ✅ Yes | - |
| `hide_getting_started_progress` | `boolean` | ✅ Yes | - |


**Required fields:** `max_file_size_upload`, `event_delivery`, `voice_mode_available`, `frontend_timeout`, `feature_flags`, `serialization_max_items_length`, `serialization_max_text_length`, `auto_saving`, `auto_saving_interval`, `health_check_max_retries`, `webhook_polling_interval`, `public_flow_cleanup_interval`, `public_flow_expiration`, `webhook_auth_enable`, `default_folder_name`, `hide_getting_started_progress`



---
## `ContentBlock`

> A block of content that can contain different types of content.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | `string` | ✅ Yes | - |
| `contents` | `array` [object] | ✅ Yes | - |
| `allow_markdown` | `boolean` | ❌ No | - |
| `media_url` | object | ❌ No | - |


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
| `mvp_components` | `boolean` | ❌ No | - |




---
## `Flow`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | ✅ Yes | - |
| `description` | object | ❌ No | - |
| `icon` | object | ❌ No | - |
| `icon_bg_color` | object | ❌ No | - |
| `gradient` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | object | ❌ No | - |
| `updated_at` | object | ❌ No | - |
| `webhook` | object | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | object | ❌ No | - |
| `tags` | object | ❌ No | - |
| `locked` | object | ❌ No | - |
| `mcp_enabled` | object | ❌ No | Can be exposed in the MCP server |
| `action_name` | object | ❌ No | The name of the action associated with the flow |
| `action_description` | object | ❌ No | The description of the action associated with the flow |
| `access_type` | `string` | ❌ No | - |
| `id` | `string` (uuid) | ❌ No | - |
| `user_id` | object | ✅ Yes | - |
| `folder_id` | object | ❌ No | - |
| `fs_path` | object | ❌ No | - |


**Required fields:** `name`, `user_id`



---
## `FlowCreate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | ✅ Yes | - |
| `description` | object | ❌ No | - |
| `icon` | object | ❌ No | - |
| `icon_bg_color` | object | ❌ No | - |
| `gradient` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | object | ❌ No | - |
| `updated_at` | object | ❌ No | - |
| `webhook` | object | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | object | ❌ No | - |
| `tags` | object | ❌ No | - |
| `locked` | object | ❌ No | - |
| `mcp_enabled` | object | ❌ No | Can be exposed in the MCP server |
| `action_name` | object | ❌ No | The name of the action associated with the flow |
| `action_description` | object | ❌ No | The description of the action associated with the flow |
| `access_type` | `string` | ❌ No | - |
| `user_id` | object | ❌ No | - |
| `folder_id` | object | ❌ No | - |
| `fs_path` | object | ❌ No | - |


**Required fields:** `name`



---
## `FlowDataRequest`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `nodes` | `array` [object] | ✅ Yes | - |
| `edges` | `array` [object] | ✅ Yes | - |
| `viewport` | object | ❌ No | - |


**Required fields:** `nodes`, `edges`



---
## `FlowHeader`

> Model representing a header for a flow - Without the data.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ✅ Yes | Unique identifier for the flow |
| `name` | `string` | ✅ Yes | The name of the flow |
| `folder_id` | object | ❌ No | The ID of the folder containing the flow. None if not associated with a folder |
| `is_component` | object | ❌ No | Flag indicating whether the flow is a component |
| `endpoint_name` | object | ❌ No | The name of the endpoint associated with this flow |
| `description` | object | ❌ No | A description of the flow |
| `data` | object | ❌ No | The data of the component, if is_component is True |
| `access_type` | object | ❌ No | The access type of the flow |
| `tags` | object | ❌ No | The tags of the flow |
| `mcp_enabled` | object | ❌ No | Flag indicating whether the flow is exposed in the MCP server |
| `action_name` | object | ❌ No | The name of the action associated with the flow |
| `action_description` | object | ❌ No | The description of the action associated with the flow |


**Required fields:** `id`, `name`



---
## `FlowListCreate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flows` | `array` [object] | ✅ Yes | - |


**Required fields:** `flows`



---
## `FlowRead`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | ✅ Yes | - |
| `description` | object | ❌ No | - |
| `icon` | object | ❌ No | - |
| `icon_bg_color` | object | ❌ No | - |
| `gradient` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `is_component` | object | ❌ No | - |
| `updated_at` | object | ❌ No | - |
| `webhook` | object | ❌ No | Can be used on the webhook endpoint |
| `endpoint_name` | object | ❌ No | - |
| `tags` | object | ❌ No | The tags of the flow |
| `locked` | object | ❌ No | - |
| `mcp_enabled` | object | ❌ No | Can be exposed in the MCP server |
| `action_name` | object | ❌ No | The name of the action associated with the flow |
| `action_description` | object | ❌ No | The description of the action associated with the flow |
| `access_type` | `string` | ❌ No | - |
| `id` | `string` (uuid) | ✅ Yes | - |
| `user_id` | object | ✅ Yes | - |
| `folder_id` | object | ✅ Yes | - |


**Required fields:** `name`, `id`, `user_id`, `folder_id`



---
## `FlowUpdate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | object | ❌ No | - |
| `description` | object | ❌ No | - |
| `data` | object | ❌ No | - |
| `folder_id` | object | ❌ No | - |
| `endpoint_name` | object | ❌ No | - |
| `mcp_enabled` | object | ❌ No | - |
| `locked` | object | ❌ No | - |
| `action_name` | object | ❌ No | - |
| `action_description` | object | ❌ No | - |
| `access_type` | object | ❌ No | - |
| `fs_path` | object | ❌ No | - |




---
## `FolderCreate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | ✅ Yes | - |
| `description` | object | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `components_list` | object | ❌ No | - |
| `flows_list` | object | ❌ No | - |


**Required fields:** `name`



---
## `FolderRead`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | ✅ Yes | - |
| `description` | object | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `id` | `string` (uuid) | ✅ Yes | - |
| `parent_id` | object | ✅ Yes | - |


**Required fields:** `name`, `id`, `parent_id`



---
## `FolderReadWithFlows`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | ✅ Yes | - |
| `description` | object | ❌ No | - |
| `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
| `id` | `string` (uuid) | ✅ Yes | - |
| `parent_id` | object | ✅ Yes | - |
| `flows` | `array` [object] | ❌ No | - |


**Required fields:** `name`, `id`, `parent_id`



---
## `FolderUpdate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | object | ❌ No | - |
| `description` | object | ❌ No | - |
| `parent_id` | object | ❌ No | - |
| `components` | `array` [string] | ❌ No | - |
| `flows` | `array` [string] | ❌ No | - |
| `auth_settings` | object | ❌ No | - |




---
## `FolderWithPaginatedFlows`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `folder` | `object` | ✅ Yes | - |
| `flows` | `object` | ✅ Yes | - |


**Required fields:** `folder`, `flows`



---
## `GraphData`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `nodes` | `array` [object] | ✅ Yes | - |
| `edges` | `array` [object] | ✅ Yes | - |
| `viewport` | object | ❌ No | - |


**Required fields:** `nodes`, `edges`



---
## `GraphDumpResponse`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `data` | `object` | ✅ Yes | - |
| `is_component` | object | ❌ No | - |
| `name` | object | ❌ No | - |
| `description` | object | ❌ No | - |
| `endpoint_name` | object | ❌ No | - |


**Required fields:** `data`



---
## `HTTPValidationError`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `detail` | `array` [object] | ❌ No | - |




---
## `HealthResponse`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | `string` | ❌ No | - |
| `chat` | `string` | ❌ No | - |
| `db` | `string` | ❌ No | - |




---
## `InputValueRequest`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `components` | object | ❌ No | - |
| `input_value` | object | ❌ No | - |
| `session` | object | ❌ No | - |
| `type` | object | ❌ No | Defines on which components the input value should be applied. &#x27;any&#x27; applies to all input components. |
| `client_request_time` | object | ❌ No | Client-side timestamp in milliseconds when the request was initiated. Used to calculate accurate end-to-end duration. |




---
## `JSONContent`


**Type:** `object`





---
## `MCPInstallRequest`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `client` | `string` | ✅ Yes | - |
| `transport` | object | ❌ No | - |


**Required fields:** `client`



---
## `MCPProjectUpdateRequest`

> Request model for updating MCP project settings including auth.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `settings` | `array` [object] | ✅ Yes | - |
| `auth_settings` | object | ❌ No | - |


**Required fields:** `settings`



---
## `MCPServerConfig`

> Pydantic model for MCP server configuration.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | object | ❌ No | - |
| `args` | object | ❌ No | - |
| `env` | object | ❌ No | - |
| `headers` | object | ❌ No | - |
| `url` | object | ❌ No | - |




---
## `MCPSettings`

> Model representing MCP settings for a flow.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ✅ Yes | - |
| `mcp_enabled` | object | ❌ No | - |
| `action_name` | object | ❌ No | - |
| `action_description` | object | ❌ No | - |
| `name` | object | ❌ No | - |
| `description` | object | ❌ No | - |


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
| `timestamp` | `string` (date-time) | ❌ No | - |
| `sender` | `string` | ✅ Yes | - |
| `sender_name` | `string` | ✅ Yes | - |
| `session_id` | `string` | ✅ Yes | - |
| `context_id` | object | ❌ No | - |
| `text` | `string` | ✅ Yes | - |
| `files` | `array` [string] | ❌ No | - |
| `error` | `boolean` | ❌ No | - |
| `edit` | `boolean` | ❌ No | - |
| `properties` | `object` | ❌ No | - |
| `category` | `string` | ❌ No | - |
| `content_blocks` | `array` [object] | ❌ No | - |
| `id` | `string` (uuid) | ✅ Yes | - |
| `flow_id` | object | ✅ Yes | - |


**Required fields:** `sender`, `sender_name`, `session_id`, `text`, `id`, `flow_id`



---
## `MessageResponse`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | object | ❌ No | - |
| `flow_id` | object | ❌ No | - |
| `timestamp` | `string` (date-time) | ❌ No | - |
| `sender` | `string` | ✅ Yes | - |
| `sender_name` | `string` | ✅ Yes | - |
| `session_id` | `string` | ✅ Yes | - |
| `context_id` | object | ❌ No | - |
| `text` | `string` | ✅ Yes | - |
| `files` | `array` [string] | ❌ No | - |
| `edit` | `boolean` | ✅ Yes | - |
| `duration` | object | ❌ No | - |
| `properties` | object | ❌ No | - |
| `category` | object | ❌ No | - |
| `content_blocks` | object | ❌ No | - |


**Required fields:** `sender`, `sender_name`, `session_id`, `text`, `edit`



---
## `MessageUpdate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `text` | object | ❌ No | - |
| `sender` | object | ❌ No | - |
| `sender_name` | object | ❌ No | - |
| `session_id` | object | ❌ No | - |
| `context_id` | object | ❌ No | - |
| `files` | object | ❌ No | - |
| `edit` | object | ❌ No | - |
| `error` | object | ❌ No | - |
| `properties` | object | ❌ No | - |




---
## `OpenAIResponsesRequest`

> OpenAI-compatible responses request with flow_id as model parameter.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `model` | `string` | ✅ Yes | The flow ID to execute (used instead of OpenAI model) |
| `input` | `string` | ✅ Yes | The input text to process |
| `stream` | `boolean` | ❌ No | Whether to stream the response |
| `background` | `boolean` | ❌ No | Whether to process in background |
| `tools` | object | ❌ No | Tools are not supported yet |
| `previous_response_id` | object | ❌ No | ID of previous response to continue conversation |
| `include` | object | ❌ No | Additional response data to include, e.g., [&#x27;tool_call.results&#x27;] |


**Required fields:** `model`, `input`



---
## `Page_FlowRead_`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | `array` [object] | ✅ Yes | - |
| `total` | `integer` | ✅ Yes | - |
| `page` | `integer` | ✅ Yes | - |
| `size` | `integer` | ✅ Yes | - |
| `pages` | `integer` | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Page_Flow_`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | `array` [object] | ✅ Yes | - |
| `total` | `integer` | ✅ Yes | - |
| `page` | `integer` | ✅ Yes | - |
| `size` | `integer` | ✅ Yes | - |
| `pages` | `integer` | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Page_TransactionLogsResponse_`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | `array` [object] | ✅ Yes | - |
| `total` | `integer` | ✅ Yes | - |
| `page` | `integer` | ✅ Yes | - |
| `size` | `integer` | ✅ Yes | - |
| `pages` | `integer` | ✅ Yes | - |


**Required fields:** `items`, `total`, `page`, `size`, `pages`



---
## `Properties`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `text_color` | object | ❌ No | - |
| `background_color` | object | ❌ No | - |
| `edited` | `boolean` | ❌ No | - |
| `source` | `object` | ❌ No | - |
| `icon` | object | ❌ No | - |
| `allow_markdown` | `boolean` | ❌ No | - |
| `positive_feedback` | object | ❌ No | - |
| `state` | `string` | ❌ No | - |
| `targets` | `array` [] | ❌ No | - |
| `usage` | object | ❌ No | - |
| `build_duration` | object | ❌ No | - |




---
## `PublicConfigResponse`

> Configuration response for public/unauthenticated endpoints like the public playground.

Contains only the configuration values needed for public features, without sensitive data.
The &#x27;type&#x27; field is a discriminator to distinguish from full ConfigResponse.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `max_file_size_upload` | `integer` | ✅ Yes | - |
| `event_delivery` | `string` | ✅ Yes | - |
| `voice_mode_available` | `boolean` | ✅ Yes | - |
| `frontend_timeout` | `integer` | ✅ Yes | - |
| `type` | `string` | ❌ No | - |


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
| `messages` | object | ❌ No | - |
| `timedelta` | object | ❌ No | - |
| `duration` | object | ❌ No | - |
| `component_display_name` | object | ❌ No | - |
| `component_id` | object | ❌ No | - |
| `used_frozen_result` | object | ❌ No | - |




---
## `RunOutputs`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `inputs` | `object` | ❌ No | - |
| `outputs` | `array` [] | ❌ No | - |




---
## `RunResponse`

> Run response schema.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `outputs` | object | ❌ No | - |
| `session_id` | object | ❌ No | - |




---
## `SimplifiedAPIRequest`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_value` | object | ❌ No | The input value |
| `input_type` | object | ❌ No | The input type |
| `output_type` | object | ❌ No | The output type |
| `output_component` | object | ❌ No | If there are multiple output components, you can specify the component to get the output from. |
| `tweaks` | object | ❌ No | The tweaks |
| `session_id` | object | ❌ No | The session id |




---
## `Source`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | object | ❌ No | The id of the source component. |
| `display_name` | object | ❌ No | The display name of the source component. |
| `source` | object | ❌ No | The source of the message. Normally used to display the model name (e.g. &#x27;gpt-4o&#x27;) |




---
## `SpanReadResponse`

> Response model for a single span, with nested children.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ✅ Yes | - |
| `name` | `string` | ✅ Yes | - |
| `type` | `string` | ✅ Yes | Types of spans that can be recorded. |
| `status` | `string` | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | object | ✅ Yes | - |
| `endTime` | object | ✅ Yes | - |
| `latencyMs` | `integer` | ✅ Yes | - |
| `inputs` | object | ✅ Yes | - |
| `outputs` | object | ✅ Yes | - |
| `error` | object | ✅ Yes | - |
| `modelName` | object | ✅ Yes | - |
| `tokenUsage` | object | ✅ Yes | - |
| `children` | `array` [] | ❌ No | - |


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
| `traces` | `array` [object] | ✅ Yes | - |
| `total` | `integer` | ✅ Yes | - |
| `pages` | `integer` | ✅ Yes | - |


**Required fields:** `traces`, `total`, `pages`



---
## `TraceRead`

> Response model for a single trace with its hierarchical span tree.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ✅ Yes | - |
| `name` | `string` | ✅ Yes | - |
| `status` | `string` | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | object | ✅ Yes | - |
| `endTime` | object | ✅ Yes | - |
| `totalLatencyMs` | `integer` | ✅ Yes | - |
| `totalTokens` | `integer` | ✅ Yes | - |
| `flowId` | `string` (uuid) | ✅ Yes | - |
| `sessionId` | `string` | ✅ Yes | - |
| `input` | object | ❌ No | - |
| `output` | object | ❌ No | - |
| `spans` | `array` [] | ❌ No | - |


**Required fields:** `id`, `name`, `status`, `startTime`, `endTime`, `totalLatencyMs`, `totalTokens`, `flowId`, `sessionId`



---
## `TraceSummaryRead`

> Lightweight trace model for list endpoint.

Serializes to camelCase JSON to match the frontend API contract.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ✅ Yes | - |
| `name` | `string` | ✅ Yes | - |
| `status` | `string` | ✅ Yes | OpenTelemetry status codes.

- UNSET: Default status, span has not ended yet
- OK: Span completed successfully
- ERROR: Span completed with an error |
| `startTime` | object | ✅ Yes | - |
| `totalLatencyMs` | `integer` | ✅ Yes | - |
| `totalTokens` | `integer` | ✅ Yes | - |
| `flowId` | `string` (uuid) | ✅ Yes | - |
| `sessionId` | `string` | ✅ Yes | - |
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
| `id` | `string` (uuid) | ✅ Yes | - |
| `timestamp` | `string` (date-time) | ❌ No | - |
| `vertex_id` | `string` | ✅ Yes | - |
| `target_id` | object | ❌ No | - |
| `inputs` | `object` | ❌ No | - |
| `outputs` | `object` | ❌ No | - |
| `status` | `string` | ✅ Yes | - |


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
| `input_tokens` | object | ❌ No | - |
| `output_tokens` | object | ❌ No | - |
| `total_tokens` | object | ❌ No | - |




---
## `UserCreate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | `string` | ✅ Yes | - |
| `password` | `string` | ✅ Yes | - |
| `optins` | object | ❌ No | - |


**Required fields:** `username`, `password`



---
## `UserRead`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ❌ No | - |
| `username` | `string` | ✅ Yes | - |
| `profile_image` | object | ✅ Yes | - |
| `store_api_key` | object | ✅ Yes | - |
| `is_active` | `boolean` | ✅ Yes | - |
| `is_superuser` | `boolean` | ✅ Yes | - |
| `create_at` | `string` (date-time) | ✅ Yes | - |
| `updated_at` | `string` (date-time) | ✅ Yes | - |
| `last_login_at` | object | ✅ Yes | - |
| `optins` | object | ❌ No | - |


**Required fields:** `username`, `profile_image`, `store_api_key`, `is_active`, `is_superuser`, `create_at`, `updated_at`, `last_login_at`



---
## `UserUpdate`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `username` | object | ❌ No | - |
| `profile_image` | object | ❌ No | - |
| `password` | object | ❌ No | - |
| `is_active` | object | ❌ No | - |
| `is_superuser` | object | ❌ No | - |
| `last_login_at` | object | ❌ No | - |
| `optins` | object | ❌ No | - |




---
## `UsersResponse`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `total_count` | `integer` | ✅ Yes | - |
| `users` | `array` [object] | ✅ Yes | - |


**Required fields:** `total_count`, `users`



---
## `ValidationError`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `loc` | `array` [] | ✅ Yes | - |
| `msg` | `string` | ✅ Yes | - |
| `type` | `string` | ✅ Yes | - |
| `input` | object | ❌ No | - |
| `ctx` | `object` | ❌ No | - |


**Required fields:** `loc`, `msg`, `type`



---
## `VertexBuildMapModel`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `vertex_builds` | `object` | ✅ Yes | - |


**Required fields:** `vertex_builds`



---
## `VertexBuildTable`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `timestamp` | `string` (date-time) | ❌ No | - |
| `id` | `string` | ✅ Yes | - |
| `data` | `object` | ❌ No | - |
| `artifacts` | `object` | ❌ No | - |
| `params` | `string` | ❌ No | - |
| `valid` | `boolean` | ✅ Yes | - |
| `flow_id` | `string` (uuid) | ✅ Yes | - |
| `job_id` | object | ❌ No | - |
| `build_id` | object | ❌ No | - |


**Required fields:** `id`, `valid`, `flow_id`



---
## `ViewPort`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `x` | `number` | ✅ Yes | - |
| `y` | `number` | ✅ Yes | - |
| `zoom` | `number` | ✅ Yes | - |


**Required fields:** `x`, `y`, `zoom`



---
## `WorkflowExecutionRequest`

> Request schema for workflow execution.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `background` | `boolean` | ❌ No | - |
| `stream` | `boolean` | ❌ No | - |
| `flow_id` | `string` | ✅ Yes | - |
| `inputs` | object | ❌ No | Component-specific inputs in flat format: &#x27;component_id.param_name&#x27;: value |


**Required fields:** `flow_id`



---
## `WorkflowStopRequest`

> Request schema for stopping workflow.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `job_id` | object | ✅ Yes | - |


**Required fields:** `job_id`



---
## `WorkflowStopResponse`

> Response schema for stopping workflow.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `job_id` | object | ✅ Yes | - |
| `message` | object | ❌ No | - |


**Required fields:** `job_id`



---
## `langflow__api__schemas__UploadFileResponse`

> File upload response schema.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ✅ Yes | - |
| `name` | `string` | ✅ Yes | - |
| `path` | `string` (path) | ✅ Yes | - |
| `size` | `integer` | ✅ Yes | - |
| `provider` | object | ❌ No | - |


**Required fields:** `id`, `name`, `path`, `size`



---
## `langflow__api__v1__schemas__UploadFileResponse`

> Upload file response schema.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flowId` | `string` | ✅ Yes | - |
| `file_path` | `string` (path) | ✅ Yes | - |


**Required fields:** `flowId`, `file_path`



---
## `langflow__services__database__models__file__model__File`


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | `string` (uuid) | ❌ No | - |
| `user_id` | `string` (uuid) | ✅ Yes | - |
| `name` | `string` | ✅ Yes | - |
| `path` | `string` | ✅ Yes | - |
| `size` | `integer` | ✅ Yes | - |
| `provider` | object | ❌ No | - |
| `created_at` | `string` (date-time) | ❌ No | - |
| `updated_at` | `string` (date-time) | ❌ No | - |


**Required fields:** `user_id`, `name`, `path`, `size`



---
## `lfx__utils__schemas__File`

> File schema.


**Type:** `object`


### Properties

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✅ Yes | - |
| `name` | `string` | ✅ Yes | - |
| `type` | `string` | ✅ Yes | - |


**Required fields:** `path`, `name`, `type`



---
