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
