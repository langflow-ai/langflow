# MCP

> Part of **Langflow**

---

## `GET` /api/v2/mcp/servers

> Get Servers


Get the list of available servers.


**Operation ID:** `get_servers_api_v2_mcp_servers_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `action_count` | **query** | boolean | ❌ No | - |



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
## `GET` /api/v2/mcp/servers/{server_name}

> Get Server Endpoint


Get a specific server.


**Operation ID:** `get_server_endpoint_api_v2_mcp_servers__server_name__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |



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
## `POST` /api/v2/mcp/servers/{server_name}

> Add Server


**Operation ID:** `add_server_api_v2_mcp_servers__server_name__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |


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
  | `command` | string | ❌ No | - |
  | `args` | array[string] | ❌ No | - |
  | `env` | object | ❌ No | - |
  | `headers` | object | ❌ No | - |
  | `url` | string | ❌ No | - |
  



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
## `PATCH` /api/v2/mcp/servers/{server_name}

> Update Server Endpoint


**Operation ID:** `update_server_endpoint_api_v2_mcp_servers__server_name__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |


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
  | `command` | string | ❌ No | - |
  | `args` | array[string] | ❌ No | - |
  | `env` | object | ❌ No | - |
  | `headers` | object | ❌ No | - |
  | `url` | string | ❌ No | - |
  



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
## `DELETE` /api/v2/mcp/servers/{server_name}

> Delete Server


**Operation ID:** `delete_server_api_v2_mcp_servers__server_name__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `server_name` | **path** | string | ✅ Yes | - |



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
