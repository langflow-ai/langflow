"""Tests for the v2 workflow endpoint."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from starlette import status


@pytest.mark.benchmark
async def test_workflow_run_no_payload(client: AsyncClient, simple_api_test, created_api_key):
    """Test the /v2/run/stateless endpoint with no payload - should return clean JSON."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text

    json_response = response.json()
    # Should have clean structure with output and metadata
    assert "output" in json_response, f"Expected 'output' key in response: {json_response}"
    assert "metadata" in json_response, f"Expected 'metadata' key in response: {json_response}"

    # Verify metadata structure
    metadata = json_response["metadata"]
    assert "flow_id" in metadata
    assert "timestamp" in metadata
    assert "duration_ms" in metadata
    assert "status" in metadata
    assert metadata["status"] == "complete"
    assert metadata["error"] is False

    # Verify output is not empty
    output = json_response["output"]
    assert output is not None


@pytest.mark.benchmark
async def test_workflow_run_with_inputs(client: AsyncClient, simple_api_test, created_api_key):
    """Test the /v2/run/stateless endpoint with inputs parameter."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {
        "inputs": {"ChatInput": {"input_value": "test message"}},
    }
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text

    json_response = response.json()
    assert "output" in json_response
    assert "metadata" in json_response
    assert json_response["metadata"]["status"] == "complete"


@pytest.mark.benchmark
async def test_workflow_run_with_empty_inputs(client: AsyncClient, simple_api_test, created_api_key):
    """Test the /v2/run/stateless endpoint with empty inputs."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    payload = {"inputs": {}}
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text

    json_response = response.json()
    assert "output" in json_response
    assert "metadata" in json_response


async def test_workflow_run_invalid_flow_id(client: AsyncClient, created_api_key):
    """Test the /v2/run/stateless endpoint with invalid flow ID."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = "invalid-flow-id"
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


async def test_workflow_run_missing_flow(client: AsyncClient, created_api_key):
    """Test the /v2/run/stateless endpoint with UUID that doesn't exist."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = UUID(int=0)
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


@pytest.mark.benchmark
async def test_workflow_run_inputs_parameter(client: AsyncClient, simple_api_test, created_api_key):
    """Test that 'inputs' parameter works correctly."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    # Use 'inputs' in the request
    payload = {
        "inputs": {"SomeComponent": {"param1": "value1"}},
    }
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers, json=payload)
    # Should succeed
    assert response.status_code == status.HTTP_200_OK, response.text

    json_response = response.json()
    assert "output" in json_response
    assert "metadata" in json_response


@pytest.mark.benchmark
async def test_workflow_stateless_no_messages_stored(
    client: AsyncClient, json_memory_chatbot_no_llm, created_api_key, logged_in_headers
):
    """Test that messages are NOT stored in the database when using the stateless endpoint."""
    import json

    from langflow.services.database.models.message.model import MessageTable
    from langflow.services.deps import session_scope
    from sqlmodel import select

    # First create the flow
    flow_data = json.loads(json_memory_chatbot_no_llm)
    create_response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert create_response.status_code == 201
    flow_id = create_response.json()["id"]
    flow_id_uuid = UUID(flow_id)

    headers = {"x-api-key": created_api_key.api_key}

    # Count messages before the call
    async with session_scope() as session:
        stmt = select(MessageTable).where(MessageTable.flow_id == flow_id_uuid)
        result = await session.exec(stmt)
        messages_before = len(result.all())

    # Make a request with an input that would normally save a message
    payload = {
        "inputs": {"ChatInput": {"input_value": "Hello, this is a test message"}},
    }
    response = await client.post(f"/api/v2/run/stateless/{flow_id}", headers=headers, json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Count messages after the call - should be the same (no new messages stored)
    async with session_scope() as session:
        stmt = select(MessageTable).where(MessageTable.flow_id == flow_id_uuid)
        result = await session.exec(stmt)
        messages_after = len(result.all())

    # Assert that NO new messages were stored
    assert messages_after == messages_before, (
        f"Expected no new messages, but found {messages_after - messages_before} new messages"
    )

    # Clean up
    await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
