# Users

> Part of **Langflow**

---

## `POST` /api/v1/users/

> Add User


Add a new user to the database.

This endpoint allows public user registration (sign up).
User activation is controlled by the NEW_USER_IS_ACTIVE setting.


**Operation ID:** `add_user_api_v1_users__post`



### Headers

| Header | Value | Required |
|--------|-------|----------|
| Authorization | Not required | - |
| Content-Type | `application/json` | ✅ |

### Request Body

- **Required:** Yes

- **Content-Type:** `application/json`
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | `username` | string | ✅ Yes | - |
  | `password` | string | ✅ Yes | - |
  | `optins` | object | ❌ No | - |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/users/

> Read All Users


Retrieve a list of users from the database with pagination.


**Operation ID:** `read_all_users_api_v1_users__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `skip` | **query** | integer | ❌ No | - |
| `limit` | **query** | integer | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `total_count` | integer | - |
| `users` | array[object] | - |
**`users`** — Array of `object`



**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `GET` /api/v1/users/whoami

> Read Current User


Retrieve the current user's data.


**Operation ID:** `read_current_user_api_v1_users_whoami_get`




### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |



---
## `PATCH` /api/v1/users/{user_id}

> Patch User


Update an existing user's data.


**Operation ID:** `patch_user_api_v1_users__user_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** | string (uuid) | ✅ Yes | - |


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
  | `username` | string | ❌ No | - |
  | `profile_image` | string | ❌ No | - |
  | `password` | string | ❌ No | - |
  | `is_active` | boolean | ❌ No | - |
  | `is_superuser` | boolean | ❌ No | - |
  | `last_login_at` | string (date-time) | ❌ No | - |
  | `optins` | object | ❌ No | - |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
## `DELETE` /api/v1/users/{user_id}

> Delete User


Delete a user from the database.


**Operation ID:** `delete_user_api_v1_users__user_id__delete`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** | string (uuid) | ✅ Yes | - |



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
## `PATCH` /api/v1/users/{user_id}/reset-password

> Reset Password


Reset a user's password.


**Operation ID:** `reset_password_api_v1_users__user_id__reset_password_patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `user_id` | **path** | string (uuid) | ✅ Yes | - |


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
  | `username` | string | ❌ No | - |
  | `profile_image` | string | ❌ No | - |
  | `password` | string | ❌ No | - |
  | `is_active` | boolean | ❌ No | - |
  | `is_superuser` | boolean | ❌ No | - |
  | `last_login_at` | string (date-time) | ❌ No | - |
  | `optins` | object | ❌ No | - |
  



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |

**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `id` | string (uuid) | - |
| `username` | string | - |
| `profile_image` | string | - |
| `store_api_key` | string | - |
| `is_active` | boolean | - |
| `is_superuser` | boolean | - |
| `create_at` | string (date-time) | - |
| `updated_at` | string (date-time) | - |
| `last_login_at` | string (date-time) | - |
| `optins` | object | - |


**Response Body** (application/json):

| Name | Type | Description |
|------|------|-------------|
| `detail` | array[object] | - |
**`detail`** — Array of `object`




---
