# Workflow

> Part of **Langflow**

---

## `POST` /api/v2/workflows

> Execute Workflow


Execute a workflow with support for sync, stream, and background modes


**Operation ID:** `execute_workflow_api_v2_workflows_post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Workflow execution response |
| **422** | Validation Error |


---
## `GET` /api/v2/workflows

> Get Workflow Status


Get status of workflow job by job ID


**Operation ID:** `get_workflow_status_api_v2_workflows_get`


### Parameters

| Name | Located In | Type | Required | Description |
|------|-----------|------|----------|-------------|
| `job_id` | **query** |  | ❌ No | Job ID to query |



### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Workflow status response |
| **422** | Validation Error |


---
## `POST` /api/v2/workflows/stop

> Stop Workflow


Stop a running workflow execution


**Operation ID:** `stop_workflow_api_v2_workflows_stop_post`



### Request Body

- **Required:** Yes


### Responses

| Status Code | Description |
|-------------|-------------|
| **200** | Successful Response |
| **422** | Validation Error |


---
