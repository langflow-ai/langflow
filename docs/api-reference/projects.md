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



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/projects/{project_id}

> Read Project


**Operation ID:** `read_project_api_v1_projects__project_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |
| `page` | **query** |  | ❌ No | - |
| `size` | **query** |  | ❌ No | - |
| `is_component` | **query** |  (boolean) | ❌ No | - |
| `is_flow` | **query** |  (boolean) | ❌ No | - |
| `search` | **query** |  (string) | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `PATCH` /api/v1/projects/{project_id}

> Update Project


**Operation ID:** `update_project_api_v1_projects__project_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/projects/{project_id}

> Delete Project


**Operation ID:** `delete_project_api_v1_projects__project_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **204** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/projects/download/{project_id}

> Download File


Download all flows from project as a zip file.


**Operation ID:** `download_file_api_v1_projects_download__project_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `project_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/projects/upload/

> Upload File


Upload flows from a file.


**Operation ID:** `upload_file_api_v1_projects_upload__post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
