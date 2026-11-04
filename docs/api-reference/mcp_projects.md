# mcp_projects

> Part of **Langflow**

---

## `GET` /api/v1/mcp/project/{project_id}

> List Project Tools


List project MCP tools.


**Operation ID:** `list_project_tools_api_v1_mcp_project__project_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |
| `mcp_enabled` | **query** | boolean | ❌ No | - |



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
## `POST` /api/v1/mcp/project/{project_id}

> Handle Project Messages


Handle POST messages for a project-specific MCP server.


**Operation ID:** `handle_project_messages_api_v1_mcp_project__project_id__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `PATCH` /api/v1/mcp/project/{project_id}

> Update Project Mcp Settings


Update the MCP settings of all flows in a project and project-level auth settings.

On MCP Composer failure, this endpoint should return with a 200 status code and an error message in
the body of the response to display to the user.


**Operation ID:** `update_project_mcp_settings_api_v1_mcp_project__project_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |


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
  | `settings` | array[object] | ✅ Yes | - |
  | `auth_settings` | object | ❌ No | Model representing authentication settings for MCP. |
  **`settings`** — Array of `object`

**`auth_settings`** ❌ — Model representing authentication settings for MCP.





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
## `GET` /api/v1/mcp/project/{project_id}/sse

> Handle Project Sse


Handle SSE connections for a specific project.


**Operation ID:** `handle_project_sse_api_v1_mcp_project__project_id__sse_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `POST` /api/v1/mcp/project/{project_id}/

> Handle Project Messages


Handle POST messages for a project-specific MCP server.


**Operation ID:** `handle_project_messages_api_v1_mcp_project__project_id___post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `DELETE` /api/v1/mcp/project/{project_id}/streamable

> Handle Project Streamable Http


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `GET` /api/v1/mcp/project/{project_id}/streamable

> Handle Project Streamable Http


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `POST` /api/v1/mcp/project/{project_id}/streamable

> Handle Project Streamable Http


Handle Streamable HTTP connections for a specific project.


**Operation ID:** `handle_project_streamable_http_api_v1_mcp_project__project_id__streamable_delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `POST` /api/v1/mcp/project/{project_id}/install

> Install Mcp Config


Install MCP server configuration for Cursor, Windsurf, or Claude.


**Operation ID:** `install_mcp_config_api_v1_mcp_project__project_id__install_post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |


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
  | `client` | string | ✅ Yes | - |
  | `transport` | string = `sse` \| `streamablehttp` | ❌ No | - |
  



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
## `GET` /api/v1/mcp/project/{project_id}/composer-url

> Get Project Composer Url


Get the MCP Composer URL for a specific project.

On failure, this endpoint should return with a 200 status code and an error message in
the body of the response to display to the user.


**Operation ID:** `get_project_composer_url_api_v1_mcp_project__project_id__composer_url_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `project_id` | string | - |
| `uses_composer` | boolean | - |
| `streamable_http_url` | string | - |
| `legacy_sse_url` | string | - |
| `error_message` | string | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/mcp/project/{project_id}/installed

> Check Installed Mcp Servers


Check if MCP server configuration is installed for this project in Cursor, Windsurf, or Claude.


**Operation ID:** `check_installed_mcp_servers_api_v1_mcp_project__project_id__installed_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
