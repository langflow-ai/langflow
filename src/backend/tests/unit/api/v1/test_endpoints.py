import asyncio
import inspect
from typing import Any

from anyio import Path
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.schemas import UpdateCustomComponentRequest
from langflow.custom.utils import build_custom_component_template

from lfx.components.agents.agent import AgentComponent


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
    template["agent_llm"]["value"] = "Custom"
    request.field_value = "Custom"
    request.template = template

    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
    result = response.json()

    # Verify that model_name is not present for Custom provider
    assert response.status_code == status.HTTP_200_OK
    assert "template" in result
    assert "model_name" not in result["template"]
