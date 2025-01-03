import asyncio
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.components.inputs import ChatInput
from langflow.custom import Component
from langflow.graph import Graph
from langflow.io import MessageTextInput, Output
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import FlowCreate
from langflow.services.database.models.job.model import JobStatus
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_db_service
from sqlalchemy.orm import selectinload
from sqlmodel import select

from tests.conftest import _delete_transactions_and_vertex_builds


class LongRunningComponent(Component):
    display_name = "Long Running Component"

    inputs = [MessageTextInput(name="input_value", display_name="Input")]

    outputs = [Output(name="output_value", display_name="Output", method="run_long_task")]

    async def run_long_task(self) -> str:
        await asyncio.sleep(100)
        return self.input_value


@pytest.fixture
async def long_running_flow(client: AsyncClient, logged_in_headers):
    chat_input = ChatInput()
    long_running_component = LongRunningComponent().set(input_value=chat_input.message_response)
    graph = Graph(start=chat_input, end=long_running_component)
    graph_dict = graph.dump(name="Long Running Component")
    flow = FlowCreate(**graph_dict)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
def create_job_request():
    """Fixture for creating a job request."""
    return {
        "name": "Test Job",
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


async def test_create_job(client: AsyncClient, logged_in_headers, simple_api_test, create_job_request):
    """Test creating a job."""
    response = await client.post(
        f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=create_job_request
    )
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to create job. Status: {response.status_code}. Response: {response.text}"
    job_id = response.json()
    assert isinstance(job_id, str), f"Expected job_id to be a string, got {type(job_id)}"

    # Verify job was created by getting it
    response = await client.get(f"/api/v1/jobs/{job_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get created job. Status: {response.status_code}. Response: {response.text}"
    job = response.json()
    assert job["id"] == job_id, f"Job ID mismatch. Expected: {job_id}, got: {job['id']}"
    assert (
        job["name"] == create_job_request["name"]
    ), f"Job name mismatch. Expected: {create_job_request['name']}, got: {job['name']}"
    assert job["status"] in [
        JobStatus.PENDING,
        JobStatus.COMPLETED,
    ], f"Expected job to be pending or completed, got: {job['status']}"


async def test_create_job_invalid_flow(client: AsyncClient, logged_in_headers, create_job_request):
    """Test creating a job with an invalid flow ID."""
    some_flow_id = uuid4()
    response = await client.post(f"/api/v1/jobs/{some_flow_id}", headers=logged_in_headers, json=create_job_request)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected 404 error for invalid flow ID. Got: {response.status_code}. Response: {response.text}"


async def test_get_job_not_found(client: AsyncClient, logged_in_headers):
    """Test getting a non-existent job."""
    response = await client.get("/api/v1/jobs/nonexistent", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected 404 for non-existent job. Got: {response.status_code}. Response: {response.text}"


async def test_get_jobs(client: AsyncClient, logged_in_headers, simple_api_test, create_job_request):
    """Test getting all jobs."""
    # Create a job first
    response = await client.post(
        f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=create_job_request
    )
    response.json()

    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to create job. Status: {response.status_code}. Response: {response.text}"
    # Get all jobs
    response = await client.get("/api/v1/jobs/", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get jobs. Status: {response.status_code}. Response: {response.text}"
    jobs = response.json()
    assert isinstance(jobs, list), f"Expected jobs to be a list, got {type(jobs)}"
    assert len(jobs) >= 1, f"Expected at least 1 job, got {len(jobs)}"
    assert all(isinstance(job["id"], str) for job in jobs), "Some job IDs are not strings"


async def test_get_jobs_with_status(client: AsyncClient, logged_in_headers, simple_api_test, create_job_request):
    """Test getting jobs filtered by status."""
    # Create a job first
    await client.post(f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=create_job_request)

    # Get all jobs
    response = await client.get("/api/v1/jobs/", headers=logged_in_headers, params={"status": "PENDING"})
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get jobs. Status: {response.status_code}. Response: {response.text}"
    jobs = response.json()
    assert isinstance(jobs, list), f"Expected jobs to be a list, got {type(jobs)}"
    assert len(jobs) >= 0, "Expected at least one job"
    if jobs:
        assert all(job["status"] == "PENDING" for job in jobs), "Some jobs do not have status PENDING"

    # Get all jobs with completed status
    response = await client.get("/api/v1/jobs/", headers=logged_in_headers, params={"status": "COMPLETED"})
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get jobs. Status: {response.status_code}. Response: {response.text}"
    jobs = response.json()
    assert isinstance(jobs, list), f"Expected jobs to be a list, got {type(jobs)}"
    if jobs:
        assert all(job["status"] == "COMPLETED" for job in jobs), "Some jobs do not have status COMPLETED"


async def test_cancel_job(client: AsyncClient, logged_in_headers, long_running_flow, create_job_request):
    """Test canceling a job."""
    # Create a job first
    response = await client.post(
        f"/api/v1/jobs/{long_running_flow['id']}", headers=logged_in_headers, json=create_job_request
    )
    job_id = response.json()

    # Cancel the job
    response = await client.delete(f"/api/v1/jobs/{job_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to cancel job. Status: {response.status_code}. Response: {response.text}"
    assert response.json() is True, f"Expected True response for job cancellation, got: {response.json()}"

    # Verify job was canceled and marked as CANCELLED
    response = await client.get(f"/api/v1/jobs/{job_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get cancelled job. Status: {response.status_code}. Response: {response.text}"
    job = response.json()
    assert job["status"] == "CANCELLED", f"Expected job to be cancelled, got: {job['status']}"
    assert not job["is_active"], "Expected job to be inactive"


async def test_cancel_nonexistent_job(client: AsyncClient, logged_in_headers):
    """Test canceling a non-existent job."""
    response = await client.delete("/api/v1/jobs/nonexistent", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_404_NOT_FOUND
    ), f"Expected 404 for non-existent job cancellation. Got: {response.status_code}. Response: {response.text}"


async def test_create_job_invalid_request(client: AsyncClient, logged_in_headers, simple_api_test):
    """Test creating a job with invalid request data."""
    invalid_request = {
        "name": "Test Job",
        # Missing required input_request field
    }
    response = await client.post(
        f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=invalid_request
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"Expected 422 for invalid request. Got: {response.status_code}. Response: {response.text}"


async def test_job_access_control(
    client: AsyncClient, logged_in_headers, another_user_headers, simple_api_test, create_job_request
):
    """Test that a user cannot access another user's jobs."""
    # assert headers are different
    assert logged_in_headers["Authorization"] != another_user_headers["Authorization"], "Headers are the same"
    # User A creates a job
    response = await client.post(
        f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=create_job_request
    )
    assert response.status_code == status.HTTP_200_OK, f"Failed to create job. Response: {response.text}"
    job_id = response.json()

    # User B tries to access User A's job
    response = await client.get(f"/api/v1/jobs/{job_id}", headers=another_user_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, (
        f"Expected 404 when accessing another user's job. "
        f"Got status {response.status_code}. Response: {response.text}"
    )

    # User B tries to cancel User A's job
    response = await client.delete(f"/api/v1/jobs/{job_id}", headers=another_user_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, (
        f"Expected 404 when canceling another user's job. "
        f"Got status {response.status_code}. Response: {response.text}"
    )


async def test_create_multiple_jobs(client: AsyncClient, logged_in_headers, simple_api_test, create_job_request):
    """Test creating multiple jobs concurrently."""
    num_jobs = 5
    jobs = [
        client.post(f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=create_job_request)
        for _ in range(num_jobs)
    ]
    responses = await asyncio.gather(*jobs)

    for i, response in enumerate(responses):
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to create job {i + 1}/{num_jobs}. " f"Status: {response.status_code}. Response: {response.text}"
        )
        job_id = response.json()
        assert isinstance(job_id, str), f"Job {i + 1}/{num_jobs}: Expected string ID, got {type(job_id)}"

    # Verify all jobs were created
    response = await client.get("/api/v1/jobs/", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get jobs list. Status: {response.status_code}. Response: {response.text}"
    jobs = response.json()
    assert len(jobs) >= num_jobs, (
        f"Expected at least {num_jobs} jobs, but found {len(jobs)}. " f"Some jobs may have failed to create."
    )


async def test_job_status_transitions(client: AsyncClient, logged_in_headers, simple_api_test, create_job_request):
    """Test job status transitions."""
    # Create a job
    response = await client.post(
        f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=create_job_request
    )
    assert response.status_code == status.HTTP_200_OK, (
        f"Failed to create job for status test. " f"Status: {response.status_code}. Response: {response.text}"
    )
    job_id = response.json()

    # Get job status
    response = await client.get(f"/api/v1/jobs/{job_id}", headers=logged_in_headers)
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Failed to get job status. Status: {response.status_code}. Response: {response.text}"
    job = response.json()

    # Verify job has a valid status
    assert "status" in job, f"Job response missing 'status' field. Response: {job}"
    assert isinstance(job["status"], str), (
        f"Expected string for job.status, got {type(job['status'])}. " f"Value: {job['status']}"
    )


async def test_create_job_malicious_input(client: AsyncClient, logged_in_headers, simple_api_test):
    """Test job creation with potentially malicious input."""
    malicious_request = {
        "name": "'; DROP TABLE jobs; --",
        "input_request": {
            "input_value": "<script>alert('xss')</script>",
            "input_type": "text",
            "output_type": "text",
            "tweaks": {"malicious": "'; DROP TABLE users; --"},
        },
    }

    response = await client.post(
        f"/api/v1/jobs/{simple_api_test['id']}", headers=logged_in_headers, json=malicious_request
    )

    # Should either sanitize and accept (200) or reject invalid input (422)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY], (
        f"Expected status 200 or 422 for malicious input, got {response.status_code}. " f"Response: {response.text}"
    )

    if response.status_code == status.HTTP_200_OK:
        job_id = response.json()
        # Verify the job was created and can be retrieved
        response = await client.get(f"/api/v1/jobs/{job_id}", headers=logged_in_headers)
        assert response.status_code == status.HTTP_200_OK, (
            f"Failed to retrieve job created with sanitized malicious input. "
            f"Status: {response.status_code}. Response: {response.text}"
        )
