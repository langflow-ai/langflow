# Files

> Part of **Langflow**

---

## `POST` /api/v1/files/upload/{flow_id}

> Upload File


**Operation ID:** `upload_file_api_v1_files_upload__flow_id__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/files/download/{flow_id}/{file_name}

> Download File


**Operation ID:** `download_file_api_v1_files_download__flow_id___file_name__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_name` | **path** |  (string) | ✅ Yes | - |
| `flow_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/files/images/{flow_id}/{file_name}

> Download Image


Download image from storage for browser rendering.


**Operation ID:** `download_image_api_v1_files_images__flow_id___file_name__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |
| `file_name` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/files/profile_pictures/{folder_name}/{file_name}

> Download Profile Picture


Download profile picture from local filesystem.&lt;br&gt;&lt;br&gt;Profile pictures are first looked up in config_dir/profile_pictures/,&lt;br&gt;then fallback to the package&#x27;s bundled profile_pictures directory.


**Operation ID:** `download_profile_picture_api_v1_files_profile_pictures__folder_name___file_name__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `folder_name` | **path** |  (string) | ✅ Yes | - |
| `file_name` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/files/profile_pictures/list

> List Profile Pictures


List profile pictures from local filesystem.&lt;br&gt;&lt;br&gt;Profile pictures are first looked up in config_dir/profile_pictures/,&lt;br&gt;then fallback to the package&#x27;s bundled profile_pictures directory.


**Operation ID:** `list_profile_pictures_api_v1_files_profile_pictures_list_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `GET` /api/v1/files/list/{flow_id}

> List Files


**Operation ID:** `list_files_api_v1_files_list__flow_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/files/delete/{flow_id}/{file_name}

> Delete File


**Operation ID:** `delete_file_api_v1_files_delete__flow_id___file_name__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_name` | **path** |  (string) | ✅ Yes | - |
| `flow_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v2/files/

> Upload User File


Upload a file for the current user and track it in the database.


**Operation ID:** `upload_user_file_api_v2_files__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `append` | **query** |  (boolean) | ❌ No | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v2/files/

> List Files


List the files available to the current user.


**Operation ID:** `list_files_api_v2_files__get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `DELETE` /api/v2/files/

> Delete All Files


Delete all files for the current user.


**Operation ID:** `delete_all_files_api_v2_files__delete`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `POST` /api/v2/files

> Upload User File


Upload a file for the current user and track it in the database.


**Operation ID:** `upload_user_file_api_v2_files_post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `append` | **query** |  (boolean) | ❌ No | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v2/files

> List Files


List the files available to the current user.


**Operation ID:** `list_files_api_v2_files_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `DELETE` /api/v2/files

> Delete All Files


Delete all files for the current user.


**Operation ID:** `delete_all_files_api_v2_files_delete`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `POST` /api/v2/files/batch/

> Download Files Batch


Download multiple files as a zip file by their IDs.


**Operation ID:** `download_files_batch_api_v2_files_batch__post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v2/files/batch/

> Delete Files Batch


Delete multiple files by their IDs.


**Operation ID:** `delete_files_batch_api_v2_files_batch__delete`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v2/files/{file_id}

> Download File


Download a file by its ID or return its content as a string/bytes.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    file_id: UUID of the file.&lt;br&gt;    current_user: Authenticated user.&lt;br&gt;    session: Database session.&lt;br&gt;    storage_service: File storage service.&lt;br&gt;    return_content: If True, return raw content (str) instead of StreamingResponse.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    StreamingResponse for client downloads or str for internal use.


**Operation ID:** `download_file_api_v2_files__file_id__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** |  (string) | ✅ Yes | - |
| `return_content` | **query** |  (boolean) | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `PUT` /api/v2/files/{file_id}

> Edit File Name


Edit the name of a file by its ID.


**Operation ID:** `edit_file_name_api_v2_files__file_id__put`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** |  (string) | ✅ Yes | - |
| `name` | **query** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v2/files/{file_id}

> Delete File


Delete a file by its ID.


**Operation ID:** `delete_file_api_v2_files__file_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `file_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
