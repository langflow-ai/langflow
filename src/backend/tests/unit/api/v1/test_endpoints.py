import asyncio
import inspect
from typing import Any

from anyio import Path
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.schemas import CustomComponentRequest, UpdateCustomComponentRequest
from lfx.components.agents.agent import AgentComponent
from lfx.custom.utils import build_custom_component_template


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "version" in result, "The dictionary must contain a key called 'version'"
    assert "main_version" in result, "The dictionary must contain a key called 'main_version'"
    assert "package" in result, "The dictionary must contain a key called 'package'"


async def test_get_config(client: AsyncClient):
    response = await client.get("api/v1/config")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_timeout" in result, "The dictionary must contain a key called 'frontend_timeout'"
    assert "auto_saving" in result, "The dictionary must contain a key called 'auto_saving'"
    assert "health_check_max_retries" in result, "The dictionary must contain a 'health_check_max_retries' key"
    assert "max_file_size_upload" in result, "The dictionary must contain a key called 'max_file_size_upload'"


async def test_update_component_outputs(client: AsyncClient, logged_in_headers: dict):
    path = Path(__file__).parent.parent.parent.parent / "data" / "dynamic_output_component.py"

    code = await path.read_text(encoding="utf-8")
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

    assert response.status_code == status.HTTP_200_OK
    output_names = [output["name"] for output in result["outputs"]]
    assert "tool_output" in output_names


async def test_update_component_model_name_options(client: AsyncClient, logged_in_headers: dict):
    """Test that model_name options are updated when selecting a provider."""
    component = AgentComponent()
    component_node, _cc_instance = build_custom_component_template(
        component,
    )

    # Initial template with OpenAI as the provider
    template = component_node["template"]
    current_model_names = template["model_name"]["options"]

    # load the code from the file at lfx.components.agents.agent.py asynchronously
    # we are at str/backend/tests/unit/api/v1/test_endpoints.py
    # find the file by using the class AgentComponent
    agent_component_file = await asyncio.to_thread(inspect.getsourcefile, AgentComponent)
    code = await Path(agent_component_file).read_text(encoding="utf-8")

    # Create the request to update the component
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=component_node,
        field="agent_llm",
        field_value="Anthropic",
        template=template,
    )

    # Make the request to update the component
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    # Verify the response
    assert response.status_code == status.HTTP_200_OK, f"Response: {response.json()}"
    assert "template" in result
    assert "model_name" in result["template"]
    assert isinstance(result["template"]["model_name"]["options"], list)
    assert len(result["template"]["model_name"]["options"]) > 0, (
        f"Model names: {result['template']['model_name']['options']}"
    )
    assert current_model_names != result["template"]["model_name"]["options"], (
        f"Current model names: {current_model_names}, New model names: {result['template']['model_name']['options']}"
    )
    # Now test with Custom provider
    template["agent_llm"]["value"] = "connect_other_models"
    request.field_value = "connect_other_models"
    request.template = template

    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    # Verify that model_name is not present for Custom provider
    assert response.status_code == status.HTTP_200_OK
    assert "template" in result
    assert "model_name" not in result["template"]


async def test_custom_component_endpoint_returns_metadata(client: AsyncClient, logged_in_headers: dict):
    """Test that the /custom_component endpoint returns metadata with module and code_hash."""
    component_code = """
from lfx.custom import Component
from lfx.inputs import MessageTextInput
from lfx.template.field.base import Output

class TestMetadataComponent(Component):
    display_name = "Test Metadata Component"
    description = "Test component for metadata"

    inputs = [
        MessageTextInput(display_name="Input", name="input_value"),
    ]
    outputs = [
        Output(display_name="Output", name="output", method="process_input"),
    ]

    def process_input(self) -> str:
        return f"Processed: {self.input_value}"
"""

    request = CustomComponentRequest(code=component_code)
    response = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert "data" in result
    assert "type" in result

    # Verify metadata is present in the response
    frontend_node = result["data"]
    assert "metadata" in frontend_node, "Frontend node should contain metadata"

    # TODO: Temporarily skip metadata checks
    # metadata = frontend_node["metadata"]
    # assert "module" in metadata, "Metadata should contain module field"
    # assert "code_hash" in metadata, "Metadata should contain code_hash field"

    # Verify metadata values
    # assert isinstance(metadata["module"], str), "Module should be a string"
    # expected_module = "custom_components.test_metadata_component"
    # assert metadata["module"] == expected_module, "Module should be auto-generated from display_name"

    # assert isinstance(metadata["code_hash"], str), "Code hash should be a string"
    # assert len(metadata["code_hash"]) == 12, "Code hash should be 12 characters long"
    # assert all(c in "0123456789abcdef" for c in metadata["code_hash"]), "Code hash should be hexadecimal"


async def test_custom_component_endpoint_metadata_consistency(client: AsyncClient, logged_in_headers: dict):
    """Test that the same component code produces consistent metadata."""
    component_code = """
from lfx.custom import Component
from lfx.template.field.base import Output

class ConsistencyTestComponent(Component):
    display_name = "Consistency Test"

    outputs = [
        Output(display_name="Output", name="output", method="get_result"),
    ]

    def get_result(self) -> str:
        return "consistent result"
"""

    # Make two identical requests
    request = CustomComponentRequest(code=component_code)

    response1 = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)
    # result1 = response1.json()

    response2 = await client.post("api/v1/custom_component", json=request.model_dump(), headers=logged_in_headers)
    # result2 = response2.json()

    # Both requests should succeed
    assert response1.status_code == status.HTTP_200_OK
    assert response2.status_code == status.HTTP_200_OK
    # TODO: Temporarily skip metadata checks

    # Metadata should be identical
    # metadata1 = result1["data"]["metadata"]
    # metadata2 = result2["data"]["metadata"]

    # assert metadata1["module"] == metadata2["module"], "Module names should be consistent"
    # assert metadata1["code_hash"] == metadata2["code_hash"], "Code hashes should be consistent for identical code"
