# Flows

> Part of **Langflow**

---

## `POST` /api/v1/flows/

> Create Flow


**Operation ID:** `create_flow_api_v1_flows__post`



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
  | `access_type` | string = `PRIVATE` \| `PUBLIC` | ❌ No | - |
  | `user_id` | string (uuid) | ❌ No | - |
  | `folder_id` | string (uuid) | ❌ No | - |
  | `fs_path` | string | ❌ No | - |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string = `PRIVATE` \| `PUBLIC` | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/flows/

> Read Flows


Retrieve a list of flows with pagination support.

Args:
    current_user (User): The current authenticated user.
    session (Session): The database session.
    settings_service (SettingsService): The settings service.
    components_only (bool, optional): Whether to return only components. Defaults to False.

    get_all (bool, optional): Whether to return all flows without pagination. Defaults to True.
    **This field must be True because of backward compatibility with the frontend - Release: 1.0.20**

    folder_id (UUID, optional): The project ID. Defaults to None.
    params (Params): Pagination parameters.
    remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.
    header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.

Returns:
    list[FlowRead] | Page[FlowRead] | list[FlowHeader]
    A list of flows or a paginated response containing the list of flows or a list of flow headers.


**Operation ID:** `read_flows_api_v1_flows__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `remove_example_flows` | **query** | boolean | ❌ No | - |
| `components_only` | **query** | boolean | ❌ No | - |
| `get_all` | **query** | boolean | ❌ No | - |
| `folder_id` | **query** | string (uuid) | ❌ No | - |
| `header_flows` | **query** | boolean | ❌ No | - |
| `page` | **query** | integer | ❌ No | - |
| `size` | **query** | integer | ❌ No | - |



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
## `DELETE` /api/v1/flows/

> Delete Multiple Flows


Delete multiple flows by their IDs.

Args:
    flow_ids (List[str]): The list of flow IDs to delete.
    user (User, optional): The user making the request. Defaults to the current active user.
    db (Session, optional): The database session.

Returns:
    dict: A dictionary containing the number of flows deleted.


**Operation ID:** `delete_multiple_flows_api_v1_flows__delete`



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
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/flows/{flow_id}

> Read Flow


Read a flow.


**Operation ID:** `read_flow_api_v1_flows__flow_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string = `PRIVATE` \| `PUBLIC` | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `PATCH` /api/v1/flows/{flow_id}

> Update Flow


Update a flow.


**Operation ID:** `update_flow_api_v1_flows__flow_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |


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
  | `name` | string | ❌ No | - |
  | `description` | string | ❌ No | - |
  | `data` | object | ❌ No | - |
  | `folder_id` | string (uuid) | ❌ No | - |
  | `endpoint_name` | string | ❌ No | - |
  | `mcp_enabled` | boolean | ❌ No | - |
  | `locked` | boolean | ❌ No | - |
  | `action_name` | string | ❌ No | - |
  | `action_description` | string | ❌ No | - |
  | `access_type` | string = `PRIVATE` \| `PUBLIC` | ❌ No | - |
  | `fs_path` | string | ❌ No | - |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string = `PRIVATE` \| `PUBLIC` | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `DELETE` /api/v1/flows/{flow_id}

> Delete Flow


Delete a flow.


**Operation ID:** `delete_flow_api_v1_flows__flow_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `GET` /api/v1/flows/public_flow/{flow_id}

> Read Public Flow


Read a public flow.


**Operation ID:** `read_public_flow_api_v1_flows_public_flow__flow_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** | string (uuid) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `name` | string | - |
| `description` | string | - |
| `icon` | string | - |
| `icon_bg_color` | string | - |
| `gradient` | string | - |
| `data` | object | - |
| `is_component` | boolean | - |
| `updated_at` | string (date-time) | - |
| `webhook` | boolean | Can be used on the webhook endpoint |
| `endpoint_name` | string | - |
| `tags` | array[string] | The tags of the flow |
| `locked` | boolean | - |
| `mcp_enabled` | boolean | Can be exposed in the MCP server |
| `action_name` | string | The name of the action associated with the flow |
| `action_description` | string | The description of the action associated with the flow |
| `access_type` | string = `PRIVATE` \| `PUBLIC` | - |
| `id` | string (uuid) | - |
| `user_id` | string (uuid) | - |
| `folder_id` | string (uuid) | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `POST` /api/v1/flows/batch/

> Create Flows


Create multiple new flows.


**Operation ID:** `create_flows_api_v1_flows_batch__post`



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
  | `flows` | array[object] | ✅ Yes | - |
  **`flows`** — Array of `object`





### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `POST` /api/v1/flows/upload/

> Upload File


Upload flows from a file.


**Operation ID:** `upload_file_api_v1_flows_upload__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `folder_id` | **query** | string (uuid) | ❌ No | - |


### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Bearer `<token>` / API Key (`x-api-key`) | ✅ |
| Content-Type | `multipart/form-data` | ✅ |

### Request Body

- **Required:** Yes

- **Content-Type:** `multipart/form-data`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `file` | string | ✅ Yes | - |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `POST` /api/v1/flows/download/

> Download Multiple File


Download all flows as a zip file.


**Operation ID:** `download_multiple_file_api_v1_flows_download__post`



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
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/flows/basic_examples/

> Read Basic Examples


Retrieve a list of basic example flows.

Args:
    session (Session): The database session.

Returns:
    list[FlowRead]: A list of basic example flows.


**Operation ID:** `read_basic_examples_api_v1_flows_basic_examples__get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `GET` /api/v1/starter-projects/

> Get Starter Projects


Get a list of starter projects.


**Operation ID:** `get_starter_projects_api_v1_starter_projects__get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
