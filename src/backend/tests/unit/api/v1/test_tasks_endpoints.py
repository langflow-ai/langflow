import uuid

from fastapi import status
from httpx import AsyncClient
from langflow.services.database.models.flow import FlowCreate
from orjson import orjson


async def _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers):
    """Helper function to create a flow for testing."""
    vector_store = orjson.loads(json_memory_chatbot_no_llm)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
    response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
    response.raise_for_status()
    return response.json()["id"]


async def _create_task(client: AsyncClient, logged_in_headers, flow_id: str, task_data=None):
    """Helper function to create a task for testing."""
    if task_data is None:
        task_data = {
            "title": "Test Task",
            "description": "A test task description",
            "author_id": flow_id,  # Using flow_id as author_id
            "assignee_id": flow_id,  # Using flow_id as assignee_id
            "category": "test",
            "state": "initial",
        }
    response = await client.post("api/v1/tasks/", json=task_data, headers=logged_in_headers)
    result = response.json()
    return result["id"], result


async def test_create_task(client: AsyncClient, logged_in_headers, json_memory_chatbot_no_llm):
    # First create a flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    task_data = {
        "title": "Test Task",
        "description": "A test task description",
        "author_id": flow_id,
        "assignee_id": flow_id,
        "category": "test",
        "state": "initial",
    }
    response = await client.post("api/v1/tasks/", json=task_data, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "title" in result, "The result must have a 'title' key"
    assert "description" in result, "The result must have a 'description' key"
    assert "author_id" in result, "The result must have a 'author_id' key"
    assert "assignee_id" in result, "The result must have a 'assignee_id' key"
    assert "category" in result, "The result must have a 'category' key"
    assert "state" in result, "The result must have a 'state' key"
    assert "status" in result, "The result must have a 'status' key"
    assert "id" in result, "The result must have an 'id' key"
    assert "created_at" in result, "The result must have a 'created_at' key"
    assert "updated_at" in result, "The result must have an 'updated_at' key"
    assert result["title"] == task_data["title"]
    assert result["description"] == task_data["description"]
    assert result["status"] == "pending"
    assert result["author_id"] == flow_id
    assert result["assignee_id"] == flow_id


async def test_read_tasks(client: AsyncClient, logged_in_headers, json_memory_chatbot_no_llm):
    # First create a flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Create a task
    await _create_task(client, logged_in_headers, flow_id)

    # Now get all tasks
    response = await client.get("api/v1/tasks/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, list), "The result must be a list"
    assert len(result) > 0, "The result must have at least one task"
    task = result[0]
    assert "title" in task, "Each task must have a 'title' key"
    assert "description" in task, "Each task must have a 'description' key"
    assert "status" in task, "Each task must have a 'status' key"
    assert task["author_id"] == flow_id


async def test_read_task(client: AsyncClient, logged_in_headers, json_memory_chatbot_no_llm):
    # First create a flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Create a task
    task_id, task_data = await _create_task(client, logged_in_headers, flow_id)

    # Now get the specific task
    response = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert result["id"] == task_id
    assert result["title"] == task_data["title"]
    assert result["description"] == task_data["description"]
    assert result["status"] == "pending"
    assert result["author_id"] == flow_id


async def test_read_task_not_found(client: AsyncClient, logged_in_headers):
    non_existent_id = str(uuid.uuid4())
    response = await client.get(f"api/v1/tasks/{non_existent_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_update_task(client: AsyncClient, logged_in_headers, json_memory_chatbot_no_llm):
    # First create a flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Create a task
    task_id, task_data = await _create_task(client, logged_in_headers, flow_id)

    # Update the task
    update_data = {"title": "Updated Task", "status": "processing"}
    response = await client.put(f"api/v1/tasks/{task_id}", json=update_data, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert result["id"] == task_id
    assert result["title"] == update_data["title"]
    assert result["status"] == update_data["status"]
    assert result["description"] == task_data["description"]  # Unchanged field
    assert result["author_id"] == flow_id  # Should remain unchanged


async def test_update_task_not_found(client: AsyncClient, logged_in_headers):
    non_existent_id = str(uuid.uuid4())
    update_data = {"title": "Updated Task", "status": "processing"}
    response = await client.put(f"api/v1/tasks/{non_existent_id}", json=update_data, headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_task(client: AsyncClient, logged_in_headers, json_memory_chatbot_no_llm):
    # First create a flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Create a task
    task_id, _ = await _create_task(client, logged_in_headers, flow_id)

    # Delete the task
    response = await client.delete(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert result["id"] == task_id

    # Verify task is deleted
    get_response = await client.get(f"api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_task_not_found(client: AsyncClient, logged_in_headers):
    non_existent_id = str(uuid.uuid4())
    response = await client.delete(f"api/v1/tasks/{non_existent_id}", headers=logged_in_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_review_task(client: AsyncClient, logged_in_headers, json_memory_chatbot_no_llm):
    # First create a flow
    flow_id = await _create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    # Create a task
    task_id, task_data = await _create_task(client, logged_in_headers, flow_id)

    # Update task to completed
    update_data = {"status": "completed"}
    response = await client.put(f"api/v1/tasks/{task_id}", json=update_data, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["status"] == "completed"

    # Now review the task
    review_data_1 = {
        "review": {
            "comment": "This task needs more work",
            "reviewer_id": flow_id,
            "reviewed_at": "2023-01-01T00:00:00+00:00",
        }
    }

    response = await client.put(f"api/v1/tasks/{task_id}", json=review_data_1, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    result = response.json()

    # Task should be back to pending status after review
    assert result["status"] == "pending"
    assert "review" in result
    assert result["review"]["comment"] == "This task needs more work"
    assert result["review"]["reviewer_id"] == flow_id
    assert "review_history" in result
    assert len(result["review_history"]) == 1

    # Complete the task again
    update_data = {"status": "completed"}
    response = await client.put(f"api/v1/tasks/{task_id}", json=update_data, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["status"] == "completed"

    # Add a second review
    review_data_2 = {
        "review": {
            "comment": "Still needs improvement",
            "reviewer_id": flow_id,
            "reviewed_at": "2023-01-02T00:00:00+00:00",
        }
    }

    response = await client.put(f"api/v1/tasks/{task_id}", json=review_data_2, headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    result = response.json()

    # Verify review history has been updated
    assert result["status"] == "pending"
    assert result["review"]["comment"] == "Still needs improvement"
    assert "review_history" in result
    assert len(result["review_history"]) == 2
    assert result["review_history"][0]["comment"] == "This task needs more work"
    assert result["review_history"][1]["comment"] == "Still needs improvement"
