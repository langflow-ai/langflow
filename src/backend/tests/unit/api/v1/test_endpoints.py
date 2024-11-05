import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.api.v1.schemas import UpdateCustomComponentRequest


async def get_dynamic_output_component_code():
    return await asyncio.to_thread(
        Path("src/backend/tests/data/dynamic_output_component.py").read_text, encoding="utf-8"
    )


@pytest.fixture
def basic_component():
    return {
        "code": '# from langflow.field_typing import Data\nfrom langflow.custom import Component\nfrom langflow.io import MessageTextInput, Output\nfrom langflow.schema import Data\n\n\nclass CustomComponent(Component):\n    display_name = "Custom Component"\n    description = "Use as a template to create your own component."\n    documentation: str = "http://docs.langflow.org/components/custom"\n    icon = "code"\n    name = "CustomComponent"\n\n    inputs = [\n        MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!"),\n    ]\n\n    outputs = [\n        Output(display_name="Output", name="output", method="build_output"),\n    ]\n\n    def build_output(self) -> Data:\n        data = Data(value=self.input_value)\n        self.status = data\n        return data\n',  # noqa: E501
        "frontend_node": {
            "template": {
                "_type": "Component",
                "code": {
                    "type": "code",
                    "required": True,
                    "placeholder": "",
                    "list": False,
                    "show": True,
                    "multiline": True,
                    "value": '# from langflow.field_typing import Data\nfrom langflow.custom import Component\nfrom langflow.io import MessageTextInput, Output\nfrom langflow.schema import Data\n\n\nclass CustomComponent(Component):\n    display_name = "Custom Component"\n    description = "Use as a template to create your own component."\n    documentation: str = "http://docs.langflow.org/components/custom"\n    icon = "code"\n    name = "CustomComponent"\n\n    inputs = [\n        MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!"),\n    ]\n\n    outputs = [\n        Output(display_name="Output", name="output", method="build_output"),\n    ]\n\n    def build_output(self) -> Data:\n        data = Data(value=self.input_value)\n        self.status = data\n        return data\n',  # noqa: E501
                    "fileTypes": [],
                    "file_path": "",
                    "password": False,
                    "name": "code",
                    "advanced": True,
                    "dynamic": True,
                    "info": "",
                    "load_from_db": False,
                    "title_case": False,
                },
                "input_value": {
                    "trace_as_input": True,
                    "trace_as_metadata": True,
                    "load_from_db": False,
                    "list": False,
                    "required": False,
                    "placeholder": "",
                    "show": True,
                    "name": "input_value",
                    "value": "Hello, World!",
                    "display_name": "Input Value",
                    "advanced": False,
                    "input_types": ["Message"],
                    "dynamic": False,
                    "info": "",
                    "title_case": False,
                    "type": "str",
                    "_input_type": "MessageTextInput",
                },
            },
            "description": "Use as a template to create your own component.",
            "icon": "code",
            "base_classes": ["Data"],
            "display_name": "Custom Component",
            "documentation": "http://docs.langflow.org/components/custom",
            "custom_fields": {},
            "output_types": [],
            "pinned": False,
            "conditional_paths": [],
            "frozen": False,
            "outputs": [
                {
                    "types": ["Data"],
                    "selected": "Data",
                    "name": "output",
                    "display_name": "Output",
                    "method": "build_output",
                    "value": "__UNDEFINED__",
                    "cache": True,
                }
            ],
            "field_order": ["input_value"],
            "beta": False,
            "legacy": False,
            "edited": False,
            "metadata": {},
        },
    }


async def test_get_version(client: AsyncClient):
    response = await client.get("api/v1/version")
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "version" in result, "The dictionary must contain a key called 'version'"
    assert "main_version" in result, "The dictionary must contain a key called 'main_version'"
    assert "package" in result, "The dictionary must contain a key called 'package'"


async def test_custom_component(client: AsyncClient, logged_in_headers, basic_component):
    response = await client.post("api/v1/custom_component", json=basic_component, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "data" in result, "The dictionary must contain a key called 'data'"
    assert "type" in result, "The dictionary must contain a key called 'type'"


async def test_custom_component_update(client: AsyncClient, logged_in_headers, basic_component):
    basic_case = basic_component.copy()
    basic_case |= {"field": "string", "field_value": "string", "template": {}}
    response = await client.post("api/v1/custom_component/update", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "template" in result, "The dictionary must contain a key called 'template'"
    assert "description" in result, "The dictionary must contain a key called 'description'"
    assert "icon" in result, "The dictionary must contain a key called 'icon'"
    assert "base_classes" in result, "The dictionary must contain a key called 'base_classes'"
    assert "display_name" in result, "The dictionary must contain a key called 'display_name'"
    assert "documentation" in result, "The dictionary must contain a key called 'documentation'"
    assert "custom_fields" in result, "The dictionary must contain a key called 'custom_fields'"
    assert "output_types" in result, "The dictionary must contain a key called 'output_types'"
    assert "pinned" in result, "The dictionary must contain a key called 'pinned'"
    assert "conditional_paths" in result, "The dictionary must contain a key called 'conditional_paths'"
    assert "frozen" in result, "The dictionary must contain a key called 'frozen'"
    assert "outputs" in result, "The dictionary must contain a key called 'outputs'"
    assert "field_order" in result, "The dictionary must contain a key called 'field_order'"
    assert "beta" in result, "The dictionary must contain a key called 'beta'"
    assert "legacy" in result, "The dictionary must contain a key called 'legacy'"
    assert "edited" in result, "The dictionary must contain a key called 'edited'"
    assert "metadata" in result, "The dictionary must contain a key called 'metadata'"


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
    code = await get_dynamic_output_component_code()
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


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_simplified_run_flow(client: AsyncClient, logged_in_headers):
    flow_id_or_name = "string"
    response = await client.post(f"api/v1/run/{flow_id_or_name}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_webhook_run_flow(client: AsyncClient, logged_in_headers):
    flow_id_or_name = "string"
    response = await client.post(f"api/v1/run/webhook/{flow_id_or_name}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_202_ACCEPTED


@pytest.mark.skip(reason="Temporarily disabled: This is currently broken")
async def test_get_task_status(client: AsyncClient, logged_in_headers):
    task_id = "string"
    response = await client.get(f"api/v1/run/task/{task_id}", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK


async def test_get_all(client: AsyncClient, logged_in_headers):
    keys = [
        "Notion",
        "agents",
        "assemblyai",
        "astra_assistants",
        "chains",
        "custom_component",
        "data",
        "documentloaders",
        "embeddings",
        "helpers",
        "inputs",
        "langchain_utilities",
        "link_extractors",
        "memories",
        "models",
        "output_parsers",
        "outputs",
        "prompts",
        "prototypes",
        "retrievers",
        "textsplitters",
        "toolkits",
        "tools",
        "vectorstores",
    ]
    response = await client.get("api/v1/all", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    for key in keys:
        assert key in result, f"The dictionary must contain a key called '{key}'"
