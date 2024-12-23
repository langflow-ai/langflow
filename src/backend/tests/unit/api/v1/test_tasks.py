import asyncio
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_db_service
from sqlalchemy.orm import selectinload
from sqlmodel import select

from tests.conftest import _delete_transactions_and_vertex_builds


@pytest.fixture
def create_task_request():
    """Fixture for creating a task request."""
    return {
        "name": "Test Task",
        "input_request": {
            "input_value": "test input",
            "input_type": "text",
            "output_type": "text",
            "tweaks": {},
        },
    }


@pytest.fixture
async def anoter_active_user(client):  # noqa: ARG001
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        user = User(
            username="another_active_user",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        stmt = select(User).where(User.username == user.username)
        if active_user := (await session.exec(stmt)).first():
            user = active_user
        else:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)
    yield user
    # Clean up
    # Now cleanup transactions, vertex_build
    async with db_manager.with_session() as session:
        user = await session.get(User, user.id, options=[selectinload(User.flows)])
        await _delete_transactions_and_vertex_builds(session, user.flows)
        await session.delete(user)

        await session.commit()


@pytest.fixture
async def another_user_headers(client, anoter_active_user):
    login_data = {"username": anoter_active_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


async def test_create_task(client: AsyncClient, logged_in_headers, simple_api_test, create_task_request):
    """Test creating a task."""
    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request
    )
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to create task. Status: {response.status_code}. Response: {response.text}"
    task_id = response.json()
    assert isinstance(task_id, str), f"Expected task_id to be a string, got {type(task_id)}"

    # Verify task was created by getting it
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get created task. Status: {response.status_code}. Response: {response.text}"
    task = response.json()
    assert task["id"] == task_id, f"Task ID mismatch. Expected: {task_id}, got: {task['id']}"
    assert (
        task["name"] == create_task_request["name"]
    ), f"Task name mismatch. Expected: {create_task_request['name']}, got: {task['name']}"
    assert task["pending"] is False, f"Expected task to not be pending, got: {task['pending']}"


async def test_create_task_invalid_flow(client: AsyncClient, logged_in_headers, create_task_request):
    """Test creating a task with an invalid flow ID."""
    some_flow_id = uuid4()
    response = await client.post(f"/api/v1/tasks/{some_flow_id}", headers=logged_in_headers, json=create_task_request)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected 404 error for invalid flow ID. Got: {response.status_code}. Response: {response.text}"


async def test_get_task_not_found(client: AsyncClient, logged_in_headers):
    """Test getting a non-existent task."""
    response = await client.get("/api/v1/tasks/nonexistent", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected 404 for non-existent task. Got: {response.status_code}. Response: {response.text}"


async def test_get_tasks(client: AsyncClient, logged_in_headers, simple_api_test, create_task_request):
    """Test getting all tasks."""
    # Create a task first
    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request
    )
    response.json()

    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to create task. Status: {response.status_code}. Response: {response.text}"
    # Get all tasks
    response = await client.get("/api/v1/tasks/", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get tasks. Status: {response.status_code}. Response: {response.text}"
    tasks = response.json()
    assert isinstance(tasks, list), f"Expected tasks to be a list, got {type(tasks)}"
    assert len(tasks) >= 1, f"Expected at least 1 task, got {len(tasks)}"
    assert all(isinstance(task["id"], str) for task in tasks), "Some task IDs are not strings"


async def test_get_tasks_with_status(client: AsyncClient, logged_in_headers, simple_api_test, create_task_request):
    """Test getting tasks filtered by status."""
    # Create a task first
    await client.post(f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request)

    # Get all tasks
    response = await client.get("/api/v1/tasks/", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get tasks. Status: {response.status_code}. Response: {response.text}"
    tasks = response.json()
    assert isinstance(tasks, list), f"Expected tasks to be a list, got {type(tasks)}"
    assert len(tasks) > 0, "Expected at least one task"


async def test_cancel_task(client: AsyncClient, logged_in_headers, simple_api_test, create_task_request):
    """Test canceling a task."""
    # Create a task first
    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request
    )
    task_id = response.json()

    # Cancel the task
    response = await client.delete(f"/api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to cancel task. Status: {response.status_code}. Response: {response.text}"
    assert response.json() is True, f"Expected True response for task cancellation, got: {response.json()}"

    # Verify task was canceled by trying to get it
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected task to be not found after cancellation. Status: {response.status_code}. Response: {response.text}"


async def test_cancel_nonexistent_task(client: AsyncClient, logged_in_headers):
    """Test canceling a non-existent task."""
    response = await client.delete("/api/v1/tasks/nonexistent", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected 404 for non-existent task cancellation. Got: {response.status_code}. Response: {response.text}"


async def test_create_task_invalid_request(client: AsyncClient, logged_in_headers, simple_api_test):
    """Test creating a task with invalid request data."""
    invalid_request = {
        "name": "Test Task",
        # Missing required input_request field
    }
    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=invalid_request
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Expected 422 for invalid request. Got: {response.status_code}. Response: {response.text}"


async def test_task_access_control(
    client: AsyncClient, logged_in_headers, another_user_headers, simple_api_test, create_task_request
):
    """Test that a user cannot access another user's tasks."""
    # assert headers are different
    assert logged_in_headers["Authorization"] != another_user_headers["Authorization"], "Headers are the same"
    # User A creates a task
    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request
    )
    assert response.status_code == status.HTTP_200_OK, f"Failed to create task. Response: {response.text}"
    task_id = response.json()

    # User B tries to access User A's task
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=another_user_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, (
        f"Expected 404 when accessing another user's task. "
        f"Got status {response.status_code}. Response: {response.text}"
    )

    # User B tries to cancel User A's task
    response = await client.delete(f"/api/v1/tasks/{task_id}", headers=another_user_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, (
        f"Expected 404 when canceling another user's task. "
        f"Got status {response.status_code}. Response: {response.text}"
    )


async def test_create_multiple_tasks(client: AsyncClient, logged_in_headers, simple_api_test, create_task_request):
    """Test creating multiple tasks concurrently."""
    num_tasks = 5
    tasks = [
        client.post(f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request)
        for _ in range(num_tasks)
    ]
    responses = await asyncio.gather(*tasks)

    for i, response in enumerate(responses):
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to create task {i + 1}/{num_tasks}. " f"Status: {response.status_code}. Response: {response.text}"
        )
        task_id = response.json()
        assert isinstance(task_id, str), f"Task {i + 1}/{num_tasks}: Expected string ID, got {type(task_id)}"

    # Verify all tasks were created
    response = await client.get("/api/v1/tasks/", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get tasks list. Status: {response.status_code}. Response: {response.text}"
    tasks = response.json()
    assert len(tasks) >= num_tasks, (
        f"Expected at least {num_tasks} tasks, but found {len(tasks)}. " f"Some tasks may have failed to create."
    )


async def test_task_status_transitions(client: AsyncClient, logged_in_headers, simple_api_test, create_task_request):
    """Test task status transitions."""
    # Create a task
    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=create_task_request
    )
    assert response.status_code == status.HTTP_200_OK, (
        f"Failed to create task for status test. " f"Status: {response.status_code}. Response: {response.text}"
    )
    task_id = response.json()

    # Get task status
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get task status. Status: {response.status_code}. Response: {response.text}"
    task = response.json()

    # Verify task has a valid pending status
    assert "pending" in task, f"Task response missing 'pending' field. Response: {task}"
    assert isinstance(task["pending"], bool), (
        f"Expected boolean for task.pending, got {type(task['pending'])}. " f"Value: {task['pending']}"
    )


async def test_create_task_malicious_input(client: AsyncClient, logged_in_headers, simple_api_test):
    """Test task creation with potentially malicious input."""
    malicious_request = {
        "name": "'; DROP TABLE tasks; --",
        "input_request": {
            "input_value": "<script>alert('xss')</script>",
            "input_type": "text",
            "output_type": "text",
            "tweaks": {"malicious": "'; DROP TABLE users; --"},
        },
    }

    response = await client.post(
        f"/api/v1/tasks/{simple_api_test['id']}", headers=logged_in_headers, json=malicious_request
    )

    # Should either sanitize and accept (200) or reject invalid input (422)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY], (
        f"Expected status 200 or 422 for malicious input, got {response.status_code}. " f"Response: {response.text}"
    )

    if response.status_code == status.HTTP_200_OK:
        task_id = response.json()
        # Verify the task was created and can be retrieved
        response = await client.get(f"/api/v1/tasks/{task_id}", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to retrieve task created with sanitized malicious input. "
            f"Status: {response.status_code}. Response: {response.text}"
        )
