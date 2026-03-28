# Flows

> Part of **Langflow**

---

## `POST` /api/v1/flows/

> Create Flow


**Operation ID:** `create_flow_api_v1_flows__post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/flows/

> Read Flows


Retrieve a list of flows with pagination support.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    current_user (User): The current authenticated user.&lt;br&gt;    session (Session): The database session.&lt;br&gt;    settings_service (SettingsService): The settings service.&lt;br&gt;    components_only (bool, optional): Whether to return only components. Defaults to False.&lt;br&gt;&lt;br&gt;    get_all (bool, optional): Whether to return all flows without pagination. Defaults to True.&lt;br&gt;    **This field must be True because of backward compatibility with the frontend - Release: 1.0.20**&lt;br&gt;&lt;br&gt;    folder_id (UUID, optional): The project ID. Defaults to None.&lt;br&gt;    params (Params): Pagination parameters.&lt;br&gt;    remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.&lt;br&gt;    header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    list[FlowRead] | Page[FlowRead] | list[FlowHeader]&lt;br&gt;    A list of flows or a paginated response containing the list of flows or a list of flow headers.


**Operation ID:** `read_flows_api_v1_flows__get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `remove_example_flows` | **query** |  (boolean) | ❌ No | - |
| `components_only` | **query** |  (boolean) | ❌ No | - |
| `get_all` | **query** |  (boolean) | ❌ No | - |
| `folder_id` | **query** |  | ❌ No | - |
| `header_flows` | **query** |  (boolean) | ❌ No | - |
| `page` | **query** |  (integer) | ❌ No | - |
| `size` | **query** |  (integer) | ❌ No | - |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/flows/

> Delete Multiple Flows


Delete multiple flows by their IDs.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    flow_ids (List[str]): The list of flow IDs to delete.&lt;br&gt;    user (User, optional): The user making the request. Defaults to the current active user.&lt;br&gt;    db (Session, optional): The database session.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    dict: A dictionary containing the number of flows deleted.


**Operation ID:** `delete_multiple_flows_api_v1_flows__delete`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/flows/{flow_id}

> Read Flow


Read a flow.


**Operation ID:** `read_flow_api_v1_flows__flow_id__get`


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
## `PATCH` /api/v1/flows/{flow_id}

> Update Flow


Update a flow.


**Operation ID:** `update_flow_api_v1_flows__flow_id__patch`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `flow_id` | **path** |  (string) | ✅ Yes | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `DELETE` /api/v1/flows/{flow_id}

> Delete Flow


Delete a flow.


**Operation ID:** `delete_flow_api_v1_flows__flow_id__delete`


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
## `GET` /api/v1/flows/public_flow/{flow_id}

> Read Public Flow


Read a public flow.


**Operation ID:** `read_public_flow_api_v1_flows_public_flow__flow_id__get`


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
## `POST` /api/v1/flows/batch/

> Create Flows


Create multiple new flows.


**Operation ID:** `create_flows_api_v1_flows_batch__post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/flows/upload/

> Upload File


Upload flows from a file.


**Operation ID:** `upload_file_api_v1_flows_upload__post`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `folder_id` | **query** |  | ❌ No | - |


### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **201** | Successful Response |
| **422** | Validation Error |


---
## `POST` /api/v1/flows/download/

> Download Multiple File


Download all flows as a zip file.


**Operation ID:** `download_multiple_file_api_v1_flows_download__post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
## `GET` /api/v1/flows/basic_examples/

> Read Basic Examples


Retrieve a list of basic example flows.&lt;br&gt;&lt;br&gt;Args:&lt;br&gt;    session (Session): The database session.&lt;br&gt;&lt;br&gt;Returns:&lt;br&gt;    list[FlowRead]: A list of basic example flows.


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
