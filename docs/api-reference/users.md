# Users

> Part of **Langflow**

---

## `POST` /api/v1/users/

> Add User


Add a new user to the database.&lt;br&gt;&lt;br&gt;This endpoint allows public user registration (sign up).&lt;br&gt;User activation is controlled by the NEW_USER_IS_ACTIVE setting.


**Operation ID:** `add_user_api_v1_users__post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/users/

> Read All Users


Retrieve a list of users from the database with pagination.


**Operation ID:** `read_all_users_api_v1_users__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `skip` | **query** |  (integer) | ❌ No | - |
| `limit` | **query** |  (integer) | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/users/whoami

> Read Current User


Retrieve the current user&#x27;s data.


**Operation ID:** `read_current_user_api_v1_users_whoami_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |


---
## `PATCH` /api/v1/users/{user_id}

> Patch User


Update an existing user&#x27;s data.


**Operation ID:** `patch_user_api_v1_users__user_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/users/{user_id}

> Delete User


Delete a user from the database.


**Operation ID:** `delete_user_api_v1_users__user_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** |  (string) | ✅ Yes | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `PATCH` /api/v1/users/{user_id}/reset-password

> Reset Password


Reset a user&#x27;s password.


**Operation ID:** `reset_password_api_v1_users__user_id__reset_password_patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
