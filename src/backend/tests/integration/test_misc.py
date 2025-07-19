from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.initial_setup.setup import load_starter_projects
from langflow.load.load import arun_flow_from_json

from lfx.graph.schema import RunOutputs


@pytest.mark.api_key_required
async def test_run_flow_with_caching_success(client: AsyncClient, starter_project, created_api_key):
    flow_id = starter_project["id"]
    headers = {"x-api-key": created_api_key.api_key}
    payload = {
        "input_value": "value1",
        "input_type": "text",
        "output_type": "text",
        "tweaks": {"parameter_name": "value"},
        "stream": False,
    }
    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "outputs" in data
    assert "session_id" in data


@pytest.mark.api_key_required
async def test_run_flow_with_caching_invalid_flow_id(client: AsyncClient, created_api_key):
    invalid_flow_id = uuid4()
    headers = {"x-api-key": created_api_key.api_key}
    payload = {"input_value": "", "input_type": "text", "output_type": "text", "tweaks": {}, "stream": False}
    response = await client.post(f"/api/v1/run/{invalid_flow_id}", json=payload, headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    assert f"Flow identifier {invalid_flow_id} not found" in data["detail"]


@pytest.mark.api_key_required
async def test_run_flow_with_caching_invalid_input_format(client: AsyncClient, starter_project, created_api_key):
    flow_id = starter_project["id"]
    headers = {"x-api-key": created_api_key.api_key}
    payload = {"input_value": {"key": "value"}, "input_type": "text", "output_type": "text", "tweaks": {}}
    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.api_key_required
async def test_run_flow_with_invalid_tweaks(client, starter_project, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = starter_project["id"]
    payload = {
        "input_value": "value1",
        "input_type": "text",
        "output_type": "text",
        "tweaks": {"invalid_tweak": "value"},
    }
    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.api_key_required
async def test_run_with_inputs_and_outputs(client, starter_project, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = starter_project["id"]
    payload = {
        "input_value": "value1",
        "input_type": "text",
        "output_type": "text",
        "tweaks": {"parameter_name": "value"},
        "stream": False,
    }
    response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text


@pytest.mark.noclient
@pytest.mark.api_key_required
async def test_run_flow_from_json_object():
    """Test loading a flow from a json file and applying tweaks."""
    project = next(project for _, project in await load_starter_projects() if "Basic Prompting" in project["name"])
    results = await arun_flow_from_json(project, input_value="test", fallback_to_env_vars=True)
    assert results is not None
    assert all(isinstance(result, RunOutputs) for result in results)
