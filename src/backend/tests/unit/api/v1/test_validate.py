from fastapi import status
from httpx import AsyncClient


async def test_post_validate_code(client: AsyncClient):
    good_code = """
from pprint import pprint
var = {"a": 1, "b": 2}
pprint(var)
    """
    response = await client.post("api/v1/validate/code", json={"code": good_code})
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "imports" in result, "The result must have an 'imports' key"
    assert "function" in result, "The result must have a 'function' key"


async def test_post_validate_prompt(client: AsyncClient):
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
            "error": "string",
            "edited": False,
            "metadata": {},
        },
    }
    response = await client.post("api/v1/validate/prompt", json=basic_case)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_node" in result, "The result must have a 'frontend_node' key"
    assert "input_variables" in result, "The result must have an 'input_variables' key"
