import json
from typing import Any

import pytest
from aiofile import async_open
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.schemas import SimplifiedAPIRequest, UpdateCustomComponentRequest
from langflow.components.data.file import FileComponent
from langflow.graph.graph.base import Graph
from langflow.services.database.models.flow.model import FlowCreate


@pytest.fixture
async def file_flow_component(client: AsyncClient, logged_in_headers):
    file_component = FileComponent()
    graph = Graph(start=file_component, end=file_component)
    graph_dict = graph.dump(name="File Component")
    flow = FlowCreate(**graph_dict)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert isinstance(result, dict), f"Expected result to be a dictionary, got {type(result)}. Response: {result}"
    assert (
        "version" in result
    ), f"Expected 'version' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "main_version" in result
    ), f"Expected 'main_version' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "package" in result
    ), f"Expected 'package' key in response, got keys: {list(result.keys())}. Response: {result}"


async def test_get_config(client: AsyncClient):
    response = await client.get("api/v1/config")
    result = response.json()

    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert isinstance(result, dict), f"Expected result to be a dictionary, got {type(result)}. Response: {result}"
    assert (
        "frontend_timeout" in result
    ), f"Expected 'frontend_timeout' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "auto_saving" in result
    ), f"Expected 'auto_saving' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "health_check_max_retries" in result
    ), f"Expected 'health_check_max_retries' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "max_file_size_upload" in result
    ), f"Expected 'max_file_size_upload' key in response, got keys: {list(result.keys())}. Response: {result}"


async def test_update_component_outputs(client: AsyncClient, logged_in_headers: dict):
    async with async_open("src/backend/tests/data/dynamic_output_component.py", encoding="utf-8") as f:
        code = await f.read()
    frontend_node: dict[str, Any] = {"outputs": []}
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=frontend_node,
        field="show_output",
        field_value=True,
        template={},
    )
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    output_names = [output["name"] for output in result["outputs"]]
    assert (
        "tool_output" in output_names
    ), f"Expected 'tool_output' in output names, got: {output_names}. Response: {result}"


async def test_successful_run_no_payload(client, simple_api_test, created_api_key):
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]

    # Create the request with form data
    input_request = SimplifiedAPIRequest(input_value=None, input_type="text", output_type="text")

    # Send as form data
    form_data = {"input_request": input_request.model_dump_json(), "stream": "false"}

    response = await client.post(
        f"/api/v1/run/upload/{flow_id}",
        headers=headers,
        data=form_data,
        files=[],  # Empty files list
    )
    result = response.json()
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert (
        "outputs" in result
    ), f"Expected 'outputs' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "session_id" in result
    ), f"Expected 'session_id' key in response, got keys: {list(result.keys())}. Response: {result}"


async def test_successful_file_upload(client: AsyncClient, file_flow_component, created_api_key):
    """Test successful file upload with correct filename format."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = file_flow_component["id"]

    # Create file content as bytes
    file_content = b"test content"

    form_data = {
        "input_value": "",
        "input_type": "text",
        "output_type": "text",
        "output_component": "",
        "stream": "false",
    }
    files = [("files", ("File::path::test.txt", file_content))]
    response = await client.post(
        f"/api/v1/run/upload/{flow_id}", headers=headers, files=files, data=form_data, follow_redirects=True
    )

    result = response.json()
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert (
        "outputs" in result
    ), f"Expected 'outputs' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "session_id" in result
    ), f"Expected 'session_id' key in response, got keys: {list(result.keys())}. Response: {result}"


async def test_invalid_filename_format(client: AsyncClient, file_flow_component, created_api_key):
    """Test file upload with invalid filename format."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = file_flow_component["id"]

    file_content = b"test content"

    form_data = {
        "input_value": "",
        "input_type": "text",
        "output_type": "text",
        "output_component": "",
        "stream": "false",
    }
    files = [("files", ("invalid_filename.txt", file_content, "text/plain"))]
    response = await client.post(
        f"/api/v1/run/upload/{flow_id}",
        headers=headers,
        data=form_data,
        files=files,
    )

    result = response.json()
    assert (
        response.status_code == status.HTTP_400_BAD_REQUEST
    ), f"Expected status code 400, got {response.status_code}. Response: {result}"
    assert (
        "Invalid file name format" in result["detail"]
    ), f"Expected error message about invalid filename format, got: {result['detail']}. Response: {result}"


async def test_multiple_file_uploads(client: AsyncClient, file_flow_component, created_api_key):
    """Test uploading multiple files."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = file_flow_component["id"]

    file1_content = b"test content 1"
    file2_content = b"test content 2"

    form_data = {
        "input_value": "",
        "input_type": "text",
        "output_type": "text",
        "output_component": "",
        "stream": "false",
    }
    response = await client.post(
        f"/api/v1/run/upload/{flow_id}",
        headers=headers,
        data=form_data,
        files=[
            ("files", ("File::path::test1.txt", file1_content, "text/plain")),
            ("files", ("File::path::test2.txt", file2_content, "text/plain")),
        ],
    )

    result = response.json()
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert (
        "outputs" in result
    ), f"Expected 'outputs' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "session_id" in result
    ), f"Expected 'session_id' key in response, got keys: {list(result.keys())}. Response: {result}"


async def test_file_upload_with_tweaks(client: AsyncClient, file_flow_component, created_api_key):
    """Test file upload with existing tweaks in the request."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = file_flow_component["id"]

    file_content = b"test content"

    form_data = {
        "input_value": "",
        "input_type": "text",
        "output_type": "text",
        "output_cojsonent": "",
        "tweaks": json.dumps({"ExistingComponent": {"param": "value"}}),
        "stream": "false",
    }
    response = await client.post(
        f"/api/v1/run/upload/{flow_id}",
        headers=headers,
        data=form_data,
        files=[
            ("files", ("File::path::test.txt", file_content, "text/plain")),
        ],
    )

    result = response.json()
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert (
        "outputs" in result
    ), f"Expected 'outputs' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "session_id" in result
    ), f"Expected 'session_id' key in response, got keys: {list(result.keys())}. Response: {result}"


async def test_component_with_multiple_file_inputs(client: AsyncClient, file_flow_component, created_api_key):
    """Test uploading multiple files to different inputs of the same component."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = file_flow_component["id"]

    main_content = b"main content"
    appendix_content = b"appendix content"

    form_data = {
        "input_value": "",
        "input_type": "text",
        "output_type": "text",
        "output_component": "",
        "stream": "false",
    }
    response = await client.post(
        f"/api/v1/run/upload/{flow_id}",
        headers=headers,
        data=form_data,
        files=[
            ("files", ("File::path::main.txt", main_content, "text/plain")),
            ("files", ("File::path::appendix.txt", appendix_content, "text/plain")),
        ],
    )

    result = response.json()
    assert (
        response.status_code == status.HTTP_200_OK
    ), f"Expected status code 200, got {response.status_code}. Response: {result}"
    assert (
        "outputs" in result
    ), f"Expected 'outputs' key in response, got keys: {list(result.keys())}. Response: {result}"
    assert (
        "session_id" in result
    ), f"Expected 'session_id' key in response, got keys: {list(result.keys())}. Response: {result}"
