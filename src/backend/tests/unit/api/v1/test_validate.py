import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.usefixtures("active_user")
async def test_post_validate_code(client: AsyncClient, logged_in_headers):
    good_code = """
from pprint import pprint
var = {"a": 1, "b": 2}
pprint(var)
    """
    response = await client.post("api/v1/validate/code", json={"code": good_code}, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "imports" in result, "The result must have an 'imports' key"
    assert "function" in result, "The result must have a 'function' key"


@pytest.mark.usefixtures("active_user")
async def test_post_validate_prompt(client: AsyncClient, logged_in_headers):
    basic_case = {
        "name": "string",
        "template": "string",
        "custom_fields": {},
        "frontend_node": {
            "template": {},
            "description": "string",
            "icon": "string",
            "is_input": True,
            "is_output": True,
            "is_composition": True,
            "base_classes": ["string"],
            "name": "",
            "display_name": "",
            "documentation": "",
            "custom_fields": {},
            "output_types": [],
            "full_path": "string",
            "pinned": False,
            "conditional_paths": [],
            "frozen": False,
            "outputs": [],
            "field_order": [],
            "beta": False,
            "minimized": False,
            "error": "string",
            "edited": False,
            "metadata": {},
        },
    }
    response = await client.post("api/v1/validate/prompt", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_node" in result, "The result must have a 'frontend_node' key"
    assert "input_variables" in result, "The result must have an 'input_variables' key"


@pytest.mark.usefixtures("active_user")
async def test_post_validate_prompt_with_invalid_data(client: AsyncClient, logged_in_headers):
    invalid_case = {
        "name": "string",
        # Missing required fields
        "frontend_node": {"template": {}, "is_input": True},
    }
    response = await client.post("api/v1/validate/prompt", json=invalid_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_post_validate_code_with_unauthenticated_user(client: AsyncClient):
    code = """
    print("Hello World")
    """
    response = await client.post("api/v1/validate/code", json={"code": code}, headers={"Authorization": "Bearer fake"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
