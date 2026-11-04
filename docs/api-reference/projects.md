# Projects

> Part of **Langflow**

---

## `GET` /api/v1/projects/

> Read Projects


**Operation ID:** `read_projects_api_v1_projects__get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `POST` /api/v1/projects/

> Create Project


**Operation ID:** `create_project_api_v1_projects__post`



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
  | `auth_settings` | object | ❌ No | Authentication settings for the folder/project |
  | `components_list` | array[string] | ❌ No | - |
  | `flows_list` | array[string] | ❌ No | - |
  



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
| `auth_settings` | object | Authentication settings for the folder/project |
| `id` | string (uuid) | - |
| `parent_id` | string (uuid) | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/projects/{project_id}

> Read Project


**Operation ID:** `read_project_api_v1_projects__project_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |
| `page` | **query** | integer | ❌ No | - |
| `size` | **query** | integer | ❌ No | - |
| `is_component` | **query** | boolean | ❌ No | - |
| `is_flow` | **query** | boolean | ❌ No | - |
| `search` | **query** | string | ❌ No | - |



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
| `auth_settings` | object | Authentication settings for the folder/project |
| `id` | string (uuid) | - |
| `parent_id` | string (uuid) | - |
| `flows` | array[object] | - |
**`flows`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `PATCH` /api/v1/projects/{project_id}

> Update Project


**Operation ID:** `update_project_api_v1_projects__project_id__patch`


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
  | `name` | string | ❌ No | - |
  | `description` | string | ❌ No | - |
  | `parent_id` | string (uuid) | ❌ No | - |
  | `components` | array[string] | ❌ No | - |
  | `flows` | array[string] | ❌ No | - |
  | `auth_settings` | object | ❌ No | - |
  



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
| `auth_settings` | object | Authentication settings for the folder/project |
| `id` | string (uuid) | - |
| `parent_id` | string (uuid) | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `DELETE` /api/v1/projects/{project_id}

> Delete Project


**Operation ID:** `delete_project_api_v1_projects__project_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `GET` /api/v1/projects/download/{project_id}

> Download File


Download all flows from project as a zip file.


**Operation ID:** `download_file_api_v1_projects_download__project_id__get`


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
## `POST` /api/v1/projects/upload/

> Upload File


Upload flows from a file.


**Operation ID:** `upload_file_api_v1_projects_upload__post`



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
